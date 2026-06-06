"""Wave 1370 — Object-stream wire-format + PDFBOX-3678 exclusions.

Exercises the ``_pack_object_streams`` / ``_emit_one_object_stream``
pipeline at a finer grain than the surface-level coverage already in
``test_xref_stream_output.py``:

* /N + /First header values must match the literal layout: /First is
  the byte offset where the first packed body begins, /N is the count
  of packed objects.
* The index header is a whitespace-separated ``<obj_num> <byte_offset>``
  sequence; offsets are relative to /First and start at 0.
* The packed-object index must be monotonic non-decreasing (packed in
  ascending object-number order so xref-stream type-2 records line up).
* PDFBOX-3678 exclusions: stream objects, the /Encrypt dict, and
  /Type /Sig dictionaries must never be packed into an ObjStm body
  (they remain free-standing indirect objects).
"""

from __future__ import annotations

import io
import re
import zlib

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdfwriter import COSWriter


def _make_doc(catalog: COSDictionary | None = None) -> COSDocument:
    doc = COSDocument()
    doc.set_version(1.5)
    if catalog is None:
        catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    # The /Root catalog is excluded from ObjStm packing (matches upstream
    # ``COSWriterCompressionPool.addObjectToPool``, which forces the catalog
    # to the top-level bucket). The exclusion tests below pair their single
    # *excluded* object with this benign packable filler so at least one
    # ObjStm is always emitted to inspect.
    filler = COSDictionary()
    filler.set_int(COSName.get_pdf_name("Filler"), 1)
    catalog.set_item(COSName.get_pdf_name("Filler"), COSObject(98, 0, resolved=filler))
    cat_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, cat_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


def _write_xref_stream(doc: COSDocument, *, object_stream: bool = True) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True, object_stream=object_stream) as w:
        w.write(doc)
    return sink.getvalue()


def _decode_objstm_body(pdf_bytes: bytes) -> tuple[bytes, int, int]:
    """Locate the first /Type /ObjStm in ``pdf_bytes`` and return
    (decoded_body, n_value, first_value)."""
    objstm_idx = pdf_bytes.find(b"/Type /ObjStm")
    if objstm_idx == -1:
        objstm_idx = pdf_bytes.find(b"/Type/ObjStm")
    assert objstm_idx != -1, "no ObjStm in output"
    # Pull dict around it — back up to the nearest "<num> <gen> obj".
    obj_match = list(re.finditer(rb"(?m)^(\d+) (\d+) obj\b", pdf_bytes))
    objstm_frame_start = max(m.start() for m in obj_match if m.start() < objstm_idx)
    region = pdf_bytes[objstm_frame_start:]

    n_match = re.search(rb"/N\s+(\d+)", region)
    first_match = re.search(rb"/First\s+(\d+)", region)
    assert n_match is not None and first_match is not None
    n_value = int(n_match.group(1))
    first_value = int(first_match.group(1))

    stream_marker = region.index(b"stream")
    body_start = stream_marker + len(b"stream")
    if region[body_start:body_start + 2] == b"\r\n":
        body_start += 2
    elif region[body_start:body_start + 1] in (b"\n", b"\r"):
        body_start += 1
    body_end = region.index(b"endstream", body_start)
    while body_end > body_start and region[body_end - 1] in (0x0A, 0x0D):
        body_end -= 1
    decoded = zlib.decompress(region[body_start:body_end])
    return decoded, n_value, first_value


def _make_doc_with_packable_kids(count: int) -> COSDocument:
    catalog = COSDictionary()
    kids = COSArray()
    for obj_num in range(2, count + 2):
        child = COSDictionary()
        child.set_int(COSName.get_pdf_name("Ord"), obj_num)
        kids.add(COSObject(obj_num, 0, resolved=child))
    catalog.set_item(COSName.get_pdf_name("Kids"), kids)
    return _make_doc(catalog)


# ---------- /N + /First wire format ----------------------------------------


def test_n_and_first_header_match_index_layout() -> None:
    """/N counts packed objects; /First is the byte offset where the
    first body begins (i.e., the length of the index header + separator)."""
    doc = _make_doc_with_packable_kids(3)
    out = _write_xref_stream(doc)
    decoded, n_value, first_value = _decode_objstm_body(out)
    # Index header sits at bytes [0:first_value); body sits at [first_value:].
    index_bytes = decoded[:first_value]
    body_bytes = decoded[first_value:]
    # Parse the index: pairs of integers ``<obj_num> <body_offset>``.
    pairs = re.findall(rb"(\d+)\s+(\d+)", index_bytes)
    assert len(pairs) == n_value, (
        f"/N says {n_value} packed objects but index has {len(pairs)} pairs"
    )
    # First body offset must be 0 — relative to /First.
    assert int(pairs[0][1]) == 0
    # Body length must equal the last pair's offset plus the length of
    # the last serialized body (we just sanity-check non-empty here).
    assert len(body_bytes) > 0


def test_packed_object_numbers_are_monotonic() -> None:
    """The xref-stream pairs ``(objstm_num, index)`` so packed objects
    must be ordered by object number — otherwise the reader's resolver
    can't map a key to its slot."""
    doc = _make_doc_with_packable_kids(5)
    out = _write_xref_stream(doc)
    decoded, _, first_value = _decode_objstm_body(out)
    index_bytes = decoded[:first_value]
    nums = [int(p[0]) for p in re.findall(rb"(\d+)\s+(\d+)", index_bytes)]
    assert nums == sorted(nums)


def test_body_offsets_are_strictly_increasing() -> None:
    """ObjStm body offsets must be strictly increasing — each body
    starts where the previous one ended."""
    doc = _make_doc_with_packable_kids(4)
    out = _write_xref_stream(doc)
    decoded, _, first_value = _decode_objstm_body(out)
    index_bytes = decoded[:first_value]
    offsets = [int(p[1]) for p in re.findall(rb"(\d+)\s+(\d+)", index_bytes)]
    assert offsets == sorted(set(offsets))


# ---------- PDFBOX-3678 exclusions -----------------------------------------


def test_stream_object_is_not_packed_into_objstm() -> None:
    """ISO 32000-1 §7.5.7: a stream cannot be packed inside another
    stream. Even with object_stream=True the COSStream payload must
    remain a free-standing indirect."""
    body = b"hello world" * 16
    encoded = zlib.compress(body)
    payload = COSStream()
    payload.set_raw_data(encoded)
    payload.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    payload.set_int(COSName.LENGTH, len(encoded))  # type: ignore[attr-defined]

    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Body"), COSObject(2, 0, resolved=payload))
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    # Decode the ObjStm body and verify the payload bytes are NOT inside it.
    decoded, _, _ = _decode_objstm_body(out)
    assert encoded not in decoded


def test_signature_dict_is_not_packed() -> None:
    """Signature dictionaries rely on the on-disk byte range; packing
    them into an ObjStm would invalidate the digest."""
    sig = COSDictionary()
    sig.set_name(COSName.TYPE, "Sig")  # type: ignore[attr-defined]
    sig.set_name(COSName.get_pdf_name("Filter"), "Adobe.PPKLite")

    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Sig"), COSObject(2, 0, resolved=sig))
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    # The ObjStm body must not contain the /Type /Sig dict.
    decoded, _, _ = _decode_objstm_body(out)
    assert b"/Type /Sig" not in decoded and b"/Type/Sig" not in decoded


def test_doctimestamp_dict_is_not_packed() -> None:
    """/Type /DocTimeStamp dictionaries are signature-like and must
    stay out of ObjStm bodies for the same byte-range reason."""
    ts = COSDictionary()
    ts.set_name(COSName.TYPE, "DocTimeStamp")  # type: ignore[attr-defined]

    catalog = COSDictionary()
    catalog.set_item(
        COSName.get_pdf_name("Stamp"), COSObject(2, 0, resolved=ts)
    )
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    decoded, _, _ = _decode_objstm_body(out)
    assert (
        b"/Type /DocTimeStamp" not in decoded
        and b"/Type/DocTimeStamp" not in decoded
    )


def test_generation_nonzero_object_is_not_packed() -> None:
    """ISO 32000-1 §7.5.7 — type-2 xref entries can only address gen=0
    objects. The packer must skip any (num, gen!=0) candidate."""
    child = COSDictionary()
    child.set_int(COSName.get_pdf_name("Marker"), 7777)
    # Generation 5 — type-2 xref can't represent this.
    catalog = COSDictionary()
    catalog.set_item(COSName.get_pdf_name("Gen5"), COSObject(2, 5, resolved=child))
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    decoded, _, _ = _decode_objstm_body(out)
    # /Marker 7777 must NOT be inside the ObjStm body (it's still emitted
    # as a free-standing indirect somewhere in the file).
    assert b"/Marker 7777" not in decoded
    # But the marker must appear elsewhere in the file (free-standing).
    assert b"/Marker 7777" in out


# ---------- chunking behaviour ---------------------------------------------


def test_multiple_objstms_emitted_when_chunk_size_exceeded() -> None:
    """When the candidate set exceeds the writer's per-stream chunk size
    (CompressParameters.DEFAULT_OBJECT_STREAM_SIZE = 200) the writer
    must spread them across multiple /Type /ObjStm objects."""
    doc = _make_doc_with_packable_kids(250)
    out = _write_xref_stream(doc)
    objstm_count = out.count(b"/Type /ObjStm") + out.count(b"/Type/ObjStm")
    assert objstm_count >= 2, (
        f"expected >=2 ObjStms for 250 candidates; saw {objstm_count}"
    )


# ---------- wave 1502: value-equality reference vs inline ------------------
#
# Upstream ``COSWriterCompressionPool`` keeps a value-hashed
# ``HashMap<COSBase, COSObjectKey>`` (COSObjectPool). For the scalar COS types
# (string / integer / float / name / boolean) ``COSBase.equals`` / ``hashCode``
# are value-based, so when a *direct* scalar inside a packed container is
# value-equal to an already-registered *indirect* scalar, upstream writes it as
# an ``N G R`` reference rather than inlining the value
# (``COSWriterObjectStream.writeObject`` → ``compressionPool.contains(base)``).
# Containers (dict / array / stream) match by identity only.


def test_direct_scalar_value_equal_to_indirect_emitted_as_reference() -> None:
    """A direct ``COSString`` value-equal to a registered indirect string is
    serialised as ``N G R`` inside the ObjStm body, not inlined — mirroring
    upstream's value-hashed compression pool (acroform.pdf object 77's
    ``[(BMW) 75 0 R (VW) (Audi)]``)."""
    catalog = COSDictionary()
    # Indirect string object 5 = (Porsche).
    porsche_indirect = COSString("Porsche")
    catalog.set_item(
        COSName.get_pdf_name("DV"), COSObject(5, 0, resolved=porsche_indirect)
    )
    # A packed dict holding an /Opt array with a *separate* (Porsche) instance.
    opt_holder = COSDictionary()
    opt = COSArray()
    opt.add(COSString("BMW"))
    opt.add(COSString("Porsche"))  # distinct instance, value-equal to obj 5
    opt.add(COSString("VW"))
    opt.add(COSString("Audi"))
    opt_holder.set_item(COSName.get_pdf_name("Opt"), opt)
    catalog.set_item(
        COSName.get_pdf_name("Holder"), COSObject(6, 0, resolved=opt_holder)
    )
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    decoded, _, _ = _decode_objstm_body(out)
    # The value-equal (Porsche) must appear as a reference to object 5, not as
    # an inlined (Porsche) literal inside the /Opt array. The other (unique)
    # strings stay inlined.
    assert b"5 0 R" in decoded, "value-equal indirect string was not referenced"
    assert b"(BMW)" in decoded
    assert b"(VW)" in decoded
    assert b"(Audi)" in decoded
    # (Porsche) appears at most once — only as the indirect object's own body,
    # never inlined inside the /Opt array.
    assert decoded.count(b"(Porsche)") == 1


def test_direct_integer_value_equal_to_indirect_emitted_as_reference() -> None:
    """The value-equality reference rule also applies to ``COSInteger``
    (another value-hashed scalar type upstream)."""
    catalog = COSDictionary()
    # Indirect integer object 5 = 42.
    catalog.set_item(
        COSName.get_pdf_name("DV"), COSObject(5, 0, resolved=COSInteger.get(42))
    )
    holder = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(7))
    arr.add(COSInteger.get(42))  # value-equal to indirect integer object 5
    holder.set_item(COSName.get_pdf_name("Vals"), arr)
    catalog.set_item(
        COSName.get_pdf_name("Holder"), COSObject(6, 0, resolved=holder)
    )
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    decoded, _, _ = _decode_objstm_body(out)
    assert b"5 0 R" in decoded, "value-equal indirect integer was not referenced"
    # The 7 stays inlined; the value-equal 42 becomes a reference, so the only
    # bare 42 token is the indirect object's own body.
    assert b"[7 5 0 R ]" in decoded or b"[7 5 0 R]" in decoded


def test_unique_direct_scalar_stays_inlined() -> None:
    """A direct scalar with NO value-equal indirect counterpart is still
    inlined — the value-equality rule must not over-reference."""
    catalog = COSDictionary()
    holder = COSDictionary()
    arr = COSArray()
    arr.add(COSString("Unique-Value-XYZ"))
    holder.set_item(COSName.get_pdf_name("Vals"), arr)
    catalog.set_item(
        COSName.get_pdf_name("Holder"), COSObject(6, 0, resolved=holder)
    )
    doc = _make_doc(catalog)
    out = _write_xref_stream(doc)
    decoded, _, _ = _decode_objstm_body(out)
    assert b"(Unique-Value-XYZ)" in decoded
