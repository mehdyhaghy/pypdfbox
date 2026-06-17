"""Live PDFBox differential for page-tree traversal + inherited attributes.

Wave 1546, agent C. Builds in-memory COS page trees by hand, wraps each in a
:class:`PDPageTree`, and for every reachable page projects the resolved
inheritable attributes (``/MediaBox`` ``/CropBox`` ``/Rotate`` ``/Resources``).

This sits in the gap between two existing probes:

* ``PageTreeCycleFuzzProbe`` (wave 1520) fuzzes cyclic / lying-``/Count`` /
  malformed-kid traversal but projects only a ``ProbeID:Type`` cell per page —
  it never resolves inherited boxes/rotate/resources of the located pages.
* ``PageInheritanceFuzzProbe`` (wave 1515) resolves those attributes but for a
  SINGLE round-tripped page loaded from PDF bytes — it never exercises
  multi-page sweeps, nearest-wins across several ``/Pages`` levels, a lying
  ``/Count`` during ``get(i)`` descent, or ``/Kids`` given as a direct dict.

The Java sibling is ``oracle/probes/PageTreeInheritFuzzProbe.java``; both sides
project the identical framed grammar so the comparison is exact::

    CASE <id> count=<n> iter=<cell;cell;...|-> get=<cell|ERR>,<cell|ERR>,<cell|ERR>

with each page cell ``<probeid>|mb=<rect>|cb=<rect>|rot=<n>|res=<present|null>``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSNull,
)
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")
_PAGES = COSName.get_pdf_name("Pages")
_KIDS = COSName.get_pdf_name("Kids")
_COUNT = COSName.get_pdf_name("Count")
_PARENT = COSName.get_pdf_name("Parent")
_MEDIA_BOX = COSName.get_pdf_name("MediaBox")
_CROP_BOX = COSName.get_pdf_name("CropBox")
_ROTATE = COSName.get_pdf_name("Rotate")
_RESOURCES = COSName.get_pdf_name("Resources")
_FONT = COSName.get_pdf_name("Font")
_PROBE_ID = COSName.get_pdf_name("ProbeID")
_GET_SWEEP = 3
_CASE_IDS = [f"I{i:02d}" for i in range(1, 21)]


def _pages(count: int) -> COSDictionary:
    node = COSDictionary()
    node.set_item(_TYPE, _PAGES)
    node.set_item(_KIDS, COSArray())
    node.set_int(_COUNT, count)
    return node


def _kids(node: COSDictionary) -> COSArray:
    kids = node.get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    return kids


def _page(identifier: str) -> COSDictionary:
    leaf = COSDictionary()
    leaf.set_item(_TYPE, _PAGE)
    leaf.set_string(_PROBE_ID, identifier)
    return leaf


def _attach(parent: COSDictionary, kid: COSDictionary) -> COSDictionary:
    _kids(parent).add(kid)
    kid.set_item(_PARENT, parent)
    return kid


def _rect(a: float, b: float, c: float, d: float) -> COSArray:
    r = COSArray()
    for v in (a, b, c, d):
        r.add(COSFloat(float(v)))
    return r


def _build(case_id: str) -> COSDictionary:  # noqa: PLR0912, C901
    root = _pages(1)
    if case_id == "I01":
        root.set_int(_COUNT, 2)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 100, 200))
        root.set_int(_ROTATE, 90)
        root.set_item(_RESOURCES, COSDictionary())
        _attach(root, _page("a"))
        _attach(root, _page("b"))
    elif case_id == "I02":
        root.set_item(_MEDIA_BOX, _rect(0, 0, 100, 200))
        root.set_int(_ROTATE, 90)
        leaf = _page("a")
        leaf.set_item(_MEDIA_BOX, _rect(0, 0, 300, 400))
        leaf.set_int(_ROTATE, 180)
        _attach(root, leaf)
    elif case_id == "I03":
        root.set_item(_MEDIA_BOX, _rect(0, 0, 50, 60))
        root.set_int(_ROTATE, 270)
        mid = _attach(root, _pages(1))
        deep = _attach(mid, _pages(1))
        _attach(deep, _page("deep"))
    elif case_id == "I04":
        root.set_int(_COUNT, 1)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 10, 10))
        mid = _attach(root, _pages(1))
        mid.set_item(_MEDIA_BOX, _rect(0, 0, 222, 333))
        _attach(mid, _page("midwins"))
    elif case_id == "I05":
        _attach(root, _page("letter"))
    elif case_id == "I06":
        root.set_item(_CROP_BOX, _rect(-50, -50, 999, 999))
        leaf = _page("cropclip")
        leaf.set_item(_MEDIA_BOX, _rect(0, 0, 300, 400))
        _attach(root, leaf)
    elif case_id == "I07":
        root.set_item(_RESOURCES, COSDictionary())
        _attach(root, _page("resinh"))
    elif case_id == "I08":
        leaf = _page("directkid")
        leaf.set_item(_MEDIA_BOX, _rect(0, 0, 11, 22))
        leaf.set_item(_PARENT, root)
        root.set_item(_KIDS, leaf)
        root.set_int(_COUNT, 1)
    elif case_id == "I09":
        root.set_int(_COUNT, 5)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 1, 2))
        _attach(root, _page("lie"))
    elif case_id == "I10":
        root.set_int(_COUNT, 1)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 7, 8))
        _kids(root).add(root)
        _attach(root, _page("aftercycle"))
    elif case_id == "I11":
        root.set_int(_COUNT, 1)
        mid = _attach(root, _pages(1))
        _kids(mid).add(root)
        _attach(mid, _page("cyc"))
    elif case_id == "I12":
        junk = COSDictionary()
        junk.set_item(_FONT, COSDictionary())
        junk.set_item(_PARENT, root)
        _kids(root).add(junk)
        _attach(root, _page("afterjunk"))
        root.set_int(_COUNT, 1)
    elif case_id == "I13":
        root.remove_item(_TYPE)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 9, 9))
        _attach(root, _page("notype"))
    elif case_id == "I14":
        root.set_int(_ROTATE, 90)
        leaf = _page("rot0")
        leaf.set_int(_ROTATE, 0)
        _attach(root, leaf)
    elif case_id == "I15":
        fake_parent = _page("fakeparent")
        fake_parent.set_item(_MEDIA_BOX, _rect(0, 0, 500, 500))
        leaf = _page("blocked")
        leaf.set_item(_PARENT, fake_parent)
        _kids(root).add(leaf)
        root.set_int(_COUNT, 1)
    elif case_id == "I16":
        root.set_int(_COUNT, 3)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 100, 100))
        group = _attach(root, _pages(2))
        group.set_int(_COUNT, 2)
        group.set_item(_MEDIA_BOX, _rect(0, 0, 200, 200))
        _attach(group, _page("ginh"))
        own = _page("gown")
        own.set_item(_MEDIA_BOX, _rect(0, 0, 300, 300))
        _attach(group, own)
        _attach(root, _page("rootlevel"))
    elif case_id == "I17":
        root.set_int(_ROTATE, 90)
        leaf = _page("rot45")
        leaf.set_int(_ROTATE, 45)
        _attach(root, leaf)
    elif case_id == "I18":
        root.set_item(_MEDIA_BOX, _rect(10, 20, 110, 220))
        _attach(root, _page("nocrop"))
    elif case_id == "I19":
        root.set_int(_COUNT, 0)
    elif case_id == "I20":
        root.set_int(_COUNT, 2)
        root.set_item(_MEDIA_BOX, _rect(0, 0, 80, 90))
        _kids(root).add(COSNull.NULL)
        _attach(root, _page("after_null"))
    else:
        raise ValueError(case_id)
    return root


def _fmt(v: float) -> str:
    """612.0 -> '612' but 612.5 -> '612.5' (mirror the probe's Java fmt)."""
    if v == int(v):
        return str(int(v))
    return str(float(v))


def _rect_cell(r: PDRectangle) -> str:
    return (
        f"{_fmt(r.lower_left_x)},{_fmt(r.lower_left_y)},"
        f"{_fmt(r.upper_right_x)},{_fmt(r.upper_right_y)}"
    )


def _error_cell(error: BaseException) -> str:
    if isinstance(error, RecursionError):
        return "STACK"
    if isinstance(error, IndexError):
        return "INDEX"
    if isinstance(error, (RuntimeError, ValueError)):
        return "STATE"
    return f"ERR:{type(error).__name__}"


def _safe(call: Callable[[], str]) -> str:
    try:
        return call()
    except BaseException as error:  # noqa: BLE001
        return _error_cell(error)


def _page_cell(page: PDPage) -> str:
    dictionary = page.get_cos_object()
    pid = dictionary.get_string(_PROBE_ID, "-")
    mb = _safe(lambda: _rect_cell(page.get_media_box()))
    cb = _safe(lambda: _rect_cell(page.get_crop_box()))
    rot = _safe(lambda: str(page.get_rotation()))
    res = _safe(lambda: "present" if page.get_resources() is not None else "null")
    return f"{pid}|mb={mb}|cb={cb}|rot={rot}|res={res}"


def _iteration_cell(tree: PDPageTree) -> str:
    try:
        cells = [_page_cell(page) for page in tree]
        return ";".join(cells) if cells else "-"
    except BaseException as error:  # noqa: BLE001
        return _error_cell(error)


def _get_cell(tree: PDPageTree, index: int) -> str:
    try:
        return _page_cell(tree.get(index))
    except BaseException as error:  # noqa: BLE001
        return _error_cell(error)


def _python_line(case_id: str) -> str:
    root = _build(case_id)
    tree = PDPageTree(root)
    gets = ",".join(_get_cell(tree, i) for i in range(_GET_SWEEP))
    return (
        f"CASE {case_id} count={tree.get_count()} "
        f"iter={_iteration_cell(tree)} get={gets}"
    )


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    return {
        line.split()[1]: line
        for line in run_probe_text("PageTreeInheritFuzzProbe").splitlines()
        if line.startswith("CASE ")
    }


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS, ids=_CASE_IDS)
def test_page_tree_inherit_fuzz_matches_pdfbox(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _python_line(case_id) == java_lines[case_id]


# ----- value-pinned regressions (run without the live oracle) -----
# Expected strings copied verbatim from the PDFBox-3.0.7 probe output so the
# behaviour is pinned even on a machine without the jar/JDK.


def test_inherited_attributes_apply_to_every_page() -> None:
    # Both pages inherit root MediaBox + Rotate + Resources.
    assert _python_line("I01") == (
        "CASE I01 count=2 "
        "iter=a|mb=0,0,100,200|cb=0,0,100,200|rot=90|res=present;"
        "b|mb=0,0,100,200|cb=0,0,100,200|rot=90|res=present "
        "get=a|mb=0,0,100,200|cb=0,0,100,200|rot=90|res=present,"
        "b|mb=0,0,100,200|cb=0,0,100,200|rot=90|res=present,INDEX"
    )


def test_nearest_level_wins_over_inherited() -> None:
    # Leaf MediaBox/Rotate override the root's.
    assert "mb=0,0,300,400" in _python_line("I02")
    assert "rot=180" in _python_line("I02")
    # Intermediate /Pages MediaBox wins over the root's.
    assert "mb=0,0,222,333" in _python_line("I04")


def test_media_box_absent_everywhere_is_us_letter() -> None:
    assert "mb=0,0,612,792" in _python_line("I05")


def test_direct_dict_kids_is_not_traversed() -> None:
    # Upstream treats /Kids only as an array; a direct dict yields no pages.
    assert _python_line("I08") == "CASE I08 count=1 iter=- get=STATE,STATE,INDEX"


def test_lying_count_is_reported_but_get_runs_out() -> None:
    line = _python_line("I09")
    assert line.startswith("CASE I09 count=5 ")
    # Only one real page; get(1) past the real walk -> STATE.
    assert line.endswith("res=null,STATE,STATE")


def test_self_kids_cycle_iterates_twice_but_get_guards() -> None:
    # Iteration visits the page twice (root re-enters its own /Kids once);
    # get(0) trips the recursion guard -> STATE.
    line = _python_line("I10")
    assert "aftercycle|mb=0,0,7,8" in line
    assert " get=STATE,INDEX,STATE" in line


def test_inheritance_stops_at_non_pages_parent() -> None:
    # Leaf's /Parent is a /Page (not /Pages): the MediaBox there is NOT
    # inherited -> US Letter default.
    assert "blocked|mb=0,0,612,792" in _python_line("I15")


def test_rotate_override_to_zero_at_leaf() -> None:
    assert "rot0|mb=0,0,612,792|cb=0,0,612,792|rot=0" in _python_line("I14")


def test_off_axis_leaf_rotate_terminates_walk_and_reads_zero() -> None:
    # Leaf carries Rotate 45 (terminates the inheritable walk), getRotation
    # rejects the non-multiple-of-90 -> 0, NOT the inherited 90.
    assert "rot45|mb=0,0,612,792|cb=0,0,612,792|rot=0" in _python_line("I17")


def test_null_kid_repaired_to_empty_letter_page() -> None:
    line = _python_line("I20")
    assert line.startswith("CASE I20 count=2 ")
    assert "-|mb=0,0,612,792" in line
    assert "after_null|mb=0,0,80,90" in line


def test_empty_tree_get_is_index_error() -> None:
    assert _python_line("I19") == "CASE I19 count=0 iter=- get=INDEX,STATE,INDEX"
