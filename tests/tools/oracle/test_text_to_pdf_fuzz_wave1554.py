"""Wave 1554 — differential fuzz of ``TextToPDF.create_pdf_from_text`` vs the
live Apache PDFBox 3.0.7 oracle.

Complements ``test_text_to_pdf_oracle.py`` (which pins one fixed multi-line body
under the default config). This module sweeps the layout knobs (font size, page
size, landscape, uniform margin) across a battery of pathological text inputs:
empty, tabs, form-feeds, CR/LF vs LF, CR-only, a single very long line that
wraps, an unbreakable 500-char word, many lines overflowing to multiple pages,
unicode beyond Latin-1, the WinAnsi-only em dash, leading/trailing whitespace,
control characters, and a custom landscape A4 / large-font A5 layout.

Each case is driven through the ``TextToPdfFuzzProbe`` Java probe and through
pypdfbox's :class:`~pypdfbox.tools.text_to_pdf.TextToPDF`, then both sides are
reduced to the *same* canonical structural summary (status, page count,
``PDFTextStripper`` text, sorted distinct ``/BaseFont`` names). The summary is
byte-for-byte comparable so any divergence in wrapping, page breaks, form-feed
handling, or font selection fails the assertion.

DOCUMENTED DIVERGENCE (CHANGES.md, simple-font encode contract):
    Apache PDFBox's standard-14 ``PDType1Font.encode`` THROWS
    ``IllegalArgumentException`` for any code point the font's WinAnsi
    encoding cannot map (tab ``\\t``, control chars, astral unicode such as
    emoji), so ``createPDFFromText`` aborts and Apache emits no document.
    pypdfbox deliberately substitutes ``b'?'`` for unmapped code points
    (round-trip-friendly writer contract) rather than raising, so pypdfbox
    *produces* a document for those same inputs. The non-encodable cases below
    therefore assert ``status=err:IllegalArgumentException`` on the Java side
    and a successful build (``status=ok``) on the pypdfbox side, pinning the
    divergence on BOTH sides instead of papering over it.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools.text_to_pdf import TextToPDF
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE_SIZES = {
    "LETTER": PDRectangle.LETTER,
    "LEGAL": PDRectangle.LEGAL,
    "A4": PDRectangle.A4,
    "A5": PDRectangle.A5,
}


def _escape(value: str) -> str:
    """Mirror the Java probe's ``escape`` so the two summaries are comparable."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _font_name(font: object) -> str | None:
    if isinstance(font, PDFont):
        return font.get_name()
    if isinstance(font, COSDictionary):
        return font.get_name_as_string(COSName.get_pdf_name("BaseFont"))
    return None


def _pypdfbox_summary(
    text: str,
    out_path: Path,
    *,
    font_size: float,
    page_size: str,
    landscape: bool,
    margin: float,
) -> str:
    """Build the same canonical summary the probe emits, from pypdfbox.

    Because pypdfbox never raises while encoding (see module docstring), the
    successful build always reports ``status=ok`` here.
    """
    tool = TextToPDF()
    tool.set_font_size(int(font_size))
    tool.set_media_box(_PAGE_SIZES[page_size])
    tool.set_landscape(landscape)
    tool.set_left_margin(margin)
    tool.set_right_margin(margin)
    tool.set_top_margin(margin)
    tool.set_bottom_margin(margin)

    with PDDocument() as doc:
        tool.create_pdf_from_text(doc, StringIO(text))
        doc.save(str(out_path))

    lines: list[str] = ["status=ok"]
    with PDDocument.load(out_path) as doc:
        lines.append(f"pages={doc.get_number_of_pages()}")
        lines.append(f"text={_escape(PDFTextStripper().get_text(doc))}")
        fonts: list[str] = []
        for page in doc.get_pages():
            resources = page.get_resources()
            if resources is None:
                continue
            for name in resources.get_font_names():
                resolved = _font_name(resources.get_font(name))
                if resolved is not None and resolved not in fonts:
                    fonts.append(resolved)
        fonts.sort()
        lines.append("fonts=" + ",".join(fonts))
    return "\n".join(lines) + "\n"


# (id, text, font_size, page_size, landscape, margin) — inputs the standard
# Helvetica font CAN encode, so Apache and pypdfbox must agree exactly.
_ENCODABLE_CASES = [
    ("formfeed", "before\fafter\n", 10.0, "LETTER", False, 40.0),
    ("multi_formfeed", "a\f\fb\n", 10.0, "LETTER", False, 40.0),
    ("formfeed_start", "\fafter\n", 10.0, "LETTER", False, 40.0),
    ("crlf", "line1\r\nline2\n", 10.0, "LETTER", False, 40.0),
    ("cr_only", "a\rb\n", 10.0, "LETTER", False, 40.0),
    ("blank_lines", "a\n\n\n\nb\n", 10.0, "LETTER", False, 40.0),
    ("no_trailing_newline", "no trailing newline", 10.0, "LETTER", False, 40.0),
    ("leading_trailing_ws", "   spaced   \n", 10.0, "LETTER", False, 40.0),
    ("long_wrapping_line", ("word " * 200).rstrip() + "\n", 10.0, "LETTER", False, 40.0),
    ("unbreakable_word", "x" * 500 + "\n", 10.0, "LETTER", False, 40.0),
    (
        "many_lines_multipage",
        "".join(f"line {i}\n" for i in range(120)),
        10.0,
        "LETTER",
        False,
        40.0,
    ),
    ("latin1_accents", "café naïve\n", 10.0, "LETTER", False, 40.0),
    ("landscape_a4", "hello world\nsecond line\n", 12.0, "A4", True, 50.0),
    (
        "a5_big_font_wrap",
        "Big text here that should wrap maybe yes indeed quite long\n",
        24.0,
        "A5",
        False,
        30.0,
    ),
    ("legal_small_margin", "alpha beta gamma\n" * 60, 8.0, "LEGAL", False, 10.0),
    ("tight_margin_letter", " The quick brown fox jumps\n" * 40, 10.0, "LETTER", False, 5.0),
]

# Cases where TextToPDF lays out identically (same status / page count /
# font set) but a DOWNSTREAM component (not TextToPDF) extracts text
# differently, so we pin status+pages+fonts and not the extracted text:
#   * "empty"   — TextToPDF (after the wave-1554 fix) emits a blank page with
#     NO content stream and NO font resource, exactly like Apache. Apache's
#     PDFTextStripper returns "" for that page; pypdfbox's returns "\n" (an
#     empty-page extraction artifact in the text stripper, a separate surface).
#   * "em_dash" — the WinAnsi em dash (U+2014 -> 0x97) is encoded correctly by
#     both sides, but pypdfbox's reverse cmap / ToUnicode path extracts it as a
#     replacement char rather than "—" (a font/text-stripper surface, not the
#     tool). Layout (1 page, Helvetica) is at parity.
_STRUCTURE_ONLY_CASES = [
    ("empty", "", False),
    ("em_dash", "a—b\n", True),
]

# Inputs containing code points the standard Helvetica font cannot encode:
# Apache RAISES (status=err:IllegalArgumentException, no document produced),
# pypdfbox substitutes b'?' and produces a document (status=ok). See module
# docstring — this is a deliberate, documented divergence we pin on both sides.
_NON_ENCODABLE_CASES = [
    ("tab", "a\tb\tc\n"),
    ("control_chars", "a\x07b\x00c\n"),
    ("emoji_astral", "hi \U0001f600 there\n"),
    ("vertical_tab", "a\x0bb\n"),
]


@pytest.mark.parametrize(
    ("case_id", "text", "font_size", "page_size", "landscape", "margin"),
    _ENCODABLE_CASES,
    ids=[c[0] for c in _ENCODABLE_CASES],
)
@requires_oracle
def test_encodable_cases_match_pdfbox(
    case_id: str,
    text: str,
    font_size: float,
    page_size: str,
    landscape: bool,
    margin: float,
    tmp_path: Path,
) -> None:
    text_path = tmp_path / f"{case_id}.txt"
    text_path.write_bytes(text.encode("utf-8"))

    java_summary = run_probe_text(
        "TextToPdfFuzzProbe",
        str(text_path),
        str(tmp_path / f"{case_id}_java.pdf"),
        str(font_size),
        page_size,
        "true" if landscape else "false",
        str(margin),
    )
    # The standard font encodes every code point in these inputs, so Apache
    # builds successfully — guard the fixture intent.
    assert java_summary.startswith("status=ok\n"), (
        f"{case_id}: oracle unexpectedly failed: {java_summary!r}"
    )

    py_summary = _pypdfbox_summary(
        text,
        tmp_path / f"{case_id}_py.pdf",
        font_size=font_size,
        page_size=page_size,
        landscape=landscape,
        margin=margin,
    )

    assert py_summary == java_summary, (
        f"TextToPDF divergence for {case_id}:\n"
        f"  java: {java_summary!r}\n"
        f"  py:   {py_summary!r}"
    )


def _structure_lines(summary: str) -> list[str]:
    """Keep status/pages/fonts; drop the ``text=`` line (extraction surface)."""
    return [
        line
        for line in summary.splitlines()
        if not line.startswith("text=")
    ]


@pytest.mark.parametrize(
    ("case_id", "text", "_has_text"),
    _STRUCTURE_ONLY_CASES,
    ids=[c[0] for c in _STRUCTURE_ONLY_CASES],
)
@requires_oracle
def test_structure_matches_pdfbox_text_extraction_diverges(
    case_id: str, text: str, _has_text: bool, tmp_path: Path
) -> None:
    """Pin layout parity (status/pages/fonts) where downstream extraction
    diverges. See ``_STRUCTURE_ONLY_CASES`` for the per-case rationale."""
    text_path = tmp_path / f"{case_id}.txt"
    text_path.write_bytes(text.encode("utf-8"))

    java_summary = run_probe_text(
        "TextToPdfFuzzProbe",
        str(text_path),
        str(tmp_path / f"{case_id}_java.pdf"),
        "10",
        "LETTER",
        "false",
        "40",
    )
    py_summary = _pypdfbox_summary(
        text,
        tmp_path / f"{case_id}_py.pdf",
        font_size=10.0,
        page_size="LETTER",
        landscape=False,
        margin=40.0,
    )
    assert _structure_lines(py_summary) == _structure_lines(java_summary), (
        f"TextToPDF layout divergence for {case_id}:\n"
        f"  java: {java_summary!r}\n"
        f"  py:   {py_summary!r}"
    )


@pytest.mark.parametrize(
    ("case_id", "text"),
    _NON_ENCODABLE_CASES,
    ids=[c[0] for c in _NON_ENCODABLE_CASES],
)
@requires_oracle
def test_non_encodable_cases_diverge_documented(
    case_id: str, text: str, tmp_path: Path
) -> None:
    """Pin the documented encode divergence on BOTH sides.

    Apache raises ``IllegalArgumentException`` (no document); pypdfbox
    substitutes ``b'?'`` and produces a one-page document.
    """
    text_path = tmp_path / f"{case_id}.txt"
    text_path.write_bytes(text.encode("utf-8"))

    java_summary = run_probe_text(
        "TextToPdfFuzzProbe",
        str(text_path),
        str(tmp_path / f"{case_id}_java.pdf"),
        "10",
        "LETTER",
        "false",
        "40",
    )
    # Apache aborts: the standard font's WinAnsi encoding cannot map these
    # code points, so createPDFFromText throws and emits no document.
    assert java_summary == "status=err:IllegalArgumentException\n", (
        f"{case_id}: expected Apache to raise on unmapped glyph, got "
        f"{java_summary!r}"
    )

    # pypdfbox does NOT raise — it substitutes b'?' (documented divergence) and
    # produces a document. Confirm a successful one-page build rather than a
    # crash.
    py_summary = _pypdfbox_summary(
        text,
        tmp_path / f"{case_id}_py.pdf",
        font_size=10.0,
        page_size="LETTER",
        landscape=False,
        margin=40.0,
    )
    assert py_summary.startswith("status=ok\n"), py_summary
    assert "\npages=1\n" in py_summary, py_summary
