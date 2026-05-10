from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDPageDestination,
    PDPageFitDestination,
    PDPageXYZDestination,
)

_NAMES: COSName = COSName.get_pdf_name("Names")
_KIDS: COSName = COSName.KIDS  # type: ignore[attr-defined]
_LIMITS: COSName = COSName.get_pdf_name("Limits")


def _xyz(page_number: int) -> PDPageXYZDestination:
    dest = PDPageXYZDestination()
    dest.set_page_number(page_number)
    return dest


def _fit(page_number: int) -> PDPageFitDestination:
    dest = PDPageFitDestination()
    dest.set_page_number(page_number)
    return dest


def _leaf(entries: list[tuple[str, PDPageDestination]]) -> COSDictionary:
    """Construct a leaf dict with a flat /Names array and proper /Limits."""
    leaf = COSDictionary()
    arr = COSArray()
    for key, dest in entries:
        arr.add(COSString(key))
        arr.add(dest.get_cos_object())
    leaf.set_item(_NAMES, arr)
    if entries:
        limits = COSArray()
        limits.add(COSString(entries[0][0]))
        limits.add(COSString(entries[-1][0]))
        leaf.set_item(_LIMITS, limits)
    return leaf


# --------- (1) flat /Names back-compat ---------


def test_flat_names_array_resolves_via_get_value() -> None:
    """A pre-existing flat /Names array (legacy shape) still resolves when the
    node is wrapped by the generic-backed PDDestinationNameTreeNode."""
    node = COSDictionary()
    arr = COSArray()
    arr.add(COSString("alpha"))
    arr.add(_xyz(0).get_cos_object())
    arr.add(COSString("beta"))
    arr.add(_fit(2).get_cos_object())
    node.set_item(_NAMES, arr)

    tree = PDDestinationNameTreeNode(node)

    alpha = tree.get_value("alpha")
    beta = tree.get_value("beta")
    assert isinstance(alpha, PDPageXYZDestination)
    assert alpha.get_page_number() == 0
    assert isinstance(beta, PDPageFitDestination)
    assert beta.get_page_number() == 2
    assert tree.get_value("missing") is None


# --------- (2) balanced /Kids tree (manual construction) ---------


def test_balanced_kids_tree_resolves_across_both_leaves() -> None:
    """Two leaves under one root (manually wired /Kids + /Limits) — both
    branches must be reachable through the root's get_value."""
    leaf_a = _leaf([("a-one", _xyz(1)), ("a-two", _fit(2))])
    leaf_b = _leaf([("b-one", _xyz(3)), ("b-two", _fit(4))])

    root = COSDictionary()
    kids = COSArray()
    kids.add(leaf_a)
    kids.add(leaf_b)
    root.set_item(_KIDS, kids)

    tree = PDDestinationNameTreeNode(root)

    left = tree.get_value("a-two")
    right = tree.get_value("b-one")
    assert isinstance(left, PDPageFitDestination)
    assert left.get_page_number() == 2
    assert isinstance(right, PDPageXYZDestination)
    assert right.get_page_number() == 3
    assert tree.get_value("does-not-exist") is None


# --------- (3) set_names writes /Names ---------


def test_set_names_with_dict_writes_names_array() -> None:
    tree = PDDestinationNameTreeNode()
    payload: dict[str, PDPageDestination] = {
        "first": _xyz(0),
        "second": _fit(5),
    }

    tree.set_names(payload)

    raw = tree.get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(raw, COSArray)
    # Sorted by key: "first" then "second", each followed by its COS array.
    assert raw.size() == 4
    assert isinstance(raw.get_object(0), COSString)
    assert raw.get_object(0).get_string() == "first"
    assert isinstance(raw.get_object(2), COSString)
    assert raw.get_object(2).get_string() == "second"
    # Round-trip via the typed accessor.
    assert tree.get_value("first") is not None
    assert tree.get_value("second") is not None


# --------- (4) get_names returns typed dict ---------


def test_get_names_returns_typed_destination_dict() -> None:
    tree = PDDestinationNameTreeNode()
    tree.set_names({"chapter-1": _xyz(0), "chapter-2": _fit(2)})

    names = tree.get_names()
    assert isinstance(names, dict)
    assert set(names) == {"chapter-1", "chapter-2"}
    assert isinstance(names["chapter-1"], PDPageXYZDestination)
    assert names["chapter-1"].get_page_number() == 0
    assert isinstance(names["chapter-2"], PDPageFitDestination)
    assert names["chapter-2"].get_page_number() == 2


# --------- (5) nested /Kids -> /Names entry reachable from root ---------


def test_nested_kids_to_names_entry_reachable_from_root() -> None:
    """root /Kids -> intermediate /Kids -> leaf /Names. The deeply nested
    leaf entry must still resolve from the root's get_value."""
    leaf = _leaf([("deep-key", _xyz(7))])

    intermediate = COSDictionary()
    inter_kids = COSArray()
    inter_kids.add(leaf)
    intermediate.set_item(_KIDS, inter_kids)
    inter_limits = COSArray()
    inter_limits.add(COSString("deep-key"))
    inter_limits.add(COSString("deep-key"))
    intermediate.set_item(_LIMITS, inter_limits)

    root = COSDictionary()
    root_kids = COSArray()
    root_kids.add(intermediate)
    root.set_item(_KIDS, root_kids)

    tree = PDDestinationNameTreeNode(root)
    resolved = tree.get_value("deep-key")
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 7


# --------- (6) /D-indirected destination dictionary leaf (upstream parity) ---------


def test_convert_cos_value_dereferences_d_dictionary_entry() -> None:
    """Upstream PDDestinationNameTreeNode.convertCOSToPD dereferences /D
    when the leaf value is a COSDictionary (named-destination indirection
    inlined into the leaf). Verify the same indirection works here."""
    inner_dest = _xyz(11).get_cos_object()
    wrapper = COSDictionary()
    wrapper.set_item(COSName.get_pdf_name("D"), inner_dest)

    arr = COSArray()
    arr.add(COSString("section-3"))
    arr.add(wrapper)
    node = COSDictionary()
    node.set_item(_NAMES, arr)

    tree = PDDestinationNameTreeNode(node)
    resolved = tree.get_value("section-3")
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 11


# --------- (7) PDFBOX-5975: invalid tree entry returns None, not raises ---------


def test_convert_cos_value_returns_none_for_invalid_entry() -> None:
    """PDFBOX-5975 — a leaf whose COS value is not a recognised page
    destination must surface as ``None`` rather than raise. Match upstream
    behaviour added for the same JIRA."""
    arr = COSArray()
    arr.add(COSString("bad"))
    # /D missing: convert_cos_to_value sees a dict with no /D entry, so
    # PDDestination.create receives None and returns None — must propagate
    # to a None get_value result, not raise.
    arr.add(COSDictionary())
    node = COSDictionary()
    node.set_item(_NAMES, arr)

    tree = PDDestinationNameTreeNode(node)
    assert tree.get_value("bad") is None


# --------- (8) convert_cos_to_pd: snake_case mirror of upstream typed factory ---------


def test_convert_cos_to_pd_returns_page_destination() -> None:
    """``convert_cos_to_pd`` is the snake_case mirror of upstream
    ``convertCOSToPD`` — typed-equivalent of ``convert_cos_to_value``."""
    tree = PDDestinationNameTreeNode()
    cos_dest = _xyz(4).get_cos_object()
    resolved = tree.convert_cos_to_pd(cos_dest)
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 4


def test_convert_cos_to_pd_dereferences_d_wrapper() -> None:
    """The ``/D``-indirection performed by ``convertCOSToPD`` must still
    apply when callers use the snake_case alias."""
    inner = _xyz(8).get_cos_object()
    wrapper = COSDictionary()
    wrapper.set_item(COSName.get_pdf_name("D"), inner)
    tree = PDDestinationNameTreeNode()
    resolved = tree.convert_cos_to_pd(wrapper)
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 8


def test_convert_cos_to_pd_returns_none_for_invalid() -> None:
    """PDFBOX-5975 behaviour also reachable via ``convert_cos_to_pd``."""
    tree = PDDestinationNameTreeNode()
    # A dict without /D resolves to None upstream.
    assert tree.convert_cos_to_pd(COSDictionary()) is None
