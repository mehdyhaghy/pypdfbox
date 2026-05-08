"""Tests for xref-stream output (PDF 32000-1 §7.5.8) and object-stream
packing (§7.5.7) added to ``COSWriter``.

Three layers of coverage:

1. surface-level wire-format checks against the emitted bytes — confirms
   the new output path actually emits ``/Type /XRef`` (and ``/Type /ObjStm``
   when packing is on) without regressing the traditional path,
2. encryption-pipeline integration — the xref stream's body MUST go
   through ``visit_from_stream``'s encryption hook so its bytes are not
   plaintext entries when an /Encrypt dict is wired,
3. round-trip via the parser — exercises the real reader which is the
   only honest sanity check for the field widths / index packing.
"""

from __future__ import annotations

import io
import re
import zlib

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter

# ---------- helpers ---------------------------------------------------------


def _make_doc(catalog_dict: COSDictionary | None = None) -> COSDocument:
    """Mirror the helper in ``test_cos_writer.py`` — minimal trailer +
    catalog #1, suitable for both traditional and xref-stream output."""
    doc = COSDocument()
    doc.set_version(1.5)
    catalog = catalog_dict if catalog_dict is not None else COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


def _make_doc_with_referenced_dictionaries(count: int) -> COSDocument:
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    kids = COSArray()
    for obj_num in range(2, count + 2):
        child = COSDictionary()
        child.set_int(COSName.get_pdf_name("Ordinal"), obj_num)
        kids.add(COSObject(obj_num, 0, resolved=child))
    catalog.set_item(COSName.get_pdf_name("Kids"), kids)
    return _make_doc(catalog)


def _write_xref_stream(doc: COSDocument, *, object_stream: bool = False) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True, object_stream=object_stream) as w:
        w.write(doc)
    return sink.getvalue()


def _write_traditional(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


# ---------- constructor / setter / getter surface --------------------------


def test_default_flags_off() -> None:
    sink = io.BytesIO()
    w = COSWriter(sink)
    assert w.is_xref_stream_output() is False
    assert w.is_object_stream_output() is False


def test_setters_and_getters_round_trip() -> None:
    sink = io.BytesIO()
    w = COSWriter(sink)
    w.set_xref_stream(True)
    w.set_object_stream(True)
    assert w.is_xref_stream_output() is True
    assert w.is_object_stream_output() is True
    w.set_xref_stream(False)
    w.set_object_stream(False)
    assert w.is_xref_stream_output() is False
    assert w.is_object_stream_output() is False


def test_constructor_flags_propagate() -> None:
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True, object_stream=True) as w:
        assert w.is_xref_stream_output()
        assert w.is_object_stream_output()


# ---------- regression: default path stays traditional ---------------------


def test_default_save_still_uses_traditional_xref_table() -> None:
    """Making xref-stream output opt-in is non-negotiable — the existing
    ``test_xref_table_format_byte_for_byte`` and the encryption-cluster
    checks rely on the traditional layout."""
    out = _write_traditional(_make_doc())
    assert b"\nxref\n" in out
    assert b"\ntrailer\n" in out
    assert b"/Type /XRef" not in out
    assert b"/Type/XRef" not in out


# ---------- xref-stream surface --------------------------------------------


def test_xref_stream_replaces_traditional_xref_and_trailer() -> None:
    out = _write_xref_stream(_make_doc())
    # No legacy keywords.
    assert b"\nxref\n" not in out
    assert b"\ntrailer\n" not in out
    # The xref stream itself.
    assert b"/Type /XRef" in out or b"/Type/XRef" in out


def test_xref_stream_dict_carries_required_entries() -> None:
    out = _write_xref_stream(_make_doc())
    # /W, /Size, /Filter, /Index — all required in the xref-stream dict
    # per ISO 32000-1 §7.5.8.2.
    assert b"/W " in out or b"/W[" in out
    assert b"/Size " in out
    assert b"/Filter /FlateDecode" in out or b"/Filter/FlateDecode" in out
    assert b"/Index " in out or b"/Index[" in out


def test_xref_stream_promotes_root_into_dict() -> None:
    out = _write_xref_stream(_make_doc())
    # /Root must live inside the xref-stream dict (it's the trailer now).
    # Look for a "/Root <num> <gen> R" pattern.
    assert b"/Root " in out


def test_xref_stream_startxref_points_at_xref_object() -> None:
    out = _write_xref_stream(_make_doc())
    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    declared = int(out[line_start:line_end].strip())
    # The xref-stream object frame begins at ``declared``; the first 64
    # bytes there must contain " obj" — the indirect-object marker.
    assert b" obj" in out[declared:declared + 64], (
        "startxref offset doesn't land on an indirect object frame"
    )


def test_xref_stream_round_trip_via_parser() -> None:
    catalog = COSDictionary()
    catalog.set_int(COSName.get_pdf_name("Custom"), 42)
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)

    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]
        assert cat.get_int(COSName.get_pdf_name("Custom")) == 42
    finally:
        parsed.close()


def test_xref_stream_round_trip_with_stream_object() -> None:
    """Streams cannot be packed into ObjStms (per spec) so they remain
    plain indirect objects even with object_stream=True; this is also the
    canonical xref-stream-only round-trip with a non-trivial body."""
    raw = b"hello xref stream" * 16
    encoded = zlib.compress(raw)
    stream = COSStream()
    stream.set_raw_data(encoded)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    stream.set_int(COSName.LENGTH, len(encoded))  # type: ignore[attr-defined]

    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    stream_obj = COSObject(2, 0, resolved=stream)
    catalog.set_item(COSName.get_pdf_name("Body"), stream_obj)
    doc = _make_doc(catalog)

    out = _write_xref_stream(doc)
    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        body = cat.get_dictionary_object(COSName.get_pdf_name("Body"))
        assert isinstance(body, COSStream)
        assert zlib.decompress(body.get_raw_data()) == raw
    finally:
        parsed.close()


# ---------- object-stream packing -------------------------------------------


def test_object_stream_emits_objstm_marker_in_output() -> None:
    out = _write_xref_stream(_make_doc(), object_stream=True)
    assert b"/Type /ObjStm" in out or b"/Type/ObjStm" in out
    # /N (object count) and /First (offset) are mandatory ObjStm dict keys.
    assert b"/N " in out
    assert b"/First " in out


def test_object_stream_default_chunk_size_matches_compress_parameters() -> None:
    out = _write_xref_stream(
        _make_doc_with_referenced_dictionaries(150),
        object_stream=True,
    )

    object_stream_count = out.count(b"/Type /ObjStm") + out.count(b"/Type/ObjStm")
    packed_counts = [int(raw) for raw in re.findall(rb"/N\s+(\d+)", out)]

    assert object_stream_count == 1
    assert max(packed_counts) > 100


def test_object_stream_yields_type2_xref_entries() -> None:
    """When object-stream packing is on, at least one xref record must be
    type=2 (compressed). Decode the xref-stream body and parse it
    against the /W field widths so we don't hard-code a stride."""
    out = _write_xref_stream(_make_doc(), object_stream=True)

    # Locate the xref-stream object — it's the one referenced by startxref.
    startxref_idx = out.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = out.index(b"\n", line_start)
    xref_offset = int(out[line_start:line_end].strip())
    after_obj = out[xref_offset:]

    # Pull the /W array out of the dict (a printed "[w1 w2 w3]" run).
    w_match = re.search(rb"/W\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s*\]", after_obj)
    assert w_match is not None, "missing /W in xref-stream dict"
    w1, w2, w3 = (int(g) for g in w_match.groups())
    record_size = w1 + w2 + w3

    # Stream body sits between ``stream\r\n`` and ``\nendstream``.
    stream_marker = after_obj.index(b"stream")
    body_start = stream_marker + len(b"stream")
    if after_obj[body_start:body_start + 2] == b"\r\n":
        body_start += 2
    elif after_obj[body_start:body_start + 1] in (b"\n", b"\r"):
        body_start += 1
    end_marker = after_obj.index(b"endstream", body_start)
    body_end = end_marker
    while body_end > body_start and after_obj[body_end - 1] in (0x0A, 0x0D):
        body_end -= 1
    decoded = zlib.decompress(after_obj[body_start:body_end])

    types = set()
    for cursor in range(0, len(decoded), record_size):
        types.add(decoded[cursor])
    assert 2 in types, (
        f"expected at least one type=2 (compressed) xref entry; saw {types}"
    )


def test_object_stream_round_trip_via_parser() -> None:
    catalog = COSDictionary()
    catalog.set_int(COSName.get_pdf_name("Tag"), 99)
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc, object_stream=True)

    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        assert cat.get_name(COSName.TYPE) == "Catalog"  # type: ignore[attr-defined]
        assert cat.get_int(COSName.get_pdf_name("Tag")) == 99
    finally:
        parsed.close()


# ---------- encryption integration ------------------------------------------


def test_xref_stream_body_stays_plaintext_when_handler_active() -> None:
    """The xref stream's body must stay plaintext (only ``/FlateDecode``-
    encoded, never enciphered) even when a security handler is wired —
    ISO 32000-2 §7.6.2: "All cross-reference streams in the file shall
    not be encrypted." The parser uses the xref stream to locate the
    /Encrypt object itself, so encrypting it would create an unresolvable
    chicken-and-egg bootstrap (FlateDecode would see ciphertext)."""
    pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

    from pypdfbox import PDDocument
    from pypdfbox.pdmodel import PDPage
    from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    pd = PDDocument()
    pd.add_page(PDPage())
    pd.protect(
        StandardProtectionPolicy(
            owner_password="owner",
            user_password="user",
            permissions=AccessPermission(),
        )
    )

    # Stage encryption then save with xref-stream output. We do this by
    # manually invoking COSWriter with the xref_stream flag rather than
    # going through ``pd.save`` (which doesn't expose the toggle yet).
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True) as w:
        w.write(pd)
    saved = sink.getvalue()

    startxref_idx = saved.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = saved.index(b"\n", line_start)
    xref_offset = int(saved[line_start:line_end].strip())
    body_window = saved[xref_offset : startxref_idx]
    stream_marker = body_window.index(b"stream")
    body_start = stream_marker + len(b"stream")
    if body_window[body_start:body_start + 2] == b"\r\n":
        body_start += 2
    elif body_window[body_start:body_start + 1] in (b"\n", b"\r"):
        body_start += 1
    end_marker = body_window.index(b"endstream", body_start)
    body_end = end_marker
    while body_end > body_start and body_window[body_end - 1] in (0x0A, 0x0D):
        body_end -= 1
    body = body_window[body_start:body_end]

    # Plaintext FlateDecoded bytes start with the zlib magic
    # 0x78 0x9C / 0x78 0xDA / 0x78 0x01. The encryption pipeline must
    # have skipped this stream — otherwise the leading byte would be
    # randomised by the cipher pass.
    assert body[:1] == b"\x78", (
        "xref-stream body lost its zlib magic — the encryption pipeline "
        "should have skipped this object per ISO 32000-2 §7.6.2"
    )

    # End-to-end sanity: the saved file must round-trip through the
    # parser with the same password (which proves the bootstrap that
    # /Encrypt's offset is readable from the cleartext xref stream).
    from pypdfbox.pdmodel import PDDocument as _PDDocument
    with _PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted()
