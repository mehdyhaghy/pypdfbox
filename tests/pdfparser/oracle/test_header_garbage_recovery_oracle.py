"""Leading-garbage-before-``%PDF-`` recovery parity, pinned against the live
Apache PDFBox 3.0.7 oracle (wave 1496; divergence closed wave 1497).

A PDF whose body is structurally clean but carries N bytes of junk *before* the
``%PDF-`` header has two distinct behaviours upstream:

* **Junk that is itself a PDF comment** (``%``-prefixed) or short junk that
  still leaves ``%PDF-`` inside the first 1024-byte scan window — the header is
  located and the file opens via the normal path.
* **Arbitrary binary / long junk that pushes ``%PDF-`` past the scan window** —
  ``COSParser.parseHeader`` does NOT find the marker, returns ``false``, and
  ``PDFParser.parse(boolean)`` (lenient) logs "Error: Header doesn't contain
  versioninfo", keeps the COSDocument's default version, and continues into
  brute-force recovery, which rescans the whole body for ``N G obj``
  definitions and rebuilds the xref + trailer. The document opens with the full
  page count and text regardless of how much junk precedes it.

Wave 1497 wired this fall-through into pypdfbox: ``PDFParser.parse`` no longer
aborts when the header is missing from the scan window — in lenient mode it
falls through to the existing offset-agnostic brute-force rebuild exactly as
upstream does, so the long-garbage case now recovers at parity. The "not a PDF"
rejection is re-derived downstream: a buffer with NO recoverable ``n g obj``
definitions still fails (brute-force finds nothing), on both sides. Strict
(non-lenient) mode still raises immediately.

Both the short-garbage (within window) and long-garbage (past window) cases are
asserted at parity below; total-garbage (no header, no objects) is asserted to
FAIL on both sides; the pure-junk-with-embedded-``obj``-tokens edge is pinned
too.
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
# Beyond-window garbage: brute-force recovery parity (wave 1497).
# ---------------------------------------------------------------------------
_RECOVERED = "ok=true\npages=2\ntext=Hello World\\nPage Two Text\\n\n"


def test_long_leading_garbage_recovers_value_pinned(tmp_path: Path) -> None:
    """Oracle-free literal pin (PDFBox 3.0.7): 2000 bytes of binary junk push
    the header past the 1024-byte scan window, yet brute-force recovery
    rebuilds both pages. Was the wave-1496 strict-xfail divergence; closed
    wave 1497 by wiring the header-not-found fall-through onto the existing
    offset-agnostic brute-force rebuild."""
    junk = (b"\x00\x01BINARYJUNK\xff" * 200)[:2000]
    pdf_path = tmp_path / "long.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    assert _pypdfbox_dump(str(pdf_path)) == _RECOVERED


@requires_oracle
@pytest.mark.parametrize("n", [1100, 2000, 8000], ids=["g1100", "g2000", "g8000"])
def test_long_leading_garbage_recovers_on_both(n: int, tmp_path: Path) -> None:
    """Differential parity: junk slightly over the old 1024-byte window
    (1100) and far past it (2000 / 8000) recovers identically on both sides."""
    junk = (b"\x00\x01BINARYJUNK\xff" * 1000)[:n]
    pdf_path = tmp_path / f"long_{n}.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    java = run_probe_text("HeaderGarbageProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert re.match(r"ok=true\npages=2\n", java)
    assert py == java


@requires_oracle
@pytest.mark.parametrize("n", [1019, 1024, 1030], ids=["b1019", "b1024", "b1030"])
def test_window_boundary_garbage_matches(n: int, tmp_path: Path) -> None:
    """The exact 1024-byte scan-window boundary: a header ending just inside
    vs just past the window must resolve identically on both sides (whether by
    the in-window header path or the brute-force fall-through)."""
    junk = (b"j" * n)
    pdf_path = tmp_path / f"boundary_{n}.pdf"
    pdf_path.write_bytes(junk + _CLEAN)
    java = run_probe_text("HeaderGarbageProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert java.startswith("ok=true")
    assert py == java


def test_total_garbage_no_header_no_objects_fails(tmp_path: Path) -> None:
    """No header AND no recoverable ``n g obj`` definitions — brute-force
    finds nothing, so the load fails. ``ok=false`` on the pypdfbox side; the
    oracle agrees below."""
    pdf_path = tmp_path / "total.pdf"
    pdf_path.write_bytes(b"\x00\x01total binary garbage with no pdf structure\xff" * 50)
    assert _pypdfbox_dump(str(pdf_path)) == "ok=false\n"


@requires_oracle
def test_total_garbage_fails_on_both(tmp_path: Path) -> None:
    """Differential: a header-less, object-less buffer fails to load in
    PDFBox too (Loader.loadPDF raises after brute-force recovers nothing)."""
    pdf_path = tmp_path / "total_oracle.pdf"
    pdf_path.write_bytes(b"\x00\x01total binary garbage with no pdf structure\xff" * 50)
    java = run_probe_text("HeaderGarbageProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert java == "ok=false\n"
    assert py == java


def test_junk_with_obj_tokens_but_no_catalog(tmp_path: Path) -> None:
    """Edge: leading junk that embeds bare ``n g obj`` tokens but no valid
    catalog / page tree. The wave-1497 header fall-through fires (brute-force
    harvests the decoy objects), so the load no longer aborts at the header.
    The rebuilt document has no resolvable /Root — and here a *pre-existing,
    orthogonal* divergence shows: pypdfbox's ``PDFParser.parse`` deliberately
    does NOT auto-invoke ``initial_parse`` (lazy /Root resolution, documented
    in pdf_parser.py), so ``get_number_of_pages`` yields 0 rather than raising,
    whereas upstream ``Loader.loadPDF`` runs ``initialParse`` and raises
    "Missing root object specification in trailer." That lazy-init split is
    NOT the header-recovery surface; it is pinned here only to document the
    boundary. The pin is pypdfbox's actual recovered-but-rootless shape."""
    decoy = b"garbage 1 0 obj << /Decoy true >> endobj 2 0 obj 42 endobj more junk "
    pdf_path = tmp_path / "decoy.pdf"
    pdf_path.write_bytes(decoy * 30)
    assert _pypdfbox_dump(str(pdf_path)) == "ok=true\npages=0\ntext=\n"


@requires_oracle
def test_junk_with_obj_tokens_oracle_rejects(tmp_path: Path) -> None:
    """Confirm the orthogonal lazy-init split: upstream rejects the rootless
    decoy (``initialParse`` → "Missing root"), pypdfbox returns a 0-page
    document. The header fall-through itself is at parity (both reach the
    rebuild); only the eager-vs-lazy /Root validation differs."""
    decoy = b"garbage 1 0 obj << /Decoy true >> endobj 2 0 obj 42 endobj more junk "
    pdf_path = tmp_path / "decoy_oracle.pdf"
    pdf_path.write_bytes(decoy * 30)
    java = run_probe_text("HeaderGarbageProbe", str(pdf_path))
    assert java == "ok=false\n"
    assert _pypdfbox_dump(str(pdf_path)) == "ok=true\npages=0\ntext=\n"
