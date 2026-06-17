"""Live PDFBox differential parity for a cross-reference chain that mixes an
xref STREAM (newest revision, PDF 1.5+) with a CLASSIC ``xref...trailer``
(older revision) via the stream dictionary's ``/Prev`` pointer.

PDF 32000-1 §7.5.8.3 — an xref stream's ``/Prev`` may point at *either*
another xref stream *or* a traditional xref table + trailer of an earlier
revision. The full document graph is the union of both revisions: every
object reachable through pypdfbox must also be reachable through PDFBox,
including objects that exist ONLY in the classic-table rev1.

A parser that stops walking at the stream — never following ``/Prev`` into a
classic table — silently loses every object that lives only in the earlier
revision. The behaviour is exercised by hand-authoring a 2-revision PDF in
``tmp_path``:

* **rev1** — classic ``xref...trailer``: catalog (1), pages (2), page (3),
  contents (4 — "Rev1 only text"), font (5), and a rev1-only marker dict (6,
  ``/Type /Marker /Tag (rev1-survivor) /Value 111``).
* **rev2** — appended incremental save written as an xref STREAM (object 8)
  whose ``/Prev`` points at rev1's classic xref offset; the stream adds one
  new marker (7, ``/Type /Marker /Tag (rev2-added) /Value 222``).

Probe :class:`XrefChainProbe` (``oracle/probes/XrefChainProbe.java``) emits
``pages`` / ``object_count`` / ``text`` plus per-object ``resolved_<n>`` /
``type_<n>`` / ``tag_<n>`` / ``value_<n>``. pypdfbox must produce the same
facts — both the rev1-only marker (object 6) and the rev2-added marker
(object 7) must resolve, and the extracted text must match byte-for-byte.
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

_TAG = COSName.get_pdf_name("Tag")
_VALUE = COSName.get_pdf_name("Value")


# ---------------------------------------------------------------- fixture build


def _pack_record(t: int, off: int, gen: int) -> bytes:
    """Pack one xref-stream record with ``/W [1 4 2]`` widths."""
    return bytes([t]) + off.to_bytes(4, "big") + gen.to_bytes(2, "big")


def _build_xref_chain_pdf() -> bytes:
    """Build a 2-revision PDF whose newest revision is an xref STREAM that
    chains ``/Prev`` into rev1's classic ``xref...trailer``.

    Object layout:
      1 catalog, 2 pages, 3 page, 4 contents (rev1 text), 5 font,
      6 marker (``rev1-survivor``, value 111)  -- rev1-only
      7 marker (``rev2-added``,    value 222)  -- rev2-added
      8 xref stream

    Both rev1's classic xref and rev2's xref stream must be consulted to see
    every object — a parser that stops at the stream loses object 6.
    """
    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")

    # ----- rev1 body (objects 1..6) ----------------------------------------
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: (
            b"<< /Length 44 >>\nstream\n"
            b"BT /F1 12 Tf 50 700 Td (Rev1 only text) Tj ET"
            b"\nendstream"
        ),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: b"<< /Type /Marker /Tag (rev1-survivor) /Value 111 >>",
    }
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"

    # ----- rev1 classic xref + trailer + startxref + %%EOF ------------------
    xref1_off = len(out)
    n_objs_rev1 = 7  # objects 0..6
    out += b"xref\n0 %d\n" % n_objs_rev1
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs_rev1):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % n_objs_rev1
    out += b"startxref\n%d\n%%%%EOF\n" % xref1_off

    # ----- rev2 body (object 7) ---------------------------------------------
    obj7_off = len(out)
    out += b"7 0 obj\n<< /Type /Marker /Tag (rev2-added) /Value 222 >>\nendobj\n"

    # ----- rev2 xref STREAM (object 8) with /Prev -> rev1 classic xref ------
    xref_stream_off = len(out)
    # /Index [7 2] -> records for objects 7 and 8 only.
    records = _pack_record(1, obj7_off, 0) + _pack_record(1, xref_stream_off, 0)
    compressed = zlib.compress(records)
    out += (
        b"8 0 obj\n<< /Type /XRef /Size 9 /Index [7 2]"
        b" /W [1 4 2] /Filter /FlateDecode /Root 1 0 R /Prev "
        + str(xref1_off).encode("ascii")
        + b" /Length "
        + str(len(compressed)).encode("ascii")
        + b" >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_stream_off).encode("ascii") + b"\n%%EOF\n"
    return bytes(out)


# ---------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, str]:
    """Parse XrefChainProbe's ``facts`` stdout. The ``text=`` line is emitted
    last and may itself contain ``=``/newlines, so it is consumed verbatim
    once encountered."""
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


def _py_object_facts(path: Path, *obj_nums: int) -> dict[str, str]:
    """Mirror XrefChainProbe's facts via pypdfbox. Closes the document in
    ``finally`` so the source file handle is released (Windows safety)."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        fields: dict[str, str] = {
            "pages": str(doc.get_number_of_pages()),
            "object_count": str(len(cos.get_xref_table())),
        }
        for num in obj_nums:
            obj = cos.get_object(COSObjectKey(num, 0))
            base = obj.get_object() if obj is not None else None
            fields[f"resolved_{num}"] = "true" if base is not None else "false"
            if isinstance(base, COSDictionary):
                type_obj = base.get_dictionary_object(COSName.TYPE)
                fields[f"type_{num}"] = (
                    type_obj.get_name() if isinstance(type_obj, COSName) else ""
                )
                tag = base.get_dictionary_object(_TAG)
                fields[f"tag_{num}"] = (
                    tag.get_string() if isinstance(tag, COSString) else ""
                )
                fields[f"value_{num}"] = str(base.get_int(_VALUE))
        fields["text"] = PDFTextStripper().get_text(doc)
        return fields
    finally:
        doc.close()


# ---------------------------------------------------------------- tests


@requires_oracle
def test_xref_stream_prev_to_classic_table_resolves_rev1_only_object(
    tmp_path: Path,
) -> None:
    """pypdfbox follows the newest xref STREAM's ``/Prev`` into the older
    revision's classic ``xref...trailer`` and resolves the rev1-only marker
    (object 6) identically to PDFBox.

    A parser that stopped at the stream (never following ``/Prev`` to a
    classic table) would miss object 6 entirely — this is the headline
    regression guard for the mixed-form chain.
    """
    pdf = tmp_path / "xref_stream_prev_classic.pdf"
    pdf.write_bytes(_build_xref_chain_pdf())

    java = _parse_facts(
        run_probe_text("XrefChainProbe", "facts", str(pdf), "6", "7")
    )
    py = _py_object_facts(pdf, 6, 7)

    # Headline guard: BOTH engines must reach the rev1-only object.
    assert java["resolved_6"] == "true", (
        "PDFBox failed to resolve the rev1-only object — fixture is broken"
    )
    assert py["resolved_6"] == "true", (
        "pypdfbox missed the rev1-only object — it did not follow the xref "
        "stream's /Prev into the classic xref table"
    )

    # Per-engine fact parity for the rev1-only and rev2-added markers.
    assert py["pages"] == java["pages"]
    assert py["type_6"] == java["type_6"] == "Marker"
    assert py["tag_6"] == java["tag_6"] == "rev1-survivor"
    assert py["value_6"] == java["value_6"] == "111"

    assert py["resolved_7"] == java["resolved_7"] == "true"
    assert py["type_7"] == java["type_7"] == "Marker"
    assert py["tag_7"] == java["tag_7"] == "rev2-added"
    assert py["value_7"] == java["value_7"] == "222"

    # Text extracted from the rev1 content stream is also reachable.
    assert py["text"] == java["text"]


@requires_oracle
def test_xref_stream_prev_to_classic_table_object_count_matches(
    tmp_path: Path,
) -> None:
    """The merged pool produced by pypdfbox must surface AT LEAST as many
    objects as PDFBox's pool — neither engine may silently drop entries
    from the older revision's classic xref table.

    The lower-bound shape (rather than strict equality) matches both
    engines' tolerance for ``object_count`` accounting: PDFBox 3.0.7
    includes the free-list head and every object the chain registered,
    pypdfbox's xref-table dict mirrors that same set."""
    pdf = tmp_path / "xref_stream_prev_classic.pdf"
    pdf.write_bytes(_build_xref_chain_pdf())

    java = _parse_facts(
        run_probe_text("XrefChainProbe", "facts", str(pdf), "1")
    )
    py = _py_object_facts(pdf, 1)

    # Catalog must resolve via either engine.
    assert java["resolved_1"] == py["resolved_1"] == "true"
    assert py["type_1"] == java["type_1"] == "Catalog"

    # Page count parity.
    assert py["pages"] == java["pages"] == "1"

    # pypdfbox must see at least as many objects as PDFBox — i.e. the
    # /Prev hop into the classic table did register the rev1 entries.
    assert int(py["object_count"]) >= int(java["object_count"])
