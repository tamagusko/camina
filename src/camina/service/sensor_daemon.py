"""Production edge-agent entry point (HTTPS + windowed counting).

Composes the new core/I/O components defined in plan 01:

    Detector  ->  Tracker  ->  WindowedCounter  ->  HttpsPublisher
                                        |              ^
                                        v              |
                                DailyAccumulator ------+
                                        |
                                ConfigPoller (hot-reloads intervals)

This daemon is headless — no OpenCV window, no local file logging. The
legacy ``ModalShareCounterApp`` in ``src/camina/app.py`` stays untouched for
dev ergonomics; this module is what runs on a production RPi5.

Typical invocation (see ``deploy/systemd/camina-sensor.service``):

    python -m src.camina.service.sensor_daemon --config configs/sensor.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import queue
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Optional

import yaml

from src.camina.core.counter import (
    DailyAccumulator,
    DailySnapshot,
    WindowSnapshot,
    WindowedCounter,
)
from src.camina.io.config_poller import ConfigPoller
from src.camina.io.http_client import HttpClient, RetryPolicy
from src.camina.io.https_publisher import HttpsPublisher
from src.camina.io.offline_buffer import OfflineBuffer
from src.camina.io.schemas import HeartbeatPayload, SensorConfig
from src.camina.utils.sqlite_integrity import check_and_recover
from src.camina.utils.systemd_notify import SystemdNotifier


logger = logging.getLogger(__name__)


# In-loop publisher sends must fail fast: the OfflineBuffer now fully owns
# durable retry + persistence (a failed send is buffered and replayed later),
# so a long inline retry ladder would only stall the detection loop during an
# outage — and a multi-minute stall kills tracks, causing double counting.
# Hence 2 attempts with a short backoff cap. RetryPolicy defaults are left
# untouched for other callers/tests.
_INLINE_RETRY = RetryPolicy(max_attempts=2, base_delay_s=0.5, max_delay_s=2.0)

# Bound the shutdown drain of the publish queue so a dead network cannot hang a
# deploy: any snapshot not delivered/buffered within this window is left in the
# outbox (durable) or re-flushed by ``_flush_open_window``.
_SHUTDOWN_FLUSH_TIMEOUT_S = 10.0

# Emit a systemd watchdog keep-alive at most this often from the main loop —
# comfortably under the unit's ``WatchdogSec=300`` so normal operation never
# trips a restart, while a genuinely stalled loop does.
_WATCHDOG_INTERVAL_S = 60.0

# First-attempt publish jitter: each sensor delays its window publish by a
# deterministic offset in ``[0, _PUBLISH_JITTER_MODULO_S)`` seconds so 100
# sensors rolling over at the same wall-clock boundary don't stampede the API.
_PUBLISH_JITTER_MODULO_S = 60

# Sentinel enqueued on shutdown so the publish worker drains remaining jobs
# then exits cleanly.
_WORKER_SENTINEL = object()


def _publish_jitter_seconds(sensor_id: str) -> float:
    """Deterministic per-sensor first-attempt publish offset in seconds."""
    digest = hashlib.sha256(sensor_id.encode("utf-8")).digest()
    return float(int.from_bytes(digest[:8], "big") % _PUBLISH_JITTER_MODULO_S)


@dataclass
class DaemonConfig:
    """Minimal start-up config read from YAML. Dynamic settings come from
    the backend via :class:`ConfigPoller`; this struct only covers what the
    device needs before its first successful connection.
    """

    sensor_id: str
    api_base_url: str
    api_token: str
    state_db_path: Path
    classes: list[str]
    fw_version: str
    publish_interval_seconds: int = 900
    heartbeat_interval_seconds: int = 600
    outbox_max_rows: int = 10_000
    # NCNN inference (added in Plan 01-01).
    ncnn_model_path: Path = Path("models/20250629_warmup_best_ncnn_model")
    imgsz: int = 480
    conf_threshold: float = 0.3

    @classmethod
    def from_yaml(cls, path: Path) -> "DaemonConfig":
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            sensor_id=data["sensor_id"],
            api_base_url=data["api_base_url"],
            api_token=data["api_token"],
            state_db_path=Path(data.get("state_db_path", "state.db")),
            classes=list(data["classes"]),
            fw_version=data.get("fw_version", "0.0.0"),
            publish_interval_seconds=int(data.get("publish_interval_seconds", 900)),
            heartbeat_interval_seconds=int(data.get("heartbeat_interval_seconds", 600)),
            outbox_max_rows=int(data.get("outbox_max_rows", 10_000)),
            ncnn_model_path=Path(
                data.get(
                    "ncnn_model_path", "models/20250629_warmup_best_ncnn_model"
                )
            ),
            imgsz=int(data.get("imgsz", 480)),
            conf_threshold=float(data.get("conf_threshold", 0.3)),
        )


class SensorDaemon:
    """Runtime orchestrator for the edge agent.

    Detection/tracking are injected via ``frame_source`` and ``detect_and_track``
    callables so this module stays importable without OpenCV/Ultralytics
    (which are heavy on CI). In production these come from the existing
    detector + tracker pipeline.
    """

    def __init__(
        self,
        config: DaemonConfig,
        frame_source,
        detect_and_track,
        started_at: Optional[datetime] = None,
    ) -> None:
        self._config = config
        self._frame_source = frame_source
        self._detect_and_track = detect_and_track
        self._started_at = started_at or datetime.now(tz=timezone.utc)

        self._counter = WindowedCounter(
            classes=config.classes,
            window_seconds=config.publish_interval_seconds,
        )
        # Quarantine a corrupt state DB (bad shutdown / power cut) before either
        # accumulator opens it, so a bad file recreates fresh instead of
        # crashing the daemon on boot (M9). Both DBs share the state path stem.
        outbox_db_path = config.state_db_path.with_suffix(".outbox.db")
        check_and_recover(config.state_db_path)
        check_and_recover(outbox_db_path)
        self._daily = DailyAccumulator(
            db_path=config.state_db_path, classes=config.classes
        )
        self._outbox = OfflineBuffer(
            db_path=outbox_db_path,
            max_rows=config.outbox_max_rows,
        )
        self._http = HttpClient(
            base_url=config.api_base_url,
            token=config.api_token,
            retry=_INLINE_RETRY,
        )
        self._publisher = HttpsPublisher(
            sensor_id=config.sensor_id,
            http_client=self._http,
            outbox=self._outbox,
        )
        self._poller = ConfigPoller(
            sensor_id=config.sensor_id,
            http_client=self._http,
            current_version="",
            apply=self._apply_config,
            persist=lambda v: logger.info("Persisted config version %s", v),
        )

        self._shutdown = Event()
        self._heartbeat_thread: Optional[Thread] = None
        self._stopped = False

        # Publish work (counts / daily / heartbeat POSTs) runs on a single
        # background worker so the detection loop never blocks on the network.
        # One worker preserves per-payload-type ordering naturally.
        self._publish_queue: "queue.Queue[object]" = queue.Queue()
        self._worker_thread: Optional[Thread] = None
        self._publish_jitter_s = _publish_jitter_seconds(config.sensor_id)

        # sd_notify is a no-op unless launched under a Type=notify systemd unit.
        self._notifier = SystemdNotifier()

    # ---------- Public API ----------

    def start(self) -> None:
        logger.info("Sensor daemon starting for %s", self._config.sensor_id)
        self._catch_up_daily()
        self._worker_thread = Thread(
            target=self._publish_worker, name="camina-publish", daemon=True
        )
        self._worker_thread.start()
        self._heartbeat_thread = Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        # Start-up complete: tell systemd we're ready (Type=notify).
        self._notifier.ready()
        try:
            self._main_loop()
        finally:
            self.stop()

    def stop(self) -> None:
        # ``_stopped`` (not ``_shutdown``) guards the run-once path: a SIGTERM
        # sets ``_shutdown`` *before* stop() runs, so gating on it would skip
        # the flush and resource cleanup entirely.
        if self._stopped:
            return
        self._stopped = True
        self._shutdown.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5.0)
        # Drain any in-flight publish jobs before closing state: the sentinel
        # makes the worker finish the remaining queue then exit. ``_shutdown``
        # is already set, so the jitter wait returns immediately and the drain
        # is bounded by ``_SHUTDOWN_FLUSH_TIMEOUT_S``.
        if self._worker_thread is not None:
            self._publish_queue.put(_WORKER_SENTINEL)
            self._worker_thread.join(timeout=_SHUTDOWN_FLUSH_TIMEOUT_S)
            if self._worker_thread.is_alive():
                logger.warning(
                    "Publish worker did not drain within %.0fs; "
                    "undelivered jobs remain buffered in the outbox",
                    _SHUTDOWN_FLUSH_TIMEOUT_S,
                )
        # Flush the open (incomplete) window before closing state so a deploy
        # doesn't silently drop up to one window of counts; the worker and
        # heartbeat threads are already joined, so the counter/daily state is
        # no longer touched concurrently.
        self._flush_open_window()
        self._outbox.close()
        self._daily.close()
        self._http.close()
        self._notifier.close()
        logger.info("Sensor daemon stopped")

    # ---------- Internal ----------

    def _main_loop(self) -> None:
        last_watchdog = time.monotonic()
        for frame in self._frame_source:
            if self._shutdown.is_set():
                break
            now = datetime.now(tz=timezone.utc)
            for track_id, class_name in self._detect_and_track(frame):
                self._counter.add(track_id=track_id, class_name=class_name, now=now)

            snapshot = self._counter.maybe_rollover(now)
            if snapshot is not None:
                # Record locally on this thread (fast local SQLite), then hand
                # the network POST to the worker so the loop never blocks.
                self._daily.add_window(snapshot)
                self._enqueue(("counts", snapshot))

            daily_snapshot = self._daily.maybe_rollover(now)
            if daily_snapshot is not None:
                # Mark published up-front so ``maybe_rollover`` doesn't re-emit
                # this row every frame while the async POST is in flight — the
                # outbox owns durable delivery, so a daily is always
                # delivered-or-buffered (F2).
                self._daily.mark_published(daily_snapshot.day)
                self._enqueue(("daily", daily_snapshot))

            if time.monotonic() - last_watchdog >= _WATCHDOG_INTERVAL_S:
                self._notifier.watchdog()
                last_watchdog = time.monotonic()

    # ---------- Publish worker ----------

    def _enqueue(self, job: tuple) -> None:
        """Hand a publish job to the worker, or run it inline when no worker is
        running (keeps direct/test call paths synchronous)."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._publish_queue.put(job)
        else:
            self._dispatch(job)

    def _dispatch(self, job: tuple) -> None:
        kind = job[0]
        if kind == "counts":
            self._publish_counts(job[1])
        elif kind == "daily":
            self._publish_daily_row(job[1])
        elif kind == "heartbeat":
            self._send_heartbeat()

    def _publish_worker(self) -> None:
        """Single consumer of the publish queue.

        Serializing all network POSTs on one thread keeps the detection loop
        non-blocking and preserves per-payload-type ordering for free. A
        ``_WORKER_SENTINEL`` (enqueued on shutdown) drains the remaining jobs
        then exits.
        """
        while True:
            job = self._publish_queue.get()
            try:
                if job is _WORKER_SENTINEL:
                    return
                if job[0] == "counts":
                    # Per-sensor first-attempt jitter, interruptible on
                    # shutdown (``_shutdown`` is already set during the drain,
                    # so this returns immediately then).
                    self._shutdown.wait(timeout=self._publish_jitter_s)
                self._dispatch(job)
            except Exception:
                logger.exception("Publish worker job failed")
            finally:
                self._publish_queue.task_done()

    # ---------- Publish helpers ----------

    def _on_window_snapshot(self, snapshot: WindowSnapshot, now: datetime) -> None:
        # Synchronous unit used by the shutdown flush (worker already joined):
        # record locally, then publish on this thread.
        self._daily.add_window(snapshot)
        self._publish_counts(snapshot)

    def _publish_counts(self, snapshot: WindowSnapshot) -> None:
        result = self._publisher.post_counts(
            snapshot=snapshot,
            config_version=self._poller.current_version,
            fw_version=self._config.fw_version,
        )
        if result.latest_config_version:
            self._poller.check(result.latest_config_version)

    def _publish_daily(self, snapshot: DailySnapshot) -> None:
        # Full synchronous daily publish used by start-up catch-up: POST and
        # mark published locally. The main-loop path marks the row published
        # up-front (to stop re-emit) and routes the POST via
        # ``_publish_daily_row``.
        result = self._publisher.post_daily(
            snapshot=snapshot,
            config_version=self._poller.current_version,
            fw_version=self._config.fw_version,
        )
        # Mark published once the outbox owns delivery (delivered in real time
        # OR buffered for later replay). Otherwise ``maybe_rollover`` re-emits
        # the same daily row every frame, flooding the outbox on an outage.
        if result.delivered or result.buffered:
            self._daily.mark_published(snapshot.day)
        if result.latest_config_version:
            self._poller.check(result.latest_config_version)

    def _publish_daily_row(self, snapshot: DailySnapshot) -> None:
        # Network-only daily publish for the worker; the main loop already
        # marked this row published, so this must not touch ``_daily``.
        result = self._publisher.post_daily(
            snapshot=snapshot,
            config_version=self._poller.current_version,
            fw_version=self._config.fw_version,
        )
        if result.latest_config_version:
            self._poller.check(result.latest_config_version)

    def _flush_open_window(self) -> None:
        """Force-close the open window on shutdown so its counts aren't lost.

        Skips publishing an empty window (no counts across all classes). The
        snapshot is marked ``partial=True`` since the window is cut short, and
        goes through the normal path so the DailyAccumulator sees it too.
        """
        now = datetime.now(tz=timezone.utc)
        snapshot = self._counter.force_snapshot(now, partial=True)
        if snapshot.total() == 0:
            return
        logger.info(
            "Flushing open window on shutdown (%d counts)", snapshot.total()
        )
        self._on_window_snapshot(snapshot, now)

    def _catch_up_daily(self) -> None:
        for snap in self._daily.pending_unpublished():
            logger.info("Publishing late daily row for %s", snap.day)
            self._publish_daily(snap)

    def _heartbeat_loop(self) -> None:
        interval = self._config.heartbeat_interval_seconds
        while not self._shutdown.wait(timeout=interval):
            # Route through the worker so the heartbeat POST shares the single
            # publish thread (no separate network path off the detection loop).
            self._enqueue(("heartbeat",))

    def _send_heartbeat(self) -> None:
        now = datetime.now(tz=timezone.utc)
        uptime_s = int((now - self._started_at).total_seconds())
        hb = HeartbeatPayload(
            sensor_id=self._config.sensor_id,
            ts=now,
            uptime_s=uptime_s,
            cpu_temp_c=_read_cpu_temp(),
            last_window_end=self._counter.window_start,
            config_version=self._poller.current_version,
            fw_version=self._config.fw_version,
            config_error=self._poller.has_error,
        )
        result = self._publisher.post_heartbeat(hb)
        if result.latest_config_version:
            self._poller.check(result.latest_config_version)

    def _apply_config(self, config: SensorConfig) -> None:
        new_window = config.publish_interval_minutes * 60
        if new_window != self._counter.window_seconds:
            logger.info(
                "Reconfiguring window: %d -> %d seconds",
                self._counter.window_seconds, new_window,
            )
            self._counter = WindowedCounter(
                classes=self._config.classes,
                window_seconds=new_window,
            )
        self._config.publish_interval_seconds = new_window
        self._config.heartbeat_interval_seconds = (
            config.heartbeat_interval_minutes * 60
        )

    def _on_signal(self, signum: int, _frame) -> None:
        logger.info("Received signal %d, shutting down", signum)
        self._shutdown.set()


def _read_cpu_temp() -> Optional[float]:
    """Best-effort CPU temperature read on Linux; returns None elsewhere."""
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        raw = path.read_text().strip()
        return round(float(raw) / 1000.0, 1)
    except OSError:
        return None


def main() -> None:
    """Module-level entry point preserved for the existing systemd unit.

    ``deploy/systemd/camina-sensor.service`` invokes
    ``python -m src.camina.service.sensor_daemon --config /etc/camina/sensor.yaml``.
    For a more flexible CLI (``--dry-run``, etc.) prefer
    ``scripts/run_sensor.py`` — both delegate to ``compose()`` so behaviour
    stays identical.
    """
    parser = argparse.ArgumentParser(description="CAMINA edge sensor daemon")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Local import to keep the stdlib-only ``DaemonConfig`` API loadable
    # without picamera2/Ultralytics on import.
    from src.camina.service.compose import compose

    cfg = DaemonConfig.from_yaml(args.config)
    daemon = compose(
        cfg,
        ncnn_model_path=cfg.ncnn_model_path,
        imgsz=cfg.imgsz,
        conf=cfg.conf_threshold,
    )
    daemon.start()


__all__ = ["DaemonConfig", "SensorDaemon"]


if __name__ == "__main__":
    main()
