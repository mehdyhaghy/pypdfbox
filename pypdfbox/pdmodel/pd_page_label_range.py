from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString

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

    @classmethod
    def is_valid_style(cls, style: str | None) -> bool:
        """Predicate: is ``style`` one of the five PDF 32000-1 §12.4.2 Table
        159 numbering-style codes?

        ``None`` returns ``False`` (the absence of /S is legal but is not a
        "valid style", it's "no style"). Useful for callers that want to
        validate user input before calling :meth:`set_style` (which, like
        upstream, stores any string verbatim without validating).
        """
        return style in cls._VALID_STYLES

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
        # Mirror upstream ``PDPageLabelRange.setStyle`` exactly: a non-null
        # value is stored verbatim via ``setName`` (NO validation against the
        # STYLE_* codes — upstream accepts any string and the label generator
        # falls back to decimal for unrecognised codes), and ``None`` removes
        # the ``/S`` entry. Use :meth:`is_valid_style` to pre-validate input.
        if style is not None:
            self._root.set_name(_KEY_STYLE, style)
        else:
            self._root.remove_item(_KEY_STYLE)

    def clear_style(self) -> None:
        """Remove the ``/S`` numbering style entry."""
        self._root.remove_item(_KEY_STYLE)

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

    def clear_start(self) -> None:
        """Remove the explicit ``/St`` entry so :meth:`get_start` defaults to 1."""
        self._root.remove_item(_KEY_START)

    # ---------- prefix ----------

    def get_prefix(self) -> str | None:
        return self._root.get_string(_KEY_PREFIX)

    def set_prefix(self, prefix: str | None) -> None:
        if prefix is None:
            self._root.remove_item(_KEY_PREFIX)
        else:
            self._root.set_string(_KEY_PREFIX, prefix)

    def clear_prefix(self) -> None:
        """Remove the ``/P`` page label prefix entry."""
        self._root.remove_item(_KEY_PREFIX)

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

    # ---------- predicates ----------

    def is_empty(self) -> bool:
        """``True`` when the wrapped dictionary carries none of the three
        defined entries (``/S``, ``/P``, ``/St``).

        An "empty" range still renders labels — :meth:`get_start` returns
        the spec default of ``1`` and :meth:`get_style` returns ``None`` so
        :meth:`compute_label_for_offset` emits the empty string. Useful for
        callers that want to skip serializing trivially-default range
        entries from a working set (e.g. when constructing a /Nums array
        and only wanting to emit ranges with non-default content).
        """
        return (
            not self._root.contains_key(_KEY_STYLE)
            and not self._root.contains_key(_KEY_PREFIX)
            and not self._root.contains_key(_KEY_START)
        )

    def has_style(self) -> bool:
        """``True`` when the ``/S`` numbering style entry is present.

        Convenience for callers that branch on the absence of ``/S`` (which
        is legal — it produces "prefix-only" labels) without needing to
        check ``get_style() is not None``."""
        return isinstance(self._root.get_dictionary_object(_KEY_STYLE), COSName)

    def has_prefix(self) -> bool:
        """``True`` when the ``/P`` page label prefix entry is present.

        Distinguishes "no prefix set" from "explicit empty-string prefix";
        :meth:`get_prefix` returns ``None`` for the former and ``""`` for
        the latter, but callers that want a single boolean check (e.g. for
        deciding whether to render a separator) can use this."""
        return isinstance(
            self._root.get_dictionary_object(_KEY_PREFIX), COSString
        )

    def has_start(self) -> bool:
        """``True`` when an explicit ``/St`` (start number) entry is set.

        Distinguishes "the spec default of 1 was implied" from "the writer
        recorded /St 1 explicitly". Useful for round-tripping decisions
        where preserving the absent /St entry matters for byte-exact
        re-serialisation."""
        return isinstance(
            self._root.get_dictionary_object(_KEY_START), COSInteger
        )

    # ---------- structural equality ----------

    def __eq__(self, other: object) -> bool:
        """Two ranges compare equal when their style, prefix, start value,
        and start index all match.

        This is structural equality on the public attributes — it does not
        require the underlying ``COSDictionary`` instances to be identical
        (so a parsed range and a freshly-built one with the same content
        compare equal). Useful for verifying round-trip behaviour and for
        deduplicating /Nums entries before serialisation."""
        if not isinstance(other, PDPageLabelRange):
            return NotImplemented
        return (
            self._start_index == other._start_index
            and self.get_style() == other.get_style()
            and self.get_prefix() == other.get_prefix()
            and self.get_start() == other.get_start()
        )

    def __hash__(self) -> int:
        """Hash matches :meth:`__eq__` — over (start_index, style, prefix,
        start). PDPageLabelRange is a thin typed wrapper, hashing on the
        public attributes (rather than dict identity) keeps it usable as a
        dict key when callers need that.

        Note: the wrapped dictionary is mutable, so a range used as a dict
        key after subsequent ``set_*`` calls will not be locatable in the
        dict — same caveat as any mutable hashable object."""
        return hash(
            (
                self._start_index,
                self.get_style(),
                self.get_prefix(),
                self.get_start(),
            )
        )

    def __repr__(self) -> str:
        return (
            f"PDPageLabelRange(start_index={self._start_index}, "
            f"style={self.get_style()!r}, "
            f"start={self.get_start()}, prefix={self.get_prefix()!r})"
        )


__all__ = ["PDPageLabelRange"]
