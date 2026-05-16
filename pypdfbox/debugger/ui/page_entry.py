"""Tree-view abstraction of a PDF page.

Ported from ``org.apache.pdfbox.debugger.ui.PageEntry``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName


class PageEntry:
    """Abstract view of a page in the tree view."""

    def __init__(
        self,
        page: COSDictionary,
        page_num: int,
        page_label: str | None,
    ) -> None:
        self._dict = page
        self._page_num = page_num
        self._page_label = page_label

    def get_dict(self) -> COSDictionary:
        """Return the underlying page dictionary."""
        return self._dict

    def get_page_num(self) -> int:
        """Return the 1-based page number."""
        return self._page_num

    def to_string(self) -> str:
        """Return the upstream ``toString`` rendering — ``Page: N`` plus label."""
        label = ""
        if self._page_label is not None:
            label = f" - {self._page_label}"
        return f"Page: {self._page_num}{label}"

    def __str__(self) -> str:
        return self.to_string()

    def get_path(self) -> str:
        """Reconstruct the tree path from the document root to this page."""
        parts = ["Root/Pages"]
        node = self._dict
        while node.contains_key(COSName.PARENT):
            parent = node.get_cos_dictionary(COSName.PARENT)
            if parent is None:
                return ""
            kids = parent.get_cos_array(COSName.KIDS)
            if kids is None:
                return ""
            idx = kids.index_of_object(node)
            if idx == -1:
                break
            parts.append(f"/Kids/[{idx}]")
            node = parent
        return "".join(parts)
