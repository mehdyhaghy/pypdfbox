"""Coverage tests for the :class:`EmbeddedVerticalFonts` example."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.embedded_vertical_fonts import (
    EmbeddedVerticalFonts,
)
from pypdfbox.pdmodel.pd_document import PDDocument

# Liberation/DejaVu fonts bundled with pypdfbox stand in for IPA Gothic for
# the structural / API parity exercise; the visible glyph fidelity is not
# the subject of these tests.
_BUNDLED_TTF = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox" / "resources" / "ttf" / "DejaVuSans.ttf"
)


def _assert_is_pdf(path: Path) -> None:
    assert path.exists(), f"missing output PDF: {path}"
    assert path.stat().st_size > 0
    assert path.read_bytes()[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Construction / static surface
# ---------------------------------------------------------------------------


def test_can_be_instantiated() -> None:
    EmbeddedVerticalFonts()


# ---------------------------------------------------------------------------
# main() — fixture-absent path
# ---------------------------------------------------------------------------


def test_main_without_fixture_raises_not_implemented(tmp_path: Path) -> None:
    """Upstream's ``main`` short-circuits when ``ipag.ttf`` is missing
    from cwd — pypdfbox surfaces the same situation as ``NotImplementedError``.
    """
    # Run from a known-empty directory to ensure the lookup fails.
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(NotImplementedError, match="ipag.ttf"):
            EmbeddedVerticalFonts.main(None)
    finally:
        os.chdir(cwd)


def test_main_with_missing_explicit_ttf_path_raises(tmp_path: Path) -> None:
    out = tmp_path / "ignored.pdf"
    with pytest.raises(NotImplementedError, match="ipag.ttf"):
        EmbeddedVerticalFonts.main([str(out), str(tmp_path / "no-such.ttf")])


def test_main_with_provided_ttf_runs(tmp_path: Path) -> None:
    """``main`` should round-trip when given a real TTF path as argv[1]."""
    if not _BUNDLED_TTF.is_file():
        pytest.skip(f"bundled font absent: {_BUNDLED_TTF}")
    out = tmp_path / "vertical.pdf"
    EmbeddedVerticalFonts.main([str(out), str(_BUNDLED_TTF)])
    _assert_is_pdf(out)


# ---------------------------------------------------------------------------
# demo_with_font()
# ---------------------------------------------------------------------------


def test_demo_with_font_writes_pdf(tmp_path: Path) -> None:
    if not _BUNDLED_TTF.is_file():
        pytest.skip(f"bundled font absent: {_BUNDLED_TTF}")
    out = tmp_path / "vertical.pdf"
    EmbeddedVerticalFonts.demo_with_font(out, _BUNDLED_TTF)
    _assert_is_pdf(out)
    with PDDocument.load(str(out)) as doc:
        assert doc.get_number_of_pages() == 1


def test_demo_with_font_accepts_str_output(tmp_path: Path) -> None:
    if not _BUNDLED_TTF.is_file():
        pytest.skip(f"bundled font absent: {_BUNDLED_TTF}")
    out = tmp_path / "vertical-str.pdf"
    EmbeddedVerticalFonts.demo_with_font(str(out), _BUNDLED_TTF)
    _assert_is_pdf(out)
