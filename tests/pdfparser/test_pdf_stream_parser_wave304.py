from __future__ import annotations

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def test_parser_reuses_cached_operator_instances_for_regular_ops() -> None:
    toks = PDFStreamParser.from_bytes(b"q q trueq falseq nullq").parse()

    assert toks[0] is toks[1]
    assert toks[0] is Operator.get_operator("q")
    assert toks[2] is Operator.get_operator("trueq")
    assert toks[3] is Operator.get_operator("falseq")
    assert toks[4] is Operator.get_operator("nullq")


def test_parser_keeps_inline_image_operators_per_occurrence() -> None:
    toks = PDFStreamParser.from_bytes(
        b"BI /W 1 /H 1 /BPC 8 ID\nA\nEI Q "
        b"BI /W 1 /H 1 /BPC 8 ID\nB\nEI"
    ).parse()

    assert len(toks) == 3
    assert toks[0] is not toks[2]
    assert isinstance(toks[0], Operator)
    assert isinstance(toks[2], Operator)
    assert toks[0].name == toks[2].name == "BI"
    assert toks[0].image_data == b"A\n"
    assert toks[2].image_data == b"B\n"
