from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel import PDPage, PDPageTree


def _make_page(label: str | None = None) -> PDPage:
    page = PDPage()
    if label is not None:
        page.get_cos_object().set_string(COSName.get_pdf_name("Label"), label)
    return page


def _label(page: PDPage) -> str | None:
    return page.get_cos_object().get_string(COSName.get_pdf_name("Label"))


def test_default_construction_empty_tree() -> None:
    tree = PDPageTree()
    assert len(tree) == 0
    assert list(tree) == []


def test_add_appends_to_kids() -> None:
    tree = PDPageTree()
    p1 = _make_page("first")
    p2 = _make_page("second")
    tree.add(p1)
    tree.add(p2)
    assert len(tree) == 2
    labels = [_label(p) for p in tree]
    assert labels == ["first", "second"]


def test_count_property_updated_on_add() -> None:
    tree = PDPageTree()
    tree.add(_make_page())
    tree.add(_make_page())
    count = tree.get_cos_object().get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(count, COSInteger)
    assert count.value == 2


def test_index_access_zero_based() -> None:
    tree = PDPageTree()
    pages = [_make_page(f"p{i}") for i in range(3)]
    for p in pages:
        tree.add(p)
    assert _label(tree[0]) == "p0"
    assert _label(tree[2]) == "p2"


def test_negative_index() -> None:
    tree = PDPageTree()
    for i in range(4):
        tree.add(_make_page(f"p{i}"))
    assert _label(tree[-1]) == "p3"
    assert _label(tree[-4]) == "p0"


def test_index_out_of_range_raises() -> None:
    tree = PDPageTree()
    tree.add(_make_page())
    with pytest.raises(IndexError):
        _ = tree[5]
    with pytest.raises(IndexError):
        _ = tree[-2]


def test_index_of_direct_pages() -> None:
    tree = PDPageTree()
    pages = [_make_page(f"p{i}") for i in range(3)]
    for page in pages:
        tree.add(page)

    assert tree.index_of(pages[0]) == 0
    assert tree.index_of(pages[2]) == 2
    assert tree.index_of_page(pages[1]) == 1


def test_index_of_indirect_page_object() -> None:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    kids = COSArray()
    root.set_item(COSName.KIDS, kids)  # type: ignore[attr-defined]

    first = _make_page("first")
    second = _make_page("second")
    first.get_cos_object().set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    second.get_cos_object().set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    kids.add(COSObject(10, resolved=first.get_cos_object()))
    kids.add(COSObject(11, resolved=second.get_cos_object()))
    root.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]

    tree = PDPageTree(root)
    assert tree.index_of(first) == 0
    assert tree.index_of(PDPage(second.get_cos_object())) == 1


def test_index_of_missing_page_returns_minus_one() -> None:
    tree = PDPageTree()
    tree.add(_make_page("present"))

    assert tree.index_of(_make_page("missing")) == -1


def test_remove_decrements_count() -> None:
    tree = PDPageTree()
    p1 = _make_page("a")
    p2 = _make_page("b")
    tree.add(p1)
    tree.add(p2)
    assert tree.remove(p1) is True
    assert len(tree) == 1
    assert _label(tree[0]) == "b"


def test_remove_unknown_returns_false() -> None:
    tree = PDPageTree()
    tree.add(_make_page("a"))
    other = _make_page("b")
    # ``other`` was never added, so its parent doesn't reference it.
    assert tree.remove(other) is False


def test_insert_before() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    c = _make_page("c")
    tree.add(a)
    tree.add(c)
    b = _make_page("b")
    tree.insert_before(b, c)
    assert [_label(p) for p in tree] == ["a", "b", "c"]


def test_insert_after() -> None:
    tree = PDPageTree()
    a = _make_page("a")
    c = _make_page("c")
    tree.add(a)
    tree.add(c)
    b = _make_page("b")
    tree.insert_after(b, a)
    assert [_label(p) for p in tree] == ["a", "b", "c"]


def test_iterates_nested_page_tree() -> None:
    """Nested intermediate /Pages node must be flattened in document order."""
    inner = COSDictionary()
    inner.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    inner_kids = COSArray()
    inner.set_item(COSName.KIDS, inner_kids)  # type: ignore[attr-defined]
    leaf1 = _make_page("a")
    leaf2 = _make_page("b")
    leaf1.get_cos_object().set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    leaf2.get_cos_object().set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    inner_kids.add(leaf1.get_cos_object())
    inner_kids.add(leaf2.get_cos_object())
    inner.set_int(COSName.COUNT, 2)  # type: ignore[attr-defined]

    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    root_kids = COSArray()
    root.set_item(COSName.KIDS, root_kids)  # type: ignore[attr-defined]
    root_kids.add(inner)
    inner.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    leaf3 = _make_page("c")
    leaf3.get_cos_object().set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    root_kids.add(leaf3.get_cos_object())
    root.set_int(COSName.COUNT, 3)  # type: ignore[attr-defined]

    tree = PDPageTree(root)
    assert [_label(p) for p in tree] == ["a", "b", "c"]
    assert len(tree) == 3


def test_get_inheritable_attribute() -> None:
    grandparent = COSDictionary()
    grandparent.set_int(COSName.get_pdf_name("Rotate"), 90)
    parent = COSDictionary()
    parent.set_item(COSName.PARENT, grandparent)  # type: ignore[attr-defined]
    leaf = COSDictionary()
    leaf.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]

    value = PDPageTree.get_inheritable_attribute(leaf, COSName.get_pdf_name("Rotate"))
    assert isinstance(value, COSInteger)
    assert value.value == 90


def test_inheritable_attribute_missing_returns_none() -> None:
    leaf = COSDictionary()
    assert PDPageTree.get_inheritable_attribute(leaf, COSName.get_pdf_name("Foo")) is None


def test_inheritable_attribute_breaks_cycles() -> None:
    """A pathological /Parent cycle must not loop forever."""
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(COSName.PARENT, b)  # type: ignore[attr-defined]
    b.set_item(COSName.PARENT, a)  # type: ignore[attr-defined]
    assert PDPageTree.get_inheritable_attribute(a, COSName.get_pdf_name("X")) is None


def test_count_recomputed_when_stored_count_wrong() -> None:
    """If /Count disagrees with the actual walk, the walk wins."""
    tree = PDPageTree()
    tree.add(_make_page())
    tree.add(_make_page())
    # Stomp on /Count to lie about the size.
    tree.get_cos_object().set_int(COSName.COUNT, 99)  # type: ignore[attr-defined]
    assert len(tree) == 2  # walk wins


def test_constructor_repairs_bare_page_root() -> None:
    """PDFBOX-3154: a page-tree root that is itself a /Type /Page dict
    must be wrapped in a synthetic /Pages node with one /Kid."""
    raw_page = COSDictionary()
    raw_page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    raw_page.set_string(COSName.get_pdf_name("Label"), "lonely")
    tree = PDPageTree(raw_page)
    # The root is no longer the page itself.
    assert tree.get_cos_object() is not raw_page
    assert len(tree) == 1
    only_page = tree[0]
    assert only_page.get_cos_object() is raw_page
    assert _label(only_page) == "lonely"


def test_get_sets_missing_type_to_page() -> None:
    """PDPageTree.get sanitizes /Type — missing /Type defaults to /Page
    so callers can rely on the entry being present after retrieval."""
    tree = PDPageTree()
    p = _make_page("untyped")
    # Strip the /Type entry that PDPage's constructor wrote.
    p.get_cos_object().remove_item(COSName.TYPE)  # type: ignore[attr-defined]
    tree.add(p)
    fetched = tree[0]
    assert fetched.get_cos_object().get_name(COSName.TYPE) == "Page"  # type: ignore[attr-defined]


def test_get_rejects_non_page_type() -> None:
    """A /Type that isn't /Page should not be silently accepted on
    leaf retrieval — upstream throws IllegalStateException."""
    tree = PDPageTree()
    bogus = COSDictionary()
    bogus.set_item(COSName.TYPE, COSName.get_pdf_name("Bogus"))  # type: ignore[attr-defined]
    # add() doesn't validate, but get()'s sanitize_type does.
    tree.add(bogus)
    with pytest.raises(ValueError, match="Expected 'Page'"):
        _ = tree[0]


def test_remove_at_returns_removed_page() -> None:
    """``remove_at(int)`` mirrors upstream's ``remove(int)`` overload —
    splice by index, return the page, decrement the count chain."""
    tree = PDPageTree()
    a = _make_page("a")
    b = _make_page("b")
    c = _make_page("c")
    for page in (a, b, c):
        tree.add(page)

    removed = tree.remove_at(1)
    assert removed.get_cos_object() is b.get_cos_object()
    assert [_label(p) for p in tree] == ["a", "c"]
    assert len(tree) == 2


def test_remove_at_negative_index() -> None:
    """``remove_at`` reuses ``__getitem__`` semantics — negative indices
    address from the end."""
    tree = PDPageTree()
    a = _make_page("a")
    b = _make_page("b")
    tree.add(a)
    tree.add(b)

    removed = tree.remove_at(-1)
    assert _label(removed) == "b"
    assert [_label(p) for p in tree] == ["a"]


def test_remove_at_out_of_range() -> None:
    tree = PDPageTree()
    tree.add(_make_page("only"))
    with pytest.raises(IndexError):
        tree.remove_at(5)


def test_inheritable_attribute_walks_via_p_alias() -> None:
    """Inheritable lookup must follow the legacy ``/P`` parent shortcut
    when ``/Parent`` is absent (matches upstream
    ``getCOSDictionary(PARENT, P)``)."""
    grandparent = COSDictionary()
    grandparent.set_int(COSName.get_pdf_name("Rotate"), 270)
    parent = COSDictionary()
    parent.set_item(COSName.get_pdf_name("P"), grandparent)
    leaf = COSDictionary()
    leaf.set_item(COSName.get_pdf_name("P"), parent)

    value = PDPageTree.get_inheritable_attribute(leaf, COSName.get_pdf_name("Rotate"))
    assert isinstance(value, COSInteger)
    assert value.value == 270


# ---------- is_page_tree_node ----------


def test_is_page_tree_node_true_for_pages_type() -> None:
    """``/Type /Pages`` always counts as an intermediate page-tree node."""
    node = COSDictionary()
    node.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    assert PDPageTree.is_page_tree_node(node) is True


def test_is_page_tree_node_true_for_kids_without_type() -> None:
    """Some malformed PDFs (PDFBOX-2250-229205.pdf) omit ``/Type /Pages``
    but still carry ``/Kids``; upstream's heuristic treats those as
    intermediates so we don't drop entire subtrees on read."""
    node = COSDictionary()
    node.set_item(COSName.KIDS, COSArray())  # type: ignore[attr-defined]
    assert PDPageTree.is_page_tree_node(node) is True


def test_is_page_tree_node_false_for_leaf_page() -> None:
    """A leaf ``/Type /Page`` (with no ``/Kids``) is *not* an intermediate."""
    page = COSDictionary()
    page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    assert PDPageTree.is_page_tree_node(page) is False


def test_is_page_tree_node_false_for_none() -> None:
    """``None`` mirrors upstream's null-check fall-through (``node != null``)."""
    assert PDPageTree.is_page_tree_node(None) is False


# ---------- get_kids ----------


def test_get_kids_returns_dictionary_entries() -> None:
    """Direct-dict kids are surfaced verbatim, in array order."""
    a = COSDictionary()
    a.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    b = COSDictionary()
    b.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    node = COSDictionary()
    node.set_item(COSName.KIDS, COSArray([a, b]))  # type: ignore[attr-defined]

    kids = PDPageTree.get_kids(node)
    assert kids == [a, b]


def test_get_kids_repairs_null_entry_in_place() -> None:
    """Mirrors upstream's ``"replaced null entry with an empty page"`` repair
    — a ``null`` slot in /Kids becomes a fresh ``/Type /Page`` placeholder
    *and* the slot in the underlying COSArray is mutated to match (so a
    second call sees the same dict, not another fresh one)."""
    real_page = COSDictionary()
    real_page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    kids_array = COSArray([real_page, None])  # type: ignore[list-item]
    node = COSDictionary()
    node.set_item(COSName.KIDS, kids_array)  # type: ignore[attr-defined]

    kids = PDPageTree.get_kids(node)
    assert len(kids) == 2
    assert kids[0] is real_page
    assert isinstance(kids[1], COSDictionary)
    assert kids[1].get_name(COSName.TYPE) == "Page"  # type: ignore[attr-defined]
    # The repair is in-place — a second call re-uses the same placeholder.
    repaired = kids[1]
    assert PDPageTree.get_kids(node)[1] is repaired


def test_get_kids_skips_non_dictionary_entries() -> None:
    """Non-null, non-dictionary entries (e.g. a stray COSName from a
    corrupted /Kids) are skipped silently."""
    page = COSDictionary()
    page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    kids_array = COSArray()
    kids_array.add(page)
    kids_array.add(COSName.get_pdf_name("Bogus"))

    node = COSDictionary()
    node.set_item(COSName.KIDS, kids_array)  # type: ignore[attr-defined]

    kids = PDPageTree.get_kids(node)
    assert kids == [page]


def test_get_kids_empty_when_no_kids_array() -> None:
    """Missing /Kids yields the empty list (upstream short-circuits to
    ``Collections.emptyList()``)."""
    node = COSDictionary()
    assert PDPageTree.get_kids(node) == []


# ---------- Wave 200: get_count direct /Count read ----------


def test_get_count_reads_count_entry_directly() -> None:
    """``get_count()`` must mirror upstream's ``root.getInt(COUNT, 0)`` —
    it returns whatever is stored, NOT a walk-validated count."""
    tree = PDPageTree()
    tree.add(_make_page())
    tree.add(_make_page())
    # Stomp on /Count to lie about the size — get_count() must report the lie.
    tree.get_cos_object().set_int(COSName.COUNT, 42)  # type: ignore[attr-defined]
    assert tree.get_count() == 42
    # len() still walks the tree and reports the true count of 2.
    assert len(tree) == 2


def test_get_count_default_zero_when_count_absent() -> None:
    """Upstream's ``getInt(COUNT, 0)`` defaults to 0 when /Count is missing."""
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    root.set_item(COSName.KIDS, COSArray())  # type: ignore[attr-defined]
    # Note: deliberately do NOT set /Count.
    tree = PDPageTree(root)
    assert tree.get_count() == 0


def test_get_count_handles_non_integer_entry_as_zero() -> None:
    """A malformed non-integer /Count (e.g. accidental name) must default
    to 0, mirroring upstream's ``getInt`` coercion semantics."""
    tree = PDPageTree()
    tree.get_cos_object().set_item(
        COSName.get_pdf_name("Count"), COSName.get_pdf_name("Bogus")
    )
    assert tree.get_count() == 0


# ---------- Wave 260: __contains__, __bool__, is_empty, has_page ----------


def test_contains_protocol_finds_member_page() -> None:
    """``page in tree`` is the Pythonic spelling of ``index_of(page) >= 0``
    and must resolve direct ``PDPage`` instances reachable from the root."""
    tree = PDPageTree()
    p1 = _make_page("first")
    p2 = _make_page("second")
    tree.add(p1)
    tree.add(p2)
    assert p1 in tree
    assert p2 in tree


def test_contains_protocol_rejects_non_member_page() -> None:
    """A page not added to the tree must report False, matching
    ``index_of`` returning ``-1``."""
    tree = PDPageTree()
    tree.add(_make_page("first"))
    orphan = _make_page("orphan")
    assert orphan not in tree


def test_contains_protocol_accepts_raw_cos_dictionary() -> None:
    """``__contains__`` must accept a raw ``COSDictionary`` page backing
    in addition to a ``PDPage`` wrapper, mirroring ``index_of``'s flexible
    accessor signature."""
    tree = PDPageTree()
    p = _make_page("first")
    tree.add(p)
    assert p.get_cos_object() in tree


def test_contains_protocol_returns_false_for_non_page_object() -> None:
    """Arbitrary non-page objects must short-circuit to False rather than
    walking the tree (defensive against callers passing strings or ints)."""
    tree = PDPageTree()
    tree.add(_make_page())
    assert "not a page" not in tree
    assert 0 not in tree  # would otherwise look like an index lookup
    assert None not in tree


def test_bool_protocol_empty_tree_is_falsy() -> None:
    """An empty tree must be falsy so callers can write ``if tree:`` to
    test for any pages without an explicit ``len(tree) > 0``."""
    tree = PDPageTree()
    assert bool(tree) is False
    assert not tree


def test_bool_protocol_populated_tree_is_truthy() -> None:
    """A populated tree is truthy regardless of the stored ``/Count``."""
    tree = PDPageTree()
    tree.add(_make_page())
    assert bool(tree) is True


def test_is_empty_predicate_matches_len_zero() -> None:
    """``is_empty()`` mirrors Java's ``Collection.isEmpty()`` and must
    agree with ``len(self) == 0``."""
    tree = PDPageTree()
    assert tree.is_empty() is True
    tree.add(_make_page())
    assert tree.is_empty() is False


def test_has_page_predicate_finds_member() -> None:
    """``has_page`` is the named alias for ``index_of(page) >= 0``."""
    tree = PDPageTree()
    p = _make_page("first")
    tree.add(p)
    assert tree.has_page(p) is True


def test_has_page_predicate_returns_false_for_orphan() -> None:
    tree = PDPageTree()
    tree.add(_make_page("first"))
    orphan = _make_page("orphan")
    assert tree.has_page(orphan) is False


def test_has_page_accepts_raw_cos_dictionary() -> None:
    """Like ``index_of``, ``has_page`` accepts the raw page dictionary."""
    tree = PDPageTree()
    p = _make_page("first")
    tree.add(p)
    assert tree.has_page(p.get_cos_object()) is True


# ---------- Wave 260: is_page_dict + get_parent static helpers ----------


def test_is_page_dict_true_for_typed_page() -> None:
    """A dict with ``/Type /Page`` is a leaf page."""
    page = COSDictionary()
    page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    assert PDPageTree.is_page_dict(page) is True


def test_is_page_dict_false_for_typed_pages_intermediate() -> None:
    """A dict with ``/Type /Pages`` is an intermediate, not a page leaf."""
    node = COSDictionary()
    node.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    assert PDPageTree.is_page_dict(node) is False


def test_is_page_dict_true_for_untyped_dict_without_kids() -> None:
    """No ``/Type`` and no ``/Kids`` falls back to "looks like a page"
    (matches the lenient upstream detection used in `_walk`)."""
    node = COSDictionary()
    assert PDPageTree.is_page_dict(node) is True


def test_is_page_dict_false_for_untyped_dict_with_kids() -> None:
    """A dict with ``/Kids`` but no ``/Type`` is treated as an intermediate
    rather than a leaf — mirrors upstream's ``isPageTreeNode`` heuristic."""
    node = COSDictionary()
    node.set_item(COSName.KIDS, COSArray())  # type: ignore[attr-defined]
    assert PDPageTree.is_page_dict(node) is False


def test_is_page_dict_false_for_none() -> None:
    """``None`` is rejected up-front — the helper is null-safe."""
    assert PDPageTree.is_page_dict(None) is False


def test_get_parent_resolves_parent_key() -> None:
    """``get_parent`` must return the ``/Parent`` dict when present."""
    parent = COSDictionary()
    parent.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    child = COSDictionary()
    child.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    assert PDPageTree.get_parent(child) is parent


def test_get_parent_falls_back_to_p_alias() -> None:
    """Mirrors upstream's ``getCOSDictionary(PARENT, P)`` fallback — when
    ``/Parent`` is absent the helper must consult the legacy ``/P`` key."""
    parent = COSDictionary()
    child = COSDictionary()
    child.set_item(COSName.get_pdf_name("P"), parent)
    assert PDPageTree.get_parent(child) is parent


def test_get_parent_returns_none_when_no_parent_or_p() -> None:
    """Orphan dictionaries return ``None`` rather than raising."""
    orphan = COSDictionary()
    assert PDPageTree.get_parent(orphan) is None


def test_get_parent_returns_none_when_parent_is_not_dictionary() -> None:
    """A non-dictionary ``/Parent`` (malformed PDF) is filtered out."""
    child = COSDictionary()
    # Set /Parent to a non-dict value (a name) to simulate malformed input.
    child.set_item(COSName.PARENT, COSName.PAGE)  # type: ignore[attr-defined]
    assert PDPageTree.get_parent(child) is None
