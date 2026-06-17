"""Live PDFBox differential parity for xref-stream ``/Index`` multi-subsection parsing.

PDF 32000-1 §7.5.8.2 — a cross-reference stream's ``/Index`` array is a
sequence of ``[start_1 count_1 start_2 count_2 ...]`` pairs. Each pair names
a contiguous block of object numbers; the encoded xref rows map onto those
object numbers in order, walking the subsections left to right. When
``/Index`` is absent the default is ``[0 Size]`` — a single contiguous block.

Wave 1453 already pinned the orthogonal ``/W`` field-width axis
(``test_xref_w_fields_oracle.py``). This file targets the *row → object-number*
mapping: a ``/Index`` with MULTIPLE NON-CONTIGUOUS subsections (e.g.
``[0 1 5 6]`` → object 0, then objects 5,6,7,8,9,10) so the mapping is
non-trivial. A parser that ignores ``/Index`` and assumes ``0..Size-1`` (or
that mis-walks the subsection boundary) mis-numbers every object after the
first subsection — the catalog / page tree / content stream then resolves to
the wrong bytes (or not at all).

Probe :class:`XrefIndexSubsectionsProbe`
(``oracle/probes/XrefIndexSubsectionsProbe.java``) emits ``pages`` /
``object_count`` / a sorted ``xref=OBJNUM:GEN:OFFSET`` map / ``text``.
pypdfbox must assign the rows to the identical object numbers, so the whole
resolved xref map (not just the page count) is compared key for key.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------- fixture build

# The five document objects are deliberately numbered 5..9 (NOT 1..5) so the
# xref stream's /Index must carry a second, non-contiguous subsection to reach
# them. Object 0 is the free-list head; object 10 is the xref stream itself.
_CATALOG_NUM = 5
_PAGES_NUM = 6
_PAGE_NUM = 7
_CONTENTS_NUM = 8
_FONT_NUM = 9
_XREF_NUM = 10

_BODY_TEXT = "Index subsection probe text"


def _objects() -> dict[int, bytes]:
    contents = (
        b"BT /F1 12 Tf 50 700 Td (" + _BODY_TEXT.encode("ascii") + b") Tj ET"
    )
    return {
        _CATALOG_NUM: b"<< /Type /Catalog /Pages %d 0 R >>" % _PAGES_NUM,
        _PAGES_NUM: b"<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % _PAGE_NUM,
        _PAGE_NUM: (
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (_PAGES_NUM, _FONT_NUM, _CONTENTS_NUM)
        ),
        _CONTENTS_NUM: (
            b"<< /Length %d >>\nstream\n" % len(contents) + contents + b"\nendstream"
        ),
        _FONT_NUM: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }


# Standard /W shape: 1-byte type, 4-byte offset, 2-byte gen/index.
_WIDTHS = (1, 4, 2)


def _pack(t: int, off: int, third: int) -> bytes:
    w0, w1, w2 = _WIDTHS
    return t.to_bytes(w0, "big") + off.to_bytes(w1, "big") + third.to_bytes(w2, "big")


def _build_pdf(index_array: bytes, subsection_objnums: list[int]) -> bytes:
    """Hand-author a single-revision PDF whose ONLY xref is a stream with a
    multi-subsection ``/Index``.

    ``subsection_objnums`` is the object-number sequence the ``/Index`` pairs
    expand to, in row order (including the leading free-head object 0). The
    encoded rows are emitted in exactly that order, so the parser must use
    ``/Index`` — not a naive ``0..Size-1`` counter — to land each row on the
    right object number.
    """
    objs = _objects()
    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")

    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"

    xref_stream_off = len(out)
    offsets[_XREF_NUM] = xref_stream_off

    records = bytearray()
    for objnum in subsection_objnums:
        if objnum == 0 or objnum not in offsets:
            # Free-list head / placeholder free entry: type 0, gen 0xFFFF.
            records += _pack(0, 0, 0xFFFF)
        else:
            records += _pack(1, offsets[objnum], 0)

    compressed = zlib.compress(bytes(records))
    size = max(subsection_objnums) + 1
    out += (
        b"%d 0 obj\n<< /Type /XRef /Size %d /Index " % (_XREF_NUM, size)
        + index_array
        + b" /W [1 4 2] /Filter /FlateDecode /Root %d 0 R /Length " % _CATALOG_NUM
        + str(len(compressed)).encode("ascii")
        + b" >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_stream_off).encode("ascii") + b"\n%%EOF\n"
    return bytes(out)


# ---------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, object]:
    """Parse the probe's stdout into ``pages`` / ``object_count`` / ``xref``
    (a sorted list of ``OBJNUM:GEN:OFFSET`` strings) / ``text``. The ``text=``
    line is last and verbatim (may contain ``=`` / newlines)."""
    fields: dict[str, object] = {}
    xref: list[str] = []
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
        if key == "xref":
            xref.append(value)
        else:
            fields[key] = value
        i += 1
    fields["xref"] = xref
    return fields


def _py_facts(path: Path) -> dict[str, object]:
    """Mirror the probe's facts via pypdfbox."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        # Sort numerically by (objnum, gen) to match the Java TreeMap order
        # rather than lexicographic string order.
        xref_lines = [
            f"{n}:{g}:{o}"
            for (n, g, o) in sorted(
                (k.get_number(), k.get_generation(), off)
                for k, off in cos.get_xref_table().items()
            )
        ]
        return {
            "pages": str(doc.get_number_of_pages()),
            "object_count": str(len(cos.get_xref_table())),
            "xref": xref_lines,
            "text": PDFTextStripper().get_text(doc),
        }
    finally:
        doc.close()


def _sorted_xref(java_xref: list[str]) -> list[str]:
    """Sort the Java xref lines numerically by (objnum, gen) so the two sides
    use the same ordering regardless of how each emitted them."""
    return [
        f"{n}:{g}:{o}"
        for (n, g, o) in sorted(
            (int(a), int(b), int(c))
            for a, b, c in (ln.split(":") for ln in java_xref)
        )
    ]


# ---------------------------------------------------------------- cases

# label, /Index bytes, the object-number sequence the rows expand to.
_CASES = [
    (
        "two_subsections",
        # [0 1 5 6] → object 0, then objects 5,6,7,8,9,10.
        b"[0 1 5 6]",
        [0, _CATALOG_NUM, _PAGES_NUM, _PAGE_NUM, _CONTENTS_NUM, _FONT_NUM, _XREF_NUM],
    ),
    (
        "three_subsections",
        # [0 1 5 4 9 2] → object 0; objects 5,6,7,8; objects 9,10.
        b"[0 1 5 4 9 2]",
        [0, _CATALOG_NUM, _PAGES_NUM, _PAGE_NUM, _CONTENTS_NUM, _FONT_NUM, _XREF_NUM],
    ),
    (
        "default_when_absent_equivalent",
        # A single contiguous subsection that still skips the free head onto
        # the high object numbers: [0 1 5 6] covers 0 then 5..10 — exercised
        # above; here we pin the explicit [0 11] full-range form for contrast.
        b"[0 11]",
        # Rows for 0..10; objects 1,2,3,4 are absent from the file so emit
        # them as free entries (type 0) — PDFBox tolerates free rows that
        # point nowhere as long as the in-use objects resolve.
        [0, 1, 2, 3, 4, _CATALOG_NUM, _PAGES_NUM, _PAGE_NUM, _CONTENTS_NUM, _FONT_NUM, _XREF_NUM],
    ),
]


# ---------------------------------------------------------------- tests


@requires_oracle
@pytest.mark.parametrize(
    ("label", "index_array", "objnums"), _CASES, ids=[c[0] for c in _CASES]
)
def test_xref_index_subsections_match_pdfbox(
    tmp_path: Path,
    label: str,
    index_array: bytes,
    objnums: list[int],
) -> None:
    """For each ``/Index`` shape, pypdfbox maps the xref-stream rows onto the
    identical object numbers PDFBox does: same page count, same xref-table
    size, same resolved (objnum, gen, offset) map, same extracted text."""
    pdf = tmp_path / f"xref_index_{label}.pdf"
    pdf.write_bytes(_build_pdf(index_array, objnums))

    java = _parse_facts(run_probe_text("XrefIndexSubsectionsProbe", "facts", str(pdf)))
    py = _py_facts(pdf)

    assert java["pages"] == "1", (
        f"PDFBox failed to parse the /Index={index_array!r} fixture — "
        "fixture is broken"
    )

    assert py["pages"] == java["pages"], (
        f"page count differs for /Index={index_array!r} "
        f"(py={py['pages']} java={java['pages']})"
    )
    assert py["object_count"] == java["object_count"], (
        f"xref-table size differs for /Index={index_array!r} "
        f"(py={py['object_count']} java={java['object_count']})"
    )
    assert py["xref"] == _sorted_xref(java["xref"]), (
        f"resolved object map differs for /Index={index_array!r} — a row "
        "landed on the wrong object number\n"
        f"py  ={py['xref']}\njava={_sorted_xref(java['xref'])}"
    )
    assert py["text"] == java["text"], (
        f"extracted text differs for /Index={index_array!r} — a mis-mapped "
        "row routes the content stream to the wrong bytes"
    )


@requires_oracle
def test_xref_index_non_contiguous_objects_resolve(tmp_path: Path) -> None:
    """Targeted pin on the non-contiguous two-subsection case: the document
    objects live at 5..9 and are only reachable through ``/Index [0 1 5 6]``'s
    second subsection. PDFBox must recover the body text (proves the bytes are
    legal) and pypdfbox must produce the byte-identical text — a parser that
    assumed ``0..Size-1`` would have placed the catalog at object 1 (which has
    no row) and failed to find a page tree."""
    objnums = [0, _CATALOG_NUM, _PAGES_NUM, _PAGE_NUM, _CONTENTS_NUM, _FONT_NUM, _XREF_NUM]
    pdf = tmp_path / "xref_index_noncontig.pdf"
    pdf.write_bytes(_build_pdf(b"[0 1 5 6]", objnums))

    java = _parse_facts(run_probe_text("XrefIndexSubsectionsProbe", "facts", str(pdf)))
    py = _py_facts(pdf)

    assert java["text"] == _BODY_TEXT + "\n", (
        "PDFBox could not recover the page text — fixture broken"
    )
    assert py["text"] == java["text"]
    assert py["pages"] == "1"
    assert py["xref"] == _sorted_xref(java["xref"])
