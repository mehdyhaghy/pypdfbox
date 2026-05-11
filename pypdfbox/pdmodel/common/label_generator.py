from __future__ import annotations

from collections.abc import Iterator

from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange

# Roman-numeral lookup table (PDFBox ``LabelGenerator.ROMANS``,
# PDPageLabels.java lines 370-374).
_ROMANS: tuple[tuple[str, ...], ...] = (
    ("", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix"),
    ("", "x", "xx", "xxx", "xl", "l", "lx", "lxx", "lxxx", "xc"),
    ("", "c", "cc", "ccc", "cd", "d", "dc", "dcc", "dccc", "cm"),
)


class LabelGenerator:
    """Iterator generating the labels for a single page-label range.

    Mirrors the package-private ``PDPageLabels.LabelGenerator`` inner class
    (PDPageLabels.java lines 295-415). Surfaced publicly here so callers
    can drive label generation manually (e.g. for streaming output) without
    going through :meth:`PDPageLabels.get_labels_by_page_indices`.
    """

    def __init__(self, label_info: PDPageLabelRange, num_pages: int) -> None:
        self._label_info: PDPageLabelRange = label_info
        self._num_pages: int = max(0, num_pages)
        self._current_page: int = 0

    # ---------- iterator protocol ----------

    def has_next(self) -> bool:
        """Java-style alias for :meth:`__next__` availability."""
        return self._current_page < self._num_pages

    def remove(self) -> None:
        """Mirrors upstream ``Iterator.remove`` — unsupported because
        labels are computed on-the-fly."""
        raise NotImplementedError("LabelGenerator does not support removal")

    def next(self) -> str:
        """Return the next label. Mirrors upstream ``next()`` (Java
        line 315). Raises :class:`StopIteration` when exhausted."""
        return self.__next__()

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        if not self.has_next():
            raise StopIteration
        buf: list[str] = []
        prefix = self._label_info.get_prefix()
        if prefix is not None:
            # PDFBOX-1047: trim at the first NUL.
            nul = prefix.find("\x00")
            if nul >= 0:
                prefix = prefix[:nul]
            buf.append(prefix)
        style = self._label_info.get_style()
        if style is not None:
            buf.append(
                self.get_number(self._label_info.get_start() + self._current_page, style)
            )
        self._current_page += 1
        return "".join(buf)

    # ---------- number rendering ----------

    @staticmethod
    def get_number(page_index: int, style: str | None) -> str:
        """Render ``page_index`` in ``style``. Mirrors upstream
        ``getNumber(int, String)`` (Java line 343).
        """
        if style is not None:
            if style == PDPageLabelRange.STYLE_DECIMAL:
                return str(page_index)
            if style == PDPageLabelRange.STYLE_LETTERS_LOWER:
                return LabelGenerator.make_letter_label(page_index)
            if style == PDPageLabelRange.STYLE_LETTERS_UPPER:
                return LabelGenerator.make_letter_label(page_index).upper()
            if style == PDPageLabelRange.STYLE_ROMAN_LOWER:
                return LabelGenerator.make_roman_label(page_index)
            if style == PDPageLabelRange.STYLE_ROMAN_UPPER:
                return LabelGenerator.make_roman_label(page_index).upper()
        return str(page_index)

    @staticmethod
    def make_roman_label(page_index: int) -> str:
        """Lower-case Roman numeral for ``page_index``.

        Mirrors upstream ``makeRomanLabel(int)`` (Java line 376), including
        the "unbounded m for thousands" Adobe quirk.
        """
        buf: list[str] = []
        power = 0
        remaining = page_index
        while power < 3 and remaining > 0:
            buf.insert(0, _ROMANS[power][remaining % 10])
            remaining //= 10
            power += 1
        if remaining > 0:
            buf.insert(0, "m" * remaining)
        return "".join(buf)

    @staticmethod
    def make_letter_label(num: int) -> str:
        """``a..z, aa..zz, aaa..zzz`` labelling for ``num``.

        Mirrors upstream ``makeLetterLabel(int)`` (Java line 404, PDF
        32000-1 Table 159).
        """
        if num <= 0:
            return ""
        num_letters = (num - 1) // 26 + 1
        letter = (num - 1) % 26
        return chr(ord("a") + letter) * num_letters


__all__ = ["LabelGenerator"]
