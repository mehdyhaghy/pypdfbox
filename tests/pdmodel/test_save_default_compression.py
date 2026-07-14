"""Hand-written tests for ``PDDocument.save``'s compression default.

Upstream PDFBox 3.0 parity: ``save()`` without an explicit
``CompressParameters`` argument packs non-stream indirect objects into
``/Type /ObjStm`` streams addressed by a ``/Type /XRef`` cross-reference
stream. ``CompressParameters.NO_COMPRESSION`` restores the traditional
uncompressed xref-table layout.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSStream
from pypdfbox.pdfwriter.compress import CompressParameters

_CONTENT = b"BT /F1 12 Tf 40 700 Td (compress me) Tj ET"


def _build_document() -> PDDocument:
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(_CONTENT)
    page.set_contents(stream)
    return pd


def _save(pd: PDDocument, *args) -> bytes:
    sink = io.BytesIO()
    pd.save(sink, *args)
    return sink.getvalue()


def test_default_save_emits_object_streams_and_xref_stream() -> None:
    saved = _save(_build_document())
    assert b"/ObjStm" in saved
    assert b"/Type /XRef" in saved or b"/Type/XRef" in saved
    assert b"\nxref\n" not in saved
    assert b"\ntrailer" not in saved


def test_default_save_equals_explicit_default_compression() -> None:
    import re

    def _normalized(data: bytes) -> bytes:
        # The trailer /ID digest folds in creation time — mask it out so
        # only the layout is compared.
        return re.sub(rb"/ID \[[^\]]*\]", b"/ID []", data)

    implicit = _save(_build_document())
    explicit = _save(_build_document(), CompressParameters.DEFAULT_COMPRESSION)
    assert _normalized(implicit) == _normalized(explicit)


def test_no_compression_save_keeps_traditional_xref_table() -> None:
    saved = _save(_build_document(), CompressParameters.NO_COMPRESSION)
    assert b"/ObjStm" not in saved
    assert b"\nxref\n" in saved
    assert b"trailer" in saved


@pytest.mark.parametrize(
    "compress_parameters",
    [None, CompressParameters.DEFAULT_COMPRESSION, CompressParameters.NO_COMPRESSION],
    ids=["implicit-default", "explicit-default", "no-compression"],
)
def test_save_round_trips_in_both_modes(compress_parameters) -> None:
    args = () if compress_parameters is None else (compress_parameters,)
    saved = _save(_build_document(), *args)
    with PDDocument.load(saved) as reloaded:
        assert reloaded.get_number_of_pages() == 1
        assert reloaded.get_page(0).get_contents() == _CONTENT


def test_default_save_is_smaller_on_object_heavy_documents() -> None:
    """The point of the default: object-heavy documents shrink."""
    pd = PDDocument()
    for _ in range(30):
        pd.add_page(PDPage())
    compressed = _save(pd)
    pd2 = PDDocument()
    for _ in range(30):
        pd2.add_page(PDPage())
    plain = _save(pd2, CompressParameters.NO_COMPRESSION)
    assert len(compressed) < len(plain)


def test_save_rejects_non_compress_parameters_argument() -> None:
    pd = _build_document()
    with pytest.raises(TypeError):
        pd.save(io.BytesIO(), object())
