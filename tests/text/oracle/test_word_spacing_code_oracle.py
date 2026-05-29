"""Live Apache PDFBox differential parity for the word-spacing (``Tw``)
*applicability* rule of PDF 32000-1 §9.3.3.

Word spacing is added to a glyph's advance **only** when the show-text byte
string yields the single-byte character code 32 (the ASCII space). It must
NOT apply to:

* a 2-byte code 32 in a composite (Type 0) font — even though the low byte
  of the 2-byte code equals ``0x20`` — and
* any single-byte code other than 32.

This surface is distinct from ``test_text_spacing_oracle.py``: that file
exercises ``Tw`` (among ``Tc`` / ``Tz`` / ``Ts`` / ``TJ``) on a *simple*
Helvetica font where the space is a single-byte code 32 and confirms ``Tw``
does not leak onto the A/B/C/D glyph advances. Here the headline is the
**composite-font carve-out**: a Type 0 font with ``/Encoding /Identity-H``
(two-byte codes) where one of the codes is exactly ``0x0020``. The glyph
LiberationSans assigns to ``=`` (U+003D) has GID 32, so under Identity-H the
character ``=`` is shown as the two-byte code ``0x0020`` — its low byte is
``0x20`` but it is **not** the single-byte space code, so ``Tw`` must not
widen its advance.

The :class:`WordSpacingCodeProbe` Java probe subclasses ``PDFTextStripper``,
emits the full extracted string (so word breaks are recovered exactly) and
one canonical ``unicode \t xDirAdj \t widthDirAdj`` line per glyph in reading
order. The per-glyph X stream proves where ``Tw`` did (simple font) and did
not (composite font) widen the advance.

Granularity reconciliation (the documented lite-port carve-out — see
``test_text_spacing_oracle.py`` and ``CHANGES.md``): Apache PDFBox emits one
``TextPosition`` per glyph; pypdfbox's lite stripper emits one per show-text
run and advances by the font's *average* glyph width without applying ``Tw``
to the cursor. So per-glyph X cannot match. The parity we assert is the
**extracted string** (the §9.3.3 rule is observable there — an engine that
wrongly applied ``Tw`` to the 2-byte code 32 would over-widen the
``=``→``=`` gaps and could spuriously insert word breaks) plus the
*Java-side* per-glyph proof that the composite-font 2-byte code 32 advances
are the bare glyph widths while the simple-font code-32 space carries +Tw.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "WordSpacingCodeProbe"
_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)
_COORD_EPS = 0.5


# ---------------------------------------------------------------------------
# Glyph-line parsing (shared shape with TextSpacingProbe).
# ---------------------------------------------------------------------------


class _Glyph:
    __slots__ = ("unicode", "x", "width")

    def __init__(self, fields: list[str]) -> None:
        self.unicode = fields[0]
        self.x = float(fields[1])
        self.width = float(fields[2])


def _java(path: str) -> tuple[str, list[_Glyph]]:
    out = run_probe_text(_PROBE, path)
    text_part = out.split("<<<TEXT\n", 1)[1].split("TEXT>>>\n", 1)[0]
    glyph_part = out.split("<<<GLYPHS\n", 1)[1].split("GLYPHS>>>", 1)[0]
    glyphs: list[_Glyph] = []
    for line in glyph_part.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        glyphs.append(_Glyph(fields))
    return text_part, glyphs


def _py(path: str) -> str:
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        return stripper.get_text(doc)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# PDF builders.
# ---------------------------------------------------------------------------


def _build_simple_pdf(content: bytes, path: str) -> None:
    """One-page PDF whose content is ``content`` with a Helvetica /F1 font.

    ``/F1`` is rewritten to whatever key the page resources allocate.
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
        rewritten = content.replace(
            b"/F1", b"/" + font_key.get_name().encode("ascii")
        )
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(rewritten)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()


def _build_type0_pdf(text: str, tw: float, path: str) -> None:
    """One-page PDF showing ``text`` through an Identity-H Type 0 font with
    word spacing ``Tw`` set.

    The show-text string is pre-encoded to the font's two-byte Identity-H
    codes (``font.encode``) and emitted as a hex string so the 2-byte code
    32 (the glyph for ``=``, GID 32 in LiberationSans) round-trips intact.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 200))
        doc.add_page(page)
        font = PDType0Font.load(doc, str(_TTF), False)
        resources = page.get_resources()
        font_key = resources.add(font)
        page.set_resources(resources)
        codes = font.encode(text)
        hex_codes = codes.hex().upper().encode("ascii")
        content = (
            b"BT\n/"
            + font_key.get_name().encode("ascii")
            + b" 24 Tf\n"
            + f"{tw:g} Tw\n".encode("ascii")
            + b"20 150 Td\n<"
            + hex_codes
            + b"> Tj\nET\n"
        )
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(content)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# (a) Simple font: code-32 space carries +Tw; non-space glyphs do not.
#     (Pins the single-byte side of the §9.3.3 rule against Java.)
# ---------------------------------------------------------------------------

# (AB CD) with Tw=30 — Tw applies to the single-byte space only.
_SIMPLE_TW = b"BT /F1 24 Tf 30 Tw 20 150 Td (AB CD) Tj ET"


@requires_oracle
def test_simple_font_code_32_carries_word_spacing() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "simple.pdf")
        _build_simple_pdf(_SIMPLE_TW, path)
        java_text, java_glyphs = _java(path)
        py_text = _py(path)

    # String parity: Tw widened the space but did not split A/B or C/D.
    assert py_text == java_text == "AB CD\n"

    by_char = {g.unicode: g for g in java_glyphs}
    a, b = by_char["A"], by_char["B"]
    space, c = by_char[" "], by_char["C"]
    # Inside a word the advance is the bare glyph width (no Tw).
    assert (b.x - a.x) == pytest.approx(a.width, abs=_COORD_EPS)
    # The single-byte code-32 space advance carries the +30pt Tw, so the
    # space->C gap is far larger than a bare space width.
    assert (c.x - space.x) > space.width + 20.0


# ---------------------------------------------------------------------------
# (b) Composite (Type 0 / Identity-H) font: a 2-byte code 32 (the glyph for
#     '=', GID 32) must NOT receive Tw even though its low byte is 0x20.
#     The whole string is two-byte codes, so NO advance carries Tw.
# ---------------------------------------------------------------------------


@requires_oracle
def test_composite_font_two_byte_code_32_ignores_word_spacing() -> None:
    # "A=B=C": codes 0x0024 0x0020 0x0025 0x0020 0x0026. The 0x0020 codes
    # are the 2-byte code 32 — Tw must not widen them.
    text = "A=B=C"
    with tempfile.TemporaryDirectory() as td:
        no_tw = str(Path(td) / "type0_notw.pdf")
        with_tw = str(Path(td) / "type0_tw.pdf")
        _build_type0_pdf(text, 0.0, no_tw)
        _build_type0_pdf(text, 40.0, with_tw)

        java_text_notw, glyphs_notw = _java(no_tw)
        java_text_tw, glyphs_tw = _java(with_tw)
        py_text_notw = _py(no_tw)
        py_text_tw = _py(with_tw)

    # Extracted string parity in both directions: '=' (code 0x0020) decodes
    # to '=', no spurious word break, identical with and without Tw.
    assert py_text_notw == java_text_notw == "A=B=C\n"
    assert py_text_tw == java_text_tw == "A=B=C\n"

    # Java-side per-glyph proof of §9.3.3: setting Tw=40 must not change any
    # X position when every code is two bytes — the 2-byte code 32 is NOT
    # the single-byte space, so word spacing is inapplicable to the whole
    # run. The glyph X stream is byte-for-byte identical to the Tw=0 layout.
    assert len(glyphs_tw) == len(glyphs_notw) == len(text)
    for g0, g1 in zip(glyphs_notw, glyphs_tw, strict=True):
        assert g1.unicode == g0.unicode
        assert g1.x == pytest.approx(g0.x, abs=_COORD_EPS)


# ---------------------------------------------------------------------------
# (c) Composite font, leading 2-byte code 32 between real glyphs: even with a
#     huge Tw the '=' (code 32) advance equals its bare glyph width, so no
#     word break is inserted and the two flanking letters stay one word.
# ---------------------------------------------------------------------------


@requires_oracle
def test_composite_two_byte_space_does_not_insert_word_break() -> None:
    # "X=Y": a single 2-byte code 32 between two letters. A real single-byte
    # Tw of 40pt would (in a simple font) blow the gap past the word-break
    # threshold; here it must not, because the code is two bytes.
    text = "X=Y"
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "type0_xy.pdf")
        _build_type0_pdf(text, 40.0, path)
        java_text, java_glyphs = _java(path)
        py_text = _py(path)

    assert py_text == java_text == "X=Y\n"
    # No word break: the '=' glyph advance is its bare width (Tw not applied),
    # so the X->'=' and '='->Y gaps are ordinary glyph advances on Java's
    # per-glyph stream.
    by_char = {g.unicode: g for g in java_glyphs}
    eq = by_char["="]
    y = by_char["Y"]
    assert (y.x - eq.x) == pytest.approx(eq.width, abs=_COORD_EPS)
