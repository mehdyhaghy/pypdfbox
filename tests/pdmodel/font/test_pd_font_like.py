"""Hand-written tests for the :class:`PDFontLike` protocol.

Covers protocol structure, runtime ``isinstance`` behaviour, and
sanity checks against pypdfbox font classes that implement (most of)
the protocol surface.
"""

from __future__ import annotations

from typing import get_type_hints

import pytest

from pypdfbox.pdmodel.font import PDFontLike
from pypdfbox.pdmodel.font.pd_font_like import PDFontLike as PDFontLikeDirect


class _MinimalFontLike:
    """Bare-bones implementation that exercises every protocol method."""

    def __init__(self, *, embedded: bool = False, damaged: bool = False) -> None:
        self._embedded = embedded
        self._damaged = damaged

    def get_name(self) -> str | None:
        return "TestFont"

    def get_font_descriptor(self):
        return None

    def get_font_matrix(self):
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def get_bounding_box(self):
        return (0.0, 0.0, 1000.0, 1000.0)

    def get_position_vector(self, code: int):
        return (0.0, 0.0)

    def get_height(self, code: int) -> float:
        return 0.0

    def get_width(self, code: int) -> float:
        return 500.0

    def has_explicit_width(self, code: int) -> bool:
        return False

    def get_width_from_font(self, code: int) -> float:
        return 500.0

    def is_embedded(self) -> bool:
        return self._embedded

    def is_damaged(self) -> bool:
        return self._damaged

    def get_average_font_width(self) -> float:
        return 500.0


class _MissingMethods:
    """Object that satisfies *some* but not all of the protocol."""

    def get_name(self) -> str:
        return "Partial"

    # No other PDFontLike methods.


def test_protocol_export_via_package() -> None:
    """``PDFontLike`` is importable from both the package and the module."""
    assert PDFontLike is PDFontLikeDirect


def test_protocol_is_runtime_checkable() -> None:
    """``isinstance`` accepts a structurally complete duck type."""
    assert isinstance(_MinimalFontLike(), PDFontLike)


def test_protocol_rejects_incomplete_type() -> None:
    """``isinstance`` rejects an object missing protocol members."""
    assert not isinstance(_MissingMethods(), PDFontLike)


def test_protocol_rejects_unrelated_type() -> None:
    assert not isinstance(object(), PDFontLike)
    assert not isinstance("not a font", PDFontLike)
    assert not isinstance(42, PDFontLike)


def test_protocol_methods_exposed() -> None:
    """All upstream PDFontLike methods are present on the protocol."""
    expected = {
        "get_name",
        "get_font_descriptor",
        "get_font_matrix",
        "get_bounding_box",
        "get_position_vector",
        "get_height",
        "get_width",
        "has_explicit_width",
        "get_width_from_font",
        "is_embedded",
        "is_damaged",
        "get_average_font_width",
    }
    members = set(dir(PDFontLike))
    missing = expected - members
    assert not missing, f"Protocol is missing methods: {missing}"


def test_protocol_no_extra_methods_beyond_upstream() -> None:
    """Protocol has no business-logic additions beyond upstream PDFontLike.

    Public Protocol members should be exactly the 12 methods enumerated
    in the upstream Java interface — no helpers, no extras.
    """
    # Public attributes that aren't dunders or runtime-checkable plumbing.
    public = {m for m in dir(PDFontLike) if not m.startswith("_")}
    expected = {
        "get_name",
        "get_font_descriptor",
        "get_font_matrix",
        "get_bounding_box",
        "get_position_vector",
        "get_height",
        "get_width",
        "has_explicit_width",
        "get_width_from_font",
        "is_embedded",
        "is_damaged",
        "get_average_font_width",
    }
    assert public == expected


def test_protocol_methods_are_callable() -> None:
    """A concrete impl can be invoked through the protocol contract."""
    font: PDFontLike = _MinimalFontLike(embedded=True)
    assert isinstance(font, PDFontLike)

    assert font.get_name() == "TestFont"
    assert font.get_font_descriptor() is None
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.get_bounding_box() == (0.0, 0.0, 1000.0, 1000.0)
    assert font.get_position_vector(65) == (0.0, 0.0)
    assert font.get_height(65) == 0.0
    assert font.get_width(65) == 500.0
    assert font.has_explicit_width(65) is False
    assert font.get_width_from_font(65) == 500.0
    assert font.is_embedded() is True
    assert font.is_damaged() is False
    assert font.get_average_font_width() == 500.0


def test_protocol_runtime_checkable_does_not_check_signatures() -> None:
    """``runtime_checkable`` only verifies attribute presence (Python
    spec), not call signatures. Document the behaviour so that future
    refactors don't accidentally tighten it.
    """

    class _WrongSig:
        # Wrong return types, but presence is what counts.
        def get_name(self):  # noqa: D401 - test stub
            return 1
        def get_font_descriptor(self): return 0  # noqa: E704
        def get_font_matrix(self): return None  # noqa: E704
        def get_bounding_box(self): return None  # noqa: E704
        def get_position_vector(self, code): return None  # noqa: E704
        def get_height(self, code): return ""  # noqa: E704
        def get_width(self, code): return ""  # noqa: E704
        def has_explicit_width(self, code): return ""  # noqa: E704
        def get_width_from_font(self, code): return ""  # noqa: E704
        def is_embedded(self): return ""  # noqa: E704
        def is_damaged(self): return ""  # noqa: E704
        def get_average_font_width(self): return ""  # noqa: E704

    assert isinstance(_WrongSig(), PDFontLike)


def test_protocol_module_docstring_references_upstream() -> None:
    """Sanity check that the upstream Java path is documented inline."""
    import pypdfbox.pdmodel.font.pd_font_like as mod

    assert "PDFontLike" in (mod.__doc__ or "")
    assert "PDFBox" in (mod.__doc__ or "")


def test_protocol_is_protocol_class() -> None:
    """The protocol's metaclass plumbing is intact (uses
    ``typing.Protocol`` machinery)."""
    # PEP 544 marker attribute.
    assert getattr(PDFontLike, "_is_protocol", False) is True
    assert getattr(PDFontLike, "_is_runtime_protocol", False) is True


def test_protocol_cannot_be_instantiated() -> None:
    """``PDFontLike()`` should raise — protocols are not concrete."""
    with pytest.raises(TypeError):
        PDFontLike()  # type: ignore[abstract]


def test_protocol_inheritance_disabled_for_runtime_check_only() -> None:
    """A ``Protocol`` subclass with extra methods can still be
    ``isinstance``-checked against the parent."""

    class _ExtendedFontLike(_MinimalFontLike):
        def extra(self) -> None:
            pass

    assert isinstance(_ExtendedFontLike(), PDFontLike)


def test_protocol_type_hints_are_resolvable() -> None:
    """``typing.get_type_hints`` resolves on every protocol method —
    catches stale forward refs / typos in annotations.
    """
    for method_name in (
        "get_name",
        "get_font_descriptor",
        "get_font_matrix",
        "get_bounding_box",
        "get_position_vector",
        "get_height",
        "get_width",
        "has_explicit_width",
        "get_width_from_font",
        "is_embedded",
        "is_damaged",
        "get_average_font_width",
    ):
        method = getattr(PDFontLike, method_name)
        hints = get_type_hints(method)
        assert isinstance(hints, dict)


# ---- pypdfbox-internal classes implement (most of) the protocol --------


def test_pd_type3_char_proc_has_glyph_bbox_and_width() -> None:
    """:class:`PDType3CharProc` is the canonical second implementor of
    upstream ``PDFontLike``. Pypdfbox doesn't yet wire its bbox / width
    accessors to the protocol-style names (``get_bounding_box`` /
    ``get_width_from_font``); the underlying d0/d1 surface lives on
    ``get_glyph_bbox`` / ``get_width``. Check those exist so future
    rewiring has a clear anchor.
    """
    from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc

    for method_name in ("get_glyph_bbox", "get_width"):
        assert hasattr(PDType3CharProc, method_name), (
            f"PDType3CharProc is expected to expose {method_name!r}"
        )


def test_pd_font_exposes_core_protocol_surface() -> None:
    """:class:`PDFont` implements the bulk of the PDFontLike contract."""
    from pypdfbox.pdmodel.font.pd_font import PDFont

    for method_name in (
        "get_name",
        "get_font_descriptor",
        "get_font_matrix",
        "is_embedded",
        "is_damaged",
        "get_average_font_width",
    ):
        assert hasattr(PDFont, method_name), (
            f"PDFont must expose {method_name!r} for PDFontLike parity"
        )
