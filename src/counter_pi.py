import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

from sort import Sort
from utils.epaper_display import EpaperCounterDisplay

# ---------------------------------------------------------------------------
# Configuration ----------------------------------------------------------------
CONFIG = yaml.safe_load(Path("src/config.yaml").read_text())
CLASSES: dict[int, str] = yaml.safe_load(Path("src/classes.yaml").read_text())
DATA_DIR = Path("data")
REFRESH_INTERVAL = CONFIG.get("refresh_interval_seconds", 10)


def interval_slot(ts: datetime) -> int:
    """Return the current logging slot index."""
    return ts.minute // CONFIG["log_interval_minutes"]


class ModalShareCounter:
    """Counts object classes, logs, and updates e‑paper display."""

    def __init__(self) -> None:
        model_path = CONFIG.get("ncnn_model_path") or CONFIG["model"]
        self.model = YOLO(model_path)
        self.tracker = Sort()

        self.cap = cv2.VideoCapture(CONFIG["camera_source"])
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG["frame_width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG["frame_height"])

        self.display = EpaperCounterDisplay()
        self.last_disp_ts = 0.0

        self.frame_cnt = 0
        self.counts = {c: 0 for c in CLASSES.values()}
        self.seen_ids = {c: set() for c in CLASSES.values()}
        self.last_slot: int | None = None

    # ---------------------------------------------------------------------
    def process_frame(self, frame: np.ndarray) -> None:
        preds = self.model.predict(frame,
                                   imgsz=CONFIG["imgsz"],
                                   conf=CONFIG["confidence_threshold"])[0]

        dets, cls_map = [], {}
        for box in preds.boxes:
            cls_id = int(box.cls)
            if cls_id not in CLASSES:
                continue
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            dets.append([x1, y1, x2, y2, float(box.conf)])
            cls_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

        tracks = self.tracker.update(np.asarray(dets) if dets else np.empty((0, 5)))

        for x1, y1, x2, y2, track_id in tracks:
            label = self._nearest_label((x1, y1, x2, y2), cls_map)
            if not label:
                continue
            tid = int(track_id)
            if tid not in self.seen_ids[label]:
                self.seen_ids[label].add(tid)
                self.counts[label] += 1

        if CONFIG["logging_enabled"]:
            self._maybe_log()
        self._maybe_display()

    # ---------------------------------------------------------------------
    @staticmethod
    def _nearest_label(box: tuple[float, ...], mapping: dict) -> str | None:
        if not mapping:
            return None
        key = min(mapping, key=lambda b: np.linalg.norm(np.subtract(b, box)))
        return mapping[key]

    # ---------------------------------------------------------------------
    def _maybe_log(self) -> None:
        now = datetime.now()
        slot = interval_slot(now)
        if slot == self.last_slot:
            return
        self.last_slot = slot

        DATA_DIR.mkdir(exist_ok=True)
        log_path = DATA_DIR / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        line = ", ".join(f"{cls}:{self.counts[cls]}" for cls in CLASSES.values())
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{now:%Y-%m-%d %H:%M}, {line}\n")

    # ---------------------------------------------------------------------
    def _maybe_display(self) -> None:
        if time.time() - self.last_disp_ts >= REFRESH_INTERVAL:
            self.display.update(self.counts)
            self.last_disp_ts = time.time()

    # ---------------------------------------------------------------------
    def run(self) -> None:
        try:
            while True:
                ok, frame = self.cap.read()
                if not ok:
                    time.sleep(0.1)  # camera unavailable, retry
                    continue
                if self.frame_cnt % CONFIG["frame_skip"] == 0:
                    self.process_frame(frame)
                self.frame_cnt += 1
        finally:
            self.cap.release()
            self.display.clear()
            self._print_summary()

    # ---------------------------------------------------------------------
    def _print_summary(self) -> None:
        print("Final counts:")
        for cls, cnt in self.counts.items():
            print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
