"""Wave 1351 coverage boost: ``PDFXrefStreamParser`` OSError-on-init.

Targets lines 41-42 of
``pypdfbox/pdfparser/pdf_xref_stream_parser.py`` — the ``except
OSError: self.close(); raise`` arm of the constructor. The constructor
calls ``_init_parser_values`` which mostly raises ``PDFParseError``
(``ValueError``-derived), but the final step constructs an
``ObjectNumbers`` whose own constructor *can* raise ``OSError`` when
the ``/Index`` array contains non-integer values. We exercise that
path here.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.pdf_xref_stream_parser import PDFXrefStreamParser


def test_constructor_closes_self_when_object_numbers_raises_oserror() -> None:
    """When ``ObjectNumbers`` rejects a non-integer ``/Index`` element
    with ``OSError``, the constructor must call ``self.close()`` before
    re-raising — covering lines 41-42.
    """
    stream = COSStream()
    # Valid /W = [1, 2, 1] so we pass the /W validation.
    w_arr = COSArray()
    for v in (1, 2, 1):
        w_arr.add(COSInteger.get(v))
    stream.set_item(COSName.W, w_arr)
    # /Index has the right shape (len == 2, even) but the first element
    # is a COSName instead of a COSInteger — ObjectNumbers raises
    # OSError("Xref stream must have integer in /Index array").
    idx_arr = COSArray()
    idx_arr.add(COSName.A)  # not a COSInteger
    idx_arr.add(COSInteger.get(1))
    stream.set_item(COSName.INDEX, idx_arr)
    # Empty body — never reached, init fails first.
    out = stream.create_raw_output_stream()
    try:
        out.write(b"")
    finally:
        out.close()
    with pytest.raises(OSError, match="integer in /Index array"):
        PDFXrefStreamParser(stream, COSDocument())
