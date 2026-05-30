from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel import pd_page_content_stream as content_stream_module
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
    _same_kid,
)

_K = COSName.get_pdf_name("K")


def test_remove_kid_uses_integer_equivalence_when_array_remove_misses() -> None:
    node = PDStructureNode("StructElem")
    raw_kids = COSArray()
    raw_kids.add(1234)  # type: ignore[arg-type]
    raw_kids.add(COSInteger.get(9))
    node.get_cos_object().set_item(_K, raw_kids)

    assert node.remove_kid(1234) is True

    assert node.get_cos_object().get_dictionary_object(_K) == COSInteger.get(9)


def test_same_kid_matches_plain_int_and_cos_integer_in_both_orders() -> None:
    assert _same_kid(COSInteger.get(42), 42) is True
    assert _same_kid(42, COSInteger.get(42)) is True


def test_format_number_matches_pdfbox_float_fast_path() -> None:
    # PDFBox narrows the operand to float32 then formats via formatFloatFast.
    # 0.125 is exactly representable in float32, so it formats as "0.125".
    assert content_stream_module._format_number(0.125) == b"0.125"
