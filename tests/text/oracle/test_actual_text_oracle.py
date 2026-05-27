"""Live Apache PDFBox differential parity for ``/ActualText`` substitution
and ``/Artifact`` handling during text extraction (PDF §14.9.4).

A ``/Span << /ActualText (...) >> BDC ... EMC`` marked-content section makes
``PDFTextStripper`` emit the ``/ActualText`` string *instead* of the
glyph-derived text — used for ligatures, hyphenation, and reordered text.
Apache PDFBox's behaviour (verified here against the live oracle):

* The ``/ActualText`` replacement is emitted **once**, at the origin of the
  span's first show-text run; every later run in the span has its glyph
  text suppressed. The cursor still advances so text after ``EMC`` lines up.
* The ``/ActualText`` string is decoded like any PDF text string, so a
  UTF-16BE ``FE FF`` BOM payload decodes to its real Unicode (e.g. ``é``).
* ``beginMarkedContentSequence`` sets the current ``actualText`` field
  *unconditionally* to the entered span's ``/ActualText`` — so a nested span
  *without* one turns substitution back off; ``endMarkedContentSequence``
  clears it again when the closing span carried one.
* By default ``PDFTextStripper`` does **not** exclude ``/Artifact`` content —
  its text is included exactly like any other marked content. This test
  pins that (a real divergence here would be a bug).

Each case builds a one-page PDF whose content stream is exactly the bytes
below (a single Helvetica-class font, registered as the page's first font,
so ``/F1`` is rewritten to the allocated resource key), runs the
``TextExtractProbe`` Java oracle, and asserts pypdfbox's default
``PDFTextStripper`` output matches byte-for-byte.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token in ``content`` is rewritten to whatever key the page
    resources actually allocate for the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 200))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        resources = page.get_resources()
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
        return PDFTextStripper().get_text(doc)
    finally:
        doc.close()


# --- Content streams -------------------------------------------------------

# (a) The high-value case: a /Span whose glyphs render as "f f i" but whose
#     /ActualText is the ligature "ffi" — extraction must yield "ffi".
_FFI = (
    b"BT /F1 24 Tf 20 150 Td "
    b"/Span <</ActualText (ffi)>> BDC (f f i) Tj EMC ET"
)
# (b) /ActualText carrying a UTF-16BE BOM payload (FE FF 00 E9 -> U+00E9 'é');
#     the glyphs (xyz) are suppressed and the decoded 'é' is emitted.
_UTF16 = (
    b"BT /F1 24 Tf 20 150 Td "
    b"/Span <</ActualText (\\376\\377\\000\\351)>> BDC (xyz) Tj EMC ET"
)
# (c) /Artifact BDC ... EMC with text — PDFBox does NOT exclude artifacts by
#     default, so both the plain and the artifact text are extracted.
_ARTIFACT = (
    b"BT /F1 24 Tf 20 150 Td "
    b"(visible) Tj /Artifact BDC (hidden?) Tj EMC ET"
)
# (d) All three on separate lines in one page.
_COMBINED = (
    b"BT /F1 18 Tf "
    b"20 160 Td /Span <</ActualText (ffi)>> BDC (f f i) Tj EMC "
    b"0 -30 Td /Span <</ActualText (\\376\\377\\000\\351)>> BDC (xyz) Tj EMC "
    b"0 -30 Td (visible) Tj /Artifact BDC ( and artifact) Tj EMC "
    b"ET"
)
# (e) /ActualText spanning a multi-string TJ array: the whole span collapses
#     to the single replacement string ("ligature"), emitted once.
_TJ_SPAN = (
    b"BT /F1 18 Tf 20 150 Td "
    b"/Span <</ActualText (ligature)>> BDC [(f) -50 (f) -50 (i)] TJ EMC ET"
)
# (f) Replacement then plain text after EMC on the same baseline.
_SPAN_THEN_PLAIN = (
    b"BT /F1 18 Tf 20 150 Td "
    b"/Span <</ActualText (X)>> BDC (abc) Tj EMC ( tail) Tj ET"
)
# (g) Two adjacent /ActualText spans on one line -> both replacements.
_TWO_SPANS = (
    b"BT /F1 18 Tf 20 150 Td "
    b"/Span <</ActualText (AA)>> BDC (q) Tj EMC "
    b"/Span <</ActualText (BB)>> BDC (w) Tj EMC ET"
)
# (h) Nested: outer /ActualText, inner valid BDC WITHOUT one -> the inner
#     span turns substitution off (PDFBox sets the field unconditionally),
#     so "b" and "c" surface around the once-emitted "whole".
_NESTED_OFF = (
    b"BT /F1 18 Tf 20 150 Td "
    b"/Span <</ActualText (whole)>> BDC (a) Tj "
    b"/Sub <</MCID 0>> BDC (b) Tj EMC (c) Tj EMC ET"
)
# (i) Nested: both spans carry /ActualText -> inner replacement applies while
#     open, outer resumes after the inner EMC.
_NESTED_BOTH = (
    b"BT /F1 18 Tf 20 150 Td "
    b"/Span <</ActualText (OUT)>> BDC (a) Tj "
    b"/Sub <</ActualText (IN)>> BDC (b) Tj EMC (c) Tj EMC ET"
)
# (j) Empty /ActualText () -> the span's glyphs are suppressed (empty
#     replacement), text after EMC is unaffected.
_EMPTY = (
    b"BT /F1 18 Tf 20 150 Td "
    b"/Span <</ActualText ()>> BDC (abc) Tj EMC (def) Tj ET"
)

_CASES = [
    ("ffi", _FFI),
    ("utf16be", _UTF16),
    ("artifact", _ARTIFACT),
    ("combined", _COMBINED),
    ("tj_span", _TJ_SPAN),
    ("span_then_plain", _SPAN_THEN_PLAIN),
    ("two_spans", _TWO_SPANS),
    ("nested_off", _NESTED_OFF),
    ("nested_both", _NESTED_BOTH),
    ("empty", _EMPTY),
]


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [c for _, c in _CASES],
    ids=[name for name, _ in _CASES],
)
def test_actual_text_and_artifact_match_pdfbox(content: bytes, tmp_path: Path) -> None:
    """pypdfbox's default ``PDFTextStripper`` output equals Apache PDFBox's
    for every ``/ActualText`` / ``/Artifact`` case."""
    pdf = tmp_path / "actual_text.pdf"
    _build_pdf(content, str(pdf))
    java = run_probe_text("TextExtractProbe", str(pdf))
    py = _py_text(str(pdf))
    assert py == java


@requires_oracle
def test_ffi_ligature_substitution(tmp_path: Path) -> None:
    """The headline case: glyphs rendering ``f f i`` under an ``/ActualText
    (ffi)`` span extract as the ligature ``ffi`` — the glyph text is
    suppressed and the replacement is emitted once."""
    pdf = tmp_path / "ffi.pdf"
    _build_pdf(_FFI, str(pdf))
    java = run_probe_text("TextExtractProbe", str(pdf))
    py = _py_text(str(pdf))
    assert py == java
    assert py == "ffi\n"
    # The raw glyph text must NOT leak through.
    assert "f f i" not in py


@requires_oracle
def test_utf16be_actual_text_decodes(tmp_path: Path) -> None:
    """A UTF-16BE BOM ``/ActualText`` payload decodes to its real Unicode
    (``é``), not the suppressed glyph run ``xyz``."""
    pdf = tmp_path / "utf16.pdf"
    _build_pdf(_UTF16, str(pdf))
    java = run_probe_text("TextExtractProbe", str(pdf))
    py = _py_text(str(pdf))
    assert py == java
    assert py == "é\n"
    assert "xyz" not in py


@requires_oracle
def test_artifact_text_included_like_pdfbox(tmp_path: Path) -> None:
    """``PDFTextStripper`` does not exclude ``/Artifact`` content by default;
    its text is extracted exactly as PDFBox extracts it."""
    pdf = tmp_path / "artifact.pdf"
    _build_pdf(_ARTIFACT, str(pdf))
    java = run_probe_text("TextExtractProbe", str(pdf))
    py = _py_text(str(pdf))
    assert py == java
    # Both the plain run and the artifact run are present.
    assert "visible" in py
    assert "hidden?" in py
