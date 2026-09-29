"""Bounds of the tracking rules, shared by ``sensor.yaml`` and the server config.

``Sort`` and ``DaemonConfig.from_yaml`` check the local values with
``check_tracking_rules``; ``camina.io.schemas.SensorConfig`` uses the same
constants for the values the server sends, so the two paths cannot drift.
"""

from __future__ import annotations

MIN_CLASS_HITS_MIN = 1
MAX_CLASS_HITS = 20
MAX_OCCLUSION_S_LIMIT = 60.0  # seconds; the lower bound is exclusive: > 0


def check_tracking_rules(max_occlusion_s: float, min_class_hits: int, relink: bool) -> None:
    """Raise ``ValueError`` naming the key when a tracking rule is out of bounds.

    Args:
        max_occlusion_s: Seconds a hidden track survives; must be in (0, 60].
        min_class_hits: Detections of its class a track needs; must be in 1..20.
        relink: Must be a real boolean: a quoted "false" is truthy in Python.

    Raises:
        ValueError: When a value is out of bounds or of the wrong type.
    """
    if isinstance(max_occlusion_s, bool) or not isinstance(max_occlusion_s, int | float):
        raise ValueError(f"max_occlusion_s must be a number, got {max_occlusion_s!r}")
    if not 0 < max_occlusion_s <= MAX_OCCLUSION_S_LIMIT:
        raise ValueError(
            f"max_occlusion_s must be in (0, {MAX_OCCLUSION_S_LIMIT:g}], got {max_occlusion_s}"
        )
    if isinstance(min_class_hits, bool) or not isinstance(min_class_hits, int):
        raise ValueError(f"min_class_hits must be an integer, got {min_class_hits!r}")
    if not MIN_CLASS_HITS_MIN <= min_class_hits <= MAX_CLASS_HITS:
        raise ValueError(
            f"min_class_hits must be in {MIN_CLASS_HITS_MIN}..{MAX_CLASS_HITS}, "
            f"got {min_class_hits}"
        )
    if not isinstance(relink, bool):
        raise ValueError(f"relink must be true or false (unquoted), got {relink!r}")
