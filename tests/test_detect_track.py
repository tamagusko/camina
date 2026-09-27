"""Unit tests for the YOLO NCNN + custom tracker adapter.

We monkeypatch ``NcnnDetector`` so the test suite never loads a real model.
Detections are synthesised as the ``(N, 6)`` arrays it returns
(``[x1, y1, x2, y2, score, class]``).

The adapter wires YOLO -> the existing custom Kalman+Hungarian tracker
(``camina.core.tracker.Sort``) and yields ``(track_id_str, class_name)``
tuples for the daemon's WindowedCounter. The track-id format is
``"<class_name>-<int>"`` so two different classes never share a track-id key.
"""

from __future__ import annotations

from typing import ClassVar

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
    """One frame's detections, converted by the fake detector to ``(N, 6)``."""

    def __init__(self, cls: list[int], conf: list[float], xyxy: list[list[float]]):
        self.cls = np.asarray(cls, dtype=float)
        self.conf = np.asarray(conf, dtype=float)
        self.xyxy = np.asarray(xyxy, dtype=float)

    def __len__(self) -> int:
        return int(self.cls.shape[0])


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


def _fake_detector_factory(boxes_per_call: list[_FakeBoxes], model_names: list[str] | None = None):
    """Build an ``NcnnDetector`` stand-in returning ``boxes_per_call[i]`` on call i.

    The detector exposes ``.names`` in ``model_names`` order (CAMINAv1 order by
    default) and returns ``(N, 6)`` rows ``[x1, y1, x2, y2, score, class]``.
    """
    state = {"i": 0}
    names_map = {i: c for i, c in enumerate(model_names or CLASSES)}

    class _FakeDetector:
        names = names_map

        def __init__(self, *_args, **_kwargs):
            pass

        def __call__(self, frame):
            idx = state["i"]
            state["i"] = min(idx + 1, len(boxes_per_call) - 1)
            b = boxes_per_call[idx]
            if not len(b):
                return np.zeros((0, 6))
            return np.column_stack([b.xyxy.reshape(-1, 4), b.conf, b.cls])

    return _FakeDetector


def test_yields_track_id_class_name_tuples(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single high-confidence ``car`` detection produces one tuple where the
    track-id string is prefixed with the class name."""
    from camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[CLASSES.index("car")],
        conf=[0.9],
        xyxy=[[10.0, 10.0, 60.0, 60.0]],
    )
    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([boxes, boxes, boxes, boxes])
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
    from camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[CLASSES.index("car")],
        conf=[0.25],  # below the 0.3 threshold
        xyxy=[[10.0, 10.0, 60.0, 60.0]],
    )
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory([boxes] * 6))

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
    from camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[99],  # Way out of range for the 9-class model.
        conf=[0.9],
        xyxy=[[10.0, 10.0, 60.0, 60.0]],
    )
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory([boxes]))
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, conf=0.3
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="Unknown class index 99"):
        list(f(frame))


def test_class_name_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the loaded model's ``.names`` does not match the configured class
    list (in order), the factory raises ``ValueError`` at build time."""
    from camina.service import detect_track

    bad_classes = ["person", "WRONG", "car", *CLASSES[3:]]

    class _FakeModel:
        names: ClassVar[dict[int, str]] = dict(enumerate(CLASSES))

        def __call__(self, *_a, **_kw):
            return []

    monkeypatch.setattr(detect_track, "NcnnDetector", lambda *_a, **_kw: _FakeModel())
    with pytest.raises(ValueError, match="Model classes"):
        detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=bad_classes)


def test_alphabetical_model_names_are_remapped_to_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TRA 2026 export lists classes alphabetically and calls motorcyclists
    ``motorcycle``. Detections must come out under the canonical names, looked
    up by name rather than by index."""
    from camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[TRA2026_MODEL_NAMES.index("car"), TRA2026_MODEL_NAMES.index("motorcycle")],
        conf=[0.9, 0.9],
        xyxy=[[10.0, 10.0, 60.0, 60.0], [200.0, 200.0, 260.0, 260.0]],
    )
    monkeypatch.setattr(
        detect_track,
        "NcnnDetector",
        _fake_detector_factory([boxes] * 5, model_names=TRA2026_MODEL_NAMES),
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
    from camina.service import detect_track

    names = [n if n != "truck" else "tram" for n in TRA2026_MODEL_NAMES]
    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([_FakeBoxes([], [], [])], names)
    )
    with pytest.raises(ValueError, match=r"tram.*class_mapping"):
        detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES)


def test_imgsz_mismatch_with_export_metadata_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Running an NCNN export at a size other than the one recorded in its
    ``metadata.yaml`` produces garbage boxes, so the factory refuses it."""
    from camina.service import detect_track

    (tmp_path / "metadata.yaml").write_text("imgsz:\n- 640\n- 640\n")
    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([_FakeBoxes([], [], [])])
    )
    with pytest.raises(ValueError, match="imgsz"):
        detect_track.make_detect_and_track(ncnn_model_path=tmp_path, classes=CLASSES, imgsz=480)


# ---------- Count gate ----------


def _run(monkeypatch: pytest.MonkeyPatch, frames: list[_FakeBoxes], gate) -> list[tuple[str, str]]:
    from camina.service import detect_track

    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory(frames))
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, conf=0.3, gate=gate
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    seen: list[tuple[str, str]] = []
    for _ in frames:
        seen.extend(list(f(frame)))
    return seen


def _car_at(x: float) -> _FakeBoxes:
    return _FakeBoxes(cls=[CLASSES.index("car")], conf=[0.9], xyxy=[[x, 200.0, x + 60.0, 240.0]])


def test_with_a_gate_a_parked_car_is_never_yielded(monkeypatch: pytest.MonkeyPatch) -> None:
    from camina.core.counting import CountGate

    assert _run(monkeypatch, [_car_at(100.0)] * 20, CountGate(min_move=1.0)) == []


def test_with_a_gate_a_moving_car_is_yielded_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from camina.core.counting import CountGate, Screenline

    frames = [_car_at(20.0 * i) for i in range(20)]  # drives left to right across x = 240
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))

    seen = _run(monkeypatch, frames, gate)

    assert len(seen) == 1 and seen[0][1] == "car" and seen[0][0].startswith("car-")


def test_a_vehicle_flickering_between_car_and_suv_is_counted_once_as_its_majority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One vehicle, detected as car on 2 of 3 frames and SUV on the rest, is one
    track: counted once, as car. With a tracker per class it was counted twice."""
    from camina.core.counting import CountGate, Screenline

    frames = [
        _FakeBoxes(
            cls=[CLASSES.index("SUV") if i % 3 == 0 else CLASSES.index("car")],
            conf=[0.9],
            xyxy=[[20.0 * i, 200.0, 20.0 * i + 60.0, 240.0]],
        )
        for i in range(20)
    ]
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))

    seen = _run(monkeypatch, frames, gate)

    assert [cls for _, cls in seen] == ["car"]
    assert seen[0].direction == "AB"


def test_closure_exposes_its_tracker_for_min_track_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    """The daemon applies the server's ``min_track_hits`` through this handle."""
    from camina.core.tracker import Sort
    from camina.service import detect_track

    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([_FakeBoxes([], [], [])])
    )
    f = detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES)
    assert isinstance(f.tracker, Sort)  # type: ignore[attr-defined]


def test_the_person_riding_a_bicycle_is_not_tracked_as_a_pedestrian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from camina.service import detect_track

    boxes = _FakeBoxes(
        cls=[CLASSES.index("cyclist"), CLASSES.index("person")],
        conf=[0.9, 0.9],
        xyxy=[[100.0, 100.0, 160.0, 220.0], [110.0, 100.0, 150.0, 180.0]],
    )
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory([boxes] * 5))
    f = detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES)
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    seen = [cls for _ in range(5) for _, cls in f(frame)]

    assert set(seen) == {"cyclist"}


def test_the_gate_must_remember_tracks_at_least_as_long_as_the_tracker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gate forgetting a track the tracker still holds would count it twice."""
    from camina.core.counting import CountGate
    from camina.service import detect_track

    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([_FakeBoxes([], [], [])])
    )
    with pytest.raises(ValueError, match="forget_after_s"):
        detect_track.make_detect_and_track(
            ncnn_model_path="ignored",
            classes=CLASSES,
            gate=CountGate(forget_after_s=4.0),
            max_occlusion_s=5.0,
        )


def test_frame_timestamps_drive_the_occlusion_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frames stamped 6 s apart: the car's track is gone and a new one starts."""
    from camina.service import detect_track

    car, empty = _car_at(100.0), _FakeBoxes([], [], [])
    frames = [car] * 4 + [empty, car, car, car, car]
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory(frames))
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, max_occlusion_s=5.0
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    stamps = [0.0, 0.1, 0.2, 0.3, 0.4, 6.5, 6.6, 6.7, 6.8]
    ids = {tid for t in stamps for tid, _ in f(frame, t=t)}

    assert len(ids) == 2


def test_the_tracker_may_relink_across_confused_vehicle_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from camina.service import detect_track

    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([_FakeBoxes([], [], [])])
    )
    f = detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES)
    car, suv, person = CLASSES.index("car"), CLASSES.index("SUV"), CLASSES.index("person")

    assert f.tracker._compatible(car, suv)  # type: ignore[attr-defined]
    assert not f.tracker._compatible(car, person)  # type: ignore[attr-defined]


def test_relinking_is_off_unless_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    from camina.service import detect_track

    monkeypatch.setattr(
        detect_track, "NcnnDetector", _fake_detector_factory([_FakeBoxes([], [], [])])
    )
    off = detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES)
    on = detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES, relink=True)

    assert off.tracker.relink is False  # type: ignore[attr-defined]
    assert on.tracker.relink is True  # type: ignore[attr-defined]


def test_a_car_is_counted_only_once_its_class_is_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With min_class_hits=14 the car has crossed the line (frame 11) before it
    confirms; it is counted, with its direction, on the frame it confirms."""
    from camina.core.counting import CountGate, Screenline
    from camina.service import detect_track

    frames = [_car_at(20.0 * i) for i in range(20)]  # centre crosses x = 240 at frame 11
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory(frames))
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, gate=gate, min_class_hits=14
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    per_frame = [list(f(frame, t=i / 10)) for i in range(len(frames))]

    counted_at = [i for i, out in enumerate(per_frame) if out]
    assert counted_at == [13]  # the car's 14th detection
    assert per_frame[13][0].direction == "AB"


def test_a_track_dying_before_its_class_confirms_is_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from camina.core.counting import CountGate, Screenline
    from camina.service import detect_track

    frames = [_car_at(20.0 * i) for i in range(15)] + [_FakeBoxes([], [], [])] * 3
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory(frames))
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)), forget_after_s=5.0)
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored",
        classes=CLASSES,
        imgsz=480,
        gate=gate,
        min_class_hits=20,
        max_occlusion_s=5.0,
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    stamps = [i / 10 for i in range(15)] + [3.0, 6.0, 9.0]
    seen = [c for t in stamps for c in f(frame, t=t)]

    assert seen == []
    assert gate.unconfirmed_dropped == 1
    assert f.gate is gate  # type: ignore[attr-defined]


# ---------- Speed ----------


def _speed_lines():
    from camina.core.counting import Screenline
    from camina.core.speed import SpeedLines

    # 480 px frame: lines at x = 120 and 360 px, 12 m apart on the road.
    return SpeedLines(
        Screenline((0.25, 0.0), (0.25, 1.0)), Screenline((0.75, 0.0), (0.75, 1.0)), 12.0
    )


def test_with_speed_lines_a_car_crossing_both_has_its_speed_taken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """20 px per 0.1 s = 200 px/s; the 240 px between the lines take 1.2 s: 36 km/h."""
    from camina.core.speed import SpeedEstimator
    from camina.service import detect_track

    frames = [_car_at(20.0 * i) for i in range(25)]
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory(frames))
    f = detect_track.make_detect_and_track(
        ncnn_model_path="ignored", classes=CLASSES, imgsz=480, speed=SpeedEstimator(_speed_lines())
    )
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    speeds = []
    for i in range(25):
        list(f(frame, t=0.1 * i))
        speeds += f.take_speeds()  # type: ignore[attr-defined]

    assert len(speeds) == 1
    assert speeds[0][0] == "car"
    assert speeds[0][1] == pytest.approx(36.0, abs=0.1)
    assert f.take_speeds() == []  # type: ignore[attr-defined]


def test_without_speed_lines_no_speed_is_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    from camina.service import detect_track

    frames = [_car_at(20.0 * i) for i in range(25)]
    monkeypatch.setattr(detect_track, "NcnnDetector", _fake_detector_factory(frames))
    f = detect_track.make_detect_and_track(ncnn_model_path="ignored", classes=CLASSES, imgsz=480)
    frame = np.zeros((480, 480, 3), dtype=np.uint8)
    for i in range(25):
        list(f(frame, t=0.1 * i))
    assert f.take_speeds() == []  # type: ignore[attr-defined]
    assert f.speed is None  # type: ignore[attr-defined]
