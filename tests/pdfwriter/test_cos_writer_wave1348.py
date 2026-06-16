"""Wave 1348 coverage-boost — exercise the remaining defensive branches
in ``COSWriter`` so the module crosses the 99% line.

Targets the eleven residual gaps reported by coverage:

* ``_format_xref_table_generation`` rejecting out-of-range generations;
* the snake_case PDFBox-parity façades (``prepare_increment``,
  ``do_write_header`` / ``_body`` / ``_compressed`` / ``_trailer`` /
  ``_x_ref_table`` / ``_x_ref_inc`` / ``_increment``,
  ``fill_gaps_with_free_entries``);
* the two negative branches of ``is_need_to_be_updated`` (non-callable
  attribute, exception inside the callable);
* the ``detect_possible_signature`` body — every guard plus the success
  edge that flips ``_reached_signature``;
* the ``info is not None`` branch in ``_do_write_body_xref_stream``;
* the ``_is_packable``→False ``continue`` inside ``_pack_object_streams``
  when a ``COSStream`` ends up in ``_key_object``;
* ``_propagate_document_id`` early-return on an /ID that already exists;
* the ``PublicKeyProtectionPolicy`` arm of ``_stage_encryption``.
"""

from __future__ import annotations

import io
from typing import Any

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
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfwriter import COSWriter, COSWriterXRefEntry
from pypdfbox.pdfwriter.cos_writer import (
    _format_xref_table_generation,
)

# ---------------------------------------------------------------------------
# module helpers
# ---------------------------------------------------------------------------


def test_wave1348_format_xref_table_generation_rejects_out_of_range() -> None:
    """A generation outside ``[0, 65535]`` is unrepresentable in a
    five-digit xref-table field; the helper must raise so callers never
    silently emit a malformed entry."""
    with pytest.raises(ValueError, match=r"\[0, 65535\]"):
        _format_xref_table_generation(-1)
    with pytest.raises(ValueError, match=r"\[0, 65535\]"):
        _format_xref_table_generation(65536)
    assert _format_xref_table_generation(0) == b"00000"
    assert _format_xref_table_generation(65535) == b"65535"


# ---------------------------------------------------------------------------
# PDFBox-parity façades — each forwards to the underscore-prefixed worker
# ---------------------------------------------------------------------------


def test_wave1348_prepare_increment_facade_populates_writer_key_table() -> None:
    """``prepare_increment`` is the snake_case alias for
    ``_prepare_increment`` and must register every key/actual the
    source's object pool already exposes."""
    actual = COSDictionary()
    actual.set_int("Marker", 1)

    doc = COSDocument()
    doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(actual)

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.prepare_increment(doc)
        assert writer._key_object[COSObjectKey(7, 0)] is actual
        assert writer._object_keys[id(actual)] == COSObjectKey(7, 0)


def test_wave1348_do_write_header_facade_emits_pdf_marker() -> None:
    """``do_write_header`` forwards to ``_do_write_header`` and must
    emit the ``%PDF-`` magic for the supplied document version."""
    doc = COSDocument()
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.do_write_header(doc)
    assert sink.getvalue().startswith(b"%PDF-")


def test_wave1348_do_write_body_facade_drains_root_info_encrypt_queue() -> None:
    """The body façade must run the same drain pipeline as
    ``_do_write_body`` — easiest probe is that a fresh empty doc still
    produces no body bytes (no /Root, no /Info)."""
    doc = COSDocument()
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.do_write_body(doc)
    assert sink.getvalue() == b""


def test_wave1348_do_write_body_compressed_facade_delegates_to_xref_stream() -> None:
    """``do_write_body_compressed`` routes to the xref-stream body path;
    a doc with /Root + /Info exercises BOTH that branch and (downstream)
    the ``info is not None`` arm inside ``_do_write_body_xref_stream``."""
    doc = COSDocument()
    trailer = COSDictionary()
    root = COSDictionary()
    root.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    info = COSDictionary()
    info.set_string(COSName.get_pdf_name("Producer"), "pypdfbox-test")
    trailer.set_item(COSName.ROOT, root)  # type: ignore[attr-defined]
    trailer.set_item(COSName.INFO, info)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)

    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True) as writer:
        writer.do_write_body_compressed(doc)

    out = sink.getvalue()
    # Both root and info must have been emitted as indirect frames.
    assert b"/Type /Catalog" in out
    assert b"/Producer (pypdfbox-test)" in out


def test_wave1348_do_write_trailer_facade_emits_trailer_keyword() -> None:
    """``do_write_trailer`` mirrors ``_do_write_trailer`` — produces the
    ``trailer\\n<<...>>\\n`` block but NOT ``startxref`` / ``%%EOF``."""
    doc = COSDocument()
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.do_write_trailer(doc)
    out = sink.getvalue()
    assert b"trailer\n" in out
    assert b"startxref" not in out
    assert b"%%EOF" not in out


def test_wave1348_do_write_x_ref_table_facade_emits_xref_keyword() -> None:
    """``do_write_x_ref_table`` is the snake_case alias for
    ``_do_write_xref_table`` and must emit at least the ``xref`` keyword
    and the mandatory free-list head."""
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.do_write_x_ref_table()
    out = sink.getvalue()
    assert out.startswith(b"xref\n")
    # free-list head: offset 0, gen 65535, flag 'f'
    assert b"0000000000 65535 f" in out


def test_wave1348_do_write_x_ref_inc_routes_non_xref_stream_to_table_branch() -> None:
    """When the source document is NOT using an xref stream,
    ``do_write_x_ref_inc`` falls through to
    ``_do_write_xref_increment`` + ``_do_write_trailer_increment``,
    emitting the classic ``xref`` + ``trailer`` pair into the
    increment buffer (incremental mode buffers, not writes-through)."""
    doc = COSDocument()  # is_xref_stream() == False by default

    sink = io.BytesIO()
    with COSWriter(sink, incremental=True) as writer:
        writer.do_write_x_ref_inc(doc)
        # Incremental writer buffers bytes — peek at the internal buffer
        # before drain (the sink stays empty until ``_do_write_increment``
        # copies source + appends).
        buffered = writer._increment_buffer.getvalue()  # type: ignore[union-attr]

    assert buffered.startswith(b"xref\n")
    assert b"trailer\n" in buffered


def test_wave1348_do_write_x_ref_inc_routes_xref_stream_when_not_incremental() -> None:
    """The second branch of the routing condition — xref-stream doc in
    full-save mode — must dispatch to ``_do_write_xref_stream``, which
    emits an ``/Type /XRef`` indirect frame."""
    doc = COSDocument()
    doc.set_xref_stream(True)

    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True) as writer:
        writer.do_write_x_ref_inc(doc)

    out = sink.getvalue()
    assert b"/Type /XRef" in out or b"/Type/XRef" in out


def test_wave1348_fill_gaps_with_free_entries_facade_records_free_zero() -> None:
    """``fill_gaps_with_free_entries`` forwards to the underscore worker
    which guarantees the free-list head (object 0, gen 65535) is
    present even if no normal entries cover that slot."""
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.add_x_ref_entry(
            COSWriterXRefEntry(13, COSObjectKey(2, 0), COSDictionary())
        )
        writer.fill_gaps_with_free_entries()
        entries = writer.get_xref_entries()

    assert any(e.free and e.key == COSObjectKey(0, 65535) for e in entries)


def test_wave1348_do_write_increment_facade_appends_empty_revision() -> None:
    """``do_write_increment`` runs the buffered append-only pipeline.
    With a fresh COSDocument carrying no dirty objects, the writer still
    appends a fresh (empty) revision — the source survives as a verbatim
    prefix and a new ``xref`` section + ``/Prev`` trailer are appended,
    matching PDFBox 3.0.7's no-op contract (oracle-confirmed wave 1565)."""
    source_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f\n0000000009 00000 n\n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
        b"startxref\n45\n%%EOF\n"
    )
    source = RandomAccessReadBuffer(source_bytes)

    sink = io.BytesIO()
    doc = COSDocument()
    doc.set_start_xref(45)

    with COSWriter(sink, incremental=True, incremental_input=source) as writer:
        writer.do_write_increment(doc)

    out = sink.getvalue()
    # No dirty objects → an empty revision is still appended.
    assert out.startswith(source_bytes), "source must survive as a verbatim prefix"
    assert len(out) > len(source_bytes), "an empty increment is still appended"
    increment = out[len(source_bytes) :]
    assert b"/Prev 45" in increment, "appended trailer must chain /Prev to 45"
    assert out.rstrip().endswith(b"%%EOF")


# ---------------------------------------------------------------------------
# is_need_to_be_updated — defensive branches
# ---------------------------------------------------------------------------


def test_wave1348_is_need_to_be_updated_returns_false_when_attribute_not_callable() -> None:
    """If ``is_needs_to_be_updated`` exists on the object but isn't a
    callable (e.g. an int sentinel), the static helper short-circuits to
    False without trying to invoke it."""

    class HasDirtyButNotCallable:
        is_needs_to_be_updated = 7  # not a callable — defensive branch

    assert COSWriter.is_need_to_be_updated(HasDirtyButNotCallable()) is False  # type: ignore[arg-type]


def test_wave1348_is_need_to_be_updated_swallows_callable_exception() -> None:
    """If the dirty-probe raises, the static helper logs nothing and
    returns False — never propagates the exception to the caller."""

    class RaisingDirty:
        def is_needs_to_be_updated(self) -> bool:
            raise RuntimeError("intentional")

    assert COSWriter.is_need_to_be_updated(RaisingDirty()) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# detect_possible_signature — every guard + the success arm
# ---------------------------------------------------------------------------


def _writer_with_signature_source(length: int) -> COSWriter:
    """Return an incremental-mode writer whose source buffer reports
    ``length`` so ``detect_possible_signature`` can compare against it."""
    source = RandomAccessReadBuffer(b"X" * length)
    writer = COSWriter(io.BytesIO(), incremental=True, incremental_input=source)
    return writer


def test_wave1348_detect_possible_signature_ignores_non_dictionary() -> None:
    """Non-dictionary input is a no-op (defensive: lets PDFBox-style
    callers pass any candidate without first type-checking)."""
    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.detect_possible_signature(COSString(b"not-a-dict"))  # type: ignore[arg-type]
        assert getattr(writer, "_reached_signature", False) is False


def test_wave1348_detect_possible_signature_noop_when_not_incremental() -> None:
    """The hook only matters in incremental-update mode; full-save mode
    bails out before inspecting any dictionary entries."""
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]

    with COSWriter(io.BytesIO()) as writer:  # incremental=False
        writer.detect_possible_signature(sig)
        assert getattr(writer, "_reached_signature", False) is False


def test_wave1348_detect_possible_signature_idempotent_once_flag_set() -> None:
    """Once ``_reached_signature`` has been raised, subsequent calls
    short-circuit immediately (the flag is monotonic)."""
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer._reached_signature = True
        writer.detect_possible_signature(sig)
        assert writer._reached_signature is True


def test_wave1348_detect_possible_signature_skips_dict_without_type_name() -> None:
    """``/Type`` must resolve to a ``COSName`` — anything else (missing,
    or a value of the wrong COS class) bails out."""
    nameless = COSDictionary()
    nameless.set_int("Length", 0)

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.detect_possible_signature(nameless)
        assert getattr(writer, "_reached_signature", False) is False


def test_wave1348_detect_possible_signature_skips_unrelated_type() -> None:
    """Only ``/Sig`` and ``/DocTimeStamp`` matter — other Type names
    (e.g. ``/Annot``) are quietly ignored."""
    other = COSDictionary()
    other.set_item(COSName.TYPE, COSName.get_pdf_name("Annot"))  # type: ignore[attr-defined]

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.detect_possible_signature(other)
        assert getattr(writer, "_reached_signature", False) is False


def test_wave1348_detect_possible_signature_skips_missing_byterange() -> None:
    """A signature dict without a 4-element ``/ByteRange`` array isn't
    a real signature placeholder yet — keep the flag down."""
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]
    # ByteRange present but wrong shape
    sig.set_item(
        COSName.get_pdf_name("ByteRange"), COSArray.of_cos_integers([0, 1, 2])
    )

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.detect_possible_signature(sig)
        assert getattr(writer, "_reached_signature", False) is False


def test_wave1348_detect_possible_signature_skips_when_third_byterange_not_int() -> None:
    """``ByteRange[2]`` must be a ``COSInteger`` to be comparable to the
    source-buffer length; a non-integer slot is a malformed placeholder."""
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]
    byterange = COSArray()
    byterange.add(COSInteger.get(0))
    byterange.add(COSInteger.get(1))
    byterange.add(COSString(b"not-int"))  # third slot is wrong type
    byterange.add(COSInteger.get(3))
    sig.set_item(COSName.get_pdf_name("ByteRange"), byterange)

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.detect_possible_signature(sig)
        assert getattr(writer, "_reached_signature", False) is False


def test_wave1348_detect_possible_signature_sets_flag_when_byterange_past_source() -> None:
    """Success edge: when ``ByteRange[2]`` > source length the hook
    flips ``_reached_signature`` so downstream tooling can recognise a
    real signature placeholder in the dirty graph."""
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]
    sig.set_item(
        COSName.get_pdf_name("ByteRange"),
        COSArray.of_cos_integers([0, 100, 9_999_999, 0]),
    )

    with _writer_with_signature_source(length=200) as writer:
        writer.detect_possible_signature(sig)
        assert writer._reached_signature is True


def test_wave1348_detect_possible_signature_doctimestamp_also_triggers_flag() -> None:
    """``/DocTimeStamp`` is a sibling signature subtype and must take
    the same path as ``/Sig``."""
    sig = COSDictionary()
    sig.set_item(  # type: ignore[attr-defined]
        COSName.TYPE, COSName.get_pdf_name("DocTimeStamp")
    )
    sig.set_item(
        COSName.get_pdf_name("ByteRange"),
        COSArray.of_cos_integers([0, 100, 9_999_999, 0]),
    )

    with _writer_with_signature_source(length=200) as writer:
        writer.detect_possible_signature(sig)
        assert writer._reached_signature is True


def test_wave1348_detect_possible_signature_keeps_flag_down_when_byterange_inside_source() -> None:
    """If ``ByteRange[2]`` <= source length, the placeholder is "old
    residue" rather than a fresh signature — flag stays down."""
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]
    sig.set_item(
        COSName.get_pdf_name("ByteRange"),
        COSArray.of_cos_integers([0, 10, 50, 10]),
    )

    with _writer_with_signature_source(length=200) as writer:
        writer.detect_possible_signature(sig)
        assert getattr(writer, "_reached_signature", False) is False


# ---------------------------------------------------------------------------
# _pack_object_streams — _is_packable returning False path
# ---------------------------------------------------------------------------


def test_wave1348_pack_object_streams_skips_stream_payload_via_is_packable() -> None:
    """A ``COSStream`` entry in ``_key_object`` is rejected by
    ``_is_packable`` (streams cannot be packed inside an ObjStm)."""
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(b"payload")

    with COSWriter(io.BytesIO(), xref_stream=True, object_stream=True) as writer:
        writer._key_object[COSObjectKey(11, 0)] = stream
        writer._pack_object_streams(COSDocument())

        # Stream must NOT have been packed — no compressed-location record.
        assert id(stream) not in writer._compressed_locations


# ---------------------------------------------------------------------------
# _propagate_document_id — existing /ID early return
# ---------------------------------------------------------------------------


def test_wave1348_propagate_document_id_preserves_existing_id_array() -> None:
    """If the trailer already carries a 2-element /ID array,
    ``_propagate_document_id`` returns early — the existing identifier
    survives untouched, which matters for re-saves of loaded docs."""
    doc = COSDocument()
    trailer = COSDictionary()
    existing = COSArray()
    existing.add(COSString(b"\x01" * 16))
    existing.add(COSString(b"\x02" * 16))
    trailer.set_item(COSName.get_pdf_name("ID"), existing)
    doc.set_trailer(trailer)

    with COSWriter(io.BytesIO()) as writer:
        writer._propagate_document_id(doc)

    # Same array instance must still be the trailer's /ID.
    assert trailer.get_dictionary_object(COSName.get_pdf_name("ID")) is existing


# ---------------------------------------------------------------------------
# _stage_encryption — PublicKeyProtectionPolicy path
# ---------------------------------------------------------------------------


def test_wave1348_stage_encryption_routes_publickey_policy_to_pubkey_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_stage_encryption`` must dispatch ``PublicKeyProtectionPolicy``
    instances to ``PublicKeySecurityHandler``. We stub the handler so
    the test doesn't need a real X.509 certificate / PKCS#7 envelope —
    the contract under test is the routing, not the crypto."""
    from pypdfbox.pdmodel.encryption import public_key_security_handler as pksh_module
    from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
        PublicKeyProtectionPolicy,
    )

    captured: dict[str, Any] = {}

    class StubHandler:
        def __init__(self, policy: Any) -> None:
            captured["policy"] = policy

        def prepare_document(self, pd_document: Any) -> None:
            captured["pd_document"] = pd_document

    monkeypatch.setattr(pksh_module, "PublicKeySecurityHandler", StubHandler)

    class FakePDDocument:
        _protection_policy = PublicKeyProtectionPolicy()
        _security_handler: Any = None

        def is_all_security_to_be_removed(self) -> bool:
            return False

        def is_encrypted(self) -> bool:
            return False

    pd = FakePDDocument()
    cos_doc = COSDocument()

    with COSWriter(io.BytesIO()) as writer:
        writer._stage_encryption(pd, cos_doc)

    # Routed: handler built from the policy, prepare_document received the pd.
    assert isinstance(captured.get("policy"), PublicKeyProtectionPolicy)
    assert captured.get("pd_document") is pd
    # /ID seeded before the handler ran.
    assert cos_doc.get_document_id() is not None
    # The stub is installed on the PDDocument for downstream consumers.
    assert isinstance(pd._security_handler, StubHandler)
    assert writer._security_handler is pd._security_handler


# ---------------------------------------------------------------------------
# Belt-and-braces: round-trip wrapper resolution through prepare_increment
# ---------------------------------------------------------------------------


def test_wave1348_prepare_increment_handles_wrapper_actual_pair() -> None:
    """``_prepare_increment`` walks the source's object pool; entries
    whose ``COSObject`` has a resolved actual must register BOTH the
    wrapper and the actual under the same key."""
    actual = COSDictionary()
    actual.set_int("X", 99)
    wrapper = COSObject(3, 0, resolved=actual)
    doc = COSDocument()
    doc.get_object_from_pool(COSObjectKey(3, 0)).set_object(actual)

    with COSWriter(io.BytesIO(), incremental=True) as writer:
        writer.prepare_increment(doc)

        # Lookup via either identity should return the same key.
        assert writer._lookup_existing_key(actual) == COSObjectKey(3, 0)
        # Wrapper lookup falls through resolved-actual handling.
        assert writer._lookup_existing_key(wrapper) == COSObjectKey(3, 0)
