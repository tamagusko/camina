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
import logging
import signal
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


logger = logging.getLogger(__name__)


# In-loop publisher sends must fail fast: the OfflineBuffer now fully owns
# durable retry + persistence (a failed send is buffered and replayed later),
# so a long inline retry ladder would only stall the detection loop during an
# outage — and a multi-minute stall kills tracks, causing double counting.
# Hence 2 attempts with a short backoff cap. RetryPolicy defaults are left
# untouched for other callers/tests.
_INLINE_RETRY = RetryPolicy(max_attempts=2, base_delay_s=0.5, max_delay_s=2.0)


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
        self._daily = DailyAccumulator(
            db_path=config.state_db_path, classes=config.classes
        )
        self._outbox = OfflineBuffer(
            db_path=config.state_db_path.with_suffix(".outbox.db"),
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

    # ---------- Public API ----------

    def start(self) -> None:
        logger.info("Sensor daemon starting for %s", self._config.sensor_id)
        self._catch_up_daily()
        self._heartbeat_thread = Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
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
        # Flush the open (incomplete) window before closing state so a deploy
        # doesn't silently drop up to one window of counts; the heartbeat
        # thread is already joined, so the counter is no longer touched
        # concurrently.
        self._flush_open_window()
        self._outbox.close()
        self._daily.close()
        self._http.close()
        logger.info("Sensor daemon stopped")

    # ---------- Internal ----------

    def _main_loop(self) -> None:
        for frame in self._frame_source:
            if self._shutdown.is_set():
                break
            now = datetime.now(tz=timezone.utc)
            for track_id, class_name in self._detect_and_track(frame):
                self._counter.add(track_id=track_id, class_name=class_name, now=now)

            snapshot = self._counter.maybe_rollover(now)
            if snapshot is not None:
                self._on_window_snapshot(snapshot, now)

            daily_snapshot = self._daily.maybe_rollover(now)
            if daily_snapshot is not None:
                self._publish_daily(daily_snapshot)

    def _on_window_snapshot(self, snapshot: WindowSnapshot, now: datetime) -> None:
        self._daily.add_window(snapshot)
        result = self._publisher.post_counts(
            snapshot=snapshot,
            config_version=self._poller.current_version,
            fw_version=self._config.fw_version,
        )
        if result.latest_config_version:
            self._poller.check(result.latest_config_version)

    def _publish_daily(self, snapshot: DailySnapshot) -> None:
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
            self._send_heartbeat()

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
