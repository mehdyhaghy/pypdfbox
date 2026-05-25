"""Wave 1403 — branch round-out for :class:`OpenTypeFont`.

Closes the partial arc ``[233,238]`` — the
``font_set is not None and font_set.fontNames`` False branch in
:meth:`get_cff`: when fontTools exposes no parsed ``cff`` font-set on the
CFF table, ``is_cid`` stays ``False`` and the projection routes to the
name-keyed :class:`CFFType1Font` path.
"""

from __future__ import annotations

from unittest import mock

from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.ttf import OTFParser
from tests.fontbox.ttf.test_open_type_font_coverage import (
    _synth_name_keyed_otf_bytes,
)


def test_get_cff_with_no_font_set_routes_to_type1() -> None:
    """When ``cff_table.cff`` is ``None`` the CID-detection ``if`` takes
    its False arc ([233,238]); ``is_cid`` stays False and the result is a
    name-keyed :class:`CFFType1Font`."""
    font = OTFParser().parse(_synth_name_keyed_otf_bytes())
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    real_bytes = cff_table.compile(font._tt)

    original_cff = cff_table.cff
    cff_table.cff = None  # type: ignore[assignment]
    cff_table.data = real_bytes  # type: ignore[attr-defined]
    try:
        cff = font.get_cff()
    finally:
        cff_table.cff = original_cff

    assert isinstance(cff, CFFType1Font)


def test_get_cff_with_empty_font_names_routes_to_type1() -> None:
    """A font-set with an empty ``fontNames`` also takes the False arc
    ([233,238]) and yields a name-keyed :class:`CFFType1Font`."""
    font = OTFParser().parse(_synth_name_keyed_otf_bytes())
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    real_bytes = cff_table.compile(font._tt)

    class _EmptyFontSet:
        fontNames: list[str] = []

    original_cff = cff_table.cff
    cff_table.cff = _EmptyFontSet()  # type: ignore[assignment]
    cff_table.data = real_bytes  # type: ignore[attr-defined]
    try:
        with mock.patch.object(cff_table, "compile", return_value=real_bytes):
            cff = font.get_cff()
    finally:
        cff_table.cff = original_cff

    assert isinstance(cff, CFFType1Font)
