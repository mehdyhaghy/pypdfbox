"""Live PDFBox differential fuzz for linearization dictionary access."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.cos.pd_linearization_dictionary import PDLinearizationDictionary
from tests.oracle.harness import requires_oracle, run_probe_text


def _array(*values) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(value)
    return array


def _dict(name: str) -> COSDictionary:
    n = COSName.get_pdf_name
    d = COSDictionary()
    if name == "valid_ints":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("L"), COSInteger.get(100))
        d.set_item(n("O"), COSInteger.get(7))
        d.set_item(n("E"), COSInteger.get(80))
        d.set_item(n("N"), COSInteger.get(3))
        d.set_item(n("T"), COSInteger.get(91))
        d.set_item(n("H"), _array(COSInteger.get(11), COSInteger.get(22)))
    elif name == "valid_floats":
        d.set_item(n("Linearized"), COSFloat(1.5))
        d.set_item(n("L"), COSFloat(100.9))
        d.set_item(n("O"), COSFloat(7.9))
        d.set_item(n("E"), COSFloat(80.9))
        d.set_item(n("N"), COSFloat(3.9))
        d.set_item(n("T"), COSFloat(91.9))
        d.set_item(n("H"), _array(COSFloat(11.9), COSFloat(22.9), COSFloat(33.9), COSFloat(44.9)))
    elif name == "zero_marker":
        d.set_item(n("Linearized"), COSInteger.ZERO)
    elif name == "negative_marker":
        d.set_item(n("Linearized"), COSInteger.get(-1))
    elif name == "string_marker":
        d.set_item(n("Linearized"), COSString("1"))
        d.set_item(n("L"), COSString("100"))
        d.set_item(n("H"), COSString("11 22"))
    elif name == "bad_h_size":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), _array(COSInteger.ONE, COSInteger.TWO, COSInteger.THREE))
    elif name == "bad_h_member":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), _array(COSInteger.ONE, COSString("2")))
    elif name == "wrong_h_type":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), n("Nope"))
    elif name == "huge_ints":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("L"), COSInteger.get(2147483648))
        d.set_item(n("O"), COSInteger.get(-2147483649))
        d.set_item(n("H"), _array(COSInteger.get(2147483648), COSInteger.get(-2147483649)))
    return d


def _hint(value: tuple[int, ...] | None) -> str:
    if value is None:
        return "absent"
    return ",".join(str(item) for item in value)


def _py_dump() -> str:
    lines: list[str] = []
    for name in [
        "empty",
        "valid_ints",
        "valid_floats",
        "zero_marker",
        "negative_marker",
        "string_marker",
        "bad_h_size",
        "bad_h_member",
        "wrong_h_type",
        "huge_ints",
    ]:
        lin = PDLinearizationDictionary(_dict(name))
        lines.append(
            f"CASE {name} linearized={str(lin.is_linearized()).lower()} "
            f"version={lin.get_linearized_version():.1f} "
            f"L={lin.get_length_of_file()} "
            f"O={lin.get_first_page_object_number()} "
            f"E={lin.get_end_of_first_page()} "
            f"N={lin.get_number_of_pages()} "
            f"T={lin.get_offset_of_first_xref()} "
            f"H={_hint(lin.get_hint_table())}\n"
        )
    return "".join(lines)


@requires_oracle
def test_linearization_dictionary_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("LinearizationDictionaryFuzzProbe")
