"""Live PDFBox differential fuzz for malformed page-label trees (wave 1518)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _array(*values) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


def _range(style=None, prefix=None, start=None) -> COSDictionary:
    out = COSDictionary()
    if style is not None:
        out.set_item(_N("S"), style)
    if prefix is not None:
        out.set_item(_N("P"), prefix)
    if start is not None:
        out.set_item(_N("St"), start)
    return out


def _nums(*values) -> COSDictionary:
    out = COSDictionary()
    out.set_item(_N("Nums"), _array(*values))
    return out


def _cases() -> list[tuple[str, COSDictionary]]:
    decimal = _range(_N("D"))
    child = _nums(COSInteger.get(2), _range(_N("a")))
    kids = COSDictionary()
    kids.set_item(_N("Kids"), _array(child))
    both = _nums(COSInteger.get(0), decimal)
    both.set_item(_N("Kids"), _array(child))
    return [
        ("empty", COSDictionary()),
        (
            "flat",
            _nums(
                COSInteger.get(0),
                decimal,
                COSInteger.get(3),
                _range(_N("r"), COSString("A-"), COSInteger.get(2)),
            ),
        ),
        ("odd_nums", _nums(COSInteger.get(0), decimal, COSInteger.get(3))),
        ("bad_key", _nums(COSString("0"), decimal)),
        ("negative_key", _nums(COSInteger.get(-1), decimal)),
        ("bad_value", _nums(COSInteger.get(0), COSInteger.get(7))),
        ("duplicate", _nums(COSInteger.get(0), decimal, COSInteger.get(0), _range(_N("A")))),
        ("unknown_style", _nums(COSInteger.get(0), _range(_N("Bogus"), COSString("P")))),
        ("prefix_nul", _nums(COSInteger.get(0), _range(_N("D"), COSString(b"A\x00B")))),
        ("start_zero", _nums(COSInteger.get(0), _range(_N("D"), start=COSInteger.get(0)))),
        ("start_negative", _nums(COSInteger.get(0), _range(_N("D"), start=COSInteger.get(-2)))),
        ("start_float", _nums(COSInteger.get(0), _range(_N("D"), start=COSFloat(2.9)))),
        ("kids", kids),
        ("kids_and_nums", both),
    ]


def _py_dump() -> str:
    doc = PDDocument()
    try:
        for _ in range(6):
            doc.add_page(PDPage())
        lines: list[str] = []
        for name, tree in _cases():
            try:
                labels = PDPageLabels(doc, tree)
                indices = ",".join(str(i) for i in labels.get_page_indices())
                rendered = "|".join(
                    label.replace("\x00", "<NUL>")
                    for label in labels.get_labels_by_page_indices()
                )
                lines.append(
                    f"CASE {name} count={labels.get_page_range_count()} "
                    f"indices={indices} labels={rendered}"
                )
            except Exception as exc:
                java_name = "IOException" if isinstance(exc, OSError) else type(exc).__name__
                lines.append(f"CASE {name} ERR:{java_name}")
        return "".join(line + "\n" for line in lines)
    finally:
        doc.close()


@requires_oracle
def test_page_label_tree_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("PageLabelTreeFuzzProbe")
