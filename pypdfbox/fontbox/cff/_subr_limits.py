"""PDFBOX-6308 subroutine limits for the fontTools charstring interpreters.

pypdfbox builds glyph outlines and advance widths by running fontTools'
charstring interpreters (``T2OutlineExtractor``, ``T2WidthExtractor``,
``T1OutlineExtractor``) instead of upstream's ``Type1CharStringParser`` /
``Type2CharStringParser``. Upstream bounds subroutine use in those parsers
(PDFBOX-6308); fontTools does not, so a self-recursive or very deep
``callsubr`` chain would only stop at Python's ``RecursionError``.

The extractor subclasses here count subroutine calls with the same rule as
the ported parsers and raise :class:`SubrLimitError` (an ``OSError``, as
upstream raises ``IOException``) with the upstream message:

* Type 2 (CFF): the glyph's *total* number of ``callsubr`` / ``callgsubr``
  calls may not exceed :data:`TYPE2_MAX_SUBR_NESTING` (upstream increments
  ``GlyphData.subrNesting`` on every call and never decrements it).
* Type 1: ``callsubr`` may not nest deeper than
  :data:`TYPE1_MAX_SUBR_NESTING` levels.

Every fontTools-backed draw / width site goes through the helpers below, so
the limit is enforced in one place. The counters add one Python-level check
per subroutine call and nothing per glyph, so normal fonts are unaffected.
"""

from __future__ import annotations

from typing import Any

from fontTools.misc import psCharStrings  # type: ignore[import-untyped]

from .type1_char_string_parser import MAX_SUBR_NESTING as TYPE1_MAX_SUBR_NESTING
from .type2_char_string_parser import MAX_SUBR_NESTING as TYPE2_MAX_SUBR_NESTING


class SubrLimitError(OSError):
    """A glyph exceeded the PDFBOX-6308 subroutine limit.

    Subclasses ``OSError`` (upstream throws a plain ``IOException``) so the
    pypdfbox wrappers that turn other fontTools failures into an empty
    glyph can let this one propagate the way upstream does."""


def type2_limit_message(font_name: str) -> str:
    """Upstream ``Type2CharStringParser.processSubr`` message."""
    return (
        f"Subroutines are nested more than {TYPE2_MAX_SUBR_NESTING} "
        f"levels deep in font {font_name}"
    )


def type1_limit_message(glyph_name: str, font_name: str) -> str:
    """Upstream ``Type1CharStringParser.processCallSubr`` message."""
    return (
        f"Subroutines are nested more than {TYPE1_MAX_SUBR_NESTING} "
        f"levels deep in glyph '{glyph_name}' of font {font_name}"
    )


class _Type2SubrCounter:
    """Mixin for fontTools Type 2 decompilers: bound the glyph's total
    number of subroutine calls (upstream ``GlyphData.subrNesting``)."""

    font_name: str = ""
    subr_calls: int = 0

    def reset(self) -> None:
        super().reset()  # type: ignore[misc]
        self.subr_calls = 0

    def _count_subr_call(self) -> None:
        if self.subr_calls >= TYPE2_MAX_SUBR_NESTING:
            raise SubrLimitError(type2_limit_message(self.font_name))
        self.subr_calls += 1

    def op_callsubr(self, index: int) -> None:
        # Upstream counts a call once the index is non-empty, before the
        # subr number is range-checked.
        if self.localSubrs:  # type: ignore[attr-defined]
            self._count_subr_call()
        super().op_callsubr(index)  # type: ignore[misc]

    def op_callgsubr(self, index: int) -> None:
        if self.globalSubrs:  # type: ignore[attr-defined]
            self._count_subr_call()
        super().op_callgsubr(index)  # type: ignore[misc]


class LimitedT2WidthExtractor(_Type2SubrCounter, psCharStrings.T2WidthExtractor):  # type: ignore[misc]
    """``T2WidthExtractor`` with the Type 2 subroutine limit."""


class LimitedT2OutlineExtractor(_Type2SubrCounter, psCharStrings.T2OutlineExtractor):  # type: ignore[misc]
    """``T2OutlineExtractor`` with the Type 2 subroutine limit."""


class LimitedT1OutlineExtractor(psCharStrings.T1OutlineExtractor):  # type: ignore[misc]
    """``T1OutlineExtractor`` with the Type 1 subroutine nesting limit."""

    font_name: str = ""
    glyph_name: str = ""

    def op_callsubr(self, index: int) -> None:
        # ``callingStack`` holds the glyph charstring plus every subr being
        # executed, so its length minus one is upstream's ``subrNesting``.
        # Upstream only checks a call whose subr number is in range.
        stack = self.operandStack
        subrs = self.subrs
        if stack and subrs is not None:
            operand = stack[-1]
            if (
                isinstance(operand, int)
                and 0 <= operand < len(subrs)
                and len(self.callingStack) - 1 >= TYPE1_MAX_SUBR_NESTING
            ):
                raise SubrLimitError(
                    type1_limit_message(self.glyph_name, self.font_name)
                )
        super().op_callsubr(index)


def type2_width(
    char_string: Any,
    local_subrs: Any,
    global_subrs: Any,
    nominal_width_x: Any,
    default_width_x: Any,
    font_name: str = "",
) -> float:
    """Run the limited Type 2 width extractor over ``char_string``."""
    extractor = LimitedT2WidthExtractor(
        local_subrs, global_subrs, nominal_width_x, default_width_x
    )
    extractor.font_name = font_name or ""
    extractor.execute(char_string)
    return float(extractor.width)


def draw_type2(
    char_string: Any, pen: Any, font_name: str = "", blender: Any = None
) -> None:
    """Limited equivalent of fontTools ``T2CharString.draw``. Objects that
    are not fontTools Type 2 charstrings (duck-typed drawables) are drawn
    with their own ``draw``."""
    if not isinstance(char_string, psCharStrings.T2CharString) or isinstance(
        char_string, psCharStrings.T1CharString
    ):
        char_string.draw(pen)
        return
    private = char_string.private
    extractor = LimitedT2OutlineExtractor(
        pen,
        getattr(private, "Subrs", []),
        char_string.globalSubrs,
        private.nominalWidthX,
        private.defaultWidthX,
        private,
        blender,
    )
    extractor.font_name = font_name or ""
    extractor.execute(char_string)
    char_string.width = extractor.width


def draw_type1(
    char_string: Any,
    pen: Any,
    glyph_name: str = "",
    font_name: str = "",
    extractor_class: type | None = None,
) -> float:
    """Limited equivalent of fontTools ``T1CharString.draw``. Returns the
    advance width and stores it on the charstring like fontTools does.
    Objects that are not fontTools Type 1 charstrings (duck-typed
    drawables) are drawn with their own ``draw``."""
    if not isinstance(char_string, psCharStrings.T1CharString):
        char_string.draw(pen)
        return float(getattr(char_string, "width", 0.0) or 0.0)
    cls = extractor_class or LimitedT1OutlineExtractor
    extractor = cls(pen, getattr(char_string, "subrs", None))
    extractor.font_name = font_name or ""
    extractor.glyph_name = glyph_name or ""
    extractor.execute(char_string)
    width = extractor.width
    char_string.width = width
    return float(width or 0.0)


class _LimitedCFFGlyph:
    __slots__ = ("_glyph_set", "_name")

    def __init__(self, glyph_set: LimitedGlyphSet, name: str) -> None:
        self._glyph_set = glyph_set
        self._name = name

    def __getattr__(self, attr: str) -> Any:
        # width / lsb / height / tsb and friends come from the real glyph.
        return getattr(self._glyph_set._inner[self._name], attr)

    def draw(self, pen: Any) -> None:
        inner = self._glyph_set._inner
        draw_type2(
            inner.charStrings[self._name],
            pen,
            self._glyph_set._font_name,
            getattr(inner, "blender", None),
        )

    def drawPoints(self, pen: Any) -> None:  # noqa: N802 (fontTools glyph protocol)
        from fontTools.pens.pointPen import (  # type: ignore[import-untyped]
            SegmentToPointPen,
        )

        self.draw(SegmentToPointPen(pen))


class LimitedGlyphSet:
    """Proxy over a fontTools CFF/CFF2 glyph set whose glyphs draw through
    :func:`draw_type2`. Component lookups made by a pen that was given this
    proxy as its glyph set are limited too."""

    def __init__(self, inner: Any, font_name: str = "") -> None:
        self._inner = inner
        self._font_name = font_name or ""

    def __getitem__(self, name: str) -> _LimitedCFFGlyph:
        # Raise KeyError for an unknown glyph, like the real glyph set.
        if name not in self._inner:
            raise KeyError(name)
        return _LimitedCFFGlyph(self, name)

    def __contains__(self, name: object) -> bool:
        return name in self._inner

    def __iter__(self) -> Any:
        return iter(self._inner)

    def __len__(self) -> int:
        return len(self._inner)

    def get(self, name: str, default: Any = None) -> Any:
        if name not in self._inner:
            return default
        return self[name]

    def keys(self) -> Any:
        return self._inner.keys()

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._inner, attr)


def limited_glyph_set(glyph_set: Any, font_name: str = "") -> Any:
    """Wrap a fontTools glyph set so CFF-flavored glyphs honor the Type 2
    subroutine limit. ``glyf`` glyph sets (no ``charStrings``) and ``None``
    are returned unchanged."""
    if glyph_set is None or isinstance(glyph_set, LimitedGlyphSet):
        return glyph_set
    if getattr(glyph_set, "charStrings", None) is None:
        return glyph_set
    return LimitedGlyphSet(glyph_set, font_name)


__all__ = [
    "TYPE1_MAX_SUBR_NESTING",
    "TYPE2_MAX_SUBR_NESTING",
    "LimitedGlyphSet",
    "LimitedT1OutlineExtractor",
    "LimitedT2OutlineExtractor",
    "LimitedT2WidthExtractor",
    "SubrLimitError",
    "draw_type1",
    "draw_type2",
    "limited_glyph_set",
    "type1_limit_message",
    "type2_limit_message",
]
