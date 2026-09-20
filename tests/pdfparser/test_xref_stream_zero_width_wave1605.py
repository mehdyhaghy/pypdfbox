"""Wave 1605 — PDFBOX-6229: reject ``/W`` arrays that sum to zero.

``PDFXrefStreamParser`` sizes each cross-reference record from
``/W [w0 w1 w2]``. A ``/W`` whose entries sum to 0 describes a
zero-length row: the read cursor never advances, so the parse loop spins
once per declared ``/Index`` object producing garbage entries — with a
large ``/Size`` that is an unbounded (memory- and CPU-burning) loop on
attacker-controlled input.

Upstream widened the existing PDFBOX-6037 pathological-width guard
(``sum > 20``) to also reject ``sum == 0``. These tests pin both ends of
the accepted range plus the neighbouring widths that must stay legal.
"""

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_xref_stream_parser import PDFXrefStreamParser


def _stream(w: tuple[int, int, int], *, index: tuple[int, int] | None = None) -> COSStream:
    stream = COSStream()
    w_arr = COSArray()
    for v in w:
        w_arr.add(COSInteger.get(v))
    stream.set_item(COSName.W, w_arr)
    if index is not None:
        idx_arr = COSArray()
        idx_arr.add(COSInteger.get(index[0]))
        idx_arr.add(COSInteger.get(index[1]))
        stream.set_item(COSName.INDEX, idx_arr)
    out = stream.create_raw_output_stream()
    try:
        out.write(b"")
    finally:
        out.close()
    return stream


def test_zero_sum_w_array_is_rejected() -> None:
    """``/W [0 0 0]`` — a zero-length record — must be refused."""
    with pytest.raises(PDFParseError, match="Incorrect /W array in XRef"):
        PDFXrefStreamParser(_stream((0, 0, 0)), COSDocument())


def test_zero_sum_w_array_rejected_before_walking_a_huge_index() -> None:
    """The guard fires during init, so a huge ``/Index`` count can never
    be walked with a non-advancing cursor (the DoS PDFBOX-6229 closed)."""
    with pytest.raises(PDFParseError, match="Incorrect /W array in XRef"):
        PDFXrefStreamParser(
            _stream((0, 0, 0), index=(0, 2_000_000_000)), COSDocument()
        )


@pytest.mark.parametrize("w", [(0, 0, 1), (0, 1, 0), (1, 0, 0), (1, 2, 1)])
def test_minimal_non_zero_widths_still_accepted(w: tuple[int, int, int]) -> None:
    """Any ``/W`` summing to at least 1 advances the cursor, so it stays
    legal — the new guard must not widen past ``sum == 0``."""
    parser = PDFXrefStreamParser(_stream(w), COSDocument())
    parser.close()


def test_oversized_w_array_still_rejected() -> None:
    """PDFBOX-6037's upper bound is untouched by the new lower bound."""
    with pytest.raises(PDFParseError, match="Incorrect /W array in XRef"):
        PDFXrefStreamParser(_stream((8, 8, 8)), COSDocument())
