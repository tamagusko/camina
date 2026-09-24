"""Tests for the NCNN-native detector that replaces the Ultralytics wrapper on the Pi.

The detector must reproduce Ultralytics' predictions for an NCNN model exactly:
same letterbox, same BGR->RGB/255 input, same best-class NMS (IoU 0.7, class
offset 7680, max 300), same rescaling to frame pixels. The parity tests run only
where Ultralytics is installed (dev machines); the Pi profile does not ship it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.camina.service.ncnn_detector import NcnnDetector, letterbox, postprocess

REPO = Path(__file__).resolve().parents[1]
MODEL = REPO / "models" / "camina_v1_yolo11n_ncnn_model"
IMAGES = sorted((REPO / "custom_model_train" / "test_images").glob("*.jpg"))
NC = 9


# ---------- letterbox ----------

def test_letterbox_pads_a_landscape_frame_top_and_bottom() -> None:
    frame = np.full((480, 640, 3), 200, dtype=np.uint8)

    x, gain, pad = letterbox(frame, 640)

    assert x.shape == (3, 640, 640) and x.dtype == np.float32
    assert gain == 1.0 and pad == (0, 80)
    assert np.allclose(x[:, :80, :], 114 / 255)       # grey bar above
    assert np.allclose(x[:, 80:560, :], 200 / 255)    # frame
    assert np.allclose(x[:, 560:, :], 114 / 255)      # grey bar below


def test_letterbox_leaves_a_square_camera_frame_untouched() -> None:
    """The Pi camera already delivers 640x640: no resize, no padding."""
    frame = np.random.default_rng(1).integers(0, 255, (640, 640, 3), dtype=np.uint8)

    x, gain, pad = letterbox(frame, 640)

    assert gain == 1.0 and pad == (0, 0)
    assert np.array_equal(x, frame[..., ::-1].transpose(2, 0, 1).astype(np.float32) / 255)


@pytest.mark.parametrize("shape", [(480, 640), (1080, 1920), (375, 500), (640, 427)])
def test_letterbox_matches_ultralytics_pixel_for_pixel(shape: tuple[int, int]) -> None:
    augment = pytest.importorskip("ultralytics.data.augment")
    frame = np.random.default_rng(2).integers(0, 255, (*shape, 3), dtype=np.uint8)

    ours, _, _ = letterbox(frame, 640)
    ref = augment.LetterBox((640, 640), auto=False, stride=32)(image=frame)
    ref = ref[..., ::-1].transpose(2, 0, 1).astype(np.float32) / 255

    assert np.array_equal(ours, ref)


# ---------- postprocess ----------

def _raw(*anchors: tuple[float, float, float, float, int, float]) -> np.ndarray:
    """Raw model output (4 + NC, 8400): one column per (cx, cy, w, h, cls, score)."""
    out = np.zeros((4 + NC, 8400), dtype=np.float32)
    for a, (cx, cy, w, h, cls, score) in enumerate(anchors):
        out[:4, a] = (cx, cy, w, h)
        out[4 + cls, a] = score
    return out


def _post(raw: np.ndarray, **kw) -> np.ndarray:
    args = dict(conf=0.3, iou=0.7, gain=1.0, pad=(0, 0), frame_shape=(640, 640))
    args.update(kw)
    return postprocess(raw, **args)


def test_overlapping_boxes_of_one_class_keep_only_the_best() -> None:
    dets = _post(_raw((100, 100, 50, 50, 2, 0.9), (102, 100, 50, 50, 2, 0.8)))

    assert dets.shape == (1, 6)
    assert dets[0, 4] == pytest.approx(0.9) and dets[0, 5] == 2


def test_overlapping_boxes_of_different_classes_both_survive() -> None:
    dets = _post(_raw((100, 100, 50, 50, 2, 0.9), (100, 100, 50, 50, 3, 0.7)))

    assert sorted(dets[:, 5].tolist()) == [2.0, 3.0]


def test_scores_at_or_below_conf_are_dropped() -> None:
    dets = _post(_raw((100, 100, 50, 50, 1, 0.3), (300, 300, 50, 50, 1, 0.31)))

    assert dets.shape == (1, 6) and dets[0, 4] == pytest.approx(0.31)


def test_boxes_are_mapped_back_to_frame_pixels_and_clipped() -> None:
    # Letterboxed 480x640 frame: pad 80 rows on top. A box near the top-left
    # corner of the frame, partly over the edge.
    dets = _post(_raw((10, 90, 40, 40, 0, 0.9)), pad=(0, 80), frame_shape=(480, 640))

    x1, y1, x2, y2 = dets[0, :4]
    assert (x1, y1) == (0.0, 0.0)               # clipped at the frame edge
    assert (x2, y2) == pytest.approx((30.0, 30.0))


def test_no_candidates_returns_an_empty_array() -> None:
    dets = _post(_raw())

    assert dets.shape == (0, 6)


# ---------- NcnnDetector on the real model ----------

requires_model = pytest.mark.skipif(not MODEL.is_dir(), reason="committed NCNN model not present")


@requires_model
def test_names_come_from_metadata_in_index_order() -> None:
    names = NcnnDetector(MODEL).names

    assert names[0] == "SUV" and names[6] == "motorcycle" and len(names) == 9


@requires_model
def test_detections_match_ultralytics_on_the_test_images() -> None:
    """The gate for dropping Ultralytics on the Pi: identical detections."""
    ultralytics = pytest.importorskip("ultralytics")
    cv2 = pytest.importorskip("cv2")
    if not IMAGES:
        pytest.skip("custom_model_train/test_images not present")

    ours = NcnnDetector(MODEL, imgsz=640, conf=0.3)
    ref = ultralytics.YOLO(str(MODEL), task="detect")

    total = 0
    for path in IMAGES:
        frame = cv2.imread(str(path))  # BGR, as Ultralytics reads it
        mine = ours(frame)
        r = ref(frame, imgsz=640, conf=0.3, verbose=False)[0].boxes
        theirs = np.column_stack([r.xyxy.numpy(), r.conf.numpy(), r.cls.numpy()])

        assert mine.shape == theirs.shape, path.name
        mine, theirs = mine[np.argsort(-mine[:, 4])], theirs[np.argsort(-theirs[:, 4])]
        assert np.array_equal(mine[:, 5], theirs[:, 5]), path.name
        assert np.allclose(mine[:, :4], theirs[:, :4], atol=0.5), path.name
        assert np.allclose(mine[:, 4], theirs[:, 4], atol=1e-3), path.name
        total += len(mine)

    assert total == 81  # the FP32 model's detections on these images (2026-09-24)
