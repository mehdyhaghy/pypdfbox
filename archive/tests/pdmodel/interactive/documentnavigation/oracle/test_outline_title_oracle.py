"""Live PDFBox differential parity for outline item ``/Title`` decoding
(``pypdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem.get_title``).

Wave 1449: PDF text strings — and especially outline titles — may be stored as
PDFDocEncoding (single-byte, PDF 32000-1 §D.3) **or** as UTF-16BE with a
``FE FF`` BOM (or UTF-16LE with ``FF FE``, or UTF-8 with ``EF BB BF`` in PDF
2.0). ``COSString.getString()`` performs the BOM sniff. This test asserts that
pypdfbox's decode is byte-identical to Apache PDFBox's across the four
high-value title-encoding shapes:

  (a) plain ASCII PDFDocEncoding;
  (b) UTF-16BE with BOM containing non-ASCII chars (``café``, ``中文``);
  (c) PDFDocEncoding with high-byte characters (``é`` via ``0xE9``,
      ``€`` via ``0xA0`` — the PDFDocEncoding deviation table);
  (d) absent title.

The fixture is hand-authored at the byte level so we control ``/Title``'s
raw bytes precisely — pypdfbox's own writer would normalise the title via
``COSString(str)`` which auto-selects PDFDocEncoding vs UTF-16BE based on
character set.

Canonical line grammar (must match
``oracle/probes/OutlineTitleEncodingProbe.java``)::

    <depth>\t<titleEscaped>\t<rawHex>

Where ``titleEscaped`` is the decoded title with backslash/newline/CR/tab
escaped and any non-ASCII codepoint emitted as ``\\uXXXX`` / ``\\UXXXXXXXX``
so the line stays pure ASCII; ``null`` for absent titles, ``empty`` for
present-but-empty. ``rawHex`` is uppercase hex of the raw COSString bytes;
``absent`` when the /Title key is missing; ``wrong-type`` when present but
not a COSString.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


def _escape_title(title: str | None) -> str:
    """Mirror ``OutlineTitleEncodingProbe.escapeTitle`` exactly."""
    if title is None:
        return "null"
    if title == "":
        return "empty"
    out: list[str] = []
    for ch in title:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif 0x20 <= cp < 0x7F:
            out.append(ch)
        elif cp <= 0xFFFF:
            out.append(f"\\u{cp:04X}")
        else:
            out.append(f"\\U{cp:08X}")
    return "".join(out)


def _dump_outline(doc: PDDocument) -> str:
    """Reproduce ``OutlineTitleEncodingProbe`` in pypdfbox terms."""
    from pypdfbox.cos import COSName, COSString

    outline = doc.get_document_catalog().get_document_outline()
    lines: list[str] = []
    title_key = COSName.get_pdf_name("Title")

    def raw_hex(item) -> str:
        cos = item.get_cos_object()
        v = cos.get_dictionary_object(title_key)
        if v is None:
            return "absent"
        if not isinstance(v, COSString):
            return "wrong-type"
        return v.get_bytes().hex().upper()

    def walk(node, depth: int) -> None:
        for item in node.children():
            lines.append(
                f"{depth}\t{_escape_title(item.get_title())}\t{raw_hex(item)}"
            )
            walk(item, depth + 1)

    if outline is not None:
        walk(outline, 0)
    # Probe terminates every line with '\n' (including the last).
    return "".join(line + "\n" for line in lines)


def _build_outline_pdf(path: Path) -> None:
    """Hand-author a minimal PDF whose outline items exercise the four
    title-encoding shapes.

    Item 0: title absent (no /Title key on the outline item dictionary).
    Item 1: plain ASCII PDFDocEncoding — bytes ``"Hello"``.
    Item 2: UTF-16BE with BOM — ``café`` (``FE FF`` + UTF-16BE bytes).
    Item 3: UTF-16BE with BOM — ``中文`` (``FE FF`` + UTF-16BE bytes).
    Item 4: PDFDocEncoding with high-byte ``é`` (``0xE9``).
    Item 5: PDFDocEncoding with deviation-table ``€`` (``0xA0``).
    Item 6: empty UTF-16BE BOM-only title (``FE FF`` only).
    Item 7: empty PDFDocEncoding title (zero-length bytes).
    """
    # Build each /Title literal/hex form. We emit hex strings for all
    # non-ASCII payloads to avoid PDF-string-literal escaping pitfalls.
    titles_hex: list[str | None] = [
        None,  # absent
        "Hello".encode("ascii").hex().upper(),  # PDFDocEncoding ASCII
        # UTF-16BE BOM + café
        ("feff" + "café".encode("utf-16-be").hex()).upper(),
        # UTF-16BE BOM + 中文
        ("feff" + "中文".encode("utf-16-be").hex()).upper(),
        # PDFDocEncoding é (0xE9 — identity from ISO-8859-1 mapping)
        "E9",
        # PDFDocEncoding € (0xA0 — PDFDocEncoding deviation)
        "A0",
        # UTF-16BE BOM only — empty UTF-16BE string
        "FEFF",
        # Empty PDFDocEncoding string
        "",
    ]

    # Allocate object numbers up-front so /First, /Next, /Prev, /Last, /Parent
    # references resolve cleanly. Object 1=catalog, 2=pages, 3=page, 4=outline
    # root, 5..N = outline items.
    n_items = len(titles_hex)
    first_item_obj = 5
    last_item_obj = first_item_obj + n_items - 1

    def title_entry(hex_form: str | None) -> str:
        if hex_form is None:
            return ""
        return f" /Title <{hex_form}>"

    item_objs: list[str] = []
    for i, hex_form in enumerate(titles_hex):
        obj_num = first_item_obj + i
        prev_ref = f" /Prev {obj_num - 1} 0 R" if i > 0 else ""
        next_ref = f" /Next {obj_num + 1} 0 R" if i < n_items - 1 else ""
        item_objs.append(
            f"{obj_num} 0 obj\n"
            f"<< /Parent 4 0 R{title_entry(hex_form)}{prev_ref}{next_ref} >>\n"
            f"endobj\n"
        )

    catalog = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R /Outlines 4 0 R >>\nendobj\n"
    pages = "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    page = (
        "3 0 obj\n"
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>\n"
        "endobj\n"
    )
    outline_root = (
        f"4 0 obj\n"
        f"<< /Type /Outlines /First {first_item_obj} 0 R "
        f"/Last {last_item_obj} 0 R /Count {n_items} >>\n"
        f"endobj\n"
    )

    body_parts = [catalog, pages, page, outline_root, *item_objs]
    # Assemble with byte-accurate offsets for the xref.
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    offsets: list[int] = []
    body = bytearray()
    for part in body_parts:
        offsets.append(len(header) + len(body))
        body.extend(part.encode("latin-1"))

    n_objects = 1 + len(body_parts)  # +1 for the free object 0 row
    xref_lines = ["xref", f"0 {n_objects}", "0000000000 65535 f "]
    for off in offsets:
        xref_lines.append(f"{off:010d} 00000 n ")
    xref = ("\n".join(xref_lines) + "\n").encode("latin-1")
    startxref_pos = len(header) + len(body)
    trailer = (
        f"trailer\n<< /Size {n_objects} /Root 1 0 R >>\n"
        f"startxref\n{startxref_pos}\n%%EOF\n"
    ).encode("latin-1")

    path.write_bytes(header + bytes(body) + xref + trailer)


def _build_fixture(tmp_path: Path) -> Path:
    pdf = tmp_path / "outline_title_encodings.pdf"
    _build_outline_pdf(pdf)
    return pdf


@requires_oracle
def test_outline_title_decoding_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's outline title decode equals PDFBox's across all four
    title-encoding shapes (PDFDocEncoding ASCII / high-byte, UTF-16BE BOM,
    absent, empty)."""
    fixture = _build_fixture(tmp_path)
    java = run_probe_text("OutlineTitleEncodingProbe", str(fixture))
    doc = PDDocument.load(str(fixture))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_outline_title_raw_bytes_round_trip(tmp_path: Path) -> None:
    """The raw ``/Title`` ``COSString.getBytes()`` bytes are preserved
    verbatim across the parse — pypdfbox's hex equals PDFBox's hex per
    item."""
    fixture = _build_fixture(tmp_path)
    java = run_probe_text("OutlineTitleEncodingProbe", str(fixture))
    doc = PDDocument.load(str(fixture))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    # Compare third tab-column (rawHex) per line.
    java_hex = [line.split("\t", 2)[2] for line in java.splitlines()]
    py_hex = [line.split("\t", 2)[2] for line in py.splitlines()]
    assert py_hex == java_hex


@requires_oracle
def test_outline_title_utf16be_bom_decoded_unicode(tmp_path: Path) -> None:
    """High-value smoke check: the UTF-16BE BOM titles decode to actual
    Unicode (``café``, ``中文``), not garbage PDFDocEncoded bytes."""
    fixture = _build_fixture(tmp_path)
    doc = PDDocument.load(str(fixture))
    try:
        items = list(doc.get_document_catalog().get_document_outline().children())
        # Item indices match _build_outline_pdf comments.
        assert items[2].get_title() == "café"
        assert items[3].get_title() == "中文"
    finally:
        doc.close()


@requires_oracle
def test_outline_title_pdfdocencoding_high_byte(tmp_path: Path) -> None:
    """PDFDocEncoding high-byte titles decode to the correct Unicode char
    (``\\xE9`` → ``é`` via ISO-8859-1 identity; ``\\xA0`` → ``€`` via
    the deviation table)."""
    fixture = _build_fixture(tmp_path)
    doc = PDDocument.load(str(fixture))
    try:
        items = list(doc.get_document_catalog().get_document_outline().children())
        assert items[4].get_title() == "é"
        assert items[5].get_title() == "€"
    finally:
        doc.close()


@requires_oracle
def test_outline_title_absent_and_empty(tmp_path: Path) -> None:
    """Absent /Title returns ``None``; empty UTF-16BE-BOM-only and
    zero-length PDFDocEncoding titles both return ``""``."""
    fixture = _build_fixture(tmp_path)
    doc = PDDocument.load(str(fixture))
    try:
        items = list(doc.get_document_catalog().get_document_outline().children())
        assert items[0].get_title() is None  # absent /Title
        assert items[6].get_title() == ""  # UTF-16BE BOM only
        assert items[7].get_title() == ""  # zero-length PDFDocEncoding
    finally:
        doc.close()
