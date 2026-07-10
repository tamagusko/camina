"""Binary LoRaWAN codec for windowed CAMINA counts (Phase-4 transport).

The LoRaWAN uplink path carries the same nine-class windowed counts as the
HTTPS path, but over a bandwidth- and duty-cycle-constrained radio bearer
(TTN → webhook). Where the HTTPS path posts a JSON ``CountsPayload``, the LoRa
path packs a fixed 20-byte binary frame that TTN forwards base64-encoded to the
ingest webhook (see ``docs/lora.md`` and ``dashboard/src/lib/lora-codec.ts``).

Wire format (schema version 2, big-endian, 20 bytes):

    off  size  field           type      notes
    0    3     camera id       ascii     "LNN"/"DNN" form, e.g. b"D01"
    3    4     window start     uint32    unix epoch seconds (UTC), big-endian
    7    2     person          uint16    busy class — widened (see below)
    9    2     cyclist         uint16    busy class — widened
    11   2     car             uint16    busy class — widened
    13   1     e-scooter       uint8     clamps at 255
    14   1     SUV             uint8     clamps at 255
    15   1     motorcyclist    uint8     clamps at 255
    16   1     bus             uint8     clamps at 255
    17   1     delivery_van    uint8     clamps at 255
    18   1     truck           uint8     clamps at 255
    19   1     schema version  uint8     == 2

Why three uint16 fields? The mock simulation (``scripts/generate_mock_dublin.py``,
``pack_lora_reference``) showed ``person`` counts at UCD pedestrian peaks reach
259–425 in a 15-minute window — a 1-byte field (max 255) saturates. ``person``,
``cyclist`` and ``car`` are the three classes that can plausibly exceed 255 per
window, so they are widened to uint16 (max 65535). The remaining six classes
stay uint8 and are clamped at 255 (a warning is logged on clamp); saturation for
those classes is not realistic at any Dublin street density.

The class order MUST match the canonical nine-class taxonomy used by
``pack_lora_reference`` in ``scripts/generate_mock_dublin.py`` and by
``ROAD_USER_CLASSES`` in ``dashboard/src/lib/types.ts``.

base64 of 20 bytes is 28 characters — far under the 200-char LoRa payload cap
(CLAUDE.md) and well under the EU868 SF12 51-byte MAC-payload limit.
"""
from __future__ import annotations

import base64
import logging
import struct
from dataclasses import dataclass
from typing import Mapping

logger = logging.getLogger(__name__)

# Canonical nine-class taxonomy. Order is load-bearing: it is the packing order
# and must stay in sync with ``CLASSES`` in scripts/generate_mock_dublin.py and
# ``ROAD_USER_CLASSES`` in dashboard/src/lib/types.ts.
CLASSES: tuple[str, ...] = (
    "person",
    "cyclist",
    "car",
    "e-scooter",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
)

# Classes widened to uint16 (busy classes that can exceed 255 per window).
WIDE_CLASSES: frozenset[str] = frozenset({"person", "cyclist", "car"})

SCHEMA_VERSION: int = 2
FRAME_BYTES: int = 20
CAM_ID_BYTES: int = 3
UINT8_MAX: int = 0xFF
UINT16_MAX: int = 0xFFFF
UINT32_MAX: int = 0xFFFFFFFF

# person/cyclist/car are the first three classes, so the packed count block is
# simply three uint16 followed by six uint8, then the 1-byte schema version.
# ">3s I HHH BBBBBB B" = 3 + 4 + 6 + 6 + 1 = 20 bytes.
_STRUCT = struct.Struct(">3sIHHHBBBBBBB")
assert _STRUCT.size == FRAME_BYTES  # noqa: S101 — layout invariant


@dataclass(frozen=True)
class LoraFrame:
    """Decoded LoRa uplink frame (the inverse of :func:`pack`)."""

    camera_id: str
    window_start_epoch: int
    counts: dict[str, int]
    schema_version: int


def _clamp(value: int, ceiling: int, cls: str, camera_id: str) -> int:
    """Clamp ``value`` into ``[0, ceiling]``; warn only on uint8 saturation."""
    if value < 0:
        return 0
    if value > ceiling:
        # uint16 classes have headroom for realistic peaks; only warn when a
        # uint8 class actually saturates (a real design signal, per the sim).
        if ceiling == UINT8_MAX:
            logger.warning(
                "LoRa count clamp: %s class %r count %d exceeds uint8 max, "
                "clamped to %d",
                camera_id, cls, value, ceiling,
            )
        return ceiling
    return value


def pack(
    camera_id: str,
    window_start_epoch: int,
    counts: Mapping[str, int],
) -> bytes:
    """Pack windowed counts into the 20-byte LoRa frame.

    Args:
        camera_id: Three-character ASCII camera id, e.g. ``"D01"``.
        window_start_epoch: Window-start unix epoch seconds (UTC), 0..2^32-1.
        counts: Per-class counts. Missing classes default to 0; unknown class
            keys are ignored. Values are clamped to the field width (uint16 for
            person/cyclist/car, uint8 for the rest); uint8 clamps log a warning.

    Returns:
        Exactly ``FRAME_BYTES`` (20) bytes.

    Raises:
        ValueError: If ``camera_id`` is not 3 ASCII bytes or the epoch is out
            of uint32 range.
    """
    cam_bytes = camera_id.encode("ascii")
    if len(cam_bytes) != CAM_ID_BYTES:
        raise ValueError(
            f"camera_id must be {CAM_ID_BYTES} ASCII bytes, got {camera_id!r}"
        )
    if not 0 <= window_start_epoch <= UINT32_MAX:
        raise ValueError(
            f"window_start_epoch {window_start_epoch} out of uint32 range"
        )

    packed: list[int] = []
    for cls in CLASSES:
        ceiling = UINT16_MAX if cls in WIDE_CLASSES else UINT8_MAX
        packed.append(_clamp(int(counts.get(cls, 0)), ceiling, cls, camera_id))

    return _STRUCT.pack(
        cam_bytes,
        window_start_epoch,
        *packed,
        SCHEMA_VERSION,
    )


def unpack(frame: bytes) -> LoraFrame:
    """Decode a 20-byte LoRa frame back into a :class:`LoraFrame`.

    Round-trip property: ``unpack(pack(cam, epoch, counts))`` yields the counts
    clamped to their field widths.

    Raises:
        ValueError: On wrong length, non-ASCII camera id, or schema mismatch.
    """
    if len(frame) != FRAME_BYTES:
        raise ValueError(
            f"LoRa frame must be {FRAME_BYTES} bytes, got {len(frame)}"
        )
    fields = _STRUCT.unpack(frame)
    cam_bytes = fields[0]
    window_start_epoch = fields[1]
    class_values = fields[2:11]
    schema_version = fields[11]
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported LoRa schema version {schema_version} "
            f"(expected {SCHEMA_VERSION})"
        )
    try:
        camera_id = cam_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError(f"camera id is not valid ASCII: {cam_bytes!r}") from exc

    counts = {cls: int(val) for cls, val in zip(CLASSES, class_values)}
    return LoraFrame(
        camera_id=camera_id,
        window_start_epoch=window_start_epoch,
        counts=counts,
        schema_version=schema_version,
    )


def pack_b64(
    camera_id: str,
    window_start_epoch: int,
    counts: Mapping[str, int],
) -> str:
    """Convenience: pack and base64-encode (the TTN ``frm_payload`` form)."""
    return base64.b64encode(pack(camera_id, window_start_epoch, counts)).decode(
        "ascii"
    )


__all__ = [
    "CLASSES",
    "WIDE_CLASSES",
    "SCHEMA_VERSION",
    "FRAME_BYTES",
    "LoraFrame",
    "pack",
    "unpack",
    "pack_b64",
]
