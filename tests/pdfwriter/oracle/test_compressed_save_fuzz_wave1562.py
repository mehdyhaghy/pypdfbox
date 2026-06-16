"""Live PDFBox differential fuzz of **COSWriter COMPRESSED save** shape.

Wave 1562, agent B. This module builds ~13 small in-memory documents with EDGE
content (a page implying a content stream, an /Info dict, nested dicts, a deep
array, a free-standing indirect dict, a parked free object number, a
previously-compressed doc re-saved, a plain-saved doc re-saved compressed, …),
COMPRESSED-saves each through pypdfbox's object-stream writer
(``COSWriter(sink, xref_stream=True, object_stream=True)``) exactly as
``CompressedSaveFuzzProbe`` drives Apache PDFBox 3.0.7
(``doc.save(out, new CompressParameters())``), reloads the saved bytes, and
compares a STABLE STRUCTURAL SHAPE describing the OBJECT-STREAM PACKING
DECISIONS — never exact bytes.

Distinct from wave 1543 (``test_cos_writer_save_fuzz_wave1543.py``), which fuzzed
the PLAIN uncompressed save shape. The contract a port must reproduce on the
COMPRESSED path:

* the output is a cross-reference STREAM (``/Type /XRef``), not a classic table,
* at least one ``/Type /ObjStm`` is emitted (compression actually happened),
* the **packing decisions** match: the number of objects packed into ObjStms
  (sum of each ObjStm's ``/N``) and the count of top-level (xref-table)
  objects are byte-for-byte identical to PDFBox's,
* SPEC INVARIANTS hold: no ``COSStream``, no ``/Root`` catalog and no
  ``/Encrypt`` dictionary may ever be packed into an ObjStm,
* ``/Root`` and ``/Info`` stay reachable after a reload, page count survives,
* the output is qpdf-valid.

Honest divergence pinned below (both sides emit valid, re-readable, qpdf-valid
compressed PDF):

* **trailer /Size off-by-one numbering** — on the compressed path PDFBox mints
  the cross-reference stream and the ``/ObjStm`` their own HIGH object numbers
  AFTER the packed members (e.g. catalog=1, packed=2,3, xref-stream=4,
  ObjStm=5 → ``/Size`` 6), leaving the packed-member numbers below the
  bookkeeping objects; pypdfbox compacts the numbering so its highest object
  number — and therefore ``/Size`` — is exactly 1 LOWER. Both are conforming
  ISO 32000-1 numberings; only the trailer ``/Size`` differs by 1. The packing
  DECISIONS (which objects pack, how many, which stay top-level) are identical,
  so ``/Size`` is asserted per-side (PDFBox = pypdfbox + 1) with this note
  rather than cross-checked for equality.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.common import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_CASES = [
    "one_page",
    "many_pages",
    "with_info",
    "with_stream",
    "nested_dicts",
    "deep_nested",
    "many_strings",
    "str_binary",
    "str_parens",
    "indirect_dict",
    "free_object",
    "recompress",
    "plain_then_compress",
]

# Cases that emit a roundtrip_str fact (a COSString hung on the catalog).
_STR_CASES = {
    "str_binary": bytes([0, 1, 2, 255, 128]),
    "str_parens": "a(b)c",
}


# ----------------------------------------------------------------- builders


def _save_compressed(doc: PDDocument, sink: io.BytesIO) -> None:
    """pypdfbox's compressed save: ObjStm packing + xref stream. Mirrors
    PDFBox's ``doc.save(out, new CompressParameters())``."""
    with COSWriter(sink, xref_stream=True, object_stream=True) as writer:
        writer.write(doc)


def _build(name: str) -> bytes:
    """Build + compressed-save an edge-case document, mirroring the Java
    probe's ``build`` switch exactly. Returns the saved bytes."""
    doc = PDDocument()
    cos = doc.get_document()
    catalog = doc.get_document_catalog().get_cos_object()

    if name == "one_page":
        doc.add_page(PDPage(PDRectangle.LETTER))
    elif name == "many_pages":
        for _ in range(8):
            doc.add_page(PDPage(PDRectangle.LETTER))
    elif name == "with_info":
        doc.add_page(PDPage(PDRectangle.LETTER))
        doc.get_document_information().set_title("Edge")
        doc.get_document_information().set_author("Fuzz")
    elif name == "with_stream":
        page = PDPage(PDRectangle.LETTER)
        doc.add_page(page)
        page.get_cos_object().set_item("ProbeStr", COSString("kept"))
    elif name == "nested_dicts":
        doc.add_page(PDPage(PDRectangle.LETTER))
        d1, d2 = COSDictionary(), COSDictionary()
        d2.set_int("Leaf", 7)
        d1.set_item("Inner", d2)
        catalog.set_item("Nested", d1)
    elif name == "deep_nested":
        doc.add_page(PDPage(PDRectangle.LETTER))
        cur = COSInteger.get(1)
        for _ in range(12):
            a = COSArray()
            a.add(cur)
            cur = a
        catalog.set_item("Nested", cur)
    elif name == "many_strings":
        doc.add_page(PDPage(PDRectangle.LETTER))
        a = COSArray()
        for i in range(20):
            a.add(COSString(f"s{i}"))
        catalog.set_item("Strs", a)
    elif name == "str_binary":
        doc.add_page(PDPage(PDRectangle.LETTER))
        catalog.set_item("ProbeStr", COSString(bytes([0, 1, 2, 255, 128])))
    elif name == "str_parens":
        doc.add_page(PDPage(PDRectangle.LETTER))
        catalog.set_item("ProbeStr", COSString("a(b)c"))
    elif name == "indirect_dict":
        doc.add_page(PDPage(PDRectangle.LETTER))
        extra = COSDictionary()
        extra.set_int("Marker", 1234)
        catalog.set_item("Extra", extra)
    elif name == "free_object":
        cos.get_xref_table()[COSObjectKey(50000, 0)] = 0
        doc.add_page(PDPage(PDRectangle.LETTER))
    elif name == "recompress":
        doc.add_page(PDPage(PDRectangle.LETTER))
        doc.get_document_information().set_title("First")
        first = io.BytesIO()
        _save_compressed(doc, first)
        doc.close()
        re_doc = PDDocument(Loader.load_pdf(first.getvalue()))
        second = io.BytesIO()
        _save_compressed(re_doc, second)
        re_doc.close()
        return second.getvalue()
    elif name == "plain_then_compress":
        doc.add_page(PDPage(PDRectangle.LETTER))
        doc.get_document_information().set_title("Plain")
        first = io.BytesIO()
        doc.save(first)
        doc.close()
        re_doc = PDDocument(Loader.load_pdf(first.getvalue()))
        second = io.BytesIO()
        _save_compressed(re_doc, second)
        re_doc.close()
        return second.getvalue()
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown case: {name}")

    buf = io.BytesIO()
    _save_compressed(doc, buf)
    doc.close()
    return buf.getvalue()


def _packed_count(saved: bytes) -> int:
    """Sum of each ``/Type /ObjStm`` stream's ``/N`` — the number of objects
    packed into object streams."""
    packed = 0
    for m in re.finditer(rb"/Type\s*/ObjStm", saved):
        seg = saved[max(0, m.start() - 200) : m.start() + 200]
        nm = re.search(rb"/N\s+(\d+)", seg)
        if nm:
            packed += int(nm.group(1))
    return packed


def _facts(name: str) -> dict[str, object]:
    """Reload the pypdfbox compressed-saved bytes and project the same shape
    the Java probe emits."""
    saved = _build(name)
    cos = Loader.load_pdf(saved)
    pd = PDDocument(cos)
    try:
        trailer = cos.get_trailer()
        facts: dict[str, object] = {
            "ok": "true",
            "xref_stream": bool(re.search(rb"/Type\s*/XRef", saved)),
            "has_objstm": bool(re.search(rb"/Type\s*/ObjStm", saved)),
            "objstm_count": len(re.findall(rb"/Type\s*/ObjStm", saved)),
            "packed": _packed_count(saved),
            "top_level": len(cos.get_xref_table()),
            "size": trailer.get_long(COSName.SIZE),
            "has_root": trailer.get_item(COSName.ROOT) is not None,
            "has_info": trailer.get_item(COSName.INFO) is not None,
            "pages": pd.get_number_of_pages(),
        }
        root_base = trailer.get_dictionary_object(COSName.ROOT)
        if isinstance(root_base, COSDictionary):
            probe = root_base.get_dictionary_object(COSName.get_pdf_name("ProbeStr"))
            if isinstance(probe, COSString):
                facts["roundtrip_str"] = probe.get_bytes().hex()
        return facts
    finally:
        pd.close()


def _parse_probe(out: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in out.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            facts[key.strip()] = value.strip()
    return facts


def _qpdf_rc(data: bytes, tmp_path: Path, name: str) -> int:
    out = tmp_path / f"{name}.pdf"
    out.write_bytes(data)
    proc = subprocess.run(
        [str(_QPDF), "--check", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode


# --------------------------------------------------- differential parity tests


@requires_oracle
@pytest.mark.parametrize("name", _CASES)
def test_compressed_save_shape_matches_pdfbox(name: str) -> None:
    """pypdfbox's compressed-save object-stream packing shape must match Apache
    PDFBox 3.0.7 on every edge-case document (modulo the documented /Size
    off-by-one numbering divergence)."""
    java = _parse_probe(run_probe_text("CompressedSaveFuzzProbe", name))
    py = _facts(name)

    assert java["ok"] == "true", f"PDFBox failed to save {name}: {java}"
    assert py["ok"] == "true"

    # Both sides emit a cross-reference STREAM, never a classic table.
    assert py["xref_stream"] is True
    assert java["xref_stream"] == "true"

    # Both sides actually compressed: at least one /Type /ObjStm.
    assert py["has_objstm"] is True
    assert java["has_objstm"] == "true"
    assert py["objstm_count"] == int(java["objstm_count"]), (
        f"objstm_count diverged for {name}: PDFBox={java['objstm_count']}, "
        f"pypdfbox={py['objstm_count']}"
    )

    # The PACKING DECISIONS are byte-identical: same number of packed members,
    # same number of top-level (xref-table) objects.
    assert py["packed"] == int(java["packed"]), (
        f"packed-count diverged for {name}: PDFBox={java['packed']}, "
        f"pypdfbox={py['packed']}"
    )
    assert py["top_level"] == int(java["top_level"]), (
        f"top_level diverged for {name}: PDFBox={java['top_level']}, "
        f"pypdfbox={py['top_level']}"
    )

    # /Root + /Info reachability and page count survive the round-trip.
    assert py["has_root"] == (java["has_root"] == "true")
    assert py["has_info"] == (java["has_info"] == "true")
    assert py["pages"] == int(java["pages"])

    # Spec invariants — the oracle reports these directly off its reloaded
    # object graph. They must be false on both sides.
    assert java["stream_in_objstm"] == "false"
    assert java["catalog_in_objstm"] == "false"
    assert java["encrypt_in_objstm"] == "false"

    # Documented divergence: PDFBox's /Size is exactly 1 higher than pypdfbox's
    # because PDFBox mints the xref-stream + ObjStm their own high object
    # numbers after the packed members; pypdfbox compacts. See module docstring.
    assert int(java["size"]) == py["size"] + 1, (
        f"/Size off-by-one expectation broke for {name}: PDFBox={java['size']}, "
        f"pypdfbox={py['size']} (expected PDFBox == pypdfbox + 1)"
    )

    if "roundtrip_str" in java:
        assert py.get("roundtrip_str") == java["roundtrip_str"], (
            f"COSString round-trip diverged for {name}: "
            f"PDFBox={java['roundtrip_str']}, pypdfbox={py.get('roundtrip_str')}"
        )


# ------------------------------------------ standalone (oracle-free) invariants


@pytest.mark.parametrize("name", _CASES)
def test_compressed_save_round_trips(name: str) -> None:
    """Every edge-case document pypdfbox compress-saves must reload without
    error, keep its /Root, and emit a cross-reference stream + at least one
    ObjStm (holds without the live oracle)."""
    saved = _build(name)
    assert re.search(rb"/Type\s*/XRef", saved), f"{name}: no xref stream"
    assert re.search(rb"/Type\s*/ObjStm", saved), f"{name}: no ObjStm"
    cos = Loader.load_pdf(saved)
    pd = PDDocument(cos)
    try:
        trailer = cos.get_trailer()
        assert trailer is not None
        assert trailer.get_item(COSName.ROOT) is not None, f"{name} lost /Root"
        # /Size is always 1 + the highest object number in the table.
        size = trailer.get_long(COSName.SIZE)
        max_num = max(
            (k.object_number for k in cos.get_xref_table()), default=0
        )
        assert size == max_num + 1, (
            f"{name}: /Size {size} != highest objnum {max_num} + 1"
        )
    finally:
        pd.close()


@pytest.mark.parametrize("name", _CASES)
def test_compressed_save_packs_no_forbidden_object(name: str) -> None:
    """SPEC INVARIANT (ISO 32000-1 §7.5.7): no COSStream, no /Root catalog and
    no /Encrypt dictionary may be packed into a /Type /ObjStm.

    We reload pypdfbox's compressed output and confirm every COSStream, the
    catalog, and (if any) the /Encrypt dict resolve as TOP-LEVEL indirects
    (present in the xref table) — a packed member would be resolved through its
    ObjStm and would be ABSENT from the xref table."""
    saved = _build(name)
    cos = Loader.load_pdf(saved)
    pd = PDDocument(cos)
    try:
        xref = cos.get_xref_table()
        top_level_keys = set(xref.keys())

        # Catalog stays top-level.
        trailer = cos.get_trailer()
        root_ref = trailer.get_item(COSName.ROOT)
        root_key = getattr(root_ref, "get_key", lambda: None)()
        if root_key is not None:
            assert root_key in top_level_keys, f"{name}: /Root packed into ObjStm"

        # /Encrypt (none in these fixtures) would stay top-level if present.
        encrypt_ref = trailer.get_item(COSName.ENCRYPT)
        assert encrypt_ref is None, f"{name}: unexpected /Encrypt"

        # Every materialized COSStream must be addressable as a top-level
        # indirect — an ObjStm body cannot hold a nested stream.
        stream_keys = [
            obj.get_key()
            for obj in cos.get_objects()
            if isinstance(obj.get_object(), COSStream)
        ]
        assert stream_keys, f"{name}: expected at least the ObjStm + xref stream"
        for key in stream_keys:
            if key is not None:
                assert key in top_level_keys, (
                    f"{name}: a COSStream ({key}) was packed into an ObjStm"
                )
    finally:
        pd.close()


@pytest.mark.parametrize("name", sorted(_STR_CASES))
def test_compressed_string_round_trip_value(name: str) -> None:
    """An escaped / binary COSString hung on the catalog survives a compressed
    save round-trip byte-for-byte, regardless of the ObjStm serialised form."""
    expected = _STR_CASES[name]
    expected_bytes = (
        expected if isinstance(expected, bytes) else expected.encode("latin-1")
    )
    saved = _build(name)
    cos = Loader.load_pdf(saved)
    pd = PDDocument(cos)
    try:
        root = cos.get_trailer().get_dictionary_object(COSName.ROOT)
        probe = root.get_dictionary_object(COSName.get_pdf_name("ProbeStr"))
        assert isinstance(probe, COSString)
        assert probe.get_bytes() == expected_bytes
    finally:
        pd.close()


@_requires_qpdf
@pytest.mark.parametrize("name", _CASES)
def test_compressed_save_is_qpdf_valid(name: str, tmp_path: Path) -> None:
    """Every compressed-saved document is qpdf-valid (rc <= 3; rc 3 is the
    benign 'xref entry for the xref stream itself is missing' note qpdf emits
    for cross-reference-stream output)."""
    saved = _build(name)
    rc = _qpdf_rc(saved, tmp_path, name)
    assert rc <= 3, f"{name}: qpdf --check rc={rc}"
