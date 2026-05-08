from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def test_wave313_b_keyword_operators_use_operator_cache() -> None:
    toks = PDFStreamParser.from_bytes(b"BT BMC B* BI /W 1 ID x EI").parse()

    assert toks[0] is Operator.get_operator("BT")
    assert toks[1] is Operator.get_operator("BMC")
    assert toks[2] is Operator.get_operator("B*")
    assert isinstance(toks[3], Operator)
    assert toks[3].get_name() == "BI"
    assert toks[3] is not Operator.get_operator("BI")
