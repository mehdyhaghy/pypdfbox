"""Live Apache PDFBox differential parity for SOFT HYPHEN (U+00AD) handling
during text extraction.

A soft hyphen (U+00AD) is a zero-width, invisible formatting character: it
marks a *permitted* hyphenation point, rendering only when a line actually
breaks there. The recurring question for a text extractor is whether it
*preserves* the soft hyphen in the extracted string or *strips* it (e.g. when
it sits at a line end where text continues). Apache PDFBox's answer, pinned
here against the live oracle:

* ``PDFTextStripper.getText()`` does **not** strip soft hyphens from ordinary
  (non-``/ActualText``) extracted text. A U+00AD in the glyph stream — whether
  mid-word (``co\xadoperate``) or at a visual line end (``word\xad``) — is
  emitted verbatim. (Soft-hyphen stripping in PDFBox is confined to the
  ``/ActualText`` replacement path, covered by ``test_actual_text_oracle.py``;
  ordinary text is untouched.)

Because U+00AD is invisible, a diff of the raw extracted text cannot show
where (or whether) a soft hyphen survived. ``oracle/probes/TextSoftHyphenProbe``
therefore emits a JSON object ``{"text": ..., "codepoints": [...]}`` whose
``codepoints`` array lists every character's Unicode scalar value in
extraction order, making the exact position of every U+00AD (173) directly
comparable to pypdfbox's :class:`PDFTextStripper`.

Encoding caveat — why these PDFs declare ``/WinAnsiEncoding`` explicitly:
U+00AD is reachable from a single-byte show-text run only under an encoding
that maps a byte to the ``sfthyphen`` glyph; that byte is ``0xAD`` under
WinAnsiEncoding. The 14 core fonts are constructed here with an explicit
``/Encoding /WinAnsiEncoding`` so that byte ``0xAD`` deterministically decodes
to U+00AD in *both* engines, isolating the soft-hyphen *extraction* behaviour
(the surface under test) from the orthogonal question of which default
encoding a *non*-``/Encoding`` Standard-14 font falls back to (a separate,
deferred divergence — pinned by the xfail at the bottom of this module).

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# U+00AD as the byte that WinAnsiEncoding maps to ``sfthyphen``.
_SHY = b"\255"


def _build_pdf(content: bytes, path: str, *, win_ansi: bool) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token in ``content`` is rewritten to the resource key the page
    actually allocates for the embedded Helvetica font. When ``win_ansi`` is
    true the font dict carries an explicit ``/Encoding /WinAnsiEncoding`` so
    byte ``0xAD`` decodes to U+00AD deterministically in both engines.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 200))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        if win_ansi:
            font.get_cos_object().set_item(
                COSName.get_pdf_name("Encoding"),
                COSName.get_pdf_name("WinAnsiEncoding"),
            )
        # A freshly-built page carries no /Resources; use the create-and-attach
        # accessor (get_resources() returns None for an absent bag since the
        # wave-1491 strict-null restoration).
        resources = page.get_or_create_resources()
        font_key = resources.add(font)
        page.set_resources(resources)
        rewritten = content.replace(b"/F1", b"/" + font_key.get_name().encode("ascii"))
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(rewritten)
        page.set_contents(stream)
        doc.save(path)
    finally:
        # try/finally so a Windows file lock on the source is always released.
        doc.close()


def _py_text(path: str) -> str:
    """Extract text with pypdfbox's default stripper, closing the doc."""
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        return stripper.get_text(doc)
    finally:
        doc.close()


def _java(path: str) -> tuple[str, list[int]]:
    """Run the oracle probe; return (text, codepoints)."""
    payload = json.loads(run_probe_text("TextSoftHyphenProbe", path))
    return payload["text"], payload["codepoints"]


# --- Content streams (WinAnsi: byte 0xAD == U+00AD soft hyphen) ------------

# (a) Soft hyphen mid-word — must survive verbatim.
_MID_WORD = b"BT /F1 18 Tf 20 150 Td (co" + _SHY + b"operate) Tj ET"
# (b) Soft hyphen at a visual line end (trailing on the line, next line
#     continues the word) — PDFBox does NOT strip it.
_LINE_END = (
    b"BT /F1 18 Tf 20 160 Td (word" + _SHY + b") Tj "
    b"0 -30 Td (next) Tj ET"
)
# (c) Multiple soft hyphens across mid-word + line-end positions on one page.
_COMBINED = (
    b"BT /F1 18 Tf 20 160 Td (co" + _SHY + b"op" + _SHY + b"erate) Tj "
    b"0 -30 Td (line" + _SHY + b") Tj "
    b"0 -30 Td (after) Tj ET"
)
# (d) A standalone soft hyphen between two words on the same line.
_STANDALONE = b"BT /F1 18 Tf 20 150 Td (a" + _SHY + b"b) Tj ET"

_CASES = [
    ("mid_word", _MID_WORD),
    ("line_end", _LINE_END),
    ("combined", _COMBINED),
    ("standalone", _STANDALONE),
]


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [c for _, c in _CASES],
    ids=[name for name, _ in _CASES],
)
def test_soft_hyphen_extraction_matches_pdfbox(content: bytes, tmp_path: Path) -> None:
    """pypdfbox's ``PDFTextStripper`` output (text + every codepoint) equals
    Apache PDFBox's for soft-hyphen cases under an explicit WinAnsiEncoding."""
    pdf = tmp_path / "shy.pdf"
    _build_pdf(content, str(pdf), win_ansi=True)
    java_text, java_cps = _java(str(pdf))
    py = _py_text(str(pdf))
    assert py == java_text
    assert [ord(c) for c in py] == java_cps


@requires_oracle
def test_soft_hyphen_preserved_not_stripped(tmp_path: Path) -> None:
    """The headline contract: PDFBox preserves U+00AD verbatim in ordinary
    extracted text — both mid-word and at a visual line end — rather than
    stripping it. pypdfbox matches, codepoint-for-codepoint."""
    pdf = tmp_path / "shy_combined.pdf"
    _build_pdf(_COMBINED, str(pdf), win_ansi=True)
    java_text, java_cps = _java(str(pdf))
    py = _py_text(str(pdf))
    assert py == java_text
    # The soft hyphen (U+00AD == 173) is present in the extracted text.
    assert 0x00AD in java_cps
    assert "­" in py
    # Mid-word soft hyphen survives: "co<SHY>op<SHY>erate" -> contains both.
    assert py.count("­") == java_text.count("­")
    # Specifically: three soft hyphens were encoded (two mid-word, one at the
    # line end) and all three survive extraction.
    assert py.count("­") == 3


@requires_oracle
def test_no_encoding_std14_default_matches_pdfbox(tmp_path: Path) -> None:
    """Non-embedded Standard-14 default-encoding parity (closed wave 1491).

    When a Standard-14 Latin font is loaded from a PDF dict that has NO
    ``/Encoding`` entry, Apache PDFBox's ``PDType1Font.readEncodingFromFont()``
    (PDType1Font.java lines 495-498) builds a ``Type1Encoding`` from the
    bundled Adobe AFM (``EncodingScheme AdobeStandardEncoding``), so byte
    0xAD decodes to U+203A (guilsinglright), 0x27 -> U+2019 (quoteright),
    0x60 -> U+2018 (quoteleft) — NOT the WinAnsi spellings. pypdfbox now
    reads the same AFM-driven ``Type1Encoding`` for that case, so the
    extracted codepoints match the oracle.

    The WinAnsi default that the *direct* ``new PDType1Font(FontName)``
    constructor uses is a separate path: that constructor writes an
    explicit ``/Encoding /WinAnsiEncoding`` into the dict, so the
    advance-width parity pinned by ``test_std14_metrics_oracle.py`` is
    preserved (that probe's fonts carry the explicit /Encoding).
    """
    pdf = tmp_path / "shy_noenc.pdf"
    _build_pdf(_MID_WORD, str(pdf), win_ansi=False)
    java_text, java_cps = _java(str(pdf))
    py = _py_text(str(pdf))
    assert [ord(c) for c in py] == java_cps
