"""A font mapping result returned by :class:`FontMapper`.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontMapping<T extends FontBoxFont>``
from PDFBox 3.0. Carries the resolved font plus a flag indicating whether
the result is a *fallback* — i.e. a substitute chosen by basic style
(bold / italic / monospace) rather than by name match.

Upstream lives at:
    ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontMapping.java``

That package mismatch is intentional on the upstream side: ``FontMapper``
/ ``FontMapping`` / ``FontMappers`` reference fontbox types and so are
themselves shipped from the ``pdfbox`` Java module. In pypdfbox we keep
them under :mod:`pypdfbox.fontbox` because there is no inverse-dependency
problem in Python — ``pypdfbox.fontbox`` is allowed to import
:class:`pypdfbox.pdmodel.font.PDFontDescriptor`-like protocols as
TYPE_CHECKING-only annotations.
"""

from __future__ import annotations

from .font_box_font import FontBoxFont


class FontMapping[T: FontBoxFont]:
    """A resolved (font, is_fallback) pair returned by a FontMapper.

    Upstream Java is a final-fields container with two getters; this
    class mirrors the shape (constructor takes the font plus the
    fallback flag, fields exposed via ``get_font`` / ``is_fallback``).
    The bound :data:`T` is :class:`FontBoxFont` so callers can have a
    typed ``FontMapping[TrueTypeFont]`` or ``FontMapping[FontBoxFont]``.
    """

    __slots__ = ("_font", "_is_fallback")

    def __init__(self, font: T, is_fallback: bool) -> None:
        # Upstream comment on ``getFont`` says "This is never null", but
        # the constructor itself doesn't enforce that. We follow the
        # upstream contract — concrete mappers are expected to return
        # ``None`` from ``getXxxFont`` rather than wrap ``None`` in a
        # FontMapping.
        self._font: T = font
        self._is_fallback: bool = bool(is_fallback)

    # ---------- accessors ----------

    def get_font(self) -> T:
        """Return the resolved FontBox font.

        Mirrors upstream ``T getFont()``. Per the upstream contract,
        this is never ``None``: a mapper that can't find anything
        returns ``None`` from its ``getXxxFont`` call rather than
        wrapping ``None`` in a ``FontMapping``.
        """
        return self._font

    def is_fallback(self) -> bool:
        """Return ``True`` if the mapping is a style-only fallback.

        Mirrors upstream ``boolean isFallback()``. Style-only fallbacks
        are picked by descriptor flags (bold / italic / monospace)
        rather than by PostScript name match — callers may want to log
        them or attempt re-embedding before final layout.
        """
        return self._is_fallback

    # ---------- repr ----------

    def __repr__(self) -> str:
        font_name: str | None
        try:
            # ``get_name`` on a real FontBoxFont can raise OSError when
            # the underlying stream is broken; fall back to the type
            # name in that case so ``repr`` stays useful in tracebacks.
            font_name = self._font.get_name() if self._font is not None else None
        except OSError:
            font_name = None
        if font_name is None:
            font_name = type(self._font).__name__
        return f"FontMapping(font={font_name!r}, is_fallback={self._is_fallback})"


__all__ = ["FontMapping"]
