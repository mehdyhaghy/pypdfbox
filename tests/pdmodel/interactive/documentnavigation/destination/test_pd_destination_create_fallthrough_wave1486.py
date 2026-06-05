"""Wave 1486 — PDDestination.create malformed-array fall-through + the
explicit XYZ short-array getter asymmetry.

Oracle-pinned against Apache PDFBox 3.0.7 (``ExplicitDestinationProbe``):

* ``PDDestination.create`` gates its array branch on ``size() > 1`` AND
  ``item[1]`` being a ``COSName``. A ``COSArray`` that fails either test is
  *not* handled by a bespoke "too short"/"not a name" error; upstream lets it
  fall through the ``else if`` chain to the final
  ``"Error: can't convert to Destination ..."`` ``IOException`` (it is neither
  a ``COSString`` nor a ``COSName`` named-destination form). pypdfbox mirrors
  the fall-through and the message prefix (the COS ``toString`` tail differs
  project-wide and is not asserted).
* A recognized-tag array with an unknown type name still raises the upstream
  ``"Unknown destination type: <name>"`` message.
* ``PDPageXYZDestination`` getters on a short (size-2) array: upstream's
  ``getLeft``/``getTop`` route through ``COSArray.getInt`` (bounds-safe, ``-1``
  default) while ``getZoom`` reads ``getObject(4)`` unguarded and throws
  ``IndexOutOfBoundsException``. pypdfbox's ``_get_float`` is uniformly
  bounds-safe and returns ``None`` for every missing slot — the better-behaved
  superset; the upstream crash is an intentional divergence (DEFERRED note),
  pinned here so a future "match upstream exactly" change is a conscious one.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_xyz_destination import (
    PDPageXYZDestination,
)

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - oracle harness optional
    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: str) -> str:  # type: ignore[misc]
        raise RuntimeError("oracle unavailable")


# --------------------------------------------------------------------------
# create() fall-through for malformed destination arrays.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "array",
    [
        COSArray(),  # size 0
        COSArray([COSInteger.get(0)]),  # size 1
        COSArray([COSInteger.get(0), COSInteger.get(5)]),  # item[1] not a name
        COSArray([COSInteger.get(0), COSString("XYZ")]),  # item[1] a string, not a name
    ],
    ids=["empty", "size1", "nonname_int", "nonname_string"],
)
def test_create_malformed_array_falls_through_to_cant_convert(array: COSArray) -> None:
    with pytest.raises(OSError, match=r"can't convert to Destination"):
        PDDestination.create(array)


def test_create_unknown_tag_keeps_unknown_destination_type_message() -> None:
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("Foo")])
    with pytest.raises(OSError, match=r"Unknown destination type: Foo"):
        PDDestination.create(arr)


def test_create_non_array_non_named_falls_through() -> None:
    # A bare COSInteger is neither COSArray, COSString nor COSName.
    with pytest.raises(OSError, match=r"can't convert to Destination"):
        PDDestination.create(COSInteger.get(7))


# --------------------------------------------------------------------------
# XYZ short-array getter asymmetry (intentional divergence).
# --------------------------------------------------------------------------


def test_xyz_short_array_getters_return_none_not_minus_one_or_throw() -> None:
    short = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    xyz = PDPageXYZDestination(short)
    # Constructing from an existing (short) array must NOT grow it — the
    # upstream ``PDPageXYZDestination(COSArray)`` ctor delegates to super
    # without growToSize, so the backing array stays size 2.
    assert xyz.get_cos_array().size() == 2
    # All three coordinate getters are bounds-safe in pypdfbox (None for the
    # missing slot); upstream's getZoom would throw IndexOutOfBounds here.
    assert xyz.get_left() is None
    assert xyz.get_top() is None
    assert xyz.get_zoom() is None


# --------------------------------------------------------------------------
# Optional live differential.
# --------------------------------------------------------------------------


@requires_oracle
def test_explicit_destination_oracle_differential() -> None:
    out = dict(
        line.split("=", 1)
        for line in run_probe_text("ExplicitDestinationProbe").splitlines()
        if "=" in line
    )
    # Fresh array shapes / sentinels (pypdfbox renders COSNull where the probe
    # prints <absent>).
    assert out["xyz_fresh_getLeft"] == "-1"
    assert out["xyz_fresh_getZoom"] == "-1.0"
    assert out["xyz_zoom0_getZoom"] == "0.0"
    # create dispatch identities (upstream reuses Fit/FitH/FitV for the bounded
    # FitB/FitBH/FitBV names; pypdfbox uses dedicated subclasses — see
    # CHANGES.md — so we only pin the unambiguous XYZ here).
    assert out["create_xyz"] == "PDPageXYZDestination"
    # Unknown-tag message.
    assert out["create_foo_msg"] == "Unknown destination type: Foo"
    # Malformed arrays fall through to the can't-convert error upstream.
    assert out["create_short_msg"].startswith("Error: can't convert to Destination")
    assert out["create_empty_msg"].startswith("Error: can't convert to Destination")
    assert out["create_nonname_msg"].startswith("Error: can't convert to Destination")
    # Short-array getZoom throws upstream (the divergence we deliberately don't
    # reproduce).
    assert out["xyz_short_getLeft"] == "-1"
    assert out["xyz_short_getZoom_exc"] == "IndexOutOfBoundsException"
    assert out["create_null"] == "null"
