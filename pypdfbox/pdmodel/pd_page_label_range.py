from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

# Page label dictionary keys (PDF 32000-1:2008 §12.4.2, Table 159).
_KEY_START: COSName = COSName.get_pdf_name("St")
_KEY_PREFIX: COSName = COSName.get_pdf_name("P")
_KEY_STYLE: COSName = COSName.get_pdf_name("S")


class PDPageLabelRange:
    """
    One entry in a ``PDPageLabels`` number tree. Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDPageLabelRange``.

    ``start_index`` is metadata about *where* this range begins in the
    enclosing /Nums tree (the integer key paired with the dictionary). It
    is **not** persisted in the underlying dictionary — upstream stores it
    only as a positional key in the parent number tree.
    """

    # Style entry values (PDF 32000-1:2008 §12.4.2, Table 159).
    STYLE_DECIMAL: str = "D"
    STYLE_ROMAN_UPPER: str = "R"
    STYLE_ROMAN_LOWER: str = "r"
    STYLE_LETTERS_UPPER: str = "A"
    STYLE_LETTERS_LOWER: str = "a"

    _VALID_STYLES: frozenset[str] = frozenset(
        {
            STYLE_DECIMAL,
            STYLE_ROMAN_UPPER,
            STYLE_ROMAN_LOWER,
            STYLE_LETTERS_UPPER,
            STYLE_LETTERS_LOWER,
        }
    )

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        start_index: int = 0,
    ) -> None:
        self._root = dictionary if dictionary is not None else COSDictionary()
        self._start_index = start_index

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._root

    # ---------- start index (range position in /Nums) ----------

    def get_start_index(self) -> int:
        return self._start_index

    def set_start_index(self, idx: int) -> None:
        self._start_index = idx

    # ---------- style ----------

    def get_style(self) -> str | None:
        return self._root.get_name(_KEY_STYLE)

    def set_style(self, style: str | None) -> None:
        if style is None:
            self._root.remove_item(_KEY_STYLE)
            return
        if style not in self._VALID_STYLES:
            raise ValueError(
                f"Invalid page label style {style!r}; must be one of "
                f"{sorted(self._VALID_STYLES)}"
            )
        self._root.set_name(_KEY_STYLE, style)

    # ---------- start ----------

    def get_start(self) -> int:
        # Upstream defaults to 1 when /St is absent.
        v = self._root.get_int(_KEY_START, 1)
        return v if v != -1 else 1

    def set_start(self, start: int) -> None:
        if start <= 0:
            raise ValueError(
                "The page numbering start value must be a positive integer"
            )
        self._root.set_int(_KEY_START, start)

    # ---------- prefix ----------

    def get_prefix(self) -> str | None:
        return self._root.get_string(_KEY_PREFIX)

    def set_prefix(self, prefix: str | None) -> None:
        if prefix is None:
            self._root.remove_item(_KEY_PREFIX)
        else:
            self._root.set_string(_KEY_PREFIX, prefix)

    # ---------- computed labels ----------

    def format_label_index(self, index: int) -> str:
        """Alias for :meth:`compute_label_for_offset`. Mirrors the upstream
        helper name used in some downstream callers (PDF 32000-1 §12.4.2).
        """
        return self.compute_label_for_offset(index)

    def compute_label_for_offset(self, offset: int) -> str:
        """Render the label for a 0-based ``offset`` within this range.

        Produces ``prefix + style-formatted(start + offset)``. When ``style``
        is ``None`` only the prefix is emitted (mirrors upstream behaviour
        and matches ``PDPageLabels.get_label_for_page``).
        """
        # Local import to avoid a circular import with pd_page_labels (which
        # imports this module at top-level).
        from .pd_page_labels import to_letters, to_roman

        prefix = self.get_prefix() or ""
        # Upstream PDFBOX-1047: trim the prefix at the first NUL.
        nul = prefix.find("\x00")
        if nul >= 0:
            prefix = prefix[:nul]
        style = self.get_style()
        if style is None:
            return prefix
        n = self.get_start() + offset
        if style == self.STYLE_DECIMAL:
            return prefix + str(n)
        if style == self.STYLE_ROMAN_UPPER:
            return prefix + to_roman(n)
        if style == self.STYLE_ROMAN_LOWER:
            return prefix + to_roman(n).lower()
        if style == self.STYLE_LETTERS_UPPER:
            return prefix + to_letters(n)
        if style == self.STYLE_LETTERS_LOWER:
            return prefix + to_letters(n).lower()
        # Unknown style — fall back to decimal (matches upstream).
        return prefix + str(n)

    def __repr__(self) -> str:
        return (
            f"PDPageLabelRange(start_index={self._start_index}, "
            f"style={self.get_style()!r}, "
            f"start={self.get_start()}, prefix={self.get_prefix()!r})"
        )


__all__ = ["PDPageLabelRange"]
