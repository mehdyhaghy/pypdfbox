"""Wave 1396 branch-coverage tests for ``PageIterator.enqueue_kids``.

Closes False-branch arrows:

* 47->exit — ``isinstance(kids, COSArray)`` False (no /Kids array)
* 58->exit — ``node is not None`` False (None passed)
* 62->exit — node has /Type but it's not /Page and has no /Kids → skipped
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.page_iterator import PageIterator


def test_enqueue_kids_with_pages_node_no_kids_array() -> None:
    """A page-tree node with a non-array /Kids is silently skipped.

    Closes False arm at line 47 (``isinstance(kids, COSArray)``).
    """
    node = COSDictionary()
    node.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Pages"))
    node.set_item(COSName.get_pdf_name("Kids"), COSInteger.get(99))  # not an array
    it = PageIterator(node)
    assert list(it) == []


def test_enqueue_kids_with_none_node() -> None:
    """Passing None short-circuits the outer if-branches.

    Closes False arm at line 58 (``node is not None``).
    """
    # We can't construct PageIterator with None because __init__ uses
    # COSDictionary type, but we can construct with empty dict and call
    # enqueue_kids(None) directly.
    empty = COSDictionary()
    it = PageIterator(empty)
    it.enqueue_kids(None)  # must not raise


def test_enqueue_kids_with_non_page_typed_node_skipped() -> None:
    """A node with /Type != /Page and no /Kids is skipped.

    Closes False arm at line 62 (``type_name is None and not /Kids``).
    """
    # node is a Catalog (not Pages, not Page) with no /Kids
    node = COSDictionary()
    node.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Catalog"))
    it = PageIterator(node)
    assert list(it) == []


def test_enqueue_kids_with_typeless_leaf_treated_as_page() -> None:
    """A leaf-shaped node with no /Type and no /Kids gets enqueued.

    Closes the True path of line 62 (sanity opposite of False arm).
    """
    node = COSDictionary()
    # No /Type, no /Kids — lenient: treat as a page.
    node.set_item(COSName.get_pdf_name("MediaBox"), COSArray())
    it = PageIterator(node)
    pages = list(it)
    assert len(pages) == 1
