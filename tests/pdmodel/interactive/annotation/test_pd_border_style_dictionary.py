from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


def test_default_constructor_sets_type_border() -> None:
    bs = PDBorderStyleDictionary()
    cos = bs.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "Border"  # type: ignore[attr-defined]


def test_default_width_is_one() -> None:
    bs = PDBorderStyleDictionary()
    assert bs.get_width() == 1.0


def test_default_style_is_solid() -> None:
    bs = PDBorderStyleDictionary()
    assert bs.get_style() == PDBorderStyleDictionary.STYLE_SOLID
    assert bs.get_style() == "S"


def test_default_dash_style_is_none() -> None:
    bs = PDBorderStyleDictionary()
    assert bs.get_dash_style() is None


def test_width_round_trip_float() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_width(2.5)
    assert bs.get_width() == 2.5


def test_width_round_trip_integer_valued_float_is_stored_as_int() -> None:
    # PDFBOX-3929: integer-valued floats are stored as int.
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    cos = bs.get_cos_object()
    raw = cos.get_dictionary_object(COSName.get_pdf_name("W"))
    # Should be a COSInteger, not a COSFloat
    from pypdfbox.cos import COSFloat
    assert not isinstance(raw, COSFloat)
    assert bs.get_width() == 2.0


def test_style_round_trip_dashed() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    assert bs.get_style() == "D"


def test_dash_style_round_trip() -> None:
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    bs = PDBorderStyleDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(3))
    arr.add(COSInteger.get(2))
    bs.set_dash_style(arr)
    rt = bs.get_dash_style()
    assert isinstance(rt, PDLineDashPattern)
    assert rt.get_dash_array() == [3.0, 2.0]


def test_construct_from_existing_dict_preserves_contents() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "D")
    d.set_float(COSName.get_pdf_name("W"), 3.5)
    bs = PDBorderStyleDictionary(d)
    assert bs.get_style() == "D"
    assert bs.get_width() == 3.5
    # Constructor with existing dict should NOT clobber /Type if present,
    # nor inject one if absent.
    assert bs.get_cos_object().get_name(COSName.TYPE) is None  # type: ignore[attr-defined]


def test_width_with_cosname_value_returns_zero() -> None:
    """Adobe quirk: name value for /W returns 0."""
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("W"), "Foo")
    bs = PDBorderStyleDictionary(d)
    assert bs.get_width() == 0.0


def test_dash_style_clear() -> None:
    bs = PDBorderStyleDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(3))
    bs.set_dash_style(arr)
    bs.set_dash_style(None)
    assert bs.get_dash_style() is None


# ---------- Wave 202: /S predicate helpers ----------


def test_is_solid_default() -> None:
    """Default style is solid; predicate reports True."""
    bs = PDBorderStyleDictionary()
    assert bs.is_solid()
    assert not bs.is_dashed()
    assert not bs.is_beveled()
    assert not bs.is_inset()
    assert not bs.is_underline()


def test_is_dashed_after_set_style() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    assert bs.is_dashed()
    assert not bs.is_solid()


def test_is_beveled_after_set_style() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_BEVELED)
    assert bs.is_beveled()
    assert not bs.is_solid()


def test_is_inset_after_set_style() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_INSET)
    assert bs.is_inset()
    assert not bs.is_solid()


def test_is_underline_after_set_style() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_UNDERLINE)
    assert bs.is_underline()
    assert not bs.is_solid()


def test_predicates_are_mutually_exclusive_for_known_styles() -> None:
    """Each known style triggers exactly one predicate."""
    style_to_pred = {
        PDBorderStyleDictionary.STYLE_SOLID: "is_solid",
        PDBorderStyleDictionary.STYLE_DASHED: "is_dashed",
        PDBorderStyleDictionary.STYLE_BEVELED: "is_beveled",
        PDBorderStyleDictionary.STYLE_INSET: "is_inset",
        PDBorderStyleDictionary.STYLE_UNDERLINE: "is_underline",
    }
    for style, expected in style_to_pred.items():
        bs = PDBorderStyleDictionary()
        bs.set_style(style)
        for name in ("is_solid", "is_dashed", "is_beveled", "is_inset", "is_underline"):
            actual = getattr(bs, name)()
            assert actual is (name == expected), (
                f"style={style!r} predicate={name} expected {name == expected}"
            )


def test_predicates_unknown_style_all_false_except_solid_when_absent() -> None:
    """An unknown /S name reports False for every named predicate."""
    bs = PDBorderStyleDictionary()
    bs.set_style("X")  # not one of the canonical S/D/B/I/U values
    assert not bs.is_solid()
    assert not bs.is_dashed()
    assert not bs.is_beveled()
    assert not bs.is_inset()
    assert not bs.is_underline()


def test_style_constants_match_spec_letters() -> None:
    """PDF 32000-1 §12.5.4 Table 166 single-letter style codes."""
    assert PDBorderStyleDictionary.STYLE_SOLID == "S"
    assert PDBorderStyleDictionary.STYLE_DASHED == "D"
    assert PDBorderStyleDictionary.STYLE_BEVELED == "B"
    assert PDBorderStyleDictionary.STYLE_INSET == "I"
    assert PDBorderStyleDictionary.STYLE_UNDERLINE == "U"


# ---------- Wave 202: set_dash_style sequence input ----------


def test_set_dash_style_accepts_list_of_floats() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_dash_style([3.0, 2.0])
    rt = bs.get_dash_style()
    assert rt is not None
    assert rt.get_dash_array() == [3.0, 2.0]


def test_set_dash_style_accepts_tuple_of_floats() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_dash_style((4.0, 1.0, 2.0))
    rt = bs.get_dash_style()
    assert rt is not None
    assert rt.get_dash_array() == [4.0, 1.0, 2.0]


def test_set_dash_style_accepts_int_sequence_coerced_to_float() -> None:
    """int values in a sequence are accepted and coerced via float()."""
    bs = PDBorderStyleDictionary()
    bs.set_dash_style([3, 2])
    rt = bs.get_dash_style()
    assert rt is not None
    assert rt.get_dash_array() == [3.0, 2.0]


def test_set_dash_style_empty_sequence_writes_empty_array() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_dash_style([])
    rt = bs.get_dash_style()
    assert rt is not None
    assert rt.get_dash_array() == []


def test_set_dash_style_rejects_string() -> None:
    """Strings/bytes are sequences but not numeric — must be rejected."""
    import pytest

    bs = PDBorderStyleDictionary()
    with pytest.raises(TypeError):
        bs.set_dash_style("3 2")  # type: ignore[arg-type]


def test_set_dash_style_rejects_arbitrary_object() -> None:
    import pytest

    bs = PDBorderStyleDictionary()
    with pytest.raises(TypeError):
        bs.set_dash_style(object())  # type: ignore[arg-type]


def test_set_dash_style_with_pd_line_dash_pattern_round_trip() -> None:
    """Existing PDLineDashPattern code path is preserved by the refactor."""
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    bs = PDBorderStyleDictionary()
    src_array = COSArray()
    src_array.add(COSInteger.get(5))
    src_array.add(COSInteger.get(3))
    pattern = PDLineDashPattern(src_array, 0)
    bs.set_dash_style(pattern)
    rt = bs.get_dash_style()
    assert rt is not None
    assert rt.get_dash_array() == [5.0, 3.0]


# ---------- Wave 202: get_dash_style_or_default upstream parity ----------


def test_get_dash_style_or_default_when_absent_installs_default_three() -> None:
    """Mirrors upstream getDashStyle() which seeds [3] when /D is absent."""
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    bs = PDBorderStyleDictionary()
    assert not bs.get_cos_object().contains_key(COSName.get_pdf_name("D"))
    rt = bs.get_dash_style_or_default()
    assert isinstance(rt, PDLineDashPattern)
    assert rt.get_dash_array() == [3.0]
    # The default array must have been written back to the underlying dict.
    assert bs.get_cos_object().contains_key(COSName.get_pdf_name("D"))
    raw = bs.get_cos_object().get_dictionary_object(COSName.get_pdf_name("D"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 1


def test_get_dash_style_or_default_when_present_returns_existing() -> None:
    """When /D is present, get_dash_style_or_default returns it unchanged."""
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    bs = PDBorderStyleDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(7))
    arr.add(COSInteger.get(2))
    bs.set_dash_style(arr)
    rt = bs.get_dash_style_or_default()
    assert isinstance(rt, PDLineDashPattern)
    assert rt.get_dash_array() == [7.0, 2.0]
    # The existing array is preserved (identity-comparable).
    assert bs.get_cos_object().get_dictionary_object(COSName.get_pdf_name("D")) is arr


def test_get_dash_style_remains_none_when_absent() -> None:
    """get_dash_style (without _or_default) keeps None semantics — i.e. it
    must NOT install the default [3] array as a side effect."""
    bs = PDBorderStyleDictionary()
    assert bs.get_dash_style() is None
    # No /D installed by the call.
    assert not bs.get_cos_object().contains_key(COSName.get_pdf_name("D"))
