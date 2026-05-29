"""Live Apache PDFBox differential parity for the COMPOSITE (Type0 / CID)
font ``getText`` pipeline.

Wave 1461 covered the *simple*-font ``/ToUnicode`` extraction surface; this
file is the composite (Type0 / CIDFont) end-to-end counterpart. The
``CompositeFontTextProbe`` walks a page's content stream with Apache
PDFBox's ``PDFStreamEngine``, decodes every glyph run drawn with a
``PDType0Font`` through ``font.readCode`` (so Identity-H two-byte codes are
honoured), and emits one canonical line per code::

    CODE <code> CID <cid> GID <gid> UNI U+XXXX[ U+YYYY...]

exercising the whole ``code -> CID -> GID`` plus ``code -> Unicode`` chain
over the genuine multi-byte byte stream. After the per-code block it emits
``===TEXT===`` followed by the page's ``PDFTextStripper`` output, so the
end-to-end extracted text is diffable too.

pypdfbox replays the same byte runs (captured via the lite
:class:`PDFTextStripper`'s ``_decode_show_text`` hook, which is the genuine
composite decode path) through ``PDType0Font.read_code`` /
``code_to_cid`` / ``code_to_gid`` / ``to_unicode`` and asserts both the
per-code lines and the extracted text match Apache PDFBox.

Fixtures:
  * ``pdfwriter/unencrypted.pdf`` — CIDFontType2, Identity-H, identity
    CID == GID, large Latin body run (3931 codes).
  * ``pdmodel/font/PDFBOX-3062-005717-p1.pdf`` — CIDFontType0 (CID-keyed
    CFF) where CID != GID: the GID is the charset index of ``cidNNNNN``
    (e.g. CID 40 → GID 10), not the identity. This is the fixture that
    surfaced the wave-1470 ``PDType0Font.code_to_gid`` bug — the parent
    previously assumed GID == CID for any descendant lacking a
    ``/CIDToGIDMap`` (the Type0/CFF case) instead of delegating to the
    descendant's charset-based ``code_to_gid``.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

_COMPOSITE_FIXTURES = [
    "pdfwriter/unencrypted.pdf",
    "pdmodel/font/PDFBOX-3062-005717-p1.pdf",
]


class _CompositeRunCapture(PDFTextStripper):
    """Lite stripper that records each ``(font, raw_bytes)`` show-text run
    drawn with a :class:`PDType0Font`, then leaves decoding to the test."""

    def __init__(self) -> None:
        super().__init__()
        self.runs: list[tuple[PDType0Font, bytes]] = []

    def _decode_show_text(self, text_bytes: bytes) -> str:  # type: ignore[override]
        font = self._active_font
        if isinstance(font, PDType0Font):
            self.runs.append((font, text_bytes))
        return super()._decode_show_text(text_bytes)


def _uni_suffix(uni: str | None) -> str:
    """Render a code's Unicode mapping the way the Java probe does:
    `` U+XXXX`` per codepoint, or `` (none)`` when empty."""
    if not uni:
        return " (none)"
    return "".join(f" U+{ord(ch):04X}" for ch in uni)


def _py_composite_lines(path: Path, page_index: int = 0) -> list[str]:
    """Replay every Type0 glyph run through the composite font pipeline and
    emit the same canonical ``CODE ... CID ... GID ... UNI ...`` lines the
    Java probe produces."""
    doc = PDDocument.load(str(path))
    try:
        cap = _CompositeRunCapture()
        cap.set_start_page(page_index + 1)
        cap.set_end_page(page_index + 1)
        cap.get_text(doc)
        lines: list[str] = []
        for font, run_bytes in cap.runs:
            stream = io.BytesIO(run_bytes)
            total = len(run_bytes)
            while stream.tell() < total:
                offset = stream.tell()
                code, consumed = font.read_code(run_bytes, offset)
                if consumed <= 0:  # defensive: never stall on a bad code
                    break
                stream.seek(offset + consumed)
                cid = font.code_to_cid(code)
                gid = font.code_to_gid(code)
                uni = font.to_unicode(code)
                lines.append(
                    f"CODE {code} CID {cid} GID {gid} UNI{_uni_suffix(uni)}"
                )
        return lines
    finally:
        doc.close()


def _py_page_text(path: Path, page_index: int = 0) -> str:
    """Extract one page's text with the default stripper, matching the
    probe's ``setStartPage``/``setEndPage`` window."""
    doc = PDDocument.load(str(path))
    try:
        stripper = PDFTextStripper()
        stripper.set_start_page(page_index + 1)
        stripper.set_end_page(page_index + 1)
        return stripper.get_text(doc)
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("rel", _COMPOSITE_FIXTURES)
def test_composite_code_cid_gid_unicode_matches_pdfbox(rel: str) -> None:
    """Per-code ``code -> CID -> GID`` + ``code -> Unicode`` over the real
    multi-byte byte stream matches Apache PDFBox for every Type0 glyph."""
    fixture = _FIXTURES / rel
    raw = run_probe_text("CompositeFontTextProbe", str(fixture), "0")
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CODE ")]
    py_lines = _py_composite_lines(fixture)
    assert py_lines == java_lines


@requires_oracle
@pytest.mark.parametrize("rel", _COMPOSITE_FIXTURES)
def test_composite_extracted_text_matches_pdfbox(rel: str) -> None:
    """The end-to-end ``PDFTextStripper`` output for the composite-font
    page matches Apache PDFBox byte-for-byte."""
    fixture = _FIXTURES / rel
    raw = run_probe_text("CompositeFontTextProbe", str(fixture), "0")
    java_text = raw.split("===TEXT===\n", 1)[1]
    py_text = _py_page_text(fixture)
    assert py_text == java_text


@requires_oracle
def test_type0_cff_cid_not_equal_gid() -> None:
    """Regression pin for the wave-1470 ``code_to_gid`` fix: the CIDFontType0
    fixture is CID-keyed CFF where the GID is the charset index, *not* the
    identity. Confirm at least one code maps to a GID that differs from its
    CID so a future regression to the identity fall-back is caught."""
    fixture = _FIXTURES / "pdmodel/font/PDFBOX-3062-005717-p1.pdf"
    py_lines = _py_composite_lines(fixture)
    assert py_lines, "expected Type0 glyph runs on the page"
    differing = [
        ln
        for ln in py_lines
        if int(ln.split()[3]) != int(ln.split()[5])  # CID != GID
    ]
    assert differing, "fixture should exercise a non-identity CID->GID map"
