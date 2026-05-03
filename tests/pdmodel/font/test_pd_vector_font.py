"""Hand-written tests for the :class:`PDVectorFont` protocol.

Covers protocol structure, runtime ``isinstance`` behaviour, and
sanity checks against pypdfbox vector font classes.
"""

from __future__ import annotations

from typing import get_type_hints

import pytest

from pypdfbox.pdmodel.font import PDVectorFont
from pypdfbox.pdmodel.font.pd_vector_font import PDVectorFont as PDVectorFontDirect


class _MinimalVectorFont:
    """Bare-bones implementation of every PDVectorFont method."""

    def __init__(self, *, glyphs: set[int] | None = None) -> None:
        self._glyphs = glyphs if glyphs is not None else {65, 66, 67}

    def get_path(self, code: int):
        return [("moveto", 0.0, 0.0), ("lineto", 100.0, 0.0)]

    def get_normalized_path(self, code: int):
        return [("moveto", 0.0, 0.0), ("lineto", 1000.0, 0.0)]

    def has_glyph(self, code: int) -> bool:
        return code in self._glyphs


class _MissingHasGlyph:
    def get_path(self, code: int):
        return None

    def get_normalized_path(self, code: int):
        return None

    # Deliberately no has_glyph.


def test_protocol_export_via_package() -> None:
    """``PDVectorFont`` is importable from both the package and the module."""
    assert PDVectorFont is PDVectorFontDirect


def test_protocol_is_runtime_checkable() -> None:
    assert isinstance(_MinimalVectorFont(), PDVectorFont)


def test_protocol_rejects_incomplete_type() -> None:
    assert not isinstance(_MissingHasGlyph(), PDVectorFont)


def test_protocol_rejects_unrelated_type() -> None:
    assert not isinstance(object(), PDVectorFont)
    assert not isinstance("not a font", PDVectorFont)
    assert not isinstance(42, PDVectorFont)
    assert not isinstance(None, PDVectorFont)


def test_protocol_methods_exposed() -> None:
    """All upstream PDVectorFont methods are present on the protocol."""
    expected = {"get_path", "get_normalized_path", "has_glyph"}
    members = set(dir(PDVectorFont))
    missing = expected - members
    assert not missing, f"Protocol is missing methods: {missing}"


def test_protocol_no_extras_beyond_upstream() -> None:
    public = {m for m in dir(PDVectorFont) if not m.startswith("_")}
    assert public == {"get_path", "get_normalized_path", "has_glyph"}


def test_protocol_methods_are_callable() -> None:
    font: PDVectorFont = _MinimalVectorFont(glyphs={65, 66})

    assert font.get_path(65) == [("moveto", 0.0, 0.0), ("lineto", 100.0, 0.0)]
    assert font.get_normalized_path(65) == [
        ("moveto", 0.0, 0.0),
        ("lineto", 1000.0, 0.0),
    ]
    assert font.has_glyph(65) is True
    assert font.has_glyph(66) is True
    assert font.has_glyph(67) is False


def test_protocol_is_protocol_class() -> None:
    assert getattr(PDVectorFont, "_is_protocol", False) is True
    assert getattr(PDVectorFont, "_is_runtime_protocol", False) is True


def test_protocol_cannot_be_instantiated() -> None:
    """Direct instantiation of a Protocol raises ``TypeError``."""
    with pytest.raises(TypeError):
        PDVectorFont()  # type: ignore[abstract]


def test_protocol_module_docstring_references_upstream() -> None:
    import pypdfbox.pdmodel.font.pd_vector_font as mod

    assert "PDVectorFont" in (mod.__doc__ or "")
    assert "PDFBox" in (mod.__doc__ or "")


def test_protocol_type_hints_are_resolvable() -> None:
    for method_name in ("get_path", "get_normalized_path", "has_glyph"):
        method = getattr(PDVectorFont, method_name)
        hints = get_type_hints(method)
        assert isinstance(hints, dict)


def test_protocol_subclass_with_extras_still_qualifies() -> None:
    class _ExtendedVectorFont(_MinimalVectorFont):
        def extra(self) -> None:
            pass

    assert isinstance(_ExtendedVectorFont(), PDVectorFont)


def test_protocol_with_all_three_methods_qualifies_even_if_returns_wrong() -> None:
    """``runtime_checkable`` checks attribute presence only — it does
    not validate return shapes. Document this behaviour to avoid
    accidental tightening of the contract."""

    class _NominalVectorFont:
        def get_path(self, code): return "not a path"  # noqa: E704
        def get_normalized_path(self, code): return None  # noqa: E704
        def has_glyph(self, code): return "yes"  # noqa: E704 (truthy non-bool)

    assert isinstance(_NominalVectorFont(), PDVectorFont)


# ---- pypdfbox-internal classes implement (most of) the protocol --------


def test_pd_type1_font_class_exposes_glyph_surface() -> None:
    """:class:`PDType1Font` exposes path / has_glyph methods. Its
    instance-method names use the ``_for_code`` suffix to avoid
    collision with the name-keyed variants — but the protocol-level
    ``get_path(code)`` API still has a counterpart implementation."""
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    assert hasattr(PDType1Font, "get_path_for_code")
    assert hasattr(PDType1Font, "has_glyph_for_code")
    assert hasattr(PDType1Font, "get_normalized_path_for_code")


def test_pd_type0_font_class_exposes_has_glyph() -> None:
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    assert hasattr(PDType0Font, "has_glyph")
    assert hasattr(PDType0Font, "get_width")


def test_pd_cid_font_type2_exposes_has_glyph() -> None:
    """CID font subclasses also implement the protocol surface."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    assert hasattr(PDCIDFontType2, "has_glyph")
    assert hasattr(PDCIDFontType2, "get_normalized_path")


def test_pd_cid_font_type0_exposes_normalized_path() -> None:
    from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0

    assert hasattr(PDCIDFontType0, "get_normalized_path")


def test_protocol_distinct_from_pd_font_like() -> None:
    """``PDVectorFont`` and ``PDFontLike`` are separate types — upstream
    declares them as two distinct interfaces, and pypdfbox should keep
    them that way."""
    from pypdfbox.pdmodel.font import PDFontLike

    assert PDVectorFont is not PDFontLike
    # Ensure structural sets don't accidentally coincide.
    vector_methods = {m for m in dir(PDVectorFont) if not m.startswith("_")}
    fontlike_methods = {m for m in dir(PDFontLike) if not m.startswith("_")}
    assert vector_methods & fontlike_methods == set()
