from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.pd_document import ExternalSigningSupport


def test_get_page_returns_page_by_zero_based_index_wave457() -> None:
    doc = PDDocument()
    first = PDPage()
    second = PDPage()
    doc.add_page(first)
    doc.add_page(second)

    assert doc.get_page(0).get_cos_object() is first.get_cos_object()
    assert doc.get_page(1).get_cos_object() is second.get_cos_object()
    doc.close()


def test_save_incremental_rejects_non_dictionary_objects_to_write_wave457() -> None:
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    doc = PDDocument(cos_doc)

    with pytest.raises(TypeError, match="COSDictionary"):
        doc.save_incremental(io.BytesIO(), {object()})  # type: ignore[arg-type]
    doc.close()


def test_closed_document_guards_save_and_external_signing_wave457() -> None:
    doc = PDDocument()
    doc.close()

    with pytest.raises(OSError, match="Cannot save a document which has been closed"):
        doc.save(io.BytesIO())
    with pytest.raises(OSError, match="Cannot save a document which has been closed"):
        doc.save_incremental_for_external_signing(io.BytesIO())


def test_extract_bracketed_concatenates_byte_range_slices_wave457() -> None:
    data = b"abcdefghi"

    assert PDDocument._extract_bracketed(data, [1, 3, 6, 2]) == b"bcdgh"


def test_splice_signature_hex_encodes_and_pads_wave457() -> None:
    buffer = bytearray(b"abc000000xyz")

    out = PDDocument._splice_signature(buffer, (3, 9), b"\x0a\xbc")

    assert out == b"abc0ABC00xyz"
    assert buffer == bytearray(b"abc000000xyz")


def test_splice_signature_rejects_oversized_blob_wave457() -> None:
    with pytest.raises(ValueError, match="larger than"):
        PDDocument._splice_signature(bytearray(b"0000"), (0, 4), b"\x01\x02\x03")


def test_write_bytes_to_target_accepts_path_and_stream_wave457(tmp_path) -> None:
    target = tmp_path / "incremental.pdf"
    stream = io.BytesIO()

    PDDocument._write_bytes_to_target(b"abc", target)
    PDDocument._write_bytes_to_target(b"def", stream)

    assert target.read_bytes() == b"abc"
    assert stream.getvalue() == b"def"


def test_external_signing_support_sets_signature_once_and_clears_staging_wave457() -> None:
    doc = PDDocument()
    doc._pending_signature = object()  # type: ignore[assignment]  # noqa: SLF001
    doc._pending_signature_interface = object()  # type: ignore[assignment]  # noqa: SLF001
    doc._pending_signature_options = object()  # noqa: SLF001
    output = io.BytesIO()
    handle = ExternalSigningSupport(
        document=doc,
        output=output,
        buffer=bytearray(b"xx0000yy"),
        contents_span=(2, 6),
        byte_range=[0, 2, 6, 2],
    )

    assert handle.get_content() == b"xxyy"
    assert handle.get_byte_range() == [0, 2, 6, 2]

    handle.set_signature(b"\x0f")

    assert output.getvalue() == b"xx0F00yy"
    assert doc.get_pending_signature() is None
    assert doc.get_signature_interface() is None
    assert doc.get_signature_options() is None

    with pytest.raises(RuntimeError, match="called twice"):
        handle.set_signature(b"\x0f")
    doc.close()


def test_requires_full_save_checks_dirty_inner_object_wave457() -> None:
    cos_doc = COSDocument(source=RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"))
    doc = PDDocument(cos_doc)
    indirect = cos_doc.get_object_from_pool(COSObjectKey(12, 0))
    indirect.set_object(COSDictionary())

    assert doc.requires_full_save()

    indirect.get_object().set_needs_to_be_updated(True)

    assert not doc.requires_full_save()
    doc.close()
