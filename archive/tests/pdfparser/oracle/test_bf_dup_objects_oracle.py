"""Live PDFBox differential parity for the brute-force duplicate-object case.

Apache PDFBox's ``BruteForceParser.bfSearchForObjects`` scans the body for
``n g obj`` headers and records each one into its object-offset map via an
unconditional ``Map.put``. When the SAME ``n g obj`` is defined more than once
in the body — a broken / repeatedly-appended file where an object was rewritten
in place but the xref was lost — the LATER (higher) offset overwrites the
earlier one: last occurrence wins. The later copy is the authoritative
definition, so the recovered document resolves the most-recent revision.

pypdfbox originally recorded the FIRST occurrence (``dict.setdefault``), which
made it resolve the stale earlier copy — observable both in the raw offset map
and downstream in the extracted text. This module pins the corrected
last-wins behaviour against the live oracle two ways:

* :class:`BfObjectOffsetsProbe` dumps the raw ``getBFCOSObjectOffsets`` map via
  reflection (no trailer rebuild) — the exact byte offset PDFBox records for
  the duplicated key.
* :class:`RecoveryProbe` drives the full lenient ``Loader.loadPDF`` recovery
  path and emits the recovered page count + extracted text, proving WHICH copy
  the recovered graph actually resolves.

The fixture defines object 5 (the page's content stream) twice: an earlier copy
drawing ``FIRST`` and a later copy drawing ``SECOND``. The xref table is
deleted, forcing a full brute-force rebuild.
"""

from __future__ import annotations

import json
from pathlib import Path

from pypdfbox.cos.cos_name import COSName
from pypdfbox.io import RandomAccessReadBufferedFile
from pypdfbox.loader import Loader
from pypdfbox.pdfparser.cos_parser import COSParser
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# ---- fixture: object 5 defined twice (FIRST earlier, SECOND later) ----

_BODY_FIRST = b"BT /F1 24 Tf 72 700 Td (FIRST) Tj ET"
_BODY_SECOND = b"BT /F1 24 Tf 72 700 Td (SECOND) Tj ET"

_OTHER_OBJS: dict[int, bytes] = {
    1: b"<< /Type /Catalog /Pages 2 0 R >>",
    2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    3: (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 7 0 R >> >> /Contents 5 0 R >>"
    ),
    7: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    8: b"<< /Producer (dup-test) >>",
}


def _stream_obj(n: int, body: bytes) -> bytes:
    return b"%d 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (
        n,
        len(body),
        body,
    )


def _build_dup_pdf() -> bytes:
    """Assemble a 1-page PDF whose content stream (obj 5) is defined twice —
    the EARLIER copy draws ``FIRST``, the LATER copy draws ``SECOND`` — with no
    xref table / trailer / startxref, forcing a full brute-force rebuild."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    out += _stream_obj(5, _BODY_FIRST)  # earlier definition of obj 5
    for n in (1, 2, 3, 7, 8):
        out += b"%d 0 obj\n" % n + _OTHER_OBJS[n] + b"\nendobj\n"
    out += _stream_obj(5, _BODY_SECOND)  # later definition of obj 5 (wins)
    out += b"\n%%EOF"
    return bytes(out)


_DUP_PDF = _build_dup_pdf()


# ---- pypdfbox-side fingerprints ----


def _pypdfbox_offsets(path: str) -> str:
    """Reproduce :class:`BfObjectOffsetsProbe`'s JSON: the raw brute-force
    object-offset map (``"objNum genNum" -> byte offset``), sorted by key."""
    access = RandomAccessReadBufferedFile(path)
    try:
        offsets = COSParser(access).bf_search_for_objects()
        payload = {
            f"{k.object_number} {k.generation_number}": v
            for k, v in offsets.items()
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    finally:
        access.close()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _pypdfbox_recovery(path: str) -> str:
    """Reproduce :class:`RecoveryProbe`'s output via the lenient default
    ``Loader.load_pdf`` recovery path."""
    try:
        cos = Loader.load_pdf(path)
    except Exception:
        return "PARSE_FAIL\n"
    try:
        pd = PDDocument(cos)
        pages = pd.get_number_of_pages()
        objects = len(cos.get_xref_table())
        trailer = cos.get_trailer()
        root = (
            trailer is not None
            and trailer.get_dictionary_object(COSName.ROOT) is not None
        )
        info = (
            trailer is not None
            and trailer.get_dictionary_object(COSName.get_pdf_name("Info"))
            is not None
        )
        text = PDFTextStripper().get_text(pd)
        return (
            f"pages={pages}\n"
            f"objects={objects}\n"
            f"root={'present' if root else 'absent'}\n"
            f"info={'present' if info else 'absent'}\n"
            f"text={_escape(text)}\n"
        )
    except Exception:
        return "PARSE_FAIL\n"
    finally:
        cos.close()


@requires_oracle
def test_bf_dup_object_offset_matches_pdfbox(tmp_path: Path) -> None:
    """The raw brute-force offset map must match PDFBox byte-for-byte — in
    particular the duplicated key (obj 5) must record the LATER offset, not
    the earlier one (last occurrence wins)."""
    pdf_path = tmp_path / "dup.pdf"
    pdf_path.write_bytes(_DUP_PDF)
    java = run_probe_text("BfObjectOffsetsProbe", str(pdf_path))
    py = _pypdfbox_offsets(str(pdf_path))
    assert json.loads(py) == json.loads(java)
    # The fixture's whole point: obj 5 is duplicated; PDFBox keeps the later
    # offset, so guard against a degenerate "both recorded the same single
    # definition" green.
    parsed = json.loads(java)
    assert parsed["5 0"] > parsed["3 0"], parsed


@requires_oracle
def test_bf_dup_object_recovery_resolves_later_copy(tmp_path: Path) -> None:
    """End-to-end: the recovered document must resolve the LATER copy of the
    duplicated content stream (text ``SECOND``), identical to PDFBox."""
    pdf_path = tmp_path / "dup.pdf"
    pdf_path.write_bytes(_DUP_PDF)
    java = run_probe_text("RecoveryProbe", str(pdf_path))
    py = _pypdfbox_recovery(str(pdf_path))
    assert py == java
    # The later copy draws "SECOND"; assert the recovery resolved it (not the
    # stale "FIRST" copy) so the test fails loudly under a first-wins regression.
    assert java == "pages=1\nobjects=6\nroot=present\ninfo=present\ntext=SECOND\\n\n"
