from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
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
    - ``dir``        — text direction in degrees (0/90/180/270), default 0.
    - ``text_matrix``— optional 6-element text matrix snapshot.

    Glyph metrics, character codes, and full text-state matrices are
    intentionally simplified (see ``CHANGES.md`` for the deferred surface).
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
    dir: float = 0.0
    text_matrix: list[float] | None = None

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

    # --- Directional / rotation-aware accessors ------------------------

    def get_x_directional_adj(self) -> float:
        """Rotation-adjusted X. Lite alias for :meth:`get_x`."""
        return self.x

    def get_y_directional_adj(self) -> float:
        """Rotation-adjusted Y. Lite alias for :meth:`get_y`."""
        return self.y

    def get_x_scale(self) -> float:
        """Horizontal scale derived from the text matrix; defaults to 1.0."""
        if self.text_matrix is not None and len(self.text_matrix) >= 1:
            return float(self.text_matrix[0])
        return 1.0

    def get_y_scale(self) -> float:
        """Vertical scale derived from the text matrix; defaults to 1.0."""
        if self.text_matrix is not None and len(self.text_matrix) >= 4:
            return float(self.text_matrix[3])
        return 1.0

    def get_height_dir(self) -> float:
        """Directional height. Lite approximation returns ``font_size``."""
        return self.font_size

    def get_dir(self) -> float:
        """Text direction in degrees (0/90/180/270)."""
        return self.dir

    def get_individual_widths(self) -> list[float]:
        """Per-character widths.

        Upstream tracks one displacement per glyph; in this lite port we
        evenly distribute :attr:`width` across the decoded characters.
        Returns an empty list when there is no text.
        """
        n = len(self.text)
        if n == 0:
            return []
        per_char = self.width / n
        return [per_char] * n

    def get_visible_text(self) -> str:
        """Visible decoded text. Lite alias for :meth:`get_unicode`."""
        return self.get_unicode()

    # --- Diacritic handling -------------------------------------------

    def contains_diacritic(self) -> bool:
        """True when the text starts with a Unicode combining mark."""
        if not self.text:
            return False
        return unicodedata.combining(self.text[0]) != 0

    def is_diacritic(self) -> bool:
        """True when the text consists exclusively of combining marks."""
        if not self.text:
            return False
        return all(unicodedata.combining(c) != 0 for c in self.text)

    def merge_diacritic(self, diacritic: TextPosition) -> None:
        """Merge a diacritic ``TextPosition`` into ``self``.

        Mirrors upstream behavior of attaching a combining mark to the
        preceding base glyph. Mutates ``self`` by appending the
        diacritic's decoded text and extending the run width.
        """
        self.text = self.text + diacritic.text
        self.width = self.width + diacritic.width

    # --- Matrix / extents ---------------------------------------------

    def get_text_matrix(self) -> list[float] | None:
        """Return the stored 6-element text matrix, if any."""
        return self.text_matrix

    def get_end_x(self) -> float:
        """X coordinate of the run's right edge."""
        return self.x + self.width

    def get_end_y(self) -> float:
        """Y coordinate of the run's top edge (cap-height approximation)."""
        return self.y + self.font_size * 0.7


__all__ = ["TextPosition"]
