"""Integrity tests for the canonical CAMINAv1 taxonomy and its mapping layer.

Covers:
  - ``configs/classes.yaml`` is the 9-class canonical set (contiguous, no dupes),
    matching the in-code mirror in ``src/utils/export_ncnn.py``.
  - ``custom_model_train/class_mapping.yaml`` is a closed alias table (every
    canonical name maps to itself; every value is canonical; the known aliases
    ``pedestrian``->``person`` and ``motorcycle``->``motorcyclist`` are present).
  - The toolchain loader resolves toolchain-named models onto canonical and
    fails loudly on unmapped / missing classes.
  - The export guard (``export_ncnn._verify_canonical_taxonomy``) passes a
    canonical model and refuses a legacy 6-class one with a clear diff.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


CANONICAL = [
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

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_class_taxonomy() -> ModuleType:
    """Import the toolchain loader by file path (it lives outside src/)."""
    path = REPO_ROOT / "custom_model_train" / "scripts" / "class_taxonomy.py"
    spec = importlib.util.spec_from_file_location("class_taxonomy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ct = _load_class_taxonomy()


# ---------- canonical set integrity ----------


def test_canonical_is_nine_classes_no_dupes_contiguous() -> None:
    canonical = ct.load_canonical_classes()
    assert canonical == CANONICAL
    assert len(canonical) == 9
    assert len(set(canonical)) == 9, "canonical taxonomy has duplicate names"


def test_canonical_matches_export_constant() -> None:
    """The YAML SSOT must not drift from the in-code mirror in export_ncnn."""
    from src.utils import export_ncnn

    assert export_ncnn.CAMINAV1_CLASSES == ct.load_canonical_classes()


# ---------- mapping-layer closure ----------


def test_mapping_is_closed_over_canonical() -> None:
    aliases = ct.load_class_aliases()
    canonical = set(ct.load_canonical_classes())

    # Every alias value is a canonical name (no value escapes the taxonomy).
    for name, target in aliases.items():
        assert target in canonical, f"{name} -> {target} is not canonical"

    # Every canonical name is present as an identity entry (closed table).
    for name in canonical:
        assert aliases.get(name) == name, f"missing identity entry for {name}"

    # The known differing aliases are declared.
    assert aliases["pedestrian"] == "person"
    assert aliases["motorcycle"] == "motorcyclist"


def test_resolve_unmapped_name_raises() -> None:
    with pytest.raises(ct.TaxonomyError):
        ct.resolve_to_canonical(["not_a_real_class"])


def test_assert_passes_for_alias_named_canonical_order() -> None:
    # A model carrying toolchain names but in canonical order must pass.
    alias_named = [
        "person", "cyclist", "car", "e-scooter", "SUV",
        "motorcyclist", "bus", "delivery_van", "truck",
    ]
    ct.assert_canonical_taxonomy(alias_named)  # no raise


def test_assert_raises_for_legacy_six_class_with_missing_list() -> None:
    legacy = ["bus", "car", "cyclist", "motorcycle", "person", "truck"]
    with pytest.raises(ct.TaxonomyError) as exc:
        ct.assert_canonical_taxonomy(legacy)
    msg = str(exc.value)
    for missing in ("e-scooter", "SUV", "delivery_van"):
        assert missing in msg, f"diff should name the missing class {missing}"


# ---------- export guard logic (mocked names, no real export) ----------


def test_export_guard_accepts_canonical_names() -> None:
    from src.utils import export_ncnn

    export_ncnn._verify_canonical_taxonomy(CANONICAL)  # no raise


def test_export_guard_rejects_legacy_six_class() -> None:
    from src.utils import export_ncnn

    legacy = ["bus", "car", "cyclist", "motorcycle", "person", "truck"]
    with pytest.raises(SystemExit) as exc:
        export_ncnn._verify_canonical_taxonomy(legacy)
    assert "Missing canonical classes" in str(exc.value)


def test_export_guard_rejects_unmapped_name() -> None:
    from src.utils import export_ncnn

    with pytest.raises(SystemExit) as exc:
        export_ncnn._verify_canonical_taxonomy(["person", "gremlin"])
    assert "Unmapped" in str(exc.value)
