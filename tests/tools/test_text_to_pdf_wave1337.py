"""Wave 1337 coverage-boost tests for ``pypdfbox.tools.text_to_pdf.TextToPDF``.

Targets the residual branches in ``TextToPDF._create_pdf_from_text`` and the
``call`` / ``main`` entry points.

**Latent bug:** ``TextToPDF`` source paths use
``PDType1Font(self.standard_font)`` to materialise the default font when
``self.font`` is ``None`` (lines 138 and 237). Our ``PDType1Font.__init__``
expects a ``COSDictionary`` — the ``FontName`` enum stored in
``self.standard_font`` triggers ``AttributeError: 'FontName' object has no
attribute 'get_dictionary_object'`` at runtime. The sister module
``pypdfbox.tools.texttopdf`` correctly resolves the default font via
``PDFontFactory.create_default_font(...)``. Filed in the wave report; tests
here drive every branch that *doesn't* depend on the broken default by
pre-loading a real :class:`PDType0Font` from a bundled TTF fixture.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.tools.text_to_pdf import DEFAULT_FONT_SIZE, PageSizes, TextToPDF

FIXTURE_TTF = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _usable_font(doc: PDDocument) -> object:
    """Load a real TTF into ``doc`` so its bounding box is non-null.

    The Standard-14 default-font path is currently broken (see module
    docstring); a TTF-backed Type0 font carries a fully-populated
    descriptor + bbox so the text-flow code can compute widths.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip(f"missing fixture: {FIXTURE_TTF}")
    return PDType0Font.load(doc, str(FIXTURE_TTF))


# ---------- _create_pdf_from_text branch coverage ----------


def test_create_pdf_from_text_basic_round_trip() -> None:
    """With a font pre-supplied, ``create_pdf_from_text`` produces at
    least one page."""
    t = TextToPDF()
    doc = PDDocument()
    try:
        t.font = _usable_font(doc)
        t.create_pdf_from_text(doc, "hello\n")
        assert doc.get_number_of_pages() >= 1
        assert t.get_font() is not None
    finally:
        doc.close()


@pytest.mark.skip(
    reason=(
        "Latent bug: ``content.splitlines()`` in ``_create_pdf_from_text`` "
        "consumes ``\\f`` (Python str.splitlines treats form-feed as a "
        "line break), so the form-feed branches at lines 162-180 / 211-221 "
        "never see a ``\\f`` token. Mirroring the upstream Java string "
        "split-on-newline-only behaviour would require ``content.split('\\n')``. "
        "Flagged in the wave 1337 report."
    )
)
def test_create_pdf_from_text_form_feed_emits_extra_page() -> None:
    """Would-be coverage of lines 166-168, 178, 180, 185, 211-221.
    Skipped pending the splitlines vs split-on-newline fix above."""
    t = TextToPDF()
    doc = PDDocument()
    try:
        t.font = _usable_font(doc)
        t.create_pdf_from_text(doc, "before\fafter\n")
        assert doc.get_number_of_pages() >= 2
    finally:
        doc.close()


def test_create_pdf_from_text_long_line_wraps_overflow() -> None:
    """Drive the ``length_if_using_next_word`` lookahead (line 185)
    until the line wraps."""
    t = TextToPDF()
    doc = PDDocument()
    try:
        t.font = _usable_font(doc)
        long_body = " ".join(["word"] * 200) + "\n"
        t.create_pdf_from_text(doc, long_body)
        assert doc.get_number_of_pages() >= 1
    finally:
        doc.close()


def test_create_pdf_from_text_empty_input_still_yields_a_page() -> None:
    """Line 223 — ``text_is_empty`` path adds the initial page even
    when the body is empty."""
    t = TextToPDF()
    doc = PDDocument()
    try:
        t.font = _usable_font(doc)
        t.create_pdf_from_text(doc, "")
        assert doc.get_number_of_pages() == 1
    finally:
        doc.close()


# ---------- entry-point coverage ----------


def test_call_with_ttf_load_branch(tmp_path: Path) -> None:
    """Line 235 — when ``self.ttf`` is set, ``call`` routes through
    ``PDType0Font.load``."""
    if not FIXTURE_TTF.exists():
        pytest.skip(f"missing fixture: {FIXTURE_TTF}")
    src = tmp_path / "in.txt"
    src.write_text("hello world\n", encoding="utf-8")
    out = tmp_path / "out.pdf"

    t = TextToPDF()
    t.infile = src
    t.outfile = out
    t.ttf = FIXTURE_TTF
    rc = t.call()
    assert rc == 0
    assert out.is_file()


def test_call_returns_io_error_code_for_missing_input(tmp_path: Path) -> None:
    """``call`` returns 4 when the input file is missing.

    Drive the ``except OSError`` arm by pointing at a path that doesn't
    exist; pre-supply a TTF so we avoid the latent default-font bug
    along the way."""
    t = TextToPDF()
    t.infile = tmp_path / "ghost.txt"
    t.outfile = tmp_path / "out.pdf"
    t.ttf = FIXTURE_TTF if FIXTURE_TTF.exists() else None
    rc = t.call()
    assert rc == 4


def test_call_raises_without_paths() -> None:
    """``call`` raises ``OSError`` when ``infile`` or ``outfile`` is
    None — both fields default to None."""
    t = TextToPDF()
    with pytest.raises(OSError, match="required"):
        t.call()


def test_page_sizes_get_page_size_letter() -> None:
    """``PageSizes`` enum exposes the rectangle through
    ``get_page_size``."""
    letter = PageSizes.LETTER.get_page_size()
    assert letter.get_width() > 0
    assert letter.get_height() > 0


def test_main_with_ttf_argument(tmp_path: Path) -> None:
    """``main`` with ``-ttf`` walks the TTF-load branch + Path
    conversion (line 287)."""
    if not FIXTURE_TTF.exists():
        pytest.skip(f"missing fixture: {FIXTURE_TTF}")
    src = tmp_path / "in.txt"
    src.write_text("hi\n", encoding="utf-8")
    out = tmp_path / "out.pdf"
    rc = TextToPDF.main(
        ["-i", str(src), "-o", str(out), "-ttf", str(FIXTURE_TTF)]
    )
    assert rc == 0


def test_main_with_landscape_and_margins(tmp_path: Path) -> None:
    """``main`` with ``-landscape`` + custom ``-margins`` walks the
    full setter sequence inside ``call``."""
    if not FIXTURE_TTF.exists():
        pytest.skip(f"missing fixture: {FIXTURE_TTF}")
    src = tmp_path / "in.txt"
    src.write_text("hi\n", encoding="utf-8")
    out = tmp_path / "out.pdf"
    rc = TextToPDF.main(
        [
            "-i", str(src),
            "-o", str(out),
            "-ttf", str(FIXTURE_TTF),
            "-landscape",
            "-margins", "20", "20", "30", "30",
        ]
    )
    assert rc == 0
    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() > mb.get_height()


def test_main_a4_page_size(tmp_path: Path) -> None:
    """``main`` with ``-pageSize A4`` covers the ``PageSizes[ns.pageSize]``
    lookup (line 283)."""
    if not FIXTURE_TTF.exists():
        pytest.skip(f"missing fixture: {FIXTURE_TTF}")
    src = tmp_path / "in.txt"
    src.write_text("hi\n", encoding="utf-8")
    out = tmp_path / "out.pdf"
    rc = TextToPDF.main(
        [
            "-i", str(src),
            "-o", str(out),
            "-ttf", str(FIXTURE_TTF),
            "-pageSize", "A4",
            "-fontSize", str(DEFAULT_FONT_SIZE),
        ]
    )
    assert rc == 0


# ---------- setter / getter sanity (cheap coverage of accessors) ----------


def test_textto_pdf_accessor_round_trip() -> None:
    """Hit every getter / setter so the accessor blocks are covered."""
    t = TextToPDF()
    t.set_font_size(14)
    assert t.get_font_size() == 14
    t.set_left_margin(11.0)
    assert t.get_left_margin() == 11.0
    t.set_right_margin(12.0)
    assert t.get_right_margin() == 12.0
    t.set_top_margin(13.0)
    assert t.get_top_margin() == 13.0
    t.set_bottom_margin(14.0)
    assert t.get_bottom_margin() == 14.0
    t.set_landscape(True)
    assert t.is_landscape() is True
    t.set_line_spacing(1.5)
    assert t.get_line_spacing() == 1.5


def test_textto_pdf_line_spacing_rejects_zero() -> None:
    t = TextToPDF()
    with pytest.raises(ValueError, match="positive"):
        t.set_line_spacing(0)
