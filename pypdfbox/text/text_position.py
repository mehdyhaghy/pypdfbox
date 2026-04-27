from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDFont


@dataclass
class TextPosition:
    """A single decoded text run with its origin in user space.

    Mirrors the conceptual shape of ``org.apache.pdfbox.text.TextPosition``
    in lite form. Upstream's ``TextPosition`` carries glyph-level
    displacement vectors, font metrics, transformation matrices, and
    Unicode mapping state; this lite port keeps just enough to support
    single-column text extraction:

    - ``text``       — the decoded characters as Python ``str``
    - ``x`` / ``y``  — text origin in user space (post-Tm, pre-Trm scaling)
    - ``font_size``  — current font size as set by ``Tf``
    - ``font_name``  — resource name from ``Tf`` (e.g. ``"F0"``), or
                       ``None`` if no font was active when the text was
                       emitted. This remains the resource alias for
                       compatibility with earlier pypdfbox builds.
    - ``font``       — resolved ``PDFont`` wrapper, when page resources
                       and the current font APIs can provide one.
    - ``resolved_font_name`` — the font dictionary's ``/BaseFont`` name
                       (typically the PostScript name), when available.
    - ``width`` / ``width_of_space`` — user-space width metadata used as
                       the foundation for later glyph-aware extraction.

    Glyph metrics, character codes, and text-state matrices are
    intentionally omitted (see ``CHANGES.md`` for the deferred surface).
    """

    text: str
    x: float
    y: float
    font_size: float
    font_name: str | None = None
    font: PDFont | None = None
    resolved_font_name: str | None = None
    width: float = 0.0
    width_of_space: float = 0.0
    char_spacing: float = 0.0
    word_spacing: float = 0.0

    def get_unicode(self) -> str:
        """Upstream calls the decoded characters ``unicode``; we expose the
        same accessor name on top of the dataclass for API familiarity."""
        return self.text

    def get_x(self) -> float:
        return self.x

    def get_y(self) -> float:
        return self.y

    def get_font_size(self) -> float:
        return self.font_size

    def get_font_name(self) -> str | None:
        return self.font_name

    def get_font(self) -> PDFont | None:
        return self.font

    def get_resolved_font_name(self) -> str | None:
        return self.resolved_font_name

    def get_width(self) -> float:
        return self.width

    def get_width_of_space(self) -> float:
        return self.width_of_space


__all__ = ["TextPosition"]
