"""Live PDFBox differential fuzz for page-label string rendering (wave 1542).

Complements ``test_page_label_tree_fuzz_wave1518`` (which fuzzed the number-tree
STRUCTURE) by fuzzing the LABEL-STRING rendering: every valid /S style plus
unknown / missing / wrong-type styles, /St boundary values (0 / negative / huge
/ float), /P prefix forms (string / name / empty), roman subtractive boundaries
(4, 9, 40, 90, 400, 900, 3999, 4000+), alphabetic doubling past 26 (AA, ZZ,
AAA), and label computation for page indices below the first range, between
ranges, and past the last range.

Mirrors ``oracle/probes/PageLabelFuzzProbe.java`` line-for-line. Expected values
are pinned against Apache PDFBox 3.0.7 (captured from the live probe). The
``@requires_oracle`` test runs the real jar when present; the value-pinned test
runs everywhere.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
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


def _tree_cases() -> list[tuple[int, str, COSDictionary]]:
    d = _N("D")
    rl = _N("r")
    ru = _N("R")
    al = _N("a")
    au = _N("A")

    style_wrong = _range()
    style_wrong.set_item(_N("S"), COSString("D"))

    prefix_name = _range()
    prefix_name.set_item(_N("S"), COSName.get_pdf_name("D"))
    prefix_name.set_item(_N("P"), _N("Nm"))

    return [
        (
            8,
            "below_first",
            _nums(
                COSInteger.get(2), _range(d),
                COSInteger.get(5), _range(rl, COSString("R-")),
            ),
        ),
        (
            10,
            "between_ranges",
            _nums(
                COSInteger.get(0), _range(d),
                COSInteger.get(4), _range(au, COSString("App-")),
                COSInteger.get(8), _range(rl, start=COSInteger.get(1)),
            ),
        ),
        (6, "past_last", _nums(COSInteger.get(0), _range(ru))),
        (
            6,
            "out_of_order",
            _nums(
                COSInteger.get(3), _range(al),
                COSInteger.get(0), _range(d),
            ),
        ),
        (4, "no_index0", _nums(COSInteger.get(1), _range(d, COSString("P-")))),
        (3, "style_D", _nums(COSInteger.get(0), _range(d))),
        (3, "style_r", _nums(COSInteger.get(0), _range(rl))),
        (3, "style_R", _nums(COSInteger.get(0), _range(ru))),
        (3, "style_a", _nums(COSInteger.get(0), _range(al))),
        (3, "style_A", _nums(COSInteger.get(0), _range(au))),
        (3, "style_unknown", _nums(COSInteger.get(0), _range(_N("Q")))),
        (3, "style_missing", _nums(COSInteger.get(0), _range(prefix=COSString("only-")))),
        (3, "style_wrongtype", _nums(COSInteger.get(0), style_wrong)),
        (2, "prefix_string", _nums(COSInteger.get(0), _range(d, COSString("X-")))),
        (2, "prefix_empty", _nums(COSInteger.get(0), _range(d, COSString("")))),
        (2, "prefix_name", _nums(COSInteger.get(0), prefix_name)),
        (2, "st_zero", _nums(COSInteger.get(0), _range(d, start=COSInteger.get(0)))),
        (2, "st_negative", _nums(COSInteger.get(0), _range(d, start=COSInteger.get(-5)))),
        (2, "st_float", _nums(COSInteger.get(0), _range(d, start=COSFloat(3.9)))),
    ]


def _render_single(style: str | None, start: int) -> str:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        style_obj = None if style is None else COSName.get_pdf_name(style)
        labels = PDPageLabels(
            doc, _nums(COSInteger.get(0), _range(style_obj, start=COSInteger.get(start)))
        )
        arr = labels.get_labels_by_page_indices()
        if not arr or arr[0] is None:
            return "null"
        return arr[0].replace("\x00", "<NUL>")
    finally:
        doc.close()


def _style_starts_line(name: str, style: str | None, starts: list[int]) -> str:
    parts = [f"{s}={_render_single(style, s)}" for s in starts]
    return f"RANGE {name} " + "|".join(parts)


def _tree_line(pages: int, name: str, tree: COSDictionary) -> str:
    doc = PDDocument()
    try:
        for _ in range(pages):
            doc.add_page(PDPage())
        labels = PDPageLabels(doc, tree)
        indices = ",".join(str(i) for i in labels.get_page_indices())
        rendered = "|".join(
            label.replace("\x00", "<NUL>")
            for label in labels.get_labels_by_page_indices()
        )
        return (
            f"TREE {name} count={labels.get_page_range_count()} "
            f"indices={indices} labels={rendered}"
        )
    finally:
        doc.close()


def _py_dump() -> str:
    lines: list[str] = []
    for pages, name, tree in _tree_cases():
        lines.append(_tree_line(pages, name, tree))
    roman_bounds = [1, 3, 4, 8, 9, 40, 49, 90, 99, 400, 900, 3999, 4000, 4999]
    letter_bounds = [1, 26, 27, 28, 52, 53, 702, 703]
    decimal_bounds = [1, 10, 100, 1000]
    lines.append(_style_starts_line("roman_lower", "r", roman_bounds))
    lines.append(_style_starts_line("roman_upper", "R", roman_bounds))
    lines.append(_style_starts_line("letters_lower", "a", letter_bounds))
    lines.append(_style_starts_line("letters_upper", "A", letter_bounds))
    lines.append(_style_starts_line("decimal", "D", decimal_bounds))
    lines.append(_style_starts_line("nostyle", None, [1, 5]))
    return "".join(line + "\n" for line in lines)


# --- Apache PDFBox 3.0.7 expected output, captured from PageLabelFuzzProbe. ---
# Notable pins:
#   * style_wrongtype: /S stored as a COSString "D" is honoured as decimal,
#     because upstream getStyle() uses getNameAsString (not getName). pypdfbox
#     was fixed in wave 1542 to match (previously emitted prefix-only "").
#   * no_index0: PDFBox's constructor always inserts a default decimal range at
#     index 0, so a tree whose first /Nums entry is at index 1 still yields a
#     range at 0 (page 0 -> "1").
#   * st_negative / st_zero: /St is read verbatim via getInt with no clamping,
#     so negative / zero starts flow straight into decimal rendering.
#   * st_float: /St 3.9 -> getInt truncates to 3.
#   * roman >= 4000 uses the Acrobat "m-per-thousand" quirk (4000 -> mmmm).
_EXPECTED = (
    "TREE below_first count=3 indices=0,2,5 labels=1|2|1|2|3|R-i|R-ii|R-iii\n"
    "TREE between_ranges count=3 indices=0,4,8 labels=1|2|3|4|App-A|App-B|App-C|App-D|i|ii\n"
    "TREE past_last count=1 indices=0 labels=I|II|III|IV|V|VI\n"
    "TREE out_of_order count=2 indices=0,3 labels=1|2|3|a|b|c\n"
    "TREE no_index0 count=2 indices=0,1 labels=1|P-1|P-2|P-3\n"
    "TREE style_D count=1 indices=0 labels=1|2|3\n"
    "TREE style_r count=1 indices=0 labels=i|ii|iii\n"
    "TREE style_R count=1 indices=0 labels=I|II|III\n"
    "TREE style_a count=1 indices=0 labels=a|b|c\n"
    "TREE style_A count=1 indices=0 labels=A|B|C\n"
    "TREE style_unknown count=1 indices=0 labels=1|2|3\n"
    "TREE style_missing count=1 indices=0 labels=only-|only-|only-\n"
    "TREE style_wrongtype count=1 indices=0 labels=1|2|3\n"
    "TREE prefix_string count=1 indices=0 labels=X-1|X-2\n"
    "TREE prefix_empty count=1 indices=0 labels=1|2\n"
    "TREE prefix_name count=1 indices=0 labels=1|2\n"
    "TREE st_zero count=1 indices=0 labels=0|1\n"
    "TREE st_negative count=1 indices=0 labels=-5|-4\n"
    "TREE st_float count=1 indices=0 labels=3|4\n"
    "RANGE roman_lower 1=i|3=iii|4=iv|8=viii|9=ix|40=xl|49=xlix|90=xc|99=xcix|"
    "400=cd|900=cm|3999=mmmcmxcix|4000=mmmm|4999=mmmmcmxcix\n"
    "RANGE roman_upper 1=I|3=III|4=IV|8=VIII|9=IX|40=XL|49=XLIX|90=XC|99=XCIX|"
    "400=CD|900=CM|3999=MMMCMXCIX|4000=MMMM|4999=MMMMCMXCIX\n"
    "RANGE letters_lower 1=a|26=z|27=aa|28=bb|52=zz|53=aaa|"
    "702=zzzzzzzzzzzzzzzzzzzzzzzzzzz|703=aaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
    "RANGE letters_upper 1=A|26=Z|27=AA|28=BB|52=ZZ|53=AAA|"
    "702=ZZZZZZZZZZZZZZZZZZZZZZZZZZZ|703=AAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
    "RANGE decimal 1=1|10=10|100=100|1000=1000\n"
    "RANGE nostyle 1=|5=\n"
)


def test_page_label_fuzz_matches_pinned_pdfbox() -> None:
    """Value-pinned parity (runs everywhere — no jar / java needed)."""
    assert _py_dump() == _EXPECTED


@requires_oracle
def test_page_label_fuzz_matches_live_pdfbox() -> None:
    """Live differential parity against the Apache PDFBox 3.0.7 jar."""
    assert _py_dump() == run_probe_text("PageLabelFuzzProbe")


def test_get_style_honours_cosstring_value() -> None:
    """Regression: wave 1542 fix — getStyle uses getNameAsString, so a /S held
    as a COSString (wrong type, but seen in the wild) is still recognised."""
    rng = _range()
    rng.set_item(_N("S"), COSString("R"))
    label_range = PDPageLabelRange(rng)
    assert label_range.get_style() == "R"
    assert label_range.compute_label_for_offset(0) == "I"
