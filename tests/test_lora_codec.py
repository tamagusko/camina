"""Unit tests for the Phase-4 LoRaWAN binary codec (src/camina/io/lora_codec).

Covers the 20-byte layout, the person/cyclist/car uint16 widening (the fix for
the uint8 saturation the mock simulation surfaced), uint8 clamp-with-warning,
round-trip identity, and rejection of malformed frames.
"""
from __future__ import annotations

import base64
import struct

import pytest

from src.camina.io.lora_codec import (
    CLASSES,
    FRAME_BYTES,
    SCHEMA_VERSION,
    WIDE_CLASSES,
    LoraFrame,
    pack,
    pack_b64,
    unpack,
)

EPOCH = 1_776_000_000  # arbitrary UTC epoch inside uint32 range
CAM = "D01"


def _full_counts(value: int = 1) -> dict[str, int]:
    return {cls: value for cls in CLASSES}


def test_frame_is_exactly_20_bytes() -> None:
    frame = pack(CAM, EPOCH, _full_counts())
    assert len(frame) == FRAME_BYTES == 20


def test_b64_is_28_chars_under_lora_cap() -> None:
    b64 = pack_b64(CAM, EPOCH, _full_counts(300))
    assert len(b64) == 28
    assert len(b64) <= 200  # CLAUDE.md LoRa payload cap
    assert len(b64) <= 51 * 4 // 3 + 4  # comfortably under EU868 SF12 airtime


def test_round_trip_identity_for_in_range_counts() -> None:
    counts = {
        "person": 425,        # exceeds uint8, fits uint16 (the sim's worst case)
        "cyclist": 259,
        "car": 310,
        "e-scooter": 40,
        "SUV": 22,
        "motorcyclist": 6,
        "bus": 8,
        "delivery_van": 12,
        "truck": 4,
    }
    decoded = unpack(pack(CAM, EPOCH, counts))
    assert decoded == LoraFrame(
        camera_id=CAM,
        window_start_epoch=EPOCH,
        counts=counts,
        schema_version=SCHEMA_VERSION,
    )
    # unpack(pack(x)) == x for in-range values.
    assert decoded.counts == counts


def test_wide_classes_carry_values_above_255() -> None:
    # person/cyclist/car must survive their busy peaks unchanged.
    for cls in WIDE_CLASSES:
        counts = {cls: 425}
        decoded = unpack(pack(CAM, EPOCH, counts))
        assert decoded.counts[cls] == 425


def test_uint8_class_clamps_at_255_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    # A narrow (uint8) class saturates at 255 and logs a warning.
    with caplog.at_level("WARNING"):
        decoded = unpack(pack(CAM, EPOCH, {"truck": 999}))
    assert decoded.counts["truck"] == 255
    assert any("clamp" in r.message.lower() for r in caplog.records)


def test_wide_class_clamp_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    # uint16 headroom: even a huge value clamps silently (no design signal).
    with caplog.at_level("WARNING"):
        decoded = unpack(pack(CAM, EPOCH, {"person": 70_000}))
    assert decoded.counts["person"] == 65535
    assert not caplog.records


def test_uint16_clamp_round_trip_property() -> None:
    # unpack(pack(x)) == clamped x, per the codec contract.
    raw = {"person": 70_000, "truck": 999, "car": -5}
    decoded = unpack(pack(CAM, EPOCH, raw))
    assert decoded.counts["person"] == 65535
    assert decoded.counts["truck"] == 255
    assert decoded.counts["car"] == 0  # negatives clamp to 0


def test_missing_classes_default_to_zero() -> None:
    decoded = unpack(pack(CAM, EPOCH, {"car": 12}))
    assert decoded.counts["car"] == 12
    assert decoded.counts["person"] == 0
    assert decoded.counts["truck"] == 0


def test_unknown_class_keys_are_ignored() -> None:
    decoded = unpack(pack(CAM, EPOCH, {"unicorn": 5, "car": 3}))
    assert decoded.counts["car"] == 3
    assert "unicorn" not in decoded.counts


def test_camera_id_round_trips() -> None:
    assert unpack(pack("L07", EPOCH, {})).camera_id == "L07"


@pytest.mark.parametrize("bad_id", ["D1", "DUBLIN", "", "Dé1"])
def test_bad_camera_id_raises(bad_id: str) -> None:
    with pytest.raises(ValueError):
        pack(bad_id, EPOCH, {})


@pytest.mark.parametrize("bad_epoch", [-1, 2**32])
def test_epoch_out_of_uint32_range_raises(bad_epoch: int) -> None:
    with pytest.raises(ValueError):
        pack(CAM, bad_epoch, {})


@pytest.mark.parametrize("length", [0, 19, 21, 24])
def test_wrong_length_frame_rejected(length: int) -> None:
    with pytest.raises(ValueError):
        unpack(b"\x00" * length)


def test_wrong_schema_version_rejected() -> None:
    frame = bytearray(pack(CAM, EPOCH, {}))
    frame[-1] = 1  # downgrade to the retired v1 schema byte
    with pytest.raises(ValueError):
        unpack(bytes(frame))


def test_layout_offsets_are_big_endian() -> None:
    # Explicitly assert the documented byte offsets so a struct-string change
    # can never silently reorder the wire format.
    frame = pack(CAM, EPOCH, {"person": 0x0102, "truck": 0x7F})
    assert frame[0:3] == b"D01"
    assert struct.unpack(">I", frame[3:7])[0] == EPOCH
    assert struct.unpack(">H", frame[7:9])[0] == 0x0102  # person uint16
    assert frame[18] == 0x7F  # truck uint8 at offset 18
    assert frame[19] == SCHEMA_VERSION


def test_pack_b64_matches_manual_encoding() -> None:
    counts = _full_counts(3)
    assert pack_b64(CAM, EPOCH, counts) == base64.b64encode(
        pack(CAM, EPOCH, counts)
    ).decode("ascii")
