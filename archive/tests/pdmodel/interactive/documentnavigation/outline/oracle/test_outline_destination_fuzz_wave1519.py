"""Live PDFBox differential fuzz for outline destination resolution.

All cases match Apache PDFBox 3.0.7 line-for-line. The former ``page_float``
recursion-guard divergence was CLOSED in wave 1595: ``find_destination_page``
now mirrors upstream ``doc.getPage(pageNumber)`` (a fresh per-lookup
``PDPageTree``), so a float ``/D[0]`` resolved after an out-of-bounds sibling
lookup on the shared document returns the page exactly as upstream does."""

from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem
from tests.oracle.harness import requires_oracle, run_probe_text

_DEST = COSName.get_pdf_name("Dest")
_A = COSName.get_pdf_name("A")
_S = COSName.get_pdf_name("S")
_D = COSName.get_pdf_name("D")


def _dest(page, type_name: str) -> COSArray:
    array = COSArray()
    array.add(page)
    array.add(COSName.get_pdf_name(type_name))
    return array


def _go_to(page) -> COSDictionary:
    action = COSDictionary()
    action.set_item(_S, COSName.get_pdf_name("GoTo"))
    action.set_item(_D, _dest(page, "Fit"))
    return action


def _item(name: str, document: PDDocument) -> COSDictionary:
    dictionary = COSDictionary()
    if name == "dest_integer":
        dictionary.set_item(_DEST, COSInteger.ONE)
    elif name == "dest_string":
        dictionary.set_item(_DEST, COSString("missing"))
    elif name == "dest_empty_array":
        dictionary.set_item(_DEST, COSArray())
    elif name == "dest_unknown_type":
        dictionary.set_item(_DEST, _dest(COSInteger.ZERO, "Bogus"))
    elif name == "page_zero":
        dictionary.set_item(_DEST, _dest(COSInteger.ZERO, "Fit"))
    elif name == "page_one":
        dictionary.set_item(_DEST, _dest(COSInteger.ONE, "Fit"))
    elif name == "page_oob":
        dictionary.set_item(_DEST, _dest(COSInteger.get(2), "Fit"))
    elif name == "page_negative":
        dictionary.set_item(_DEST, _dest(COSInteger.get(-1), "Fit"))
    elif name == "page_float":
        dictionary.set_item(_DEST, _dest(COSFloat(1.9), "Fit"))
    elif name == "page_direct":
        dictionary.set_item(_DEST, _dest(document.get_page(1).get_cos_object(), "Fit"))
    elif name == "action_page_one":
        dictionary.set_item(_A, _go_to(COSInteger.ONE))
    elif name == "bad_dest_valid_action":
        dictionary.set_item(_DEST, _dest(COSInteger.ZERO, "Bogus"))
        dictionary.set_item(_A, _go_to(COSInteger.ONE))
    elif name == "wrong_action":
        dictionary.set_item(_A, COSInteger.ONE)
    return dictionary


def _destination_cell(item: PDOutlineItem) -> str:
    try:
        destination = item.get_destination()
        return "null" if destination is None else type(destination).__name__
    except Exception as exc:
        if isinstance(exc, OSError):
            name = "IOException"
        elif isinstance(exc, IndexError):
            name = "IndexOutOfBoundsException"
        else:
            name = type(exc).__name__
        return f"ERR:{name}"


def _page_cell(item: PDOutlineItem, document: PDDocument) -> str:
    try:
        found = item.find_destination_page(document)
        if found is None:
            return "null"
        for index, page in enumerate(document.get_pages()):
            if page.get_cos_object() is found:
                return str(index)
        return "foreign"
    except Exception as exc:
        if isinstance(exc, OSError):
            name = "IOException"
        elif isinstance(exc, IndexError):
            name = "IndexOutOfBoundsException"
        else:
            name = type(exc).__name__
        return f"ERR:{name}"


def _py_dump() -> str:
    cases = [
        "none",
        "dest_integer",
        "dest_string",
        "dest_empty_array",
        "dest_unknown_type",
        "page_zero",
        "page_one",
        "page_oob",
        "page_negative",
        "page_float",
        "page_direct",
        "action_page_one",
        "bad_dest_valid_action",
        "wrong_action",
    ]
    lines: list[str] = []
    with PDDocument() as document:
        document.add_page(PDPage())
        document.add_page(PDPage())
        for name in cases:
            item = PDOutlineItem(_item(name, document))
            lines.append(
                f"CASE {name} dest={_destination_cell(item)} "
                f"page={_page_cell(item, document)}\n"
            )
    return "".join(lines)


# Wave 1595: the ``page_float`` recursion-guard divergence is CLOSED. Both
# engines now resolve a float ``/D[0]`` (1.9) to page index 1 even after the
# preceding ``page_oob`` out-of-bounds lookup on the shared document, because
# ``find_destination_page`` routes through ``doc.get_page(n)`` → a fresh
# per-lookup ``PDPageTree`` exactly as upstream ``doc.getPage(n)`` does. Every
# case — including ``page_float`` — now matches PDFBox 3.0.7 line-for-line.
_EXPECTED_PAGE_FLOAT_LINE = "CASE page_float dest=PDPageFitDestination page=1"


@requires_oracle
def test_outline_destination_fuzz_matches_pdfbox() -> None:
    """Every case matches Apache PDFBox 3.0.7 line-for-line, including the
    formerly-divergent ``page_float`` case (closed in wave 1595)."""
    python_lines = _py_dump().splitlines()
    java_lines = run_probe_text("OutlineDestinationFuzzProbe").splitlines()

    assert len(python_lines) == len(java_lines)
    for py, jv in zip(python_lines, java_lines, strict=True):
        assert py == jv
        if py.startswith("CASE page_float "):
            assert py == _EXPECTED_PAGE_FLOAT_LINE, (
                f"page_float token drifted to {py!r}"
            )
