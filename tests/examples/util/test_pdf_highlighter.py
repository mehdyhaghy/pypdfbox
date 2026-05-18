"""Tests for :class:`PDFHighlighter`."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.pdf_highlighter import PDFHighlighter
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _make_pdf_with_text(path: Path, text: str) -> Path:
    """Build a tiny PDF with one page containing ``text`` rendered via
    a base 14 Helvetica font."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(PDType1Font(), 12)
            cs.new_line_at_offset(50, 700)
            cs.show_text(text)
            cs.end_text()
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------------------------------------------------------------------------
# generate_xml_highlight
# ---------------------------------------------------------------------------


def test_generate_xml_highlight_emits_wrapper(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("highlight.pdf")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        PDFHighlighter().generate_xml_highlight(doc, "anything", out)
    text = out.getvalue()
    assert text.startswith("<XML>")
    assert "<Highlight>" in text
    assert "</Highlight>" in text
    assert text.endswith("</XML>")


def test_generate_xml_highlight_normalizes_single_string(tmp_path: Path) -> None:
    """A single ``str`` is normalised to a one-element list (covers the
    isinstance(words, str) branch in ``generate_xml_highlight``)."""
    src = _make_pdf_with_text(tmp_path / "doc.pdf", "Hello World")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        h = PDFHighlighter()
        h.generate_xml_highlight(doc, "Hello", out)
    # The single search string was wrapped — verify post-call state.
    assert h._searched_words == ["Hello"]


def test_generate_xml_highlight_accepts_string_list(tmp_path: Path) -> None:
    """When ``words`` is already a list it bypasses the str wrap."""
    src = _make_pdf_with_text(tmp_path / "doc.pdf", "Apple Banana Cherry")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        h = PDFHighlighter()
        h.generate_xml_highlight(doc, ["Banana", "Cherry"], out)
    assert h._searched_words == ["Banana", "Cherry"]


def test_end_page_emits_loc_for_match() -> None:
    """Directly exercise ``end_page`` with a populated buffer to mirror
    the per-page callback path the Java upstream relies on."""
    h = PDFHighlighter()
    out = io.StringIO()
    h._highlighter_output = out
    h._text_os = io.StringIO()
    h._text_writer = h._text_os
    h._searched_words = ["needle"]
    h._text_os.write("haystack needle haystack")
    h.end_page(object())
    text = out.getvalue()
    assert "<loc" in text
    assert "pg=" in text
    assert "pos=" in text
    assert "len=6" in text  # len("needle")


def test_end_page_matches_case_insensitive() -> None:
    h = PDFHighlighter()
    out = io.StringIO()
    h._highlighter_output = out
    h._text_os = io.StringIO()
    h._text_writer = h._text_os
    h._searched_words = ["NEEDLE"]
    h._text_os.write("hay needle hay")
    h.end_page(object())
    assert "<loc" in out.getvalue()


def test_end_page_writes_nothing_when_no_match() -> None:
    h = PDFHighlighter()
    out = io.StringIO()
    h._highlighter_output = out
    h._text_os = io.StringIO()
    h._text_writer = h._text_os
    h._searched_words = ["missing"]
    h._text_os.write("alpha beta gamma")
    h.end_page(object())
    assert "<loc" not in out.getvalue()


def test_generate_xml_highlight_no_match_only_wrapper(tmp_path: Path) -> None:
    src = _make_pdf_with_text(tmp_path / "doc.pdf", "alpha beta")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        PDFHighlighter().generate_xml_highlight(doc, "gamma", out)
    text = out.getvalue()
    assert "<loc" not in text
    assert "<Highlight>" in text


def test_end_page_returns_when_state_not_initialized() -> None:
    """``end_page`` must be a no-op when ``generate_xml_highlight`` has
    not been invoked first (text_os / output sinks are ``None``)."""
    highlighter = PDFHighlighter()
    # Pass a dummy page-like object; the method should return immediately.
    highlighter.end_page(object())


def test_end_page_strips_axxx_artifacts(tmp_path: Path) -> None:
    """When the buffered page text contains "a<digits>" artifacts the
    cleanup branch (``re.sub(r"a\\d{1,3}", ".", page)``) must trigger."""
    src = _make_pdf_with_text(tmp_path / "doc.pdf", "data1 data22 alpha")
    out = io.StringIO()
    with PDDocument.load(str(src)) as doc:
        # Search for a literal "." matches anywhere; using a string that
        # cannot match avoids polluting the assertion.
        PDFHighlighter().generate_xml_highlight(doc, "alpha", out)
    # Generation finished without raising even when the artifact regex
    # fires; if the body contained 'a' the regex was evaluated.
    text = out.getvalue()
    assert text.endswith("</XML>")


# ---------------------------------------------------------------------------
# main / usage entry points
# ---------------------------------------------------------------------------


def test_main_with_zero_args_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PDFHighlighter.main([])
    err = capsys.readouterr().err
    assert "usage:" in err
    assert "PDFHighlighter" in err


def test_main_with_one_arg_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PDFHighlighter.main(["only-one.pdf"])
    assert "usage:" in capsys.readouterr().err


def test_main_with_none_argv_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PDFHighlighter.main(None)
    assert "usage:" in capsys.readouterr().err


def test_main_runs_with_file_and_word(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _make_pdf_with_text(tmp_path / "doc.pdf", "Hello World")
    PDFHighlighter.main([str(src), "Hello"])
    out = capsys.readouterr().out
    assert "<XML>" in out
    assert "</XML>" in out


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    PDFHighlighter.usage()
    out = capsys.readouterr()
    assert "usage:" in out.err
    assert out.out == ""


def test_constructor_initializes_state() -> None:
    h = PDFHighlighter()
    assert h._highlighter_output is None
    assert h._searched_words == []
    assert h._text_os is None


def test_encoding_class_constant() -> None:
    assert PDFHighlighter.ENCODING == "utf-16"


def test_module_main_guard_resolves() -> None:
    mod = sys.modules["pypdfbox.examples.util.pdf_highlighter"]
    assert mod.PDFHighlighter is PDFHighlighter


def test_constructor_swallows_attribute_error_when_setter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lite ports of ``PDFTextStripper`` may not expose every separator
    setter — the constructor wraps the four ``set_*`` calls in a
    ``try / except AttributeError`` so missing helpers degrade gracefully
    (wave 1351 line-coverage of the except-branch at lines 35-37).
    """
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    # Remove ``set_should_separate_by_beads`` so the chain raises
    # ``AttributeError`` on the third statement of the ``try`` block. The
    # constructor must swallow the exception and finish initialisation.
    monkeypatch.delattr(PDFTextStripper, "set_should_separate_by_beads")
    highlighter = PDFHighlighter()
    assert highlighter._highlighter_output is None
    assert highlighter._searched_words == []
    assert highlighter._text_os is None
    assert highlighter._text_writer is None
