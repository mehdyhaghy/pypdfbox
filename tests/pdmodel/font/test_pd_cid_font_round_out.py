"""Wave 211 — small remaining gaps on PDCIDFont.

Covers:

* ``set_dw(None)`` / ``has_dw`` — None handling for the default-width entry.
* ``get_dw2_position_vector_y`` / ``get_dw2_displacement_vector_y`` —
  typed split accessors over ``/DW2``.
* ``get_default_position_vector_for_cid`` — per-CID variant matching
  upstream ``PDCIDFont.getDefaultPositionVector(int cid)``.
* ``has_cid_to_gid_map_stream`` / ``is_identity_cid_to_gid_map`` —
  predicate helpers over the three valid ``/CIDToGIDMap`` states.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

_DW = COSName.get_pdf_name("DW")
_DW2 = COSName.get_pdf_name("DW2")
_W = COSName.get_pdf_name("W")
_CID_TO_GID_MAP = COSName.get_pdf_name("CIDToGIDMap")


# ---------- set_dw(None) / has_dw ----------


def test_has_dw_false_when_absent() -> None:
    font = PDCIDFontType0()
    assert font.has_dw() is False
    # spec default still returned
    assert font.get_dw() == 1000


def test_has_dw_true_after_explicit_set() -> None:
    font = PDCIDFontType0()
    font.set_dw(500)
    assert font.has_dw() is True
    assert font.get_dw() == 500


def test_has_dw_distinguishes_explicit_1000_from_default() -> None:
    font = PDCIDFontType0()
    assert font.has_dw() is False
    font.set_dw(1000)
    assert font.has_dw() is True
    assert font.get_dw() == 1000


def test_set_dw_none_removes_entry() -> None:
    font = PDCIDFontType0()
    font.set_dw(750)
    assert font.has_dw() is True
    font.set_dw(None)
    assert font.has_dw() is False
    # falls back to spec default
    assert font.get_dw() == 1000


# ---------- /DW2 typed split accessors ----------


def test_dw2_position_vector_y_default_when_absent() -> None:
    font = PDCIDFontType0()
    assert font.get_dw2_position_vector_y() == 880.0


def test_dw2_displacement_vector_y_default_when_absent() -> None:
    font = PDCIDFontType0()
    assert font.get_dw2_displacement_vector_y() == -1000.0


def test_dw2_typed_accessors_after_explicit_set() -> None:
    font = PDCIDFontType0()
    arr = COSArray()
    arr.add(COSInteger.get(900))
    arr.add(COSInteger.get(-1100))
    font.set_dw2(arr)
    assert font.get_dw2_position_vector_y() == 900.0
    assert font.get_dw2_displacement_vector_y() == -1100.0


def test_dw2_typed_accessors_with_real_numbers() -> None:
    font = PDCIDFontType0()
    arr = COSArray()
    arr.add(COSFloat(875.5))
    arr.add(COSFloat(-998.25))
    font.set_dw2(arr)
    assert font.get_dw2_position_vector_y() == 875.5
    assert font.get_dw2_displacement_vector_y() == -998.25


def test_dw2_typed_accessors_short_array_falls_back_to_defaults() -> None:
    font = PDCIDFontType0()
    arr = COSArray()
    arr.add(COSInteger.get(900))  # only one entry
    font.set_dw2(arr)
    assert font.get_dw2_position_vector_y() == 880.0
    assert font.get_dw2_displacement_vector_y() == -1000.0


# ---------- get_default_position_vector_for_cid ----------


def test_default_position_vector_for_cid_uses_dw_when_no_w() -> None:
    font = PDCIDFontType0()
    # No /W, no /DW2 → glyph width = 1000, dw2[0] = 880.
    v_x, v_y = font.get_default_position_vector_for_cid(42)
    assert v_x == 500.0  # 1000 / 2
    assert v_y == 880.0


def test_default_position_vector_for_cid_uses_w_when_present() -> None:
    font = PDCIDFontType0()
    # /W: cid 5 → width 600
    w = COSArray()
    w.add(COSInteger.get(5))
    inner = COSArray()
    inner.add(COSInteger.get(600))
    w.add(inner)
    font.set_w(w)
    v_x, v_y = font.get_default_position_vector_for_cid(5)
    assert v_x == 300.0  # 600 / 2
    assert v_y == 880.0
    # cid outside /W still uses /DW
    v_x_default, _ = font.get_default_position_vector_for_cid(999)
    assert v_x_default == 500.0  # /DW default 1000 / 2


def test_default_position_vector_for_cid_uses_dw2_position_y() -> None:
    font = PDCIDFontType0()
    arr = COSArray()
    arr.add(COSInteger.get(950))
    arr.add(COSInteger.get(-900))
    font.set_dw2(arr)
    _, v_y = font.get_default_position_vector_for_cid(0)
    assert v_y == 950.0


def test_get_position_vector_falls_back_through_per_cid_helper() -> None:
    """When /W2 has no entry for the cid, get_position_vector should match
    get_default_position_vector_for_cid exactly."""
    font = PDCIDFontType0()
    font.set_dw(800)
    arr = COSArray()
    arr.add(COSInteger.get(900))
    arr.add(COSInteger.get(-1100))
    font.set_dw2(arr)
    expected = font.get_default_position_vector_for_cid(7)
    assert font.get_position_vector(7) == expected
    # And the value itself: width 800 / 2 = 400, v_y = 900
    assert font.get_position_vector(7) == (400.0, 900.0)


# ---------- /CIDToGIDMap predicates ----------


def test_is_identity_cid_to_gid_map_true_when_absent() -> None:
    font = PDCIDFontType2()
    assert font.is_identity_cid_to_gid_map() is True
    assert font.has_cid_to_gid_map_stream() is False


def test_is_identity_cid_to_gid_map_true_when_name_identity() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.is_identity_cid_to_gid_map() is True
    assert font.has_cid_to_gid_map_stream() is False


def test_is_identity_cid_to_gid_map_false_when_other_name() -> None:
    font = PDCIDFontType2()
    # Per spec only /Identity is meaningful as a name; any other name is
    # not the identity mapping.
    font.set_cid_to_gid_map("Custom")
    assert font.is_identity_cid_to_gid_map() is False
    assert font.has_cid_to_gid_map_stream() is False


def test_has_cid_to_gid_map_stream_true_for_stream() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\x00\x01\x00\x02")
    font.set_cid_to_gid_map(stream)
    assert font.has_cid_to_gid_map_stream() is True
    assert font.is_identity_cid_to_gid_map() is False


def test_predicates_after_clearing_map() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\x00\x05")
    font.set_cid_to_gid_map(stream)
    assert font.has_cid_to_gid_map_stream() is True
    font.set_cid_to_gid_map(None)
    assert font.has_cid_to_gid_map_stream() is False
    assert font.is_identity_cid_to_gid_map() is True
