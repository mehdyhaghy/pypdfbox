"""Hand-written tests for FontMapper / DefaultFontMapper / FontMapping.

Upstream Java has no checked-in unit tests for ``FontMapper``,
``FontMapping`` or ``FontMappers`` in PDFBox 3.0 — the surface is
exercised indirectly through ``TestPDFontFactory`` and rendering tests.
The tests below cover the API contract directly: protocol satisfaction,
constructor invariants, Standard 14 resolution, alias resolution and
descriptor-flag-driven fallback.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_mapper import (
    DefaultFontMapper,
    FontMapper,
    Standard14FontWrapper,
)
from pypdfbox.fontbox.font_mapping import FontMapping
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_FIXED_PITCH,
    FLAG_ITALIC,
    FLAG_SERIF,
    PDFontDescriptor,
)


# ---------------------------------------------------------------------------
# FontBoxFont protocol
# ---------------------------------------------------------------------------


def test_standard14_wrapper_satisfies_font_box_font_protocol() -> None:
    """``Standard14FontWrapper`` is a runtime-checkable :class:`FontBoxFont`."""
    mapper = DefaultFontMapper()
    mapping = mapper.get_font_box_font("Helvetica", None)
    assert mapping is not None
    assert isinstance(mapping.get_font(), FontBoxFont)


def test_protocol_rejects_non_font_objects() -> None:
    """An object missing ``get_path`` is not a ``FontBoxFont``."""

    class _PartialFont:
        def get_name(self) -> str:
            return "x"

    assert not isinstance(_PartialFont(), FontBoxFont)


# ---------------------------------------------------------------------------
# FontMapping
# ---------------------------------------------------------------------------


def test_font_mapping_round_trips_font_and_flag() -> None:
    wrapper = DefaultFontMapper().get_font_box_font("Times-Roman", None)
    assert wrapper is not None
    inner = wrapper.get_font()
    fm = FontMapping(inner, is_fallback=False)
    assert fm.get_font() is inner
    assert fm.is_fallback() is False


def test_font_mapping_camelcase_aliases_match_snake_case() -> None:
    wrapper = DefaultFontMapper().get_font_box_font("Courier", None)
    assert wrapper is not None
    fm = FontMapping(wrapper.get_font(), is_fallback=True)
    assert fm.getFont() is fm.get_font()
    assert fm.isFallback() is fm.is_fallback() is True


def test_font_mapping_repr_includes_font_name() -> None:
    wrapper = DefaultFontMapper().get_font_box_font("Symbol", None)
    assert wrapper is not None
    fm = FontMapping(wrapper.get_font(), is_fallback=False)
    text = repr(fm)
    assert "Symbol" in text
    assert "is_fallback=False" in text


def test_font_mapping_coerces_fallback_flag_to_bool() -> None:
    wrapper = DefaultFontMapper().get_font_box_font("Helvetica", None)
    assert wrapper is not None
    fm = FontMapping(wrapper.get_font(), is_fallback=1)  # type: ignore[arg-type]
    assert fm.is_fallback() is True


# ---------------------------------------------------------------------------
# Standard14FontWrapper — FontBoxFont implementation surface
# ---------------------------------------------------------------------------


def test_standard14_wrapper_get_name_returns_canonical() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Helvetica", None)
    assert mapping is not None
    assert mapping.get_font().get_name() == "Helvetica"


def test_standard14_wrapper_get_width_matches_afm() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Helvetica", None)
    assert mapping is not None
    font = mapping.get_font()
    # ``A`` has a non-zero advance in every Standard 14 font with Latin
    # coverage; we don't pin the exact value (AFM ships 667/em for
    # Helvetica) but it must be > 0.
    assert font.get_width("A") > 0.0


def test_standard14_wrapper_has_glyph_recognises_known_glyph() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Helvetica", None)
    assert mapping is not None
    font = mapping.get_font()
    assert font.has_glyph("A") is True
    assert font.has_glyph("ThisGlyphDoesNotExist") is False


def test_standard14_wrapper_font_matrix_is_type1_default() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Times-Roman", None)
    assert mapping is not None
    assert mapping.get_font().get_font_matrix() == [
        0.001,
        0.0,
        0.0,
        0.001,
        0.0,
        0.0,
    ]


def test_standard14_wrapper_get_font_bbox_is_4tuple_of_int() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Courier", None)
    assert mapping is not None
    bbox = mapping.get_font().get_font_bbox()
    assert isinstance(bbox, tuple)
    assert len(bbox) == 4
    assert all(isinstance(v, int) for v in bbox)


def test_standard14_wrapper_get_path_returns_empty_path() -> None:
    """AFMs don't ship outlines — wrapper returns an empty path."""
    mapping = DefaultFontMapper().get_font_box_font("Helvetica", None)
    assert mapping is not None
    assert mapping.get_font().get_path("A") == []


def test_standard14_wrapper_repr_includes_canonical_name() -> None:
    wrapper = Standard14FontWrapper.__new__(Standard14FontWrapper)
    # Avoid pulling AFM metrics here — repr only formats the name.
    wrapper._name = "Helvetica"  # type: ignore[attr-defined]
    wrapper._metrics = None  # type: ignore[attr-defined]
    assert repr(wrapper) == "Standard14FontWrapper('Helvetica')"


# ---------------------------------------------------------------------------
# DefaultFontMapper — Standard 14 resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "canonical",
    [
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Oblique",
        "Helvetica-BoldOblique",
        "Times-Roman",
        "Times-Bold",
        "Times-Italic",
        "Times-BoldItalic",
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
        "Symbol",
        "ZapfDingbats",
    ],
)
def test_standard14_canonical_names_resolve_without_fallback(
    canonical: str,
) -> None:
    """Every canonical Standard 14 name resolves to a non-fallback mapping."""
    mapper = DefaultFontMapper()
    mapping = mapper.get_font_box_font(canonical, None)
    assert mapping is not None
    assert mapping.is_fallback() is False
    assert mapping.get_font().get_name() == canonical


def test_alias_resolves_to_canonical_without_fallback() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Arial", None)
    assert mapping is not None
    assert mapping.is_fallback() is False
    assert mapping.get_font().get_name() == "Helvetica"


def test_repeated_lookups_return_same_wrapper_instance() -> None:
    mapper = DefaultFontMapper()
    a = mapper.get_font_box_font("Helvetica", None)
    b = mapper.get_font_box_font("Helvetica", None)
    assert a is not None and b is not None
    # Cache hit on canonical name — same wrapper instance.
    assert a.get_font() is b.get_font()


# ---------------------------------------------------------------------------
# DefaultFontMapper — descriptor-flag fallback
# ---------------------------------------------------------------------------


def _descriptor_with_flags(flags: int) -> PDFontDescriptor:
    desc = PDFontDescriptor()
    desc.set_flags(flags)
    return desc


def test_unknown_name_no_descriptor_falls_back_to_helvetica() -> None:
    mapping = DefaultFontMapper().get_font_box_font("Unknown-Font-Name", None)
    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font().get_name() == "Helvetica"


def test_unknown_name_italic_descriptor_falls_back_to_helvetica_oblique() -> None:
    desc = _descriptor_with_flags(FLAG_ITALIC)
    mapping = DefaultFontMapper().get_font_box_font("Some-Italic-Font", desc)
    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font().get_name() == "Helvetica-Oblique"


def test_unknown_name_fixed_pitch_descriptor_falls_back_to_courier() -> None:
    desc = _descriptor_with_flags(FLAG_FIXED_PITCH)
    mapping = DefaultFontMapper().get_font_box_font("Some-Mono-Font", desc)
    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font().get_name() == "Courier"


def test_unknown_name_fixed_italic_descriptor_falls_back_to_courier_oblique() -> None:
    desc = _descriptor_with_flags(FLAG_FIXED_PITCH | FLAG_ITALIC)
    mapping = DefaultFontMapper().get_font_box_font("Some-MonoItalic", desc)
    assert mapping is not None
    assert mapping.get_font().get_name() == "Courier-Oblique"


def test_unknown_name_serif_descriptor_falls_back_to_times_roman() -> None:
    desc = _descriptor_with_flags(FLAG_SERIF)
    mapping = DefaultFontMapper().get_font_box_font("Some-Serif-Font", desc)
    assert mapping is not None
    assert mapping.get_font().get_name() == "Times-Roman"


def test_unknown_name_serif_italic_descriptor_falls_back_to_times_italic() -> None:
    desc = _descriptor_with_flags(FLAG_SERIF | FLAG_ITALIC)
    mapping = DefaultFontMapper().get_font_box_font("Some-SerifItalic", desc)
    assert mapping is not None
    assert mapping.get_font().get_name() == "Times-Italic"


def test_default_mapper_returns_none_for_truetype_lookup() -> None:
    """Default mapper has no on-disk font scanner — TT lookup returns None."""
    assert DefaultFontMapper().get_true_type_font("Helvetica", None) is None


def test_default_mapper_returns_none_for_opentype_lookup() -> None:
    """Default mapper has no on-disk font scanner — OT lookup returns None."""
    assert DefaultFontMapper().get_open_type_font("Helvetica", None) is None


# ---------------------------------------------------------------------------
# FontMapper interface — abstract methods
# ---------------------------------------------------------------------------


def test_font_mapper_is_abstract() -> None:
    with pytest.raises(TypeError):
        FontMapper()  # type: ignore[abstract]


def test_subclass_must_implement_all_three_methods() -> None:
    class _Half(FontMapper):
        def get_true_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

    with pytest.raises(TypeError):
        _Half()  # type: ignore[abstract]


def test_camelcase_aliases_dispatch_to_snake_case() -> None:
    mapper = DefaultFontMapper()
    snake = mapper.get_font_box_font("Helvetica", None)
    camel = mapper.getFontBoxFont("Helvetica", None)
    assert snake is not None and camel is not None
    # Both reach the same cached wrapper.
    assert snake.get_font() is camel.get_font()
