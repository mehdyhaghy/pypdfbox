"""``PDPageTree`` emptiness predicates and ``len`` semantics.

``__len__`` walks the tree and corrects a lying ``/Count`` to the real
reachable-leaf count (upstream ``getCount()`` parity is the O(1)
``get_count()`` accessor). ``is_empty`` / ``__bool__`` short-circuit at the
first reachable leaf instead of computing the full length — the observable
result is unchanged: a tree is empty iff a document-order walk yields no pages,
regardless of what ``/Count`` claims.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree

_COUNT = COSName.get_pdf_name("Count")
_KIDS = COSName.get_pdf_name("Kids")


def test_fresh_tree_is_empty() -> None:
    tree = PDPageTree()
    assert tree.is_empty()
    assert not tree
    assert not tree.has_pages()
    assert len(tree) == 0


def test_non_empty_tree() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    tree = doc.get_pages()
    assert not tree.is_empty()
    assert tree
    assert tree.has_pages()
    assert len(tree) == 1
    doc.close()


def test_is_empty_ignores_lying_positive_count() -> None:
    """A ``/Count`` that lies high on an actually-empty tree must NOT make it
    report non-empty — emptiness follows the walk, not the stored count."""
    tree = PDPageTree()
    tree.get_cos_object().set_int(_COUNT, 99)
    # No kids added; the tree is really empty.
    assert tree.get_cos_object().get_dictionary_object(_KIDS).size() == 0
    assert tree.is_empty()
    assert not tree
    assert len(tree) == 0  # walk wins over the lying /Count


def test_is_empty_ignores_lying_zero_count() -> None:
    """A ``/Count`` of 0 on a tree that really has pages must report
    non-empty (the walk finds the pages)."""
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    tree = doc.get_pages()
    tree.get_cos_object().set_int(_COUNT, 0)  # lie: say empty
    assert not tree.is_empty()
    assert tree
    assert len(tree) == 2  # walk wins
    doc.close()


def test_bool_matches_is_empty() -> None:
    tree = PDPageTree()
    assert bool(tree) is (not tree.is_empty())
    doc = PDDocument()
    doc.add_page(PDPage())
    t2 = doc.get_pages()
    assert bool(t2) is (not t2.is_empty())
    doc.close()
