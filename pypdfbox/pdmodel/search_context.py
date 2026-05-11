from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary

if TYPE_CHECKING:
    from .pd_page import PDPage


class SearchContext:
    """State holder for :meth:`PDPageTree.index_of`.

    Mirrors the private ``PDPageTree.SearchContext`` inner class (Java
    lines 429-445). Tracks the running 0-based page index and flips
    ``found`` when the dictionary identity matches the page being searched
    for. Surfaced as a public class so callers porting upstream tests can
    reference the same name.
    """

    __slots__ = ("searched", "index", "found")

    def __init__(self, page: PDPage | COSDictionary) -> None:
        # Local import to avoid a cycle (PDPage imports pdmodel).
        from .pd_page import PDPage as _PDPage  # noqa: PLC0415

        if isinstance(page, _PDPage):
            self.searched: COSDictionary = page.get_cos_object()
        elif isinstance(page, COSDictionary):
            self.searched = page
        else:
            raise TypeError(
                "SearchContext expected PDPage or COSDictionary; "
                f"got {type(page).__name__}"
            )
        self.index: int = -1
        self.found: bool = False

    def visit_page(self, current: COSDictionary) -> None:
        """Increment the running index and flip ``found`` when ``current``
        is the searched dictionary. Mirrors upstream ``visitPage`` (Java
        line 440)."""
        self.index += 1
        if self.searched is current:
            self.found = True


__all__ = ["SearchContext"]
