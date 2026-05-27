"""Live PDFBox differential parity for broken-file recovery parsing.

Apache PDFBox's ``Loader.loadPDF`` is lenient by default: when the trailing
``startxref`` offset is garbled, the whole xref table + trailer are missing, or
an individual xref subsection offset is wrong, the parser brute-force-scans the
body for ``N G obj`` definitions and rebuilds the cross-reference + trailer
(``COSParser.retrieveTrailer`` / ``rebuildTrailer`` / ``checkXrefOffsets``).

This module hand-builds a valid 8-object, 2-page PDF (real Helvetica text on
each page) via byte assembly, then PROGRAMMATICALLY CORRUPTS it three ways —
each still recoverable by a brute-force object scan:

* ``startxref`` — the ``startxref`` offset is replaced with a nonsense number;
  the keyword is present but points nowhere.
* ``noxref`` — the entire ``xref`` table + ``trailer`` + ``startxref`` are
  deleted (body objects kept); recovery needs a full brute-force rebuild.
* ``subsection`` — one xref subsection entry (the first content stream) is
  rewritten to a wrong byte offset; recovery needs per-entry correction.

For each, the :class:`RecoveryProbe` Java oracle emits the RECOVERED facts —
``getNumberOfPages()``, ``COSDocument`` xref-table object count, ``/Root`` /
``/Info`` presence, and ``PDFTextStripper`` text — and pypdfbox must produce the
same canonical fingerprint. Where one engine recovers and the other throws is a
high-value divergence (the probe emits ``PARSE_FAIL`` on any throw).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# ---- valid multi-object PDF (built via pypdfbox-compatible byte assembly) ----

_BODY1 = b"BT /F1 24 Tf 72 700 Td (Hello World) Tj ET"
_BODY2 = b"BT /F1 18 Tf 72 700 Td (Page Two Text) Tj ET"


def _build_pdf() -> bytes:
    """Assemble a well-formed 8-object, 2-page PDF with a traditional xref
    table + trailer + ``startxref``."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 7 0 R >> >> /Contents 5 0 R >>"
        ),
        4: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>"
        ),
        5: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(_BODY1), _BODY1),
        6: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(_BODY2), _BODY2),
        7: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        8: b"<< /Producer (pypdfbox-test) /Title (Recovery Fixture) >>",
    }
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_off = len(out)
    n_objs = max(objs) + 1
    out += b"xref\n0 %d\n" % n_objs
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 8 0 R >>\n" % n_objs
    out += b"startxref\n%d\n%%%%EOF" % xref_off
    return bytes(out)


# ---- the three corruption modes ----


def _corrupt_startxref(data: bytes) -> bytes:
    """(a) Garble the ``startxref`` offset to a nonsense number — the
    keyword stays but its target points nowhere."""
    m = re.search(rb"startxref\n(\d+)\n", data)
    assert m is not None
    return data[: m.start(1)] + b"9999999" + data[m.end(1) :]


def _corrupt_noxref(data: bytes) -> bytes:
    """(b) Delete the whole xref table + trailer + startxref, keeping every
    body object. Truncates at the ``xref`` keyword and appends a bare
    ``%%EOF`` so only a full brute-force rebuild can recover the graph."""
    idx = data.rindex(b"\nxref\n")
    return data[:idx] + b"\n%%EOF"


def _corrupt_subsection(data: bytes) -> bytes:
    """(c) Rewrite one xref subsection entry (object 5 — the first content
    stream) to a wrong byte offset; the object body is intact, so a
    per-entry brute-force correction recovers it."""
    xref_idx = data.rindex(b"\nxref\n")
    head = data[:xref_idx]
    tail = data[xref_idx:]
    lines = tail.split(b"\n")
    # lines: ['', 'xref', '0 9', '<free>', '<obj1>', ...]; obj5 -> index 8.
    target = 3 + 5
    assert b" n " in lines[target]
    lines[target] = b"0000000123 00000 n "
    return head + b"\n".join(lines)


_CLEAN = _build_pdf()
_CASES: dict[str, bytes] = {
    "clean": _CLEAN,
    "startxref": _corrupt_startxref(_CLEAN),
    "noxref": _corrupt_noxref(_CLEAN),
    "subsection": _corrupt_subsection(_CLEAN),
}


# ---- pypdfbox-side fingerprint (mirrors RecoveryProbe's output) ----


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _pypdfbox_dump(path: str) -> str:
    """Produce the same canonical recovery fingerprint the Java
    ``RecoveryProbe`` emits, loading ``path`` via the lenient (default)
    ``Loader.load_pdf``. Returns ``PARSE_FAIL\\n`` on any throw."""
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
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_recovery_matches_pdfbox(name: str, tmp_path: Path) -> None:
    """pypdfbox must recover the SAME page count, object count, /Root /Info
    presence, and text as PDFBox 3.0.7 for each corruption mode."""
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(_CASES[name])
    java = run_probe_text("RecoveryProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert py == java
    # Guard against a "both fail identically" green: the recovery target is
    # an actual recovery, not a shared PARSE_FAIL.
    assert java.startswith("pages=")
