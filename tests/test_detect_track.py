"""Unit tests for the YOLO NCNN + custom tracker adapter.

We monkeypatch the Ultralytics ``YOLO`` class so the test suite never loads a
real model. Detections are synthesised directly as ``MagicMock`` results
matching the relevant subset of the Ultralytics ``Results`` API
(``.boxes.cls``, ``.boxes.conf``, ``.boxes.xyxy``).

The adapter wires YOLO -> the existing custom Kalman+Hungarian tracker
(``src.camina.core.tracker.Sort``) and yields ``(track_id_str, class_name)``
tuples for the daemon's WindowedCounter. The track-id format is
``"<class_name>-<int>"`` so two different classes never share a track-id key.
"""
from __future__ import annotations

import numpy as np
import pytest


CLASSES = [
    "person",
    "cyclist",
    "car",
    "e-scooter",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
]


class _FakeBoxes:
    """Mimic the ``ultralytics.engine.results.Boxes`` API used by the adapter."""

    def __init__(self, cls: list[int], conf: list[float], xyxy: list[list[float]]):
        self.cls = np.asarray(cls, dtype=float)
        self.conf = np.asarray(conf, dtype=float)
        self.xyxy = np.asarray(xyxy, dtype=float)

    def __len__(self) -> int:
        return int(self.cls.shape[0])


class _FakeResult:
    def __init__(self, boxes: _FakeBoxes):
        self.boxes = boxes


# Class order of the TRA 2026 YOLO11n NCNN export (alphabetical, as Ultralytics
# wrote it), including the dataset alias ``motorcycle`` for ``motorcyclist``.
TRA2026_MODEL_NAMES = [
    "SUV",
    "bus",
    "car",
    "cyclist",
    "delivery_van",
    "e-scooter",
    "motorcycle",
    "person",
    "truck",
]


def _fake_yolo_factory(
    boxes_per_call: list[_FakeBoxes], model_names: list[str] | None = None
):
    """Build a ``YOLO`` stand-in whose call returns a list of fake results.

    The fake model is callable: ``model(frame, ...)`` returns
    ``[FakeResult(boxes_per_call[i])]`` and advances ``i`` on each call.
    The model exposes ``.names`` in ``model_names`` order (CAMINAv1 order by
    default).
    """
    state = {"i": 0}
    names_map = {i: c for i, c in enumerate(model_names or CLASSES)}

    class _FakeModel:
        names = names_map

        def __call__(self, frame, **kwargs):  # noqa: D401 — mimic YOLO signature
            idx = state["i"]
            state["i"] = min(idx + 1, len(boxes_per_call) - 1)
            return [_FakeResult(boxes_per_call[idx])]

    def _ctor(_path):
        return _FakeModel()

    return _ctor


def test_yields_track_id_class_name_tuples(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single high-confidence ``car`` detection produces one tuple where the
    track-id string is prefixed with the class name."""
    from src.camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[CLASSES.index("car")],
        conf=[0.9],
        xyxy=[[10.0, 10.0, 60.0, 60.0]],
    )
    monkeypatch.setattr(
        detect_track, "YOLO", _fake_yolo_factory([boxes, boxes, boxes, boxes])
    )

    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, conf=0.3
    )

    # The Sort tracker requires ``min_hits=3`` confirmations before emitting a
    # track. Feed the same detection multiple times so we cross that threshold.
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    seen: list[tuple[str, str]] = []
    for _ in range(5):
        seen.extend(list(f(frame)))

    assert seen, "expected at least one (track_id, class_name) tuple"
    track_id, class_name = seen[-1]
    assert class_name == "car"
    assert track_id.startswith("car-")
    # All entries must be string track-ids prefixed with their class.
    for tid, cls in seen:
        assert cls in CLASSES
        assert tid.startswith(f"{cls}-")


def test_filters_below_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detections below the configured confidence threshold are dropped before
    the tracker, so they never produce a ``(track_id, class_name)`` tuple."""
    from src.camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[CLASSES.index("car")],
        conf=[0.25],  # below the 0.3 threshold
        xyxy=[[10.0, 10.0, 60.0, 60.0]],
    )
    monkeypatch.setattr(
        detect_track, "YOLO", _fake_yolo_factory([boxes] * 6)
    )

    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, conf=0.3
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)

    seen: list[tuple[str, str]] = []
    for _ in range(6):
        seen.extend(list(f(frame)))

    assert seen == [], f"expected no tuples below conf threshold, got {seen}"


def test_unknown_class_index_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A detection with a class index outside ``0..len(classes)-1`` raises
    ``ValueError`` so the daemon fails loudly instead of mis-attributing
    counts."""
    from src.camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[99],  # Way out of range for the 9-class model.
        conf=[0.9],
        xyxy=[[10.0, 10.0, 60.0, 60.0]],
    )
    monkeypatch.setattr(
        detect_track, "YOLO", _fake_yolo_factory([boxes])
    )
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, conf=0.3
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="Unknown class index 99"):
        list(f(frame))


def test_class_name_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the loaded model's ``.names`` does not match the configured class
    list (in order), the factory raises ``ValueError`` at build time."""
    from src.camina.service import detect_track

    bad_classes = ["person", "WRONG", "car"] + CLASSES[3:]

    class _FakeModel:
        names = {i: c for i, c in enumerate(CLASSES)}

        def __call__(self, *_a, **_kw):
            return []

    monkeypatch.setattr(detect_track, "YOLO", lambda _p: _FakeModel())
    with pytest.raises(ValueError, match="Model classes"):
        detect_track.make_detect_and_track(
            ncnn_model_path="ignored", classes=bad_classes
        )


def test_alphabetical_model_names_are_remapped_to_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TRA 2026 export lists classes alphabetically and calls motorcyclists
    ``motorcycle``. Detections must come out under the canonical names, looked
    up by name rather than by index."""
    from src.camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[TRA2026_MODEL_NAMES.index("car"), TRA2026_MODEL_NAMES.index("motorcycle")],
        conf=[0.9, 0.9],
        xyxy=[[10.0, 10.0, 60.0, 60.0], [200.0, 200.0, 260.0, 260.0]],
    )
    monkeypatch.setattr(
        detect_track,
        "YOLO",
        _fake_yolo_factory([boxes] * 5, model_names=TRA2026_MODEL_NAMES),
    )

    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=640, conf=0.3
    )
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    seen: list[tuple[str, str]] = []
    for _ in range(5):
        seen.extend(list(f(frame)))

    assert {cls for _, cls in seen} == {"car", "motorcyclist"}
    for tid, cls in seen:
        assert tid.startswith(f"{cls}-")


def test_unknown_model_class_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model class name with no alias entry (here ``tram``) fails at build
    time instead of being dropped or counted under the wrong class."""
    from src.camina.service import detect_track

    names = [n if n != "truck" else "tram" for n in TRA2026_MODEL_NAMES]
    monkeypatch.setattr(
        detect_track, "YOLO", _fake_yolo_factory([_FakeBoxes([], [], [])], names)
    )
    with pytest.raises(ValueError, match=r"tram.*class_mapping"):
        detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES)


def test_imgsz_mismatch_with_export_metadata_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Running an NCNN export at a size other than the one recorded in its
    ``metadata.yaml`` produces garbage boxes, so the factory refuses it."""
    from src.camina.service import detect_track

    (tmp_path / "metadata.yaml").write_text("imgsz:\n- 640\n- 640\n")
    monkeypatch.setattr(
        detect_track, "YOLO", _fake_yolo_factory([_FakeBoxes([], [], [])])
    )
    with pytest.raises(ValueError, match="imgsz"):
        detect_track.make_detect_and_track(
            ncnn_model_path=tmp_path, classes=CLASSES, imgsz=480
        )
