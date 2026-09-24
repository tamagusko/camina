"""YOLO detection on an NCNN model without Ultralytics or PyTorch.

The sensor used to run its NCNN model through Ultralytics' ``YOLO`` wrapper,
which imports PyTorch (~700 MB installed) and, on ARM64, asks for ncnn built
from git source. This module is the same pipeline in NumPy, ported from
Ultralytics 8.3.123 so that detections are identical
(``tests/test_ncnn_detector.py`` checks it against Ultralytics):

1. ``letterbox`` — ``LetterBox(auto=False)``: resize keeping the aspect ratio
   (``cv2.INTER_LINEAR``), pad to a square with grey 114, BGR -> RGB, /255.
2. The NCNN forward pass.
3. ``postprocess`` — ``non_max_suppression`` (best class only, score strictly
   above ``conf``, class-offset greedy NMS at IoU ``iou``, at most 300 boxes)
   then ``scale_boxes`` back to frame pixels, clipped to the frame.

Frames are BGR-ordered, as OpenCV and picamera2's "RGB888" format deliver
them. The Pi camera is configured for square frames at the model size, so on
the device the resize and padding steps are no-ops.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import yaml

logger = logging.getLogger(__name__)

_PAD_VALUE = 114
_MAX_WH = 7680      # class offset for batched NMS (Ultralytics' max_wh)
_MAX_NMS = 30000    # boxes kept for NMS, by score
_MAX_DET = 300


def letterbox(frame: np.ndarray, size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Prepare a BGR frame as the model's (3, size, size) float32 RGB input.

    Args:
        frame: ``(H, W, 3)`` uint8 image in BGR order.
        size: Square model input size.

    Returns:
        ``(x, gain, (pad_x, pad_y))`` — the input tensor, and the scale and
        padding that ``postprocess`` needs to map boxes back to the frame.
    """
    h, w = frame.shape[:2]
    gain = min(size / h, size / w)
    new_w, new_h = int(round(w * gain)), int(round(h * gain))
    img = frame
    if (new_w, new_h) != (w, h):
        import cv2  # only for non-square sources; the Pi camera needs no resize

        img = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    dw, dh = (size - new_w) / 2, (size - new_h) / 2
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    if top or bottom or left or right:
        img = np.pad(img, ((top, bottom), (left, right), (0, 0)), constant_values=_PAD_VALUE)

    x = np.ascontiguousarray(img[..., ::-1].transpose(2, 0, 1)).astype(np.float32) / 255
    # Padding as Ultralytics' scale_boxes recomputes it (unrounded new size).
    pad = (round((size - w * gain) / 2 - 0.1), round((size - h * gain) / 2 - 0.1))
    return x, gain, pad


def postprocess(
    raw: np.ndarray,
    *,
    conf: float,
    iou: float,
    gain: float,
    pad: tuple[int, int],
    frame_shape: tuple[int, int],
) -> np.ndarray:
    """Turn raw model output into detections in frame pixels.

    Args:
        raw: ``(4 + nc, anchors)`` output — cx, cy, w, h, then per-class scores.
        conf: Keep boxes whose best class score is strictly above this.
        iou: NMS IoU threshold; a box overlapping a better one of the same
            class by more than this is dropped.
        gain: Letterbox scale (model pixels per frame pixel).
        pad: Letterbox padding ``(x, y)`` in model pixels.
        frame_shape: ``(H, W)`` of the original frame.

    Returns:
        ``(N, 6)`` float32 rows ``[x1, y1, x2, y2, score, class]``, best first.
    """
    scores = raw[4:]
    best, cls = scores.max(0), scores.argmax(0)
    keep = best > conf
    if not keep.any():
        return np.zeros((0, 6), dtype=np.float32)

    cx, cy, bw, bh = raw[:4, keep]
    boxes = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], axis=1)
    best, cls = best[keep], cls[keep].astype(np.float32)

    order = np.argsort(-best, kind="stable")[:_MAX_NMS]
    boxes, best, cls = boxes[order], best[order], cls[order]
    kept = _nms(boxes + cls[:, None] * _MAX_WH, best, iou)[:_MAX_DET]

    dets = np.column_stack([boxes[kept], best[kept], cls[kept]]).astype(np.float32)
    dets[:, [0, 2]] -= pad[0]
    dets[:, [1, 3]] -= pad[1]
    dets[:, :4] /= gain
    h, w = frame_shape
    dets[:, [0, 2]] = dets[:, [0, 2]].clip(0, w)
    dets[:, [1, 3]] = dets[:, [1, 3]].clip(0, h)
    return dets


def _nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> np.ndarray:
    """Greedy NMS over boxes already sorted best-first; returns kept indices."""
    x1, y1, x2, y2 = boxes.T
    area = (x2 - x1) * (y2 - y1)
    order = np.arange(len(scores))
    kept: list[int] = []
    while order.size:
        i, rest = order[0], order[1:]
        kept.append(int(i))
        iw = (np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest])).clip(0)
        ih = (np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest])).clip(0)
        inter = iw * ih
        order = rest[inter / (area[i] + area[rest] - inter) <= iou]
    return np.asarray(kept, dtype=np.int64)


class NcnnDetector:
    """An NCNN YOLO model: ``detector(frame)`` -> ``(N, 6)`` detections."""

    def __init__(self, model_dir: Path | str, imgsz: int = 640, conf: float = 0.3, iou: float = 0.7) -> None:
        """Load ``model.ncnn.param``/``.bin`` and the class names from ``metadata.yaml``.

        Raises:
            RuntimeError: when NCNN cannot load the model files.
        """
        import ncnn

        model_dir = Path(model_dir)
        meta = yaml.safe_load((model_dir / "metadata.yaml").read_text(encoding="utf-8"))
        self.names: dict[int, str] = {int(k): v for k, v in meta["names"].items()}
        self.imgsz, self.conf, self.iou = imgsz, conf, iou

        self._ncnn = ncnn
        self._net = ncnn.Net()
        if self._net.load_param(str(model_dir / "model.ncnn.param")) or self._net.load_model(
            str(model_dir / "model.ncnn.bin")
        ):
            raise RuntimeError(f"NCNN could not load the model in {model_dir}")
        self._input = self._net.input_names()[0]
        self._output = sorted(self._net.output_names())[0]
        logger.info("Loaded NCNN model %s (%d classes, imgsz %d)", model_dir, len(self.names), imgsz)

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        """Detect objects in one BGR frame; rows are ``[x1, y1, x2, y2, score, class]``."""
        x, gain, pad = letterbox(frame, self.imgsz)
        mat = self._ncnn.Mat(x)  # wraps x without copying: x must outlive the forward pass
        with self._net.create_extractor() as ex:
            ex.input(self._input, mat)
            _, out = ex.extract(self._output)
        return postprocess(
            np.array(out), conf=self.conf, iou=self.iou, gain=gain, pad=pad, frame_shape=frame.shape[:2]
        )


__all__ = ["NcnnDetector", "letterbox", "postprocess"]
