"""Live PDFBox differential parity for the document-level COS container —
``org.apache.pdfbox.cos.COSDocument`` — on a PARSED (populated) document.
Wave 1561, agent B.

Where the wave-1537 sibling (``test_cos_document_fuzz_wave1537.py``) built
fresh / empty documents in memory and probed the lifecycle corners, this wave
loads real PDF bytes through the parser and exercises the accessors that only
mean something once the object pool, the xref table, and the trailer are
populated:

* ``get_version`` read from the ``%PDF-x.y`` header (1.4 vs 1.6 vs 1.7);
* ``get_trailer`` presence + ``/Size``;
* ``get_objects_by_type(name)`` count for present types (Page / Pages /
  Catalog) and an absent one, plus the two-arg ``(name, alt)`` overload;
* ``is_encrypted`` + ``get_encryption_dictionary`` presence;
* ``get_document_id`` presence + element count — catches wrong ``/ID`` arity
  verbatim (upstream returns the array as-is, no validation);
* ``get_xref_table`` size (free entries excluded);
* ``get_object_from_pool`` for a present key (resolves a ``/Type``) and an
  absent key (placeholder, null object);
* ``get_highest_xref_object_number``.

The ``CosDocumentLoadFuzzProbe`` Java oracle loads the very same bytes and
emits the identical ``KEY=VALUE`` projection; each non-divergent key is
asserted byte-identical. Honest divergences are pinned BOTH sides with a
comment.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_parser import PDFParser
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------
# Fixture builders — small, hand-rolled single-section PDFs. Object layout is
# always: 1=Catalog, 2=Pages, 3=Page, 4=Page, then optional Encrypt + Info.
# --------------------------------------------------------------------------


def _obj(num: int, body: str) -> bytes:
    return f"{num} 0 obj\n{body}\nendobj\n".encode("latin-1")


def _build(
    *,
    header: bytes = b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n",
    id_clause: str = "/ID [<AABB> <CCDD>]",
    info: bool = True,
    free3: bool = False,
) -> bytes:
    buf = bytearray(header)
    offsets: dict[int, int] = {}

    def add(num: int, body: str) -> None:
        offsets[num] = len(buf)
        buf.extend(_obj(num, body))

    add(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add(2, "<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>")
    add(3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")
    add(4, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")
    next_num = 5
    enc_clause = ""
    info_clause = ""
    if info:
        add(next_num, "<< /Title (T) >>")
        info_clause = f" /Info {next_num} 0 R"
        next_num += 1
    last = next_num

    xref_off = len(buf)
    buf.extend(f"xref\n0 {last}\n".encode("latin-1"))
    buf.extend(b"0000000000 65535 f \n")
    for num in range(1, last):
        if free3 and num == 3:
            buf.extend(b"0000000000 00001 f \n")
        else:
            buf.extend(f"{offsets[num]:010d} 00000 n \n".encode("latin-1"))
    buf.extend(b"trailer\n")
    buf.extend(
        (
            f"<< /Size {last} /Root 1 0 R{info_clause}{enc_clause} {id_clause} >>\n"
        ).encode("latin-1")
    )
    buf.extend(b"startxref\n")
    buf.extend(f"{xref_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return bytes(buf)


_VARIANTS: dict[str, bytes] = {
    # Baseline: version 1.6, two-element /ID, Info present, no encryption.
    "populated": _build(),
    # No /ID entry at all.
    "noid": _build(id_clause=""),
    # Wrong /ID arity — a single element (returned verbatim, size 1).
    "idarity1": _build(id_clause="/ID [<AABB>]"),
    # Wrong /ID arity — three elements (returned verbatim, size 3).
    "idarity3": _build(id_clause="/ID [<AABB> <CCDD> <EEFF>]"),
    # Header declares 1.7.
    "version17": _build(header=b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"),
    # Header declares 1.4 (the COSDocument default).
    "version14": _build(header=b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"),
    # Object 3 (a Page) is a free / deleted xref entry — must NOT be counted by
    # get_objects_by_type (its key never lands in the xref table).
    "free3": _build(free3=True),
}

# ``get_highest_xref_object_number`` is a KNOWN divergence: upstream's
# traditional-xref parser records the highest object number it consumed (5 in
# these fixtures), whereas pypdfbox's parser does not yet feed
# ``set_highest_xref_object_number`` — the COSDocument accessor itself is
# correct (it returns the stored field) but the field is left at its 0 default.
# Pinned BOTH sides; tracked as a parser follow-up in DEFERRED.md (out of this
# wave's cos_document.py scope).
_KNOWN_DIVERGENCES = {
    "highestXRef": ("0", "5"),  # (pypdfbox, java)
}

# In the ``free3`` fixture object 3 is a free / deleted xref entry. Upstream's
# parser never materialises a free entry into the object pool, so neither the
# xref-table pass nor the pool-only pass of getObjectsByType sees it (Page count
# 1). pypdfbox's parser DOES materialise the freed object's still-present body
# into the pool, so getObjectsByType's pool-only second pass (faithfully ported
# from upstream — it must surface in-memory-created objects) re-counts it (Page
# count 2). The divergence is a PARSER artifact, not a COSDocument one: the xref
# table itself correctly omits key (3,0). Pinned BOTH sides; tracked as a parser
# follow-up in DEFERRED.md.
_FREE3_DIVERGENCES = {
    "pageCount": ("2", "1"),  # (pypdfbox, java)
    "pageOrPagesCount": ("3", "2"),  # (pypdfbox, java)
}


def _float(value: float) -> str:
    # Match Java's Float.toString for the header versions we emit (1.4, 1.6,
    # 1.7) — all have exact short decimal reprs.
    return f"{value:.1f}"


def _type_of(cos_obj: object) -> str:
    if cos_obj is None:
        return "null"
    resolved = cos_obj.get_object()  # type: ignore[attr-defined]
    from pypdfbox.cos.cos_dictionary import COSDictionary

    if isinstance(resolved, COSDictionary):
        t = resolved.get_cos_name(COSName.TYPE)
        return "notype" if t is None else "/" + t.get_name()
    return "nondict"


def _py_projection(data: bytes) -> dict[str, str]:
    parser = PDFParser(RandomAccessReadBuffer(data))
    doc = parser.parse()
    try:
        parser.initial_parse()
        out: dict[str, str] = {}

        out["version"] = _float(doc.get_version())

        trailer = doc.get_trailer()
        out["trailer"] = "null" if trailer is None else "nonnull"
        if trailer is None:
            out["size"] = "null"
        else:
            size = trailer.get_int(COSName.SIZE)
            out["size"] = str(size)

        out["pageCount"] = str(len(doc.get_objects_by_type(COSName.PAGE)))
        out["pagesCount"] = str(len(doc.get_objects_by_type(COSName.PAGES)))
        out["catalogCount"] = str(len(doc.get_objects_by_type(COSName.CATALOG)))
        out["absentCount"] = str(
            len(doc.get_objects_by_type(COSName.get_pdf_name("Nope")))
        )
        out["pageOrPagesCount"] = str(
            len(doc.get_objects_by_type(COSName.PAGE, COSName.PAGES))
        )

        out["isEncrypted"] = str(doc.is_encrypted()).lower()
        out["encDict"] = (
            "null" if doc.get_encryption_dictionary() is None else "nonnull"
        )

        id_array = doc.get_document_id()
        out["docId"] = "null" if id_array is None else "nonnull"
        out["docIdSize"] = "null" if id_array is None else str(id_array.size())

        out["xrefSize"] = str(len(doc.get_xref_table()))
        out["highestXRef"] = str(doc.get_highest_xref_object_number())

        present = doc.get_object_from_pool(COSObjectKey(1, 0))
        out["poolPresentNull"] = (
            "null"
            if present is None
            else ("objnull" if present.get_object() is None else "objnonnull")
        )
        out["poolPresentType"] = _type_of(present)

        absent = doc.get_object_from_pool(COSObjectKey(9999, 0))
        out["poolAbsentNull"] = (
            "null"
            if absent is None
            else ("objnull" if absent.get_object() is None else "objnonnull")
        )

        return out
    finally:
        doc.close()


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        key, _, value = raw.partition("=")
        out[key] = value
    return out


@requires_oracle
@pytest.mark.parametrize("variant", sorted(_VARIANTS))
def test_cos_document_load_fuzz_matches_pdfbox(variant: str) -> None:
    data = _VARIANTS[variant]
    # The Java probe takes a file path; write the fixture to a temp file, close
    # the handle before the probe reads it (Windows WinError 32), unlink after.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        java = _parse(run_probe_text("CosDocumentLoadFuzzProbe", str(tmp_path)))
    finally:
        tmp_path.unlink(missing_ok=True)

    py = _py_projection(data)

    divergences = dict(_KNOWN_DIVERGENCES)
    if variant == "free3":
        divergences.update(_FREE3_DIVERGENCES)

    assert set(py) == set(java), f"{variant}: key set mismatch"
    for key in java:
        if key in divergences:
            py_pin, java_pin = divergences[key]
            assert py[key] == py_pin, f"{variant}/{key}: pypdfbox changed: {py[key]!r}"
            assert java[key] == java_pin, (
                f"{variant}/{key}: upstream changed: {java[key]!r}"
            )
        else:
            assert py[key] == java[key], (
                f"{variant}/{key}: py={py[key]!r} != java={java[key]!r}"
            )
