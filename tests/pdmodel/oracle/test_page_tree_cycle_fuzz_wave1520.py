"""Live PDFBox differential for malformed page-tree traversal (wave 1520)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")
_PAGES = COSName.get_pdf_name("Pages")
_KIDS = COSName.get_pdf_name("Kids")
_COUNT = COSName.get_pdf_name("Count")
_PARENT = COSName.get_pdf_name("Parent")
_PROBE_ID = COSName.get_pdf_name("ProbeID")
_INHERITED = COSName.get_pdf_name("ProbeInherited")
_CASE_IDS = [f"P{i:02d}" for i in range(1, 24)]


class _CaseData:
    def __init__(
        self,
        root: COSDictionary,
        inherited_node: COSDictionary | None = None,
    ) -> None:
        self.root = root
        self.inherited_node = inherited_node


def _root(count: int) -> COSDictionary:
    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)
    root.set_item(_KIDS, COSArray())
    root.set_int(_COUNT, count)
    return root


def _kids(node: COSDictionary) -> COSArray:
    kids = node.get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    return kids


def _leaf(identifier: str) -> COSDictionary:
    leaf = COSDictionary()
    leaf.set_item(_TYPE, _PAGE)
    leaf.set_string(_PROBE_ID, identifier)
    return leaf


def _build(case_id: str) -> _CaseData:
    root = _root(1)
    if case_id == "P01":
        root.set_int(_COUNT, 2)
        _kids(root).add(_leaf("a"))
        _kids(root).add(_leaf("b"))
    elif case_id == "P02":
        _kids(root).add(root)
    elif case_id == "P03":
        node = _root(1)
        _kids(root).add(node)
        _kids(node).add(root)
    elif case_id == "P04":
        root.set_item(_KIDS, COSInteger.ONE)
    elif case_id == "P05":
        root.remove_item(_KIDS)
    elif case_id == "P06":
        _kids(root).add(COSNull.NULL)
    elif case_id == "P07":
        root.set_int(_COUNT, 2)
        _kids(root).add(COSInteger.ONE)
        _kids(root).add(COSName.get_pdf_name("BadKid"))
        _kids(root).add(COSNull.NULL)
        _kids(root).add(_leaf("a"))
    elif case_id == "P08":
        _kids(root).add(_leaf("a"))
        _kids(root).add(_leaf("b"))
    elif case_id == "P09":
        root.set_int(_COUNT, 3)
        _kids(root).add(_leaf("a"))
    elif case_id == "P10":
        root.set_int(_COUNT, 2)
        leaf = _leaf("a")
        _kids(root).add(leaf)
        _kids(root).add(leaf)
    elif case_id == "P11":
        root.set_int(_COUNT, 2)
        node = _root(1)
        _kids(node).add(_leaf("a"))
        _kids(root).add(node)
        _kids(root).add(node)
    elif case_id == "P12":
        node = root
        for _ in range(256):
            child = _root(1)
            _kids(node).add(child)
            node = child
        _kids(node).add(_leaf("deep"))
    elif case_id == "P13":
        leaf = COSDictionary()
        leaf.set_string(_PROBE_ID, "missing")
        _kids(root).add(leaf)
    elif case_id == "P14":
        leaf = _leaf("wrong")
        leaf.set_item(_TYPE, COSName.get_pdf_name("Wrong"))
        _kids(root).add(leaf)
    elif case_id == "P15":
        leaf = _leaf("integer")
        leaf.set_item(_TYPE, COSInteger.ONE)
        _kids(root).add(leaf)
    elif case_id == "P16":
        leaf = _leaf("page-kids")
        leaf.set_item(_KIDS, COSInteger.ONE)
        _kids(root).add(leaf)
    elif case_id == "P17":
        root.remove_item(_TYPE)
        _kids(root).add(_leaf("a"))
    elif case_id == "P18":
        leaf = _leaf("self-parent")
        leaf.set_item(_PARENT, leaf)
        _kids(root).add(leaf)
        return _CaseData(root, leaf)
    elif case_id == "P19":
        leaf = _leaf("parent-cycle")
        parent_a = _root(0)
        parent_b = _root(0)
        leaf.set_item(_PARENT, parent_a)
        parent_a.set_item(_PARENT, parent_b)
        parent_b.set_item(_PARENT, parent_a)
        _kids(root).add(leaf)
        return _CaseData(root, leaf)
    elif case_id == "P20":
        leaf = _leaf("blocked-parent")
        node = _leaf("not-pages")
        node.set_string(_INHERITED, "blocked")
        leaf.set_item(_PARENT, node)
        _kids(root).add(leaf)
        return _CaseData(root, leaf)
    elif case_id == "P21":
        leaf = _leaf("inherited")
        node = _root(0)
        node.set_string(_INHERITED, "ok")
        leaf.set_item(_PARENT, node)
        _kids(root).add(leaf)
        return _CaseData(root, leaf)
    elif case_id == "P22":
        root.set_int(_COUNT, 2)
        node = _root(0)
        _kids(node).add(_leaf("hidden"))
        _kids(root).add(node)
        _kids(root).add(_leaf("direct"))
    elif case_id == "P23":
        node = _root(0)
        node.remove_item(_KIDS)
        _kids(root).add(node)
    else:
        raise ValueError(case_id)
    return _CaseData(root)


def _page_cell(page: PDPage) -> str:
    dictionary = page.get_cos_object()
    identifier = dictionary.get_string(_PROBE_ID, "-")
    type_name = dictionary.get_name_as_string(_TYPE, "-")
    return f"{identifier}:{type_name}"


def _error_cell(error: BaseException) -> str:
    if isinstance(error, RecursionError):
        return "STACK"
    if isinstance(error, IndexError):
        return "INDEX"
    if isinstance(error, (RuntimeError, ValueError)):
        return "STATE"
    return f"ERR:{type(error).__name__}"


def _call_cell(call: Callable[[], PDPage]) -> str:
    try:
        return _page_cell(call())
    except BaseException as error:
        return _error_cell(error)


def _iteration_cell(tree: PDPageTree) -> str:
    try:
        pages = [_page_cell(page) for page in tree]
        return ",".join(pages) if pages else "-"
    except BaseException as error:
        return _error_cell(error)


def _inherited_cell(node: COSDictionary | None) -> str:
    if node is None:
        return "-"
    value = PDPageTree.get_inheritable_attribute(node, _INHERITED)
    return value.get_string() if isinstance(value, COSString) else "null"


def _first_parent_cell(root: COSDictionary) -> str:
    kids = root.get_dictionary_object(_KIDS)
    if not isinstance(kids, COSArray) or kids.size() == 0:
        return "-"
    first = kids.get_object(0)
    if not isinstance(first, COSDictionary):
        return "-"
    parent = first.get_dictionary_object(_PARENT)
    if not isinstance(parent, COSDictionary):
        return "null"
    return "root" if parent is root else "other"


def _python_line(case_id: str) -> str:
    data = _build(case_id)
    tree = PDPageTree(data.root)
    iteration = _iteration_cell(tree)
    return (
        f"CASE {case_id} iter={iteration} count={tree.get_count()} "
        f"get0={_call_cell(lambda: tree.get(0))} "
        f"get1={_call_cell(lambda: tree.get(1))} "
        f"inherit={_inherited_cell(data.inherited_node)} "
        f"firstParent={_first_parent_cell(data.root)}"
    )


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    return {
        line.split()[1]: line
        for line in run_probe_text("PageTreeCycleFuzzProbe").splitlines()
        if line.startswith("CASE ")
    }


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS, ids=_CASE_IDS)
def test_page_tree_cycle_fuzz_matches_pdfbox(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _python_line(case_id) == java_lines[case_id]


def test_duplicate_leaf_is_iterated_twice() -> None:
    assert "iter=a:Page,a:Page" in _python_line("P10")


def test_invalid_leaf_type_is_skipped_by_iterator() -> None:
    assert "iter=-" in _python_line("P14")


def test_null_child_repair_does_not_invent_parent() -> None:
    assert _python_line("P06").endswith("firstParent=null")


def test_inheritance_stops_at_non_pages_parent() -> None:
    assert "inherit=null" in _python_line("P20")
