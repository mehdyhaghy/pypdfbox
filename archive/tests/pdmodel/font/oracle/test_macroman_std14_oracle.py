"""Live Apache PDFBox parity for a Standard-14 PDType1Font with an explicit
``/Encoding /MacRomanEncoding`` override.

This pins the surface where a non-embedded Standard-14 Helvetica carries an
explicit ``/Encoding /MacRomanEncoding`` (rather than relying on the WinAnsi
default surfaced by ``read_encoding_from_font`` for the unembedded Std-14 path
— wave 1431). The override forces the code -> glyph-name map to MacRoman's
table, which disagrees with WinAnsi at ~108 codes spanning the 0x80..0xFF
block; the per-glyph AFM width must then be looked up under the MacRoman name
(e.g. 0xA5 -> "bullet" -> 350.0, NOT WinAnsi's 0xA5 -> "yen" -> 556.0).

For every PDSimpleFont on page 0 the probe
(``oracle/probes/MacRomanStd14Probe.java``) reports the resolved encoding's
class + identifier + base, plus the (glyph-name, width) pair for each code in
a hand-picked MR-vs-WA divergent subset, plus the ``PDFTextStripper`` text.
Parity here means pypdfbox produces the same encoding identifier, the same
glyph names on the differing codes, the same AFM widths under those names, and
the same extracted unicode text after MacRoman -> AGL -> unicode resolution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# MR-vs-WA divergent codes — must match ``MacRomanStd14Probe.CODES``.
_CODES: tuple[int, ...] = (
    0x80, 0x85, 0xA0, 0xA1, 0xA4, 0xA5, 0xA6, 0xA7, 0xAA, 0xAE, 0xB4,
    0xC4, 0xC9, 0xCA, 0xCE, 0xD0, 0xD1, 0xD2, 0xD6, 0xD8, 0xDA, 0xDE, 0xDF,
)


def _build_macroman_std14_pdf(out_path: Path) -> None:
    """Write a one-page PDF with a non-embedded Standard-14 Helvetica whose
    ``/Encoding`` is the predefined ``/MacRomanEncoding`` COSName. The content
    stream emits one ``Tj`` string of raw bytes covering every code in
    ``_CODES`` — i.e. exactly the MR-vs-WA divergent codes the probe reports
    on — so the extracted text reflects the MacRoman -> AGL -> unicode chain
    (not the WinAnsi one)."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        # Minimal Standard-14 Helvetica font dict (PDType1Font would normally
        # build this for a font registered via FontName.HELVETICA) plus the
        # explicit /Encoding /MacRomanEncoding override.
        font_dict = COSDictionary()
        font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
        font_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
        font_dict.set_item(
            COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
        )
        font_dict.set_item(
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("MacRomanEncoding"),
        )
        font = PDType1Font(font_dict)

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = PDPageContentStream(doc, page)
        cs.begin_text()
        cs.set_font(font, 14)
        cs.new_line_at_offset(40, 700)
        # Emit raw MacRoman bytes — show_text passes bytes through unchanged
        # rather than running them through a unicode encode step.
        cs.show_text(bytes(_CODES))
        cs.end_text()
        cs.close()

        doc.save(str(out_path))
    finally:
        doc.close()


def _canon_number(value: float) -> str:
    """Render a number the way the Java probe's ``canonNumber`` does — an
    integer-valued float prints as the integer (``350`` not ``350.0``)."""
    if value == int(value):
        return str(int(value))
    return str(float(value))


def _parse_probe(output: str) -> dict:
    """Parse ``MacRomanStd14Probe`` stdout into a structured dict."""
    font_line: list[str] | None = None
    enc: list[str] | None = None
    names: dict[int, str] = {}
    widths: dict[int, str] = {}
    text_lines: list[str] = []
    for line in output.splitlines():
        fields = line.split("\t")
        tag = fields[0]
        if tag == "FONT":
            font_line = fields[1:]
        elif tag == "ENC":
            enc = fields[1:]
        elif tag == "CODE":
            code = int(fields[1])
            names[code] = fields[2]
            widths[code] = fields[3]
        elif tag == "TEXT":
            text_lines.append("" if fields[1] == "␀" else fields[1])
    return {
        "font": font_line,
        "enc": enc,
        "names": names,
        "widths": widths,
        "text_lines": text_lines,
    }


def _py_per_font(pdf_path: Path) -> dict:
    """Reproduce the probe's per-font output from pypdfbox.

    Reads the first PDSimpleFont on page 0 (matches the probe's
    ``TreeMap``-sorted single-font fixture), then emits its encoding
    identifier, the differing-code glyph names + widths, and the document's
    PDFTextStripper text — the exact set the parity assertions diff on.
    """
    doc = PDDocument.load(pdf_path)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        assert res is not None
        font_names = sorted(n.name for n in res.get_font_names())
        assert font_names, "fixture must carry at least one font"
        font = res.get_font(COSName.get_pdf_name(font_names[0]))
        assert isinstance(font, PDSimpleFont)

        enc = font.get_encoding_typed()
        is_dict = isinstance(enc, DictionaryEncoding)
        if enc is None:
            enc_class = "null"
            enc_id = "null"
            base_id = "null"
        else:
            enc_class = type(enc).__name__
            enc_id = _encoding_id(enc)
            base_id = (
                _encoding_id(enc.get_base_encoding()) if is_dict else enc_id
            )

        names: dict[int, str] = {}
        widths: dict[int, str] = {}
        for code in _CODES:
            glyph = ".notdef" if enc is None else enc.get_name(code)
            names[code] = glyph
            widths[code] = _canon_number(font.get_width(code))

        text = PDFTextStripper().get_text(doc)
        text_lines = [
            line.replace("\r", "") for line in text.split("\n")
        ]

        return {
            "font": [
                font_names[0],
                font.get_name(),
                font.get_sub_type(),
                "true" if font.is_embedded() else "false",
            ],
            "enc": [enc_class, enc_id, "true" if is_dict else "false", base_id],
            "names": names,
            "widths": widths,
            "text_lines": text_lines,
        }
    finally:
        doc.close()


def _encoding_id(enc: object) -> str:
    """Mirror the probe's ``encodingId``: the encoding's /Encoding COSName
    literal when it has one, else the class simple name, else "null"."""
    if enc is None:
        return "null"
    cos = enc.get_cos_object()
    if isinstance(cos, COSName):
        return cos.name
    return type(enc).__name__


@requires_oracle
def test_macroman_std14_helvetica_matches_pdfbox(tmp_path: Path) -> None:
    """Non-embedded Standard-14 Helvetica with /Encoding /MacRomanEncoding:
    encoding identifier, per-code glyph names, AFM-resolved widths, and the
    extracted text after MacRoman -> AGL -> unicode all match PDFBox."""
    pdf = tmp_path / "macroman_std14_helvetica.pdf"
    _build_macroman_std14_pdf(pdf)

    oracle = _parse_probe(run_probe_text("MacRomanStd14Probe", str(pdf)))
    assert oracle["font"] is not None, (
        "probe reported no FONT line — fixture lost its Helvetica resource"
    )
    base_font, sub_type, embedded = oracle["font"][1], oracle["font"][2], oracle["font"][3]
    # Sanity: PDFBox must agree with the build contract (non-embedded Std-14).
    assert base_font == "Helvetica"
    assert sub_type == "Type1"
    assert embedded == "false"
    assert oracle["enc"] is not None
    assert oracle["enc"][1] == "MacRomanEncoding", (
        f"oracle reported encoding id {oracle['enc'][1]!r} — fixture lost its "
        "MacRoman override"
    )

    py = _py_per_font(pdf)

    # Per-font identity (base font, subtype, embedded flag) must match.
    assert py["font"] == oracle["font"], (
        f"FONT line diverges:\n  oracle={oracle['font']!r}\n  py={py['font']!r}"
    )

    # Resolved encoding class + COSName identifier + base must match: this is
    # where a WinAnsi-vs-MacRoman regression would surface.
    assert py["enc"] == oracle["enc"], (
        f"ENC line diverges (encoding override regressed?):\n"
        f"  oracle={oracle['enc']!r}\n  py={py['enc']!r}"
    )

    # MacRoman code -> glyph name on the differing codes. A bug that still
    # resolved via WinAnsi would show "yen" at 0xA5 instead of "bullet" etc.
    name_diffs = [
        (c, py["names"][c], oracle["names"][c])
        for c in _CODES
        if py["names"][c] != oracle["names"][c]
    ]
    assert not name_diffs, (
        "MacRoman code->name divergences (still resolving as WinAnsi?):\n"
        + "\n".join(f"  0x{c:02X}: py={p!r} oracle={o!r}" for c, p, o in name_diffs)
    )

    # AFM width must be looked up under the MacRoman glyph name. A bug that
    # resolved the name correctly but kept the WinAnsi default for the width
    # lookup (or vice versa) would diverge here even though the names matched.
    width_diffs = [
        (c, py["widths"][c], oracle["widths"][c])
        for c in _CODES
        if py["widths"][c] != oracle["widths"][c]
    ]
    assert not width_diffs, (
        "AFM-via-MacRoman-name width divergences:\n"
        + "\n".join(f"  0x{c:02X}: py={p!r} oracle={o!r}" for c, p, o in width_diffs)
    )

    # Extracted text must reflect MacRoman -> AGL -> unicode resolution.
    assert py["text_lines"] == oracle["text_lines"], (
        "PDFTextStripper output diverges:\n"
        f"  oracle={oracle['text_lines']!r}\n  py={py['text_lines']!r}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "code,glyph_name",
    [
        (0xA5, "bullet"),     # MR; WA would resolve to "yen"
        (0xAA, "trademark"),  # MR; WA would resolve to "ordfeminine"
    ],
)
def test_macroman_std14_canonical_differing_codes(
    code: int, glyph_name: str, tmp_path: Path
) -> None:
    """Sanity-pin the canonical MacRoman/WinAnsi divergence cases — these are
    the two cases called out in the task brief. Builds the same fixture and
    asserts both the resolved glyph name AND the AFM-resolved width come from
    MacRoman, exactly matching PDFBox."""
    pdf = tmp_path / f"macroman_canonical_{code:02X}.pdf"
    _build_macroman_std14_pdf(pdf)

    oracle = _parse_probe(run_probe_text("MacRomanStd14Probe", str(pdf)))
    py = _py_per_font(pdf)
    assert oracle["names"][code] == glyph_name
    assert py["names"][code] == glyph_name
    assert py["widths"][code] == oracle["widths"][code]
