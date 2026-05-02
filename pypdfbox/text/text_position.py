from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

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
    - ``rotation``   — page rotation in degrees (0/90/180/270), default 0.
    - ``page_width`` / ``page_height`` — page extents in user space; used
                       by upstream's directional accessors when text is
                       rendered on a rotated page.
    - ``text_matrix``— optional 6-element text matrix snapshot.
    - ``font_size_in_pt`` — explicit font size in points, when known
                       (matches upstream ``getFontSizeInPt()``); falls
                       back to :attr:`font_size` when unset.

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
    rotation: float = 0.0
    page_width: float = 0.0
    page_height: float = 0.0
    text_matrix: list[float] | None = None
    font_size_in_pt: float | None = None

    # ------------------------------------------------------------------
    # Decoded text
    # ------------------------------------------------------------------

    def get_unicode(self) -> str:
        """Upstream calls the decoded characters ``unicode``; we expose the
        same accessor name on top of the dataclass for API familiarity."""
        return self.text

    def set_unicode(self, value: str) -> None:
        """Replace the decoded characters.

        Mirrors upstream's package-private ``setUnicode``: used when the
        caller has post-processed the decoded text (e.g. NFKC
        normalisation, glyph-list remapping) and wants the corrected
        string visible through subsequent :meth:`get_unicode` calls.
        """
        self.text = value

    def get_character(self) -> str:
        """Upstream alias for the decoded characters.

        ``TextPosition.getCharacter()`` predates the rename to
        ``getUnicode()`` and is still part of the public surface.
        """
        return self.text

    def get_visible_text(self) -> str:
        """Visible decoded text. Lite alias for :meth:`get_unicode`."""
        return self.get_unicode()

    def get_character_codes(self) -> list[int]:
        """Internal PDF character codes for the glyphs in this run.

        Upstream returns the ``int[]`` captured at decode time. The lite
        port doesn't track raw character codes (decoding goes straight
        from byte stream to Unicode via ``/ToUnicode`` / ``/Differences``)
        so we approximate with the Unicode code points of the decoded
        text. Callers that depend on the *original* PDF code values
        should treat this as best-effort — see ``CHANGES.md``.
        """
        return [ord(ch) for ch in self.text]

    def get_visually_ordered_unicode(self) -> str:
        """Same as :meth:`get_unicode` but reversed when the run contains
        right-to-left text.

        Mirrors upstream's ``getVisuallyOrderedUnicode``: PDF Arabic and
        Hebrew runs are emitted in logical order (the order a typist
        enters them); some downstream consumers want them in visual order
        (the order they appear left-to-right on the rendered page). When
        any code point in the run has bidirectional class ``R`` (Hebrew /
        general RTL) or ``AL`` (Arabic letters) we return the string
        reversed; otherwise we return it unchanged. A single-codepoint
        string is returned as-is even if RTL — there's nothing to
        reorder.
        """
        text = self.text
        if len(text) <= 1:
            return text
        for ch in text:
            if unicodedata.bidirectional(ch) in ("R", "AL"):
                return text[::-1]
        return text

    # ------------------------------------------------------------------
    # Coordinates
    # ------------------------------------------------------------------

    def get_x(self) -> float:
        return self.x

    def get_y(self) -> float:
        return self.y

    def get_end_x(self) -> float:
        """X coordinate of the run's right edge."""
        return self.x + self.width

    def get_end_y(self) -> float:
        """Y coordinate of the run's top edge (cap-height approximation)."""
        return self.y + self.font_size * 0.7

    # ------------------------------------------------------------------
    # Font / scale
    # ------------------------------------------------------------------

    def get_font_size(self) -> float:
        return self.font_size

    def get_font_size_in_pt(self) -> float:
        """Font size in typographic points.

        Upstream's ``getFontSizeInPt()`` returns the rendered size after
        the current transformation matrix has been applied. In lite mode
        we don't track CTM, so we fall back to the explicit
        :attr:`font_size_in_pt` if set, otherwise to the unscaled
        :attr:`font_size`.
        """
        if self.font_size_in_pt is not None:
            return self.font_size_in_pt
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

    # ------------------------------------------------------------------
    # Direction / rotation
    # ------------------------------------------------------------------

    def get_dir(self) -> float:
        """Text direction in degrees (0/90/180/270)."""
        return self.dir

    def get_rotation(self) -> float:
        """Page rotation in degrees (0/90/180/270)."""
        return self.rotation

    def get_page_width(self) -> float:
        """Page width in user-space units."""
        return self.page_width

    def get_page_height(self) -> float:
        """Page height in user-space units."""
        return self.page_height

    def get_x_dir_adj(self) -> float:
        """Direction-adjusted X.

        Upstream rotates the run's origin into a non-rotated frame so
        that downstream sorting can treat all pages as if they were
        portrait. We apply the same rotation about the page rectangle
        when :attr:`dir` is non-zero, otherwise return :attr:`x`.
        """
        d = self.dir % 360.0
        if d == 0.0:
            return self.x
        if d == 90.0:
            return self.y
        if d == 180.0:
            return self.page_width - self.x
        if d == 270.0:
            return self.page_height - self.y
        # Generic fallback: rotate about page center.
        rad = math.radians(d)
        return self.x * math.cos(rad) + self.y * math.sin(rad)

    # Upstream PDFBox spells this ``getXDirAdj``; expose a snake_case
    # alias matching the upstream name for porting parity.
    def get_x_directional_adj(self) -> float:
        """Alias for :meth:`get_x_dir_adj`."""
        return self.get_x_dir_adj()

    def get_y_dir_adj(self) -> float:
        """Direction-adjusted Y.

        See :meth:`get_x_dir_adj`. Upstream returns a Y measured from the
        rotated frame's top edge.
        """
        d = self.dir % 360.0
        if d == 0.0:
            return self.y
        if d == 90.0:
            return self.page_width - self.x
        if d == 180.0:
            return self.page_height - self.y
        if d == 270.0:
            return self.x
        rad = math.radians(d)
        return -self.x * math.sin(rad) + self.y * math.cos(rad)

    def get_y_directional_adj(self) -> float:
        """Alias for :meth:`get_y_dir_adj`."""
        return self.get_y_dir_adj()

    def get_width_dir_adj(self) -> float:
        """Direction-adjusted run width."""
        return self.width

    def get_height(self) -> float:
        """Maximum height of all characters in this run.

        Upstream tracks ``maxHeight`` separately from the font size; in
        lite mode we use the font size as the height proxy (same value
        :meth:`get_height_dir` returns) so the two accessors agree. See
        ``CHANGES.md`` for the deferred per-glyph metrics.
        """
        return self.font_size

    def get_height_dir(self) -> float:
        """Directional height. Lite approximation returns ``font_size``."""
        return self.font_size

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def contains(self, other: TextPosition) -> bool:
        """Return True if ``self`` and ``other`` horizontally overlap.

        Mirrors upstream's overlap check used in
        ``suppressDuplicateOverlappingText`` — two runs overlap when one
        starts before the other ends along the X axis on the same line.
        """
        if other is None:
            return False
        # Different baselines never overlap in the lite model.
        if abs(self.y - other.y) > 0.5 * max(self.font_size, other.font_size, 1.0):
            return False
        a_start = self.x
        a_end = self.x + self.width
        b_start = other.x
        b_end = other.x + other.width
        return not (a_end <= b_start or b_end <= a_start)

    def completely_contains(self, other: TextPosition) -> bool:
        """Return True when ``other``'s bounding box fits entirely inside
        ``self``'s bounding box.

        Mirrors upstream's ``completelyContains``: a strict containment
        check used by glyph-collision detection (the laxer
        :meth:`contains` allows fractional X overlap). The bounding box
        is ``(x, y) -> (x + width, y + height)`` in user space, where
        ``height`` is :meth:`get_height_dir`. ``None`` is never
        contained.
        """
        if other is None:
            return False
        this_left = self.x
        this_right = self.x + self.width
        other_left = other.x
        other_right = other.x + other.width
        if this_left > other_left or other_right > this_right:
            return False
        this_top = self.y
        this_bottom = self.y + self.get_height_dir()
        other_top = other.y
        other_bottom = other.y + other.get_height_dir()
        if this_top > other_top or other_bottom > this_bottom:
            return False
        return True

    # ------------------------------------------------------------------
    # Per-character widths
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Diacritic handling
    # ------------------------------------------------------------------

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

    def merge_diacritic(
        self,
        diacritic: TextPosition,
        normalizer: Callable[[str], str] | None = None,
    ) -> None:
        """Merge a diacritic ``TextPosition`` into ``self``.

        Mirrors upstream behavior of attaching a combining mark to the
        preceding base glyph. Mutates ``self`` by appending the
        diacritic's decoded text and extending the run width.

        ``normalizer`` is invoked with the concatenated text and may
        return a normalized form (e.g. ``unicodedata.normalize("NFC",
        text)``). When ``None`` we leave the concatenation as-is to
        preserve the decomposed sequence — matching upstream's
        ``GlyphList`` parameterization, which is opt-in.
        """
        merged = self.text + diacritic.text
        if normalizer is not None:
            merged = normalizer(merged)
        self.text = merged
        self.width = self.width + diacritic.width

    # ------------------------------------------------------------------
    # Matrix
    # ------------------------------------------------------------------

    def get_text_matrix(self) -> list[float] | None:
        """Return the stored 6-element text matrix, if any."""
        return self.text_matrix

    # ------------------------------------------------------------------
    # Value-based equality (upstream parity)
    # ------------------------------------------------------------------

    # Subset of fields used by upstream ``TextPosition.equals`` /
    # ``hashCode``. Per the PDFBOX-4701 comment in upstream, the decoded
    # ``unicode`` text is intentionally excluded — it is mutated in
    # place by ``mergeDiacritic`` and would otherwise break the
    # equals/hash contract for keys already inserted into a ``HashSet``.
    _EQ_FIELDS: tuple[str, ...] = (
        "x",
        "y",
        "width",
        "font_size",
        "font_size_in_pt",
        "page_width",
        "page_height",
        "rotation",
        "width_of_space",
        "font_name",
        "resolved_font_name",
        "font",
    )

    def equals(self, other: object) -> bool:
        """Value-based equality on the upstream-stable subset of fields.

        Mirrors ``org.apache.pdfbox.text.TextPosition.equals`` (and its
        explicit comment ``do not compare mutable fields (PDFBOX-4701)``).
        Returns ``True`` only when ``other`` is also a
        :class:`TextPosition` and every field listed in
        :attr:`_EQ_FIELDS` is equal — the decoded :attr:`text` is
        deliberately excluded so post-construction mutation (e.g. via
        :meth:`merge_diacritic`) does not change a position's identity
        in a hashed container.

        The dataclass-generated ``__eq__`` remains in place for plain
        ``==`` comparisons (it compares *all* fields, including the
        decoded text) — :meth:`equals` is the upstream-parity entry
        point for callers porting Java code that depends on the
        narrower contract.
        """
        if other is self:
            return True
        if not isinstance(other, TextPosition):
            return False
        for name in self._EQ_FIELDS:
            if getattr(self, name) != getattr(other, name):
                return False
        # Element-wise compare of the optional text matrix list.
        if self.text_matrix != other.text_matrix:
            return False
        return True

    def __hash__(self) -> int:
        """Hash on the same upstream-stable subset used by :meth:`equals`.

        The dataclass decorator would otherwise leave ``__hash__`` as
        ``None`` (because we keep ``eq=True`` for the all-field
        comparison), making :class:`TextPosition` unhashable. We restore
        hashability by producing a tuple-hash over the immutable subset
        — sufficient for use as a dict key or set member while
        preserving the PDFBOX-4701 invariant that mutating decoded text
        doesn't move a position in a hashed container.
        """
        tm = tuple(self.text_matrix) if self.text_matrix is not None else None
        return hash(
            (
                self.x,
                self.y,
                self.width,
                self.font_size,
                self.font_size_in_pt,
                self.page_width,
                self.page_height,
                self.rotation,
                self.width_of_space,
                self.font_name,
                self.resolved_font_name,
                id(self.font) if self.font is not None else 0,
                tm,
            )
        )

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.text


__all__ = ["TextPosition"]
