from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
)

from .pd_page_label_range import PDPageLabelRange

if TYPE_CHECKING:
    from .pd_document import PDDocument


_NUMS: COSName = COSName.get_pdf_name("Nums")
_KIDS: COSName = COSName.get_pdf_name("Kids")


# Roman-numeral lookup table (PDFBox ``LabelGenerator.ROMANS``).
_ROMANS: tuple[tuple[str, ...], ...] = (
    ("", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix"),
    ("", "x", "xx", "xxx", "xl", "l", "lx", "lxx", "lxxx", "xc"),
    ("", "c", "cc", "ccc", "cd", "d", "dc", "dcc", "dccc", "cm"),
)


def _make_roman_label(page_index: int) -> str:
    """Lower-case Roman numeral for ``page_index`` (>= 1).

    For ``page_index >= 4000`` upstream prepends one ``m`` per thousand —
    technically incorrect but matches Adobe Acrobat's behaviour.
    """
    buf: list[str] = []
    power = 0
    while power < 3 and page_index > 0:
        buf.insert(0, _ROMANS[power][page_index % 10])
        page_index //= 10
        power += 1
    if page_index > 0:
        buf.insert(0, "m" * page_index)
    return "".join(buf)


def _make_letter_label(num: int) -> str:
    """``a..z, aa..zz, aaa..zzz`` labelling (PDF 32000-1 Table 159)."""
    if num <= 0:
        # Upstream's algorithm only handles positive integers; mirror by
        # returning empty for non-positive (matches signum behaviour).
        return ""
    num_letters = (num - 1) // 26 + 1
    letter = (num - 1) % 26
    return chr(ord("a") + letter) * num_letters


class PDPageLabels:
    """
    Page label dictionary (PDF 32000-1:2008 §12.4.2). Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDPageLabels``.

    The underlying number tree is represented here as a simple in-memory
    ``dict[int, PDPageLabelRange]``. A full ``PDNumberTreeNode`` port that
    supports balanced /Kids splits and lazy loading is deferred — see
    ``CHANGES.md``. Reads handle both flat ``/Nums`` arrays and a single
    level of ``/Kids`` for compatibility with documents in the wild.
    """

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary | None = None,
    ) -> None:
        self._doc = document
        self._labels: dict[int, PDPageLabelRange] = {}
        # Required default range starting at page 0 (PDF 32000-1 p. 375).
        default_range = PDPageLabelRange()
        default_range.set_style(PDPageLabelRange.STYLE_DECIMAL)
        self._labels[0] = default_range
        if dict_ is not None:
            self._find_labels(dict_)

    # ---------- number-tree traversal (stub) ----------

    def _find_labels(self, node: COSDictionary) -> None:
        kids = node.get_dictionary_object(_KIDS)
        if isinstance(kids, COSArray):
            for i in range(kids.size()):
                child = kids.get_object(i)
                if isinstance(child, COSDictionary):
                    self._find_labels(child)
            return
        nums = node.get_dictionary_object(_NUMS)
        if not isinstance(nums, COSArray):
            return
        i = 0
        while i + 1 < nums.size():
            key_obj = nums.get_object(i)
            value_obj = nums.get_object(i + 1)
            i += 2
            if not isinstance(key_obj, COSInteger):
                continue
            if not isinstance(value_obj, COSDictionary):
                continue
            key = key_obj.value
            if key < 0:
                continue
            self._labels[key] = PDPageLabelRange(value_obj)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        arr = COSArray()
        for key in sorted(self._labels):
            arr.add(COSInteger.get(key))
            arr.add(self._labels[key].get_cos_object())
        out = COSDictionary()
        out.set_item(_NUMS, arr)
        return out

    # ---------- range access ----------

    def get_page_range_count(self) -> int:
        """Always >= 1 — PDF 32000-1 requires a range starting at page 0."""
        return len(self._labels)

    def get_page_label_range(self, start_page: int) -> PDPageLabelRange | None:
        return self._labels.get(start_page)

    def set_label_item(self, start_page: int, item: PDPageLabelRange) -> None:
        if start_page < 0:
            raise ValueError(
                "startPage parameter of set_label_item may not be < 0"
            )
        self._labels[start_page] = item

    def get_label_range_iterator(self) -> Iterator[tuple[int, PDPageLabelRange]]:
        """Yield ``(start_page, range)`` pairs in start-page order. Pythonic
        equivalent of upstream's ``labels.entrySet().iterator()`` exposure."""
        for key in sorted(self._labels):
            yield key, self._labels[key]

    def get_page_indices(self) -> list[int]:
        """Sorted list of start-page indices (one per defined range)."""
        return sorted(self._labels)

    # ---------- computed labels ----------

    def get_label_by_page_index(self, page_index: int) -> str | None:
        """Compute the label for the 0-based page index. Returns ``None``
        if ``page_index`` is out of the document's page range."""
        if page_index < 0:
            return None
        labels = self.get_labels_by_page_indices()
        if page_index >= len(labels):
            return None
        return labels[page_index]

    def get_labels_by_page_indices(self) -> list[str]:
        """Return a list of labels, one per page in the document, in order."""
        number_of_pages = self._doc.get_number_of_pages()
        result: list[str | None] = [None] * number_of_pages
        self._compute_labels(
            lambda idx, label: result.__setitem__(idx, label)
            if 0 <= idx < number_of_pages
            else None,
            number_of_pages,
        )
        # Replace any leftover ``None`` with empty string so the contract
        # (``list[str]``) holds even if the number tree doesn't cover every
        # page (matches upstream behaviour where the array slot stays null).
        return [r if r is not None else "" for r in result]

    def get_page_indices_by_labels(self) -> dict[str, int]:
        """Inverse map. Where a label repeats, the highest index wins."""
        number_of_pages = self._doc.get_number_of_pages()
        out: dict[str, int] = {}
        self._compute_labels(lambda idx, label: out.__setitem__(label, idx), number_of_pages)
        return out

    # ---------- internal computation ----------

    def _compute_labels(
        self,
        handler,
        number_of_pages: int,
    ) -> None:
        if not self._labels:
            return
        sorted_starts = sorted(self._labels)
        page_index = 0
        for i, start in enumerate(sorted_starts):
            label_info = self._labels[start]
            if i + 1 < len(sorted_starts):
                num_pages = sorted_starts[i + 1] - start
            else:
                num_pages = number_of_pages - start
            for label in _LabelGenerator(label_info, num_pages):
                handler(page_index, label)
                page_index += 1

    # ---------- introspection ----------

    def __repr__(self) -> str:
        return f"PDPageLabels(ranges={self.get_page_range_count()})"


class _LabelGenerator:
    """Stateful iterator producing the labels for a single range."""

    def __init__(self, label_info: PDPageLabelRange, num_pages: int) -> None:
        self._label_info = label_info
        self._num_pages = max(0, num_pages)
        self._current = 0

    def __iter__(self) -> _LabelGenerator:
        return self

    def __next__(self) -> str:
        if self._current >= self._num_pages:
            raise StopIteration
        buf: list[str] = []
        prefix = self._label_info.get_prefix()
        if prefix is not None:
            # Upstream PDFBOX-1047 trims at the first NUL.
            nul = prefix.find("\x00")
            if nul >= 0:
                prefix = prefix[:nul]
            buf.append(prefix)
        style = self._label_info.get_style()
        if style is not None:
            buf.append(_render_number(self._label_info.get_start() + self._current, style))
        self._current += 1
        return "".join(buf)


def _render_number(page_index: int, style: str) -> str:
    if style == PDPageLabelRange.STYLE_DECIMAL:
        return str(page_index)
    if style == PDPageLabelRange.STYLE_LETTERS_LOWER:
        return _make_letter_label(page_index)
    if style == PDPageLabelRange.STYLE_LETTERS_UPPER:
        return _make_letter_label(page_index).upper()
    if style == PDPageLabelRange.STYLE_ROMAN_LOWER:
        return _make_roman_label(page_index)
    if style == PDPageLabelRange.STYLE_ROMAN_UPPER:
        return _make_roman_label(page_index).upper()
    # Unknown style — fall back to decimal (matches upstream).
    return str(page_index)


__all__ = ["PDPageLabels"]
