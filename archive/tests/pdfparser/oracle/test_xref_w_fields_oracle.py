"""Live PDFBox differential parity for xref-stream ``/W`` field-width parsing.

PDF 32000-1 §7.5.8.3 — every entry in a cross-reference stream has three
fields whose byte widths are declared via the stream-dictionary's ``/W``
array. Real-world producers pick whichever combination keeps the encoded
xref smallest:

* **Compact** ``/W [1 2 1]`` — tiny files (every offset fits in 16 bits,
  every gen/index fits in 8). PDFBox writes this for documents under
  ~64 KiB and any parser that hard-codes wider entries silently slurps
  the next entry's bytes in.
* **Standard** ``/W [1 4 2]`` — the shape PDFBox emits by default
  (4-byte offset, 2-byte gen / index-into-objstm). Already covered by
  the existing `test_xref_chain_oracle.py` fixture, but pinned again
  here so the three-case sweep shares one probe.
* **Large** ``/W [1 8 2]`` — required when any offset exceeds
  ``2^32`` (huge PDFs, 4 GiB+ revisions). The 8-byte field forces the
  parser into big-endian shifts up to 56 bits; a small-int truncation
  bug here is invisible until a real >4 GiB file shows up. Pin this on
  hand-crafted bytes — we do not need to materialise a 4 GiB file to
  exercise the parser's 8-byte arithmetic.

Probe :class:`XrefWFieldsProbe` (``oracle/probes/XrefWFieldsProbe.java``)
emits ``pages`` / ``object_count`` / ``text``. pypdfbox must report the
same facts for each ``/W`` shape — a `/W` decoder that wrong-shifts a
byte mis-routes the offset and the catalog (or page tree, or content
stream) fails to resolve, surfacing as a non-matching ``pages``,
``object_count``, or ``text``.
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


_OBJECTS: dict[int, bytes] = {
    1: b"<< /Type /Catalog /Pages 2 0 R >>",
    2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    3: (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    ),
    4: (
        b"<< /Length 46 >>\nstream\n"
        b"BT /F1 12 Tf 50 700 Td (W-fields probe text) Tj ET"
        b"\nendstream"
    ),
    5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
}


def _pack(t: int, off: int, third: int, widths: tuple[int, int, int]) -> bytes:
    """Pack one xref-stream record under ``widths = (W0, W1, W2)``.

    The caller must pass values that already fit the requested widths —
    the free-list head, in particular, must use ``third=0`` (not
    ``0xFFFF``) when ``W2 == 1``, because PDF xref streams encode every
    record in the fixed widths declared by ``/W`` and a 0xFFFF gen would
    not fit a 1-byte field. PDFBox tolerates this since the free chain
    isn't followed when the document has no actual free entries (the
    only record with type 0 is the head)."""
    w0, w1, w2 = widths
    return (
        t.to_bytes(w0, "big")
        + off.to_bytes(w1, "big")
        + third.to_bytes(w2, "big")
    )


def _build_xref_w_fields_pdf(widths: tuple[int, int, int]) -> bytes:
    """Hand-author a single-revision PDF whose ONLY xref is a stream with
    the requested ``/W`` widths.

    Object layout:
      1 catalog, 2 pages, 3 page, 4 contents, 5 font, 6 xref stream.

    For ``/W [1 8 2]`` the offsets still comfortably fit in 4 bytes — the
    point is to exercise the parser's 8-byte big-endian shift arithmetic
    end-to-end (the high bytes will be zero, but the parser must walk
    every one of them for the record-length bookkeeping to line up). A
    bug like ``int.from_bytes(buf[:4], "big")`` (hard-coded width) or
    ``(b << 24) | (b << 16) | (b << 8) | b`` (truncating shifter) would
    drop the offset.
    """
    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")

    offsets: dict[int, int] = {}
    for n in sorted(_OBJECTS):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + _OBJECTS[n] + b"\nendobj\n"

    # ------ object 6: the xref stream itself --------------------------------
    xref_stream_off = len(out)

    # /Index [0 7] → records for objects 0 (free head) and 1..6.
    # Free-list-head gen is clamped to the maximum that fits W2:
    # ``W2 == 1`` → 0xFF, ``W2 >= 2`` → 0xFFFF. PDFBox accepts either
    # since the chain isn't walked when no real free entries exist.
    free_gen = 0xFFFF if widths[2] >= 2 else 0xFF
    records = _pack(0, 0, free_gen, widths)
    for n in range(1, 6):
        records += _pack(1, offsets[n], 0, widths)
    # Object 6 is the xref stream — its own self-offset.
    records += _pack(1, xref_stream_off, 0, widths)

    compressed = zlib.compress(records)
    w_str = (
        b"["
        + str(widths[0]).encode("ascii")
        + b" "
        + str(widths[1]).encode("ascii")
        + b" "
        + str(widths[2]).encode("ascii")
        + b"]"
    )
    out += (
        b"6 0 obj\n<< /Type /XRef /Size 7 /Index [0 7] /W "
        + w_str
        + b" /Filter /FlateDecode /Root 1 0 R /Length "
        + str(len(compressed)).encode("ascii")
        + b" >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_stream_off).encode("ascii") + b"\n%%EOF\n"
    return bytes(out)


# ---------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, str]:
    """Parse XrefWFieldsProbe's ``facts`` stdout. The ``text=`` line is
    emitted last and may itself contain ``=``/newlines, so it is consumed
    verbatim once encountered."""
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


def _py_facts(path: Path) -> dict[str, str]:
    """Mirror XrefWFieldsProbe's facts via pypdfbox."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        return {
            "pages": str(doc.get_number_of_pages()),
            "object_count": str(len(cos.get_xref_table())),
            "text": PDFTextStripper().get_text(doc),
        }
    finally:
        doc.close()


# ---------------------------------------------------------------- tests


_WIDTHS_CASES = [
    ("compact", (1, 2, 1)),
    ("standard", (1, 4, 2)),
    ("large", (1, 8, 2)),
]


@requires_oracle
@pytest.mark.parametrize(("label", "widths"), _WIDTHS_CASES, ids=[c[0] for c in _WIDTHS_CASES])
def test_xref_w_fields_decode_matches_pdfbox(
    tmp_path: Path,
    label: str,
    widths: tuple[int, int, int],
) -> None:
    """For each ``/W`` width combination (compact / standard / large),
    pypdfbox decodes the xref stream identically to PDFBox: same page
    count, same xref-table size, same extracted text."""
    pdf = tmp_path / f"xref_w_{label}.pdf"
    pdf.write_bytes(_build_xref_w_fields_pdf(widths))

    java = _parse_facts(run_probe_text("XrefWFieldsProbe", "facts", str(pdf)))
    py = _py_facts(pdf)

    # Sanity: PDFBox must be able to read the fixture — otherwise the
    # hand-authored bytes are the bug, not the pypdfbox decoder.
    assert java["pages"] == "1", (
        f"PDFBox failed to parse the /W={widths} fixture — fixture is broken"
    )

    assert py["pages"] == java["pages"], (
        f"pypdfbox page count differs from PDFBox for /W={widths} "
        f"(py={py['pages']} java={java['pages']})"
    )
    assert py["object_count"] == java["object_count"], (
        f"pypdfbox xref-table size differs from PDFBox for /W={widths} "
        f"(py={py['object_count']} java={java['object_count']})"
    )
    assert py["text"] == java["text"], (
        f"pypdfbox extracted text differs from PDFBox for /W={widths} — "
        "a wrong-shifted offset routes the content stream to the wrong "
        "bytes"
    )


@requires_oracle
def test_xref_w_fields_large_8_byte_offset_arithmetic(tmp_path: Path) -> None:
    """Targeted pin on the 8-byte offset width: PDFBox must read the
    fixture (proves the bytes are legal) and pypdfbox must extract the
    exact same body text. A small-int truncation bug in pypdfbox's
    ``parse_value`` (e.g. masking with 0xFFFFFFFF, or hard-coded
    ``int.from_bytes(buf[:4])``) would surface here even when the
    high 4 bytes of the offset are zero, because the per-record byte
    accounting would still be off by 4 bytes per entry."""
    pdf = tmp_path / "xref_w_large.pdf"
    pdf.write_bytes(_build_xref_w_fields_pdf((1, 8, 2)))

    java = _parse_facts(run_probe_text("XrefWFieldsProbe", "facts", str(pdf)))
    py = _py_facts(pdf)

    assert java["text"] == "W-fields probe text\n", (
        "PDFBox could not recover the page text — fixture broken"
    )
    assert py["text"] == java["text"]
    assert py["pages"] == "1"
    assert py["object_count"] == java["object_count"]
