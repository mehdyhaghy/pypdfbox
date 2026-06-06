"""Leading-garbage-before-``%PDF-`` recovery parity, pinned against the live
Apache PDFBox 3.0.7 oracle (wave 1496).

A PDF whose body is structurally clean but carries N bytes of junk *before* the
``%PDF-`` header has two distinct behaviours upstream:

* **Junk that is itself a PDF comment** (``%``-prefixed) or short junk that
  still leaves ``%PDF-`` inside the first 1024-byte scan window — the header is
  located and the file opens via the normal path.
* **Arbitrary binary / long junk that pushes ``%PDF-`` past the scan window** —
  ``COSParser.parsePDFHeader`` does NOT find the marker, but (per upstream) it
  does NOT abort: it logs, assigns the default version, and the parse continues
  into brute-force recovery, which rescans the whole body for ``N G obj``
  definitions and rebuilds the xref + trailer. The document opens with the full
  page count and text regardless of how much junk precedes it.

pypdfbox currently diverges on the second case: ``PDFParser.parse_header``
raises ``PDFParseError("missing %PDF- header")`` as soon as the marker is not in
the 1024-byte window, so a file with >~1019 bytes of leading garbage fails to
load even though every object is intact and brute-force recovery could rebuild
it. This is a STRUCTURAL divergence (the "header-not-found → fall through to
brute-force" recovery path is not wired into pypdfbox's ``parse``); it is pinned
strict-xfail on BOTH sides here and tracked in ``DEFERRED.md``.

The short-garbage case (within the window) is asserted at parity below as a
regression guard so the eventual fix does not break it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text


# ---------------------------------------------------------------------------
# A structurally clean two-page PDF with absolute xref offsets (so prepending
# junk invalidates every offset and only the header-offset / brute-force path
# can recover it).
# ---------------------------------------------------------------------------
def _build_clean_pdf() -> bytes:
    body1 = b"BT /F1 12 Tf 72 720 Td (Hello World) Tj ET"
    body2 = b"BT /F1 12 Tf 72 720 Td (Page Two Text) Tj ET"
    objs = {
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
        5: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body1), body1),
        6: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body2), body2),
        7: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        8: b"<< /Producer (pypdfbox-test) /Title (Header Garbage) >>",
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


_CLEAN = _build_clean_pdf()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _pypdfbox_dump(path: str) -> str:
    """``ok=true / pages / text`` fingerprint matching ``HeaderGarbageProbe``;
    ``ok=false`` on any throw."""
    try:
        cos = Loader.load_pdf(path)
    except Exception:
        return "ok=false\n"
    try:
        pd = PDDocument(cos)
        pages = pd.get_number_of_pages()
        text = PDFTextStripper().get_text(pd)
        return f"ok=true\npages={pages}\ntext={_escape(text)}\n"
    except Exception:
        return "ok=false\n"
    finally:
        cos.close()


# ---------------------------------------------------------------------------
# Within-window garbage: parity regression guard (both load successfully).
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize("n", [16, 256, 900], ids=["g16", "g256", "g900"])
def test_short_leading_garbage_loads_on_both(n: int, tmp_path: Path) -> None:
    junk = (b"JUNK \x01\x02\x03 " * 200)[:n]
    pdf_path = tmp_path / f"short_{n}.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    java = run_probe_text("HeaderGarbageProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert java.startswith("ok=true")
    assert py == java


def test_short_leading_garbage_loads_value_pinned(tmp_path: Path) -> None:
    """Oracle-free literal pin (PDFBox 3.0.7): 256 bytes of binary junk before
    the header still opens to two pages of text."""
    junk = (b"JUNK \x01\x02\x03 " * 200)[:256]
    pdf_path = tmp_path / "short.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    assert _pypdfbox_dump(str(pdf_path)) == (
        "ok=true\npages=2\ntext=Hello World\\nPage Two Text\\n\n"
    )


# ---------------------------------------------------------------------------
# Beyond-window garbage: STRUCTURAL divergence — strict-xfail both sides.
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    reason="STRUCTURAL: pypdfbox PDFParser.parse_header raises on a header not "
    "found within the 1024-byte scan window; upstream COSParser.parsePDFHeader "
    "returns the default version and falls through to brute-force recovery, so "
    "PDFBox recovers all pages with arbitrary leading garbage. Tracked in "
    "DEFERRED.md (pdfparser/recovery).",
    strict=True,
)
def test_long_leading_garbage_recovers_like_pdfbox(tmp_path: Path) -> None:
    junk = (b"\x00\x01BINARYJUNK\xff" * 200)[:2000]
    pdf_path = tmp_path / "long.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    # Upstream PDFBox 3.0.7 recovers two pages + text from this exact input
    # (HeaderGarbageProbe: ok=true / pages=2 / text=Hello World\nPage Two...).
    assert _pypdfbox_dump(str(pdf_path)) == (
        "ok=true\npages=2\ntext=Hello World\\nPage Two Text\\n\n"
    )


@requires_oracle
def test_long_leading_garbage_oracle_recovers(tmp_path: Path) -> None:
    """Confirm the oracle DOES recover the long-garbage case (so the xfail
    above is genuinely both-sides: pypdfbox fails, PDFBox succeeds)."""
    junk = (b"\x00\x01BINARYJUNK\xff" * 200)[:2000]
    pdf_path = tmp_path / "long_oracle.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    java = run_probe_text("HeaderGarbageProbe", str(pdf_path))
    assert re.match(r"ok=true\npages=2\n", java)
    # And pypdfbox currently fails it (the divergence under deferral).
    assert _pypdfbox_dump(str(pdf_path)) == "ok=false\n"
