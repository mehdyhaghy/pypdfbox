from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

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


def to_roman(n: int) -> str:
    """Public helper: upper-case Roman numeral for ``n`` (>= 1).

    Returns an empty string for non-positive input (matches the internal
    label generator). Mirrors PDFBox's roman rendering.
    """
    return _make_roman_label(n).upper()


def to_letters(n: int) -> str:
    """Public helper: upper-case letter label (``A..Z, AA..ZZ, ...``).

    Letter labels follow the PDF 32000-1 Table 159 doubling scheme:
    1→A, 26→Z, 27→AA, 28→BB, etc. Returns empty for non-positive input.
    """
    return _make_letter_label(n).upper()


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

    # Style entry values, mirrored on the wrapper for convenience so callers
    # don't have to import ``PDPageLabelRange`` just for the constants.
    STYLE_DECIMAL: str = PDPageLabelRange.STYLE_DECIMAL
    STYLE_ROMAN_UPPER: str = PDPageLabelRange.STYLE_ROMAN_UPPER
    STYLE_ROMAN_LOWER: str = PDPageLabelRange.STYLE_ROMAN_LOWER
    STYLE_LETTERS_UPPER: str = PDPageLabelRange.STYLE_LETTERS_UPPER
    STYLE_LETTERS_LOWER: str = PDPageLabelRange.STYLE_LETTERS_LOWER

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary | None = None,
    ) -> None:
        self._doc = document
        # Optional explicit override of the page count used when computing
        # labels. ``None`` means "ask the document". Mirrors the typed
        # accessor pair :meth:`get_number_of_pages` / :meth:`set_number_of_pages`.
        self._number_of_pages: int | None = None
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

    def find_label_range_containing(
        self, page_index: int
    ) -> PDPageLabelRange | None:
        """Return the :class:`PDPageLabelRange` whose span covers
        ``page_index`` (0-based), or ``None`` if ``page_index`` is negative
        or no range starts at or before it.

        Selects the range with the greatest ``start_index`` that is still
        ``<= page_index`` — same algorithm as :meth:`get_label_for_page`.
        """
        if page_index < 0:
            return None
        sorted_starts = sorted(self._labels)
        if not sorted_starts:
            return None
        if page_index < sorted_starts[0]:
            return None
        chosen = sorted_starts[0]
        for s in sorted_starts:
            if s <= page_index:
                chosen = s
            else:
                break
        return self._labels[chosen]

    # ---------- typed page-count accessor ----------

    def get_number_of_pages(self) -> int:
        """Return the page count used when materialising the full label
        list. Returns the explicit override set via
        :meth:`set_number_of_pages` if present, else the wrapped document's
        page count, else 0 when neither is available.
        """
        if self._number_of_pages is not None:
            return self._number_of_pages
        if self._doc is not None:
            try:
                return self._doc.get_number_of_pages()
            except Exception:
                return 0
        return 0

    def set_number_of_pages(self, count: int) -> None:
        """Override the page count used by :meth:`get_labels_by_page_indices`
        and friends. Pass ``None`` via :meth:`set_number_of_pages` is not
        supported — clear by re-binding to a document if needed.
        """
        if count < 0:
            raise ValueError(
                "count parameter of set_number_of_pages may not be < 0"
            )
        self._number_of_pages = count

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

    def get_label_for_page(self, index: int) -> str:
        """Compute the label for the 0-based page ``index`` without needing
        to know the document's total page count.

        Walks the in-memory ``/Nums`` ranges, finds the range covering
        ``index``, and renders ``prefix + style(start_number + (index -
        range_start))``. Returns ``str(index + 1)`` for negative indices /
        no-op cases (mirrors the spec default of decimal labelling).
        """
        if index < 0:
            return str(index + 1)
        sorted_starts = sorted(self._labels)
        # Find the range whose start is the greatest <= index.
        range_start = sorted_starts[0]
        for s in sorted_starts:
            if s <= index:
                range_start = s
            else:
                break
        info = self._labels[range_start]
        offset = index - range_start
        prefix = info.get_prefix() or ""
        # Upstream PDFBOX-1047: trim the prefix at the first NUL.
        nul = prefix.find("\x00")
        if nul >= 0:
            prefix = prefix[:nul]
        style = info.get_style()
        if style is None:
            return prefix
        return prefix + _render_number(info.get_start() + offset, style)

    def get_label_ranges(self) -> list[dict[str, Any]]:
        """List each /Nums range as a ``dict`` with keys ``start_index``,
        ``style`` (``/S``), ``prefix`` (``/P``), ``start_number`` (``/St``).

        Convenience for callers that want plain-data introspection without
        touching ``PDPageLabelRange`` directly.
        """
        out: list[dict[str, Any]] = []
        for start in sorted(self._labels):
            info = self._labels[start]
            out.append(
                {
                    "start_index": start,
                    "style": info.get_style(),
                    "prefix": info.get_prefix(),
                    "start_number": info.get_start(),
                }
            )
        return out

    def set_label_range(
        self,
        start_index: int,
        style: str | None = None,
        prefix: str | None = None,
        start_number: int = 1,
    ) -> None:
        """Append (or replace) a range entry in /Nums at ``start_index``.

        Convenience constructor on top of :meth:`set_label_item`. ``style``
        should be one of the ``STYLE_*`` constants. ``start_number`` must be
        positive (PDF 32000-1 §12.4.2 — ``/St`` is a positive integer).
        """
        if start_index < 0:
            raise ValueError(
                "start_index parameter of set_label_range may not be < 0"
            )
        item = PDPageLabelRange()
        if style is not None:
            item.set_style(style)
        if prefix is not None:
            item.set_prefix(prefix)
        # ``set_start`` itself validates positivity; default 1 is the spec
        # default so we only emit /St when the caller asked for non-default.
        if start_number != 1:
            item.set_start(start_number)
        self._labels[start_index] = item

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


__all__ = ["PDPageLabels", "to_letters", "to_roman"]
