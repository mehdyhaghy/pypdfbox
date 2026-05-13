"""Wave 239 — predicate helpers on ``PDRectlinearMeasureDictionary``.

These ``has_*`` predicates have no upstream PDFBox 3.0.x counterpart;
they are convenience accessors that distinguish absent entries from
entries set to the upstream-default sentinel. ``has_cyx()`` in
particular lets callers tell the difference between ``/CYX`` actually
absent (``get_cyx()`` returns ``-1.0`` per upstream default) and an
``/CYX`` entry explicitly set to ``-1.0``.

The predicates inspect only the COS layer via ``contains_key`` —
they never materialise a wrapper.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.interactive.measurement import (
    PDNumberFormatDictionary,
    PDRectlinearMeasureDictionary,
)


# --------------------------------------------------------------------------- /R
def test_has_scale_ratio_default_false() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.has_scale_ratio() is False


def test_has_scale_ratio_true_after_set() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_scale_ratio("1in = 1mi")
    assert rl.has_scale_ratio() is True


def test_has_scale_ratio_false_after_set_none() -> None:
    """``set_scale_ratio(None)`` removes the entry — predicate must reflect that."""
    rl = PDRectlinearMeasureDictionary()
    rl.set_scale_ratio("1in = 1mi")
    assert rl.has_scale_ratio() is True
    rl.set_scale_ratio(None)
    assert rl.has_scale_ratio() is False


# --------------------------------------------------------------------------- /CYX
def test_has_cyx_default_false() -> None:
    """A fresh dictionary has no /CYX even though ``get_cyx()`` returns -1.0."""
    rl = PDRectlinearMeasureDictionary()
    assert rl.get_cyx() == -1.0
    assert rl.has_cyx() is False


def test_has_cyx_true_after_set() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_cyx(2.5)
    assert rl.has_cyx() is True
    assert rl.get_cyx() == pytest.approx(2.5)


def test_has_cyx_disambiguates_explicit_negative_one() -> None:
    """The whole point of the predicate: an explicit -1.0 must be detectable."""
    rl = PDRectlinearMeasureDictionary()
    assert rl.has_cyx() is False  # absent, get_cyx() defaults to -1.0
    rl.set_cyx(-1.0)
    assert rl.has_cyx() is True  # present and equal to the sentinel
    assert rl.get_cyx() == -1.0


# --------------------------------------------------------------------------- /O
def test_has_coord_system_origin_default_false() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.has_coord_system_origin() is False


def test_has_coord_system_origin_true_after_set() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_coord_system_origin([0.0, 0.0])
    assert rl.has_coord_system_origin() is True


def test_has_coord_system_origin_true_for_empty_array() -> None:
    """An empty ``/O`` array still counts as present."""
    rl = PDRectlinearMeasureDictionary()
    rl.set_coord_system_origin([])
    assert rl.has_coord_system_origin() is True
    assert rl.get_coord_system_origin() == []


# --------------------------------------------------------------------------- number-format arrays
@pytest.mark.parametrize(
    ("predicate", "setter"),
    [
        ("has_change_xs", "set_change_xs"),
        ("has_change_ys", "set_change_ys"),
        ("has_distances", "set_distances"),
        ("has_areas", "set_areas"),
        ("has_angles", "set_angles"),
        ("has_line_slopes", "set_line_sloaps"),
    ],
)
def test_number_format_array_predicates_default_false(
    predicate: str, setter: str
) -> None:
    rl = PDRectlinearMeasureDictionary()
    assert getattr(rl, predicate)() is False


@pytest.mark.parametrize(
    ("predicate", "setter"),
    [
        ("has_change_xs", "set_change_xs"),
        ("has_change_ys", "set_change_ys"),
        ("has_distances", "set_distances"),
        ("has_areas", "set_areas"),
        ("has_angles", "set_angles"),
        ("has_line_slopes", "set_line_sloaps"),
        ("has_line_sloaps", "set_line_slopes"),
    ],
)
def test_number_format_array_predicates_true_after_set(
    predicate: str, setter: str
) -> None:
    rl = PDRectlinearMeasureDictionary()
    getattr(rl, setter)([PDNumberFormatDictionary()])
    assert getattr(rl, predicate)() is True


def test_has_line_slopes_alias_matches_has_line_sloaps() -> None:
    """The two spellings target the same ``/S`` slot."""
    rl = PDRectlinearMeasureDictionary()
    assert rl.has_line_slopes() == rl.has_line_sloaps() is False
    rl.set_line_slopes([PDNumberFormatDictionary()])
    assert rl.has_line_slopes() is True
    assert rl.has_line_sloaps() is True


def test_has_line_slopes_via_set_line_sloaps_typo() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_line_sloaps([PDNumberFormatDictionary()])
    # Both spellings see the entry.
    assert rl.has_line_slopes() is True
    assert rl.has_line_sloaps() is True


def test_has_change_xs_true_for_empty_array() -> None:
    """An empty ``/X`` array is still present and predicate must report True."""
    rl = PDRectlinearMeasureDictionary()
    rl.set_change_xs([])
    assert rl.has_change_xs() is True
    assert rl.get_change_xs() == []


# ----- predicates inspect COS layer only -----
def test_has_predicates_do_not_materialise_wrappers() -> None:
    """Predicates must only touch ``contains_key`` — never wrap the value.

    Verified by stuffing a wrong-type value (``COSString``) at /X and
    checking that ``has_change_xs()`` still returns ``True`` even
    though ``get_change_xs()`` would not match.
    """
    rl = PDRectlinearMeasureDictionary()
    cos = rl.get_cos_object()
    cos.set_item(COSName.get_pdf_name("X"), COSString("not-an-array"))
    assert rl.has_change_xs() is True
    # ``get_change_xs`` filters non-array values to None per upstream contract.
    assert rl.get_change_xs() is None


def test_predicates_via_wrapped_existing_dictionary() -> None:
    """Predicates work when constructed via the ``COSDictionary`` overload."""
    src = COSDictionary()
    src.set_string(COSName.get_pdf_name("R"), "1in = 1mi")
    arr = COSArray()
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(2.0))
    src.set_item(COSName.get_pdf_name("O"), arr)
    src.set_float(COSName.get_pdf_name("CYX"), 0.75)

    rl = PDRectlinearMeasureDictionary(src)
    assert rl.has_scale_ratio() is True
    assert rl.has_coord_system_origin() is True
    assert rl.has_cyx() is True
    assert rl.has_change_xs() is False
    assert rl.has_distances() is False
