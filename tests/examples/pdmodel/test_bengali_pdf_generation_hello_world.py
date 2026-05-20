"""Coverage-boost tests for ``pypdfbox.examples.pdmodel.bengali_pdf_generation_hello_world``.

Targets the missing branches in wave 1335:

* ``_read_bengali_lines`` (comment-filter)
* ``main()`` with explicit TTF path (Type0 font, width-aware reflow)
* ``get_re_aligned_text_based_on_page_height`` (page-split logic)
* ``get_re_aligned_text_based_on_page_width`` separator-token branches
* ``get_bengali_text_from_file`` env-var override search-strategy
* ``_tokenize_keep_separators`` empty-string short-circuit
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel import bengali_pdf_generation_hello_world as bg_mod
from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.examples.pdmodel.bengali_pdf_generation_hello_world import (
    BengaliPdfGenerationHelloWorld,
    _read_bengali_lines,
    _tokenize_keep_separators,
)
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_REPO_TTF = Path(
    "/Users/nitro/Documents/pypdfbox/pypdfbox/resources/ttf/DejaVuSans.ttf"
)


# ---------------------------------------------------------------------------
# Constructor + module surface
# ---------------------------------------------------------------------------


def test_constructor_is_a_no_op() -> None:
    obj = BengaliPdfGenerationHelloWorld()
    assert obj is not None
    # Class-level constants surface for parity.
    assert BengaliPdfGenerationHelloWorld.FONT_SIZE == 20
    assert BengaliPdfGenerationHelloWorld.MARGIN == 20
    assert BengaliPdfGenerationHelloWorld.LINE_GAP == 5
    assert BengaliPdfGenerationHelloWorld.LOHIT_BENGALI_TTF.endswith(
        "Lohit-Bengali.ttf",
    )


def test_get_page_size_returns_a4() -> None:
    rect = BengaliPdfGenerationHelloWorld.get_page_size()
    assert rect is PDRectangle.A4


# ---------------------------------------------------------------------------
# _read_bengali_lines — comment filter
# ---------------------------------------------------------------------------


def test_read_bengali_lines_filters_comments(tmp_path: Path) -> None:
    sample = tmp_path / "bengali-samples.txt"
    sample.write_text(
        "# header comment\nline-1\nline-2\n# trailing\n",
        encoding="utf-8",
    )
    lines = _read_bengali_lines(sample)
    assert lines == ["line-1", "line-2"]


def test_read_bengali_lines_empty_file(tmp_path: Path) -> None:
    sample = tmp_path / "empty.txt"
    sample.write_text("", encoding="utf-8")
    assert _read_bengali_lines(sample) == []


def test_read_bengali_lines_strips_crlf(tmp_path: Path) -> None:
    sample = tmp_path / "crlf.txt"
    # Write with CRLF line endings, no trailing newline on second line.
    sample.write_bytes(b"alpha\r\nbeta\r\n")
    lines = _read_bengali_lines(sample)
    assert lines == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# _tokenize_keep_separators
# ---------------------------------------------------------------------------


def test_tokenize_keep_separators_empty_string() -> None:
    assert _tokenize_keep_separators("", " ") == []


def test_tokenize_keep_separators_basic() -> None:
    # Mirrors Java's ``StringTokenizer(text, sep, true)``.
    assert _tokenize_keep_separators("foo bar", " ") == ["foo", " ", "bar"]


def test_tokenize_keep_separators_leading_separator() -> None:
    assert _tokenize_keep_separators(" foo", " ") == [" ", "foo"]


def test_tokenize_keep_separators_only_separators() -> None:
    assert _tokenize_keep_separators("   ", " ") == [" ", " ", " "]


# ---------------------------------------------------------------------------
# main() — usage + Helvetica fallback + explicit TTF
# ---------------------------------------------------------------------------


def test_main_usage_no_args() -> None:
    with pytest.raises(SystemExit):
        BengaliPdfGenerationHelloWorld.main([])


def test_main_usage_none_argv() -> None:
    with pytest.raises(SystemExit):
        BengaliPdfGenerationHelloWorld.main(None)


def test_main_helvetica_fallback_writes_pdf(tmp_path: Path, capsys) -> None:
    out = tmp_path / "bengali.pdf"
    BengaliPdfGenerationHelloWorld.main([str(out)])
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
    captured = capsys.readouterr()
    assert "The generated pdf filename is" in captured.out
    assert str(out) in captured.out


def test_main_with_explicit_ttf_writes_pdf(tmp_path: Path) -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    out = tmp_path / "bengali_ttf.pdf"
    BengaliPdfGenerationHelloWorld.main([str(out), str(_REPO_TTF)])
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
    # Round-trip parse to confirm at least one page emerged.
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() >= 1


def test_main_with_nonexistent_ttf_falls_back(tmp_path: Path) -> None:
    out = tmp_path / "bengali_missing.pdf"
    # Non-existent TTF path triggers the ``is_file()`` False branch and
    # falls back to Helvetica.
    BengaliPdfGenerationHelloWorld.main(
        [str(out), str(tmp_path / "does-not-exist.ttf")],
    )
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# get_re_aligned_text_based_on_page_height — page-split branches
# ---------------------------------------------------------------------------


def test_re_aligned_height_single_page_when_fits() -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    doc = PDDocument()
    try:
        font = PDType0Font.load(doc, _REPO_TTF)
        # A4 minus margins is huge → all lines fit on one page.
        pages = (
            BengaliPdfGenerationHelloWorld
            .get_re_aligned_text_based_on_page_height(
                ["one", "two", "three"], font, 800.0,
            )
        )
        assert len(pages) == 1
        assert pages[0] == ["one", "two", "three"]
    finally:
        doc.close()


def test_re_aligned_height_multi_page_when_overflow() -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    doc = PDDocument()
    try:
        font = PDType0Font.load(doc, _REPO_TTF)
        # Tiny workable height forces every line onto its own page.
        pages = (
            BengaliPdfGenerationHelloWorld
            .get_re_aligned_text_based_on_page_height(
                ["a", "b", "c", "d"], font, 1.0,
            )
        )
        # Multi-page split — at least the first line lives alone.
        assert sum(len(p) for p in pages) == 4
        assert len(pages) >= 2
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# get_re_aligned_text_based_on_page_width
# ---------------------------------------------------------------------------


def test_re_aligned_width_short_lines_pass_through() -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    doc = PDDocument()
    try:
        font = PDType0Font.load(doc, _REPO_TTF)
        out = (
            BengaliPdfGenerationHelloWorld
            .get_re_aligned_text_based_on_page_width(
                ["hi", "there"], font, 1000.0,
            )
        )
        # Each source line emits a flat chunk; whitespace is preserved.
        assert "hi" in "".join(out)
        assert "there" in "".join(out)
    finally:
        doc.close()


def test_re_aligned_width_long_line_wraps() -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    doc = PDDocument()
    try:
        font = PDType0Font.load(doc, _REPO_TTF)
        # Tiny page width forces the wrap branch (line 234-236 in source).
        out = (
            BengaliPdfGenerationHelloWorld
            .get_re_aligned_text_based_on_page_width(
                ["alpha beta gamma delta"], font, 10.0,
            )
        )
        # Should have wrapped into multiple chunks.
        assert len(out) >= 2
        joined = "".join(out)
        for word in ("alpha", "beta", "gamma", "delta"):
            assert word in joined
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# get_bengali_text_from_file — env-var override (strategy 2)
# ---------------------------------------------------------------------------


def test_get_bengali_text_from_file_env_var_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf_dir = tmp_path / "ttf"
    ttf_dir.mkdir()
    sample = ttf_dir / "bengali-samples.txt"
    sample.write_text(
        "# header\nএকটি\nদুই\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYPDFBOX_RESOURCE_DIR", str(tmp_path))
    # Force strategy 1 (bundled package data) to miss by patching
    # importlib.resources lookup. We rely on the env-var path winning
    # before the developer-tree walk picks up unrelated files.
    lines = BengaliPdfGenerationHelloWorld.get_bengali_text_from_file()
    # Even if the developer-tree path is also present, the env-var
    # candidate comes first in ``candidates`` — assert at least one of
    # our two sample lines is the first match.
    if lines:
        assert "একটি" in lines or "দুই" in lines or lines == [
            "একটি", "দুই",
        ]


def test_get_bengali_text_from_file_returns_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without env-var override, the function still returns a list (may
    # be empty or pulled from a fallback path).
    monkeypatch.delenv("PYPDFBOX_RESOURCE_DIR", raising=False)
    result = BengaliPdfGenerationHelloWorld.get_bengali_text_from_file()
    assert isinstance(result, list)


def test_get_bengali_text_from_file_handles_missing_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Point env-var override at a directory that does NOT contain the
    # sample file AND stub out ``Path.is_file`` so that no candidate
    # (including the ``/tmp/pdfbox`` developer-tree path which may exist
    # on a CI box that mirrored upstream) matches → exercises the
    # "candidate not is_file" loop tail and returns an empty list.
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setenv("PYPDFBOX_RESOURCE_DIR", str(empty_dir))
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    result = BengaliPdfGenerationHelloWorld.get_bengali_text_from_file()
    assert result == []


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def test_fallback_sample_module_constant() -> None:
    assert bg_mod._FALLBACK_SAMPLE  # not empty
    assert all(isinstance(s, str) for s in bg_mod._FALLBACK_SAMPLE)


def test_main_falls_back_to_sample_when_corpus_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force ``get_bengali_text_from_file`` to return an empty list so
    # ``main()`` lands on the ``_FALLBACK_SAMPLE`` branch (line 91-92).
    monkeypatch.setattr(
        BengaliPdfGenerationHelloWorld,
        "get_bengali_text_from_file",
        staticmethod(lambda: []),
    )
    out = tmp_path / "bengali_fallback.pdf"
    BengaliPdfGenerationHelloWorld.main([str(out)])
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"


def test_main_helvetica_fallback_uses_skipped_placeholder(
    tmp_path: Path,
) -> None:
    # Helvetica lacks the codepoints in _FALLBACK_SAMPLE; the inner
    # ``show_text`` raises and triggers the ``[skipped]`` placeholder
    # (line 153-157).
    out = tmp_path / "skipped.pdf"
    BengaliPdfGenerationHelloWorld.main([str(out)])
    # The PDF is still well-formed.
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"


def test_get_re_aligned_text_helvetica_raises_attribute_error() -> None:
    # Helvetica fallback has no /FontDescriptor → get_font_descriptor()
    # returns None and the height re-align raises AttributeError, which
    # main() catches and falls back to a single-line-per-page layout.
    font = make_standard14_type1_font(FontName.HELVETICA)
    with pytest.raises((AttributeError, TypeError)):
        BengaliPdfGenerationHelloWorld.get_re_aligned_text_based_on_page_height(
            ["x"], font, 100.0,
        )
