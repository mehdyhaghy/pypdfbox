"""Live PDFBox differential parity for object streams chained via ``/Extends``.

PDF 32000-1 §7.5.7 — an object stream's ``/Extends`` entry references a prior
object stream, forming a chain (ObjStm A ``/Extends`` B ``/Extends`` C). For
*lookup* the chain is informational: a 1.5+ reader resolves each compressed
object through the container named by that object's cross-reference-stream
type-2 entry (``container-object-number, index-within-container``), it does NOT
walk ``/Extends`` to find an object. ``/Extends`` exists so a writer can append
a new ObjStm that logically continues a prior one, and so a reader that
enumerates a whole chain knows the ordering.

The orthogonal two-level ``/Extends`` case is already pinned by
``test_hybrid_xref_oracle.py`` (``extends_objstm_chain.pdf``, one object per
container). This file deepens that to the dimensions the harness brief calls
out — ``/N`` and ``/First`` handling *across the chain*:

* a THREE-level chain (container 11 ``/Extends`` 8 ``/Extends`` 7);
* MULTIPLE objects packed per container (``/N`` = 2 each), so the
  stream-index axis of each xref type-2 entry is exercised, not just the
  container number;
* objects deliberately scattered so the home container of an object is NOT
  predictable from its object number — only the xref type-2 entry (and thus a
  parser that honours ``container,index`` per object) lands each one right.

:class:`ObjStmExtendsProbe` emits, per requested object, ``resolved`` /
``type`` / ``marker`` / ``value`` and the raw ``getXrefTable()`` value
(negative => compressed; magnitude is the home container number) plus page
count and extracted text. pypdfbox must match every field, proving each
object routes to its correct home ObjStm regardless of chain depth.

Fixture is hand-authored in-memory (no on-disk fixture, no new PROVENANCE
binary row).
"""

from __future__ import annotations

import zlib
from pathlib import Path

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------- object layout
#
# Regular (uncompressed) objects 1..5 build the page; object 15 is the xref
# stream. The six payload dictionaries live in three chained ObjStms:
#
#   ObjStm 7  (base, no /Extends)  packs objects  6, 12
#   ObjStm 8  (/Extends 7)         packs objects  9, 13
#   ObjStm 11 (/Extends 8)         packs objects 10, 14
#
# So the chain is 11 -> 8 -> 7 (three levels), each container holds /N = 2
# objects, and the home container of a payload object is NOT a function of its
# number (e.g. 9 lives in 8, 10 lives in 11, 12 lives in 7).

_CATALOG = 1
_PAGES = 2
_PAGE = 3
_CONTENTS = 4
_FONT = 5
_XREF = 15

_BODY_TEXT = "Extends chain three levels"

# payload object number -> (marker string, value int)
_PAYLOAD = {
    6: ("in-base-objstm-a", 100),
    12: ("in-base-objstm-b", 101),
    9: ("in-extending-1-a", 200),
    13: ("in-extending-1-b", 201),
    10: ("in-extending-2-a", 300),
    14: ("in-extending-2-b", 301),
}

# container object number -> (list of packed payload object numbers, /Extends target or None)
_CONTAINERS = {
    7: ([6, 12], None),
    8: ([9, 13], 7),
    11: ([10, 14], 8),
}

_MARKER = COSName.get_pdf_name("Marker")
_VALUE = COSName.get_pdf_name("Value")


def _payload_dict(num: int) -> bytes:
    mark, val = _PAYLOAD[num]
    return (
        b"<< /Type /ExtendsEntry /Marker (%s) /Value %d >>"
        % (mark.encode("ascii"), val)
    )


def _build_objstm_body(packed: list[int]) -> tuple[bytes, int]:
    """Return (decoded ObjStm body bytes, /First) for the packed objects."""
    bodies = [_payload_dict(n) for n in packed]
    # header: "num off num off ...", offsets relative to /First.
    header = bytearray()
    offset = 0
    payload = bytearray()
    for n, body in zip(packed, bodies, strict=True):
        header += b"%d %d " % (n, offset)
        payload += body + b" "
        offset += len(body) + 1
    first = len(header)
    return bytes(header) + bytes(payload), first


def _build_pdf() -> bytes:
    objs: dict[int, bytes] = {}
    contents = (
        b"BT /F1 24 Tf 72 700 Td (" + _BODY_TEXT.encode("ascii") + b") Tj ET"
    )
    objs[_CATALOG] = b"<< /Type /Catalog /Pages %d 0 R >>" % _PAGES
    objs[_PAGES] = b"<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % _PAGE
    objs[_PAGE] = (
        b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
        % (_PAGES, _FONT, _CONTENTS)
    )
    objs[_CONTENTS] = (
        b"<< /Length %d >>\nstream\n" % len(contents) + contents + b"\nendstream"
    )
    objs[_FONT] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}

    # Regular objects.
    for n in (_CATALOG, _PAGES, _PAGE, _CONTENTS, _FONT):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"

    # type-2 entries: payload object num -> (container num, index in container).
    type2: dict[int, tuple[int, int]] = {}
    for container, (packed, extends) in _CONTAINERS.items():
        body, first = _build_objstm_body(packed)
        for idx, pnum in enumerate(packed):
            type2[pnum] = (container, idx)
        compressed = zlib.compress(body)
        ext = b" /Extends %d 0 R" % extends if extends is not None else b""
        offsets[container] = len(out)
        out += (
            b"%d 0 obj\n<< /Type /ObjStm /N %d /First %d%s "
            b"/Length %d /Filter /FlateDecode >>\nstream\n"
            % (container, len(packed), first, ext, len(compressed))
            + compressed
            + b"\nendstream\nendobj\n"
        )

    # XRef stream (object 15). /W [1 4 2]: type, field2, field3.
    xref_off = len(out)
    offsets[_XREF] = xref_off
    size = _XREF + 1
    rows = bytearray()
    for n in range(size):
        if n == 0:
            rows += _pack(0, 0, 0xFFFF)  # free-list head
        elif n in type2:
            container, idx = type2[n]
            rows += _pack(2, container, idx)  # compressed
        elif n in offsets:
            rows += _pack(1, offsets[n], 0)  # uncompressed
        else:
            rows += _pack(0, 0, 0xFFFF)  # absent => free
    compressed_xref = zlib.compress(bytes(rows))
    out += (
        b"%d 0 obj\n<< /Type /XRef /Size %d /W [1 4 2] /Index [0 %d] "
        b"/Root %d 0 R /Length %d /Filter /FlateDecode >>\nstream\n"
        % (_XREF, size, size, _CATALOG, len(compressed_xref))
        + compressed_xref
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF\n"
    return bytes(out)


_W = (1, 4, 2)


def _pack(t: int, f2: int, f3: int) -> bytes:
    return (
        t.to_bytes(_W[0], "big") + f2.to_bytes(_W[1], "big") + f3.to_bytes(_W[2], "big")
    )


# ---------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        key, sep, value = line.partition("=")
        if not sep:
            i += 1
            continue
        if key == "text":
            fields["text"] = "\n".join([value, *lines[i + 1 :]])
            break
        fields[key] = value
        i += 1
    return fields


def _py_facts(path: Path, obj_nums: list[int]) -> dict[str, str]:
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        fields: dict[str, str] = {"pages": str(doc.get_number_of_pages())}
        xref = cos.get_xref_table()
        for num in obj_nums:
            key = COSObjectKey(num, 0)
            obj = cos.get_object(key)
            base = obj.get_object() if obj is not None else None
            fields[f"resolved_{num}"] = "true" if base is not None else "false"
            if isinstance(base, COSDictionary):
                t = base.get_dictionary_object(COSName.TYPE)
                fields[f"type_{num}"] = t.get_name() if isinstance(t, COSName) else ""
                mk = base.get_dictionary_object(_MARKER)
                fields[f"marker_{num}"] = (
                    mk.get_string() if isinstance(mk, COSString) else ""
                )
                fields[f"value_{num}"] = str(base.get_int(_VALUE))
            off = xref.get(key)
            fields[f"xref_{num}"] = "absent" if off is None else str(off)
        fields["text"] = PDFTextStripper().get_text(doc)
        return fields
    finally:
        doc.close()


# ---------------------------------------------------------------- tests

_OBJ_NUMS = sorted(_PAYLOAD)  # 6, 9, 10, 12, 13, 14


@requires_oracle
def test_objstm_extends_three_level_chain_matches_pdfbox(tmp_path: Path) -> None:
    """Every payload object across the three-level ``/Extends`` chain resolves
    to the identical dictionary, page count, and text as PDFBox — and the raw
    xref routing (container number + sign) matches, proving each object lands
    in its correct home ObjStm regardless of chain depth or pack index."""
    pdf = tmp_path / "objstm_extends_3level.pdf"
    pdf.write_bytes(_build_pdf())

    args = ["facts", str(pdf), *(str(n) for n in _OBJ_NUMS)]
    java = _parse_facts(run_probe_text("ObjStmExtendsProbe", *args))
    py = _py_facts(pdf, _OBJ_NUMS)

    # Fixture sanity: PDFBox must itself resolve everything.
    assert java["pages"] == "1", "PDFBox failed to parse the chained fixture"
    for n in _OBJ_NUMS:
        assert java[f"resolved_{n}"] == "true", (
            f"PDFBox failed to resolve object {n} — fixture broken"
        )

    assert py["pages"] == java["pages"]
    for n in _OBJ_NUMS:
        assert py[f"resolved_{n}"] == "true", (
            f"pypdfbox missed object {n} in the /Extends chain"
        )
        assert py[f"type_{n}"] == java[f"type_{n}"] == "ExtendsEntry", n
        assert py[f"marker_{n}"] == java[f"marker_{n}"] == _PAYLOAD[n][0], n
        assert py[f"value_{n}"] == java[f"value_{n}"] == str(_PAYLOAD[n][1]), n
        assert py[f"xref_{n}"] == java[f"xref_{n}"], (
            f"xref routing differs for object {n} — wrong home container "
            f"(py={py[f'xref_{n}']} java={java[f'xref_{n}']})"
        )

    assert py["text"] == java["text"]


@requires_oracle
def test_objstm_extends_routes_each_object_to_its_container(tmp_path: Path) -> None:
    """Targeted pin: object 10 lives in the deepest container (11), object 12
    in the base container (7), and object 9 in the middle (8). Their xref
    type-2 entries must route each to its own container — PDFBox stores the
    home container as a negative value, and pypdfbox must store the identical
    one. A parser that walked ``/Extends`` instead of honouring the per-object
    type-2 entry would mis-route at least one."""
    pdf = tmp_path / "objstm_extends_route.pdf"
    pdf.write_bytes(_build_pdf())

    args = ["facts", str(pdf), "12", "9", "10"]
    java = _parse_facts(run_probe_text("ObjStmExtendsProbe", *args))
    py = _py_facts(pdf, [12, 9, 10])

    # PDFBox routes via negative container numbers; magnitude == container obj.
    assert int(java["xref_12"]) < 0 and int(java["xref_9"]) < 0
    assert int(java["xref_10"]) < 0
    assert py["xref_12"] == java["xref_12"]
    assert py["xref_9"] == java["xref_9"]
    assert py["xref_10"] == java["xref_10"]
    assert py["marker_12"] == "in-base-objstm-b"
    assert py["marker_9"] == "in-extending-1-a"
    assert py["marker_10"] == "in-extending-2-a"
