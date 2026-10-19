"""Hand-written tests for ``get_hinted_normalized_path`` (PDFBOX-3293) on
the pdmodel font classes. ``TrueTypeFont.get_hinted_path`` is stubbed:
the GlyphHinter interpreter itself lands in a later wave."""

from pathlib import Path
from typing import Any

import pytest
from fontTools.pens.recordingPen import RecordingPen

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font import PDTrueTypeFont, PDType0Font, PDType1Font
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_vector_font import PDVectorFont

_LIBERATION = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture
def stub_hinter(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Replace the hinting entry point with one returning a 2048-unit box
    (LiberationSans has unitsPerEm 2048), or None at ppem <= 8."""
    calls: list[tuple[int, int]] = []

    def _hinted(self: TrueTypeFont, gid: int, ppem: int) -> RecordingPen | None:
        calls.append((gid, ppem))
        if ppem <= 8:
            return None
        pen = RecordingPen()
        pen.moveTo((0, 0))
        pen.lineTo((2048, 0))
        pen.qCurveTo((2048, 1024), (1024, 2048))
        pen.closePath()
        return pen

    monkeypatch.setattr(TrueTypeFont, "get_hinted_path", _hinted)
    return calls


def test_true_type_hinted_path_is_normalized_to_1000(
    stub_hinter: list[tuple[int, int]],
) -> None:
    with PDDocument() as doc:
        font = PDTrueTypeFont.load(doc, _LIBERATION.read_bytes(), WinAnsiEncoding.INSTANCE)
        path = font.get_hinted_normalized_path(ord("H"), 16)
        assert path == [
            ("moveTo", ((0.0, 0.0),)),
            ("lineTo", ((1000.0, 0.0),)),
            ("qCurveTo", ((1000.0, 500.0), (500.0, 1000.0))),
            ("closePath", ()),
        ]
        assert stub_hinter == [(font.code_to_gid(ord("H")), 16)]
        # the hinter's None passes through
        assert font.get_hinted_normalized_path(ord("H"), 8) is None


def test_true_type_gid_zero_is_not_hinted(
    stub_hinter: list[tuple[int, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    with PDDocument() as doc:
        font = PDTrueTypeFont.load(doc, _LIBERATION.read_bytes(), WinAnsiEncoding.INSTANCE)
        monkeypatch.setattr(font, "code_to_gid", lambda code: 0)
        assert font.get_hinted_normalized_path(ord("H"), 16) is None
        assert stub_hinter == []


def test_non_embedded_true_type_is_not_hinted(stub_hinter: list[tuple[int, int]]) -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("TrueType"))
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font = PDTrueTypeFont(d)
    assert not font.is_embedded()
    assert font.get_hinted_normalized_path(ord("H"), 16) is None
    assert stub_hinter == []


def test_type0_hinted_path_uses_descendant_command_shape(
    stub_hinter: list[tuple[int, int]],
) -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _LIBERATION, embed_subset=False)
        gid = font.get_descendant_font().code_to_gid(43)
        path = font.get_hinted_normalized_path(43, 16)
        assert path is not None
        assert path[0] == ("moveto", 0.0, 0.0)
        assert path[1] == ("lineto", 1000.0, 0.0)
        assert path[2][0] == "curveto"
        assert path[2][-2:] == (500.0, 1000.0)
        assert path[-1] == ("closepath",)
        assert stub_hinter == [(gid, 16)]
        assert font.get_hinted_normalized_path(43, 8) is None


def test_type0_without_descendant_returns_none() -> None:
    font = PDType0Font.__new__(PDType0Font)
    font.get_descendant_font = lambda: None  # type: ignore[method-assign]
    assert font.get_hinted_normalized_path(1, 16) is None


def test_non_hinting_fonts_default_to_none() -> None:
    assert PDType1Font().get_hinted_normalized_path(ord("H"), 16) is None
    assert PDCIDFont.get_hinted_normalized_path(None, 1, 16) is None  # type: ignore[arg-type]


def test_protocol_default_is_not_a_structural_member() -> None:
    class _Minimal:
        def get_path(self, code: int) -> Any:
            return []

        def get_normalized_path(self, code: int) -> Any:
            return []

        def has_glyph(self, code: int) -> bool:
            return True

    assert isinstance(_Minimal(), PDVectorFont)
    assert PDVectorFont.get_hinted_normalized_path(_Minimal(), 1, 16) is None  # type: ignore[attr-defined]
