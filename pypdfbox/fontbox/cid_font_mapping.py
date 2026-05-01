"""CID-aware font mapping result.

Mirrors ``org.apache.pdfbox.pdmodel.font.CIDFontMapping`` from PDFBox 3.0.

A :class:`CIDFontMapping` is a :class:`FontMapping` over an OpenType
font (CFF-flavoured) that *also* carries a TrueType fallback. Upstream
``FontMapperImpl.getCIDFont`` returns one of these when it has to
resolve a CID-keyed font: if the requested CID font is available it
sets the OpenType slot, otherwise it sets the TTF slot to a name-only
substitute.

Upstream Java is a ``final`` class; we keep parity by not subclassing
it inside pypdfbox (callers should construct one of the two valid
shapes — OTF-only or TTF-only — directly).
"""

from __future__ import annotations

from typing import Any

from .font_box_font import FontBoxFont
from .font_mapping import FontMapping


class CIDFontMapping(FontMapping[Any]):
    """A :class:`FontMapping` with an extra TrueType fallback slot.

    Two valid constructor shapes mirror upstream:

    - ``CIDFontMapping(otf_font, None, is_fallback=False)`` — CID font
      hit; :meth:`is_cid_font` returns ``True``.
    - ``CIDFontMapping(None, ttf_font, is_fallback=...)`` — CID font
      miss, name-substitute via TrueType; :meth:`is_cid_font` returns
      ``False``.

    Upstream ``getFont()`` is typed ``OpenTypeFont`` but the field is
    declared as ``T extends FontBoxFont``. We keep the looser
    ``FontBoxFont | None`` typing because pypdfbox's
    :class:`FontMapping` already permits ``None`` in repr-construction
    paths and the rendering layer duck-types both shapes.
    """

    __slots__ = ("_ttf",)

    def __init__(
        self,
        font: Any | None,
        font_box_font: FontBoxFont | None,
        is_fallback: bool,
    ) -> None:
        super().__init__(font, is_fallback)  # type: ignore[arg-type]
        self._ttf: FontBoxFont | None = font_box_font

    # ---------- accessors ----------

    def get_true_type_font(self) -> FontBoxFont | None:
        """Return the TrueType fallback when :meth:`is_cid_font` is False.

        Mirrors upstream ``FontBoxFont getTrueTypeFont()``. Returns
        ``None`` when the OTF / CID slot was filled instead.
        """
        return self._ttf

    def is_cid_font(self) -> bool:
        """Return ``True`` when the OpenType / CID slot is set.

        Mirrors upstream ``boolean isCIDFont()`` — implemented exactly
        the same way (``getFont() != null``).
        """
        return self.get_font() is not None

    # ---------- repr ----------

    def __repr__(self) -> str:
        otf_name: str | None = None
        otf = self.get_font()
        if otf is not None:
            try:
                otf_name = otf.get_name()
            except (OSError, AttributeError):
                otf_name = type(otf).__name__
        ttf_name: str | None = None
        if self._ttf is not None:
            try:
                ttf_name = self._ttf.get_name()
            except (OSError, AttributeError):
                ttf_name = type(self._ttf).__name__
        return (
            f"CIDFontMapping(font={otf_name!r}, ttf={ttf_name!r}, "
            f"is_fallback={self.is_fallback()})"
        )


__all__ = ["CIDFontMapping"]
