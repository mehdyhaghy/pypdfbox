from __future__ import annotations

from pypdfbox.cos import COSInteger, COSName
from pypdfbox.pdmodel import PDPage, PDPageTree


def _make_page(label: str | None = None) -> PDPage:
    page = PDPage()
    if label is not None:
        page.get_cos_object().set_string(COSName.get_pdf_name("Label"), label)
    return page


def _label(page: PDPage) -> str | None:
    return page.get_cos_object().get_string(COSName.get_pdf_name("Label"))


def _count(tree: PDPageTree) -> int:
    value = tree.get_cos_object().get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(value, COSInteger)
    return value.value


def test_index_of_returns_correct_index_after_multiple_adds() -> None:
    tree = PDPageTree()
    pages = [_make_page(f"p{i}") for i in range(4)]
    for page in pages:
        tree.add(page)

    for expected_index, page in enumerate(pages):
        assert tree.index_of(page) == expected_index


def test_index_of_unrelated_page_returns_minus_one() -> None:
    tree = PDPageTree()
    tree.add(_make_page("present"))
    tree.add(_make_page("also-present"))

    stranger = _make_page("never-added")
    assert tree.index_of(stranger) == -1


def test_insert_after_splices_in_correct_position() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    c = _make_page("c")
    d = _make_page("d")
    tree.add(a)
    tree.add(c)
    tree.add(d)

    b = _make_page("b")
    tree.insert_after(b, a)

    assert [_label(p) for p in tree] == ["a", "b", "c", "d"]
    assert tree.index_of(b) == 1
    assert _count(tree) == 4


def test_insert_before_splices_in_correct_position() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    c = _make_page("c")
    d = _make_page("d")
    tree.add(a)
    tree.add(c)
    tree.add(d)

    b = _make_page("b")
    tree.insert_before(b, c)

    assert [_label(p) for p in tree] == ["a", "b", "c", "d"]
    assert tree.index_of(b) == 1
    assert _count(tree) == 4


def test_remove_returns_true_and_decrements_count() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    b = _make_page("b")
    c = _make_page("c")
    tree.add(a)
    tree.add(b)
    tree.add(c)
    assert _count(tree) == 3

    assert tree.remove(b) is True

    assert _count(tree) == 2
    assert len(tree) == 2
    assert [_label(p) for p in tree] == ["a", "c"]
    assert tree.index_of(b) == -1


def test_remove_unrelated_page_returns_false() -> None:
    tree = PDPageTree()
    tree.add(_make_page("a"))
    tree.add(_make_page("b"))
    assert _count(tree) == 2

    stranger = _make_page("not-in-tree")
    assert tree.remove(stranger) is False
    # Count must be unchanged.
    assert _count(tree) == 2
    assert len(tree) == 2
