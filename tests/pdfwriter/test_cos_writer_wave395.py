from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessWriteBuffer
from pypdfbox.pdfwriter import COSWriter, COSWriterXRefEntry
from pypdfbox.pdfwriter.cos_writer import _RawSinkAdapter


def test_wave395_raw_sink_adapter_close_delegates_when_available() -> None:
    class Sink:
        def __init__(self) -> None:
            self.closed = False

        def write(self, data: bytes) -> None:
            assert data == b"x"

        def close(self) -> None:
            self.closed = True

    sink = Sink()
    adapter = _RawSinkAdapter(sink)

    assert adapter.write(b"x") == 1
    adapter.close()

    assert sink.closed is True


def test_wave395_closed_writer_rejects_write() -> None:
    writer = COSWriter(io.BytesIO())
    writer.close()

    with pytest.raises(OSError, match="COSWriter already closed"):
        writer.write(COSDocument())


def test_wave395_do_write_object_single_arg_and_none_payload_branches() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        dictionary = COSDictionary()
        dictionary.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]

        writer.do_write_object(dictionary)
        before = len(writer.get_xref_entries())
        writer.do_write_object(COSObjectKey(99, 0), None)

    assert len(writer.get_xref_entries()) == before
    assert b"1 0 obj" in sink.getvalue()
    assert b"/Type /Catalog" in sink.getvalue()


def test_wave395_object_number_accessors_resolve_wrappers_to_actuals() -> None:
    actual = COSDictionary()
    wrapper = COSObject(7, 3, resolved=actual)

    with COSWriter(io.BytesIO()) as writer:
        writer.write_reference(actual)

        assert writer.get_object_number(wrapper) == writer.get_object_number(actual)
        assert writer.get_generation_number(wrapper) == 0


def test_wave395_get_object_key_preserves_dangling_declared_reference() -> None:
    dangling = COSObject(17, 4)

    with COSWriter(io.BytesIO()) as writer:
        key = writer._get_object_key(dangling)

    assert key == COSObjectKey(17, 4)


def test_wave395_write_with_bad_pddocument_get_document_type_raises() -> None:
    class BadPDDocument:
        def get_document(self) -> object:
            return object()

        def is_encrypted(self) -> bool:
            return False

    with (
        COSWriter(io.BytesIO()) as writer,
        pytest.raises(TypeError, match="did not return a COSDocument"),
    ):
        writer.write(BadPDDocument())


def test_wave395_stage_encryption_rejects_non_standard_policy() -> None:
    # ``_stage_encryption`` now accepts both Standard and PublicKey policies;
    # anything else surfaces as ``TypeError`` rather than ``NotImplementedError``.
    class FakePDDocument:
        _protection_policy = object()

        def is_all_security_to_be_removed(self) -> bool:
            return False

    with (
        COSWriter(io.BytesIO()) as writer,
        pytest.raises(TypeError, match="PublicKeyProtectionPolicy"),
    ):
        writer._stage_encryption(FakePDDocument(), COSDocument())


def test_wave395_stage_encryption_reuses_existing_handler_for_encrypted_doc() -> None:
    handler = object()

    class FakePDDocument:
        _protection_policy = None
        _security_handler = handler

        def is_all_security_to_be_removed(self) -> bool:
            return False

        def is_encrypted(self) -> bool:
            return True

    with COSWriter(io.BytesIO()) as writer:
        writer._stage_encryption(FakePDDocument(), COSDocument())
        assert writer._security_handler is handler


def test_wave395_document_id_helpers_create_and_preserve_missing_trailer() -> None:
    doc = COSDocument()

    with COSWriter(io.BytesIO()) as writer:
        writer._propagate_document_id(doc)
        first_id = doc.get_document_id()
        writer._ensure_document_id(COSDocument())

    assert first_id is not None
    assert first_id.size() == 2


def test_wave395_refresh_encrypt_dict_id_handles_missing_and_non_dict_entries() -> None:
    with COSWriter(io.BytesIO()) as writer:
        writer._security_handler = object()
        writer._refresh_encrypt_dict_id(COSDocument())
        assert writer._encrypt_dict_id is None

        doc = COSDocument()
        trailer = COSDictionary()
        trailer.set_item(COSName.ENCRYPT, COSString(b"not-a-dict"))  # type: ignore[attr-defined]
        doc.set_trailer(trailer)
        writer._refresh_encrypt_dict_id(doc)
        assert writer._encrypt_dict_id is None


def test_wave395_byterange_placeholder_rejected_for_signature_dict() -> None:
    doc = COSDocument()
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]
    sig.set_item(COSName.get_pdf_name("ByteRange"), COSArray.of_cos_integers([0, 0, 0, 0]))
    doc.get_object_from_pool(COSObjectKey(3, 0)).set_object(sig)

    with (
        COSWriter(io.BytesIO()) as writer,
        pytest.raises(NotImplementedError, match="ByteRange"),
    ):
        writer._reject_signed_with_byterange_placeholder(doc)


def test_wave395_incremental_prepare_and_enqueue_skip_dangling_pool_entries() -> None:
    doc = COSDocument()
    doc.get_object_from_pool(COSObjectKey(1, 0))

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer._prepare_increment(doc)
        writer._enqueue_dirty_objects(doc)

        assert writer._key_object == {}
        assert not writer._objects_to_write


def test_wave395_write_to_output_uses_random_access_write_buffer() -> None:
    sink = RandomAccessWriteBuffer()

    with COSWriter(sink) as writer:
        writer._write_to_output(b"abc")

    assert sink.to_bytes() == b"abc"


def test_wave395_header_uses_explicit_pdf_version_override() -> None:
    doc = COSDocument()
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer.set_pdf_version(1, 7)
        writer._do_write_header(doc)

    assert sink.getvalue().startswith(b"%PDF-1.7\n")


def test_wave395_body_and_trailer_handle_missing_trailer_directly() -> None:
    doc = COSDocument()
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer._do_write_body(doc)
        writer._do_write_body_xref_stream(doc)
        writer.write_trailer(doc)

    out = sink.getvalue()
    assert b"trailer\n" in out
    assert b"/Size 1" in out


def test_wave395_queue_deduplicates_already_queued_objects() -> None:
    obj = COSDictionary()

    with COSWriter(io.BytesIO()) as writer:
        writer._objects_to_write.append(obj)
        writer._add_object_to_write(obj)

        assert list(writer._objects_to_write) == [obj]


def test_wave395_queue_skips_actual_that_already_has_key() -> None:
    actual = COSDictionary()
    wrapper = COSObject(5, 0, resolved=actual)

    with COSWriter(io.BytesIO()) as writer:
        writer._get_object_key(actual)
        writer._add_object_to_write(wrapper)

        assert not writer._objects_to_write


def test_wave395_do_write_object_skips_dangling_and_packed_actuals() -> None:
    packed = COSDictionary()
    dangling = COSObject(9, 0)

    with COSWriter(io.BytesIO()) as writer:
        writer._do_write_object(dangling)
        writer._packed_object_ids.add(id(packed))
        writer._do_write_object(packed)

        assert not writer.get_xref_entries()
        assert id(packed) in writer._written_objects


def test_wave395_do_write_object_with_key_can_emit_null_payload() -> None:
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer._do_write_object_with_key(COSObjectKey(10, 0), COSObject(10, 0))

    out = sink.getvalue()
    assert b"10 0 obj\nnull\nendobj" in out


def test_wave395_free_list_head_can_point_to_later_gap() -> None:
    with COSWriter(io.BytesIO()) as writer:
        writer.add_xref_entry(
            COSWriterXRefEntry(0, COSObjectKey(0, 0), COSDictionary())
        )
        writer.add_xref_entry(
            COSWriterXRefEntry(20, COSObjectKey(2, 0), COSDictionary())
        )
        writer._fill_gaps_with_free_entries()

        free_zero = [
            entry
            for entry in writer.get_xref_entries()
            if entry.free and entry.key == COSObjectKey(0, 65535)
        ]

    assert free_zero
    assert free_zero[-1].offset == 1


def test_wave395_object_stream_packer_skips_existing_packed_and_nonzero_generation() -> None:
    packed = COSDictionary()
    nonzero_generation = COSDictionary()

    with COSWriter(io.BytesIO(), xref_stream=True, object_stream=True) as writer:
        writer._key_object[COSObjectKey(1, 0)] = packed
        writer._packed_object_ids.add(id(packed))
        writer._key_object[COSObjectKey(2, 1)] = nonzero_generation

        writer._pack_object_streams(COSDocument())

        assert writer._compressed_locations == {}


def test_wave395_string_encryption_uses_handler_without_mutating_source() -> None:
    class Handler:
        def encrypt_string(self, data: bytes, obj_num: int, gen: int) -> bytes:
            assert data == b"plain"
            assert (obj_num, gen) == (4, 2)
            return b"\x80cipher"

    source = COSString(b"plain")
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer._security_handler = Handler()
        writer._current_object_key = COSObjectKey(4, 2)
        writer.visit_from_string(source)

    assert source.get_bytes() == b"plain"
    assert sink.getvalue() == b"<80636970686572>"


def test_wave395_array_dictionary_stream_and_object_leaf_cold_paths() -> None:
    direct_dict = COSDictionary()
    direct_dict.set_direct(True)
    direct_dict.set_int("Answer", 42)
    arr = COSArray([None, direct_dict])

    stream = COSStream()
    plain_object = COSObject(6, 0, resolved=COSInteger.get(7))
    dangling_object = COSObject(7, 0)
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer.visit_from_array(arr)
        writer.visit_from_stream(stream)
        writer.visit_from_object(plain_object)
        writer.visit_from_object(dangling_object)

    out = sink.getvalue()
    assert b"[null <<\n/Answer 42\n>>\n]\n" in out
    assert b"/Length 0" in out
    assert b"stream\r\n\r\nendstream" in out
    assert out.rstrip().endswith(b"7null")


def test_wave395_float_formatter_rejects_nan_and_expands_tiny_scientific() -> None:
    with pytest.raises(ValueError, match="NaN"):
        COSWriter.format_float(float("nan"))

    # PDFBox's COSFloat.formatString expands a tiny scientific value to plain
    # notation (BigDecimal.toPlainString) rather than collapsing it to "0":
    # 1e-20 is well within float32 range, so it round-trips to a long decimal.
    assert COSWriter.format_float(1e-20) == b"0.00000000000000000001"
