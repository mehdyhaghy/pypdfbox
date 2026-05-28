"""Live PDFBox differential parity for /Prev-chained trailer resolution.

A multi-section (incrementally-updated) PDF carries several xref sections, each
closed by its own trailer and linked back to the previous one via ``/Prev``.
The consolidated document trailer that ``COSDocument.getTrailer()`` exposes is
the *merge* of these section trailers: the newest section's keys win, and any
key the newest section omits falls back down the ``/Prev`` chain (PDF 32000-1
§7.5.6, mirrored by PDFBox's ``XrefTrailerResolver``).

This test builds multi-section fixtures in-memory that exercise the merge
precedence directly:

  * ``REPOINT_ROOT`` — the update section re-points ``/Root`` to a brand-new
    catalog object and adds a new ``/Info``; the resolved ``/Root`` / ``/Info``
    / ``/ID`` / ``/Size`` must all come from the *newest* section.
  * ``OMIT_INFO`` — the update section's trailer omits ``/Info`` entirely; the
    resolved ``/Info`` must fall back to the base section's value.
  * ``ADD_INFO`` — the base section has no ``/Info``; the update section adds
    one; the resolved trailer must surface it.

For each, Apache PDFBox 3.0.7 resolves the trailer via the ``TrailerResolveProbe``
Java probe and emits a canonical JSON summary of the resolved keys (``/Root``
ref, catalog object key + ``/Type``, ``/Info`` ref, ``/Size``, ``/Encrypt``
presence, ``/ID`` string byte-lengths). pypdfbox parses the same bytes and emits
the same summary with identical emit rules; the two must match character for
character.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_string import COSString
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_parser import PDFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


def _obj(num: int, body: str) -> bytes:
    return f"{num} 0 obj\n{body}\nendobj\n".encode("latin-1")


def _build_base(buf: bytearray, info: bool) -> int:
    """Append the base section (catalog 1, pages 2, page 3, optional info 4)
    plus its xref + trailer. Returns the base xref byte offset."""
    offsets: dict[int, int] = {}

    def add(num: int, body: str) -> None:
        offsets[num] = len(buf)
        buf.extend(_obj(num, body))

    add(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add(3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")
    last = 4
    if info:
        add(4, "<< /Title (Original Title) /Author (Alice) >>")
        last = 5

    xref_off = len(buf)
    buf.extend(f"xref\n0 {last}\n".encode("latin-1"))
    buf.extend(b"0000000000 65535 f \n")
    for num in range(1, last):
        buf.extend(f"{offsets[num]:010d} 00000 n \n".encode("latin-1"))
    buf.extend(b"trailer\n")
    info_entry = " /Info 4 0 R" if info else ""
    buf.extend(
        (
            f"<< /Size {last} /Root 1 0 R{info_entry} "
            "/ID [<0123456789ABCDEF0123456789ABCDEF> "
            "<0123456789ABCDEF0123456789ABCDEF>] >>\n"
        ).encode("latin-1")
    )
    buf.extend(b"startxref\n")
    buf.extend(f"{xref_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return xref_off


def _multi_section_pdf(kind: str) -> bytes:
    """Build a two-section incremental-update PDF.

    ``kind``:
      * ``"repoint_root"`` — update re-points /Root + adds /Info, new /ID.
      * ``"omit_info"`` — base has /Info; update trailer omits /Info.
      * ``"add_info"`` — base has no /Info; update adds /Info.
    """
    buf = bytearray(_HEADER)
    base_has_info = kind != "add_info"
    base_xref = _build_base(buf, info=base_has_info)

    offsets2: dict[int, int] = {}

    def add2(num: int, body: str) -> None:
        offsets2[num] = len(buf)
        buf.extend(_obj(num, body))

    if kind == "repoint_root":
        add2(5, "<< /Type /Catalog /Pages 2 0 R >>")
        add2(6, "<< /Title (Updated Title) /Author (Bob) /Subject (Rev2) >>")
        new_nums = [5, 6]
        trailer = (
            "<< /Size 7 /Root 5 0 R /Info 6 0 R /Prev "
            f"{base_xref} /ID [<0123456789ABCDEF0123456789ABCDEF> "
            "<FEDCBA9876543210>] >>"
        )
    elif kind == "omit_info":
        # Update only revises the page; trailer keeps /Root 1 0 R, omits /Info
        # so the resolved /Info must fall back to the base's 4 0 R.
        add2(3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>")
        new_nums = [3]
        trailer = (
            "<< /Size 5 /Root 1 0 R /Prev "
            f"{base_xref} /ID [<0123456789ABCDEF0123456789ABCDEF> "
            "<FEDCBA9876543210>] >>"
        )
    elif kind == "add_info":
        # Base had no /Info; the update introduces one (object 4).
        add2(4, "<< /Title (Late Info) /Producer (pypdfbox) >>")
        new_nums = [4]
        trailer = (
            "<< /Size 5 /Root 1 0 R /Info 4 0 R /Prev "
            f"{base_xref} /ID [<0123456789ABCDEF0123456789ABCDEF> "
            "<FEDCBA9876543210>] >>"
        )
    else:  # pragma: no cover - defensive
        raise ValueError(kind)

    xref2_off = len(buf)
    # One contiguous subsection starting at the lowest new object number.
    start = min(new_nums)
    buf.extend(f"xref\n{start} {len(new_nums)}\n".encode("latin-1"))
    for num in sorted(new_nums):
        buf.extend(f"{offsets2[num]:010d} 00000 n \n".encode("latin-1"))
    buf.extend(b"trailer\n")
    buf.extend((trailer + "\n").encode("latin-1"))
    buf.extend(b"startxref\n")
    buf.extend(f"{xref2_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return bytes(buf)


def _pypdfbox_resolve(data: bytes) -> dict[str, object]:
    """Parse ``data`` with pypdfbox and emit the same trailer-resolution
    summary the Java ``TrailerResolveProbe`` produces."""
    parser = PDFParser(RandomAccessReadBuffer(data))
    doc = parser.parse()
    try:
        parser.initial_parse()
        trailer = doc.get_trailer()
        assert trailer is not None
        out: dict[str, object] = {}

        raw_root = trailer.get_item(COSName.ROOT)
        if isinstance(raw_root, COSObject):
            key = f"{raw_root.get_object_number()} {raw_root.get_generation_number()}"
            out["root"] = key
            out["rootIsRef"] = True
            out["catalog"] = key
            resolved = raw_root.get_object()
            if isinstance(resolved, COSDictionary):
                type_name = resolved.get_item(COSName.TYPE)
                if isinstance(type_name, COSName):
                    out["catalogType"] = "/" + type_name.get_name()
        elif isinstance(raw_root, COSDictionary):
            out["root"] = "direct"
            out["rootIsRef"] = False
            type_name = raw_root.get_item(COSName.TYPE)
            if isinstance(type_name, COSName):
                out["catalogType"] = "/" + type_name.get_name()

        raw_info = trailer.get_item(COSName.INFO)
        if isinstance(raw_info, COSObject):
            out["info"] = (
                f"{raw_info.get_object_number()} {raw_info.get_generation_number()}"
            )

        raw_size = trailer.get_item(COSName.SIZE)
        if raw_size is not None and hasattr(raw_size, "int_value"):
            out["size"] = raw_size.int_value()

        out["encrypt"] = trailer.contains_key(COSName.ENCRYPT)

        raw_id = trailer.get_item(COSName.ID)
        if isinstance(raw_id, COSArray):
            lens: list[int] = []
            for i in range(raw_id.size()):
                element = raw_id.get_object(i)
                if isinstance(element, COSString):
                    lens.append(len(element.get_bytes()))
            out["id"] = lens

        return out
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("kind", ["repoint_root", "omit_info", "add_info"])
def test_trailer_resolution_matches_pdfbox(kind: str) -> None:
    data = _multi_section_pdf(kind)
    # The Java probe takes a file path; write the in-memory fixture to a temp
    # file. Close the handle before the probe reads it and unlink afterwards
    # so the path is never held open on Windows (WinError 32).
    with tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        java_json = run_probe_text("TrailerResolveProbe", str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    java = json.loads(java_json)
    py = _pypdfbox_resolve(data)
    assert py == java


@requires_oracle
def test_repoint_root_picks_newest_section() -> None:
    """Regression pin: the resolved /Root is the update section's NEW catalog
    (object 5), not the base section's original catalog (object 1)."""
    data = _multi_section_pdf("repoint_root")
    py = _pypdfbox_resolve(data)
    assert py["root"] == "5 0"
    assert py["catalog"] == "5 0"
    assert py["info"] == "6 0"
    assert py["size"] == 7
    # The newest /ID's second element is the 8-byte <FEDCBA9876543210>.
    assert py["id"] == [16, 8]


@requires_oracle
def test_omit_info_falls_back_to_prev() -> None:
    """Regression pin: when the newest trailer omits /Info, the merge falls
    back down the /Prev chain to the base section's /Info (object 4)."""
    data = _multi_section_pdf("omit_info")
    py = _pypdfbox_resolve(data)
    assert py["root"] == "1 0"
    assert py["info"] == "4 0"
