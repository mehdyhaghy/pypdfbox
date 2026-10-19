"""``PDPageContentStream.set_font`` GSUB worker selection for Type 0 fonts.

``GlyphSubstitutionTable.get_gsub_data()`` picks the language from the
font's script list (upstream ``GlyphSubstitutionDataExtractor``), so an
embedded LiberationSans Type 0 font gets ``GsubWorkerForLatin`` rather
than ``DefaultGsubWorker`` (which logs "does not perform actual GSUB
substitutions"), DejaVuSans gets real ``liga`` substitutions, and a font
whose scripts match no language (Cousine: ``hebr`` only) gets no worker.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_latin import GsubWorkerForLatin
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

_REPO = Path(__file__).resolve().parents[2]
_LIBERATION = _REPO / "tests" / "fixtures" / "fontbox" / "ttf" / "LiberationSans-Regular.ttf"
_RESOURCES = _REPO / "pypdfbox" / "resources" / "ttf"


def _show(path: Path, text: str) -> tuple[bytes, dict]:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType0Font.load(doc, str(path))
        cs = PDPageContentStream(doc, page)
        try:
            cs.begin_text()
            cs.set_font(font, 12)
            workers = dict(cs._gsub_workers)
            cs.show_text(text)
            cs.end_text()
        finally:
            cs.close()
        return page.get_contents(), workers
    finally:
        doc.close()


def test_set_font_liberation_type0_logs_no_default_gsub_worker_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        _content, workers = _show(_LIBERATION, "Hello")
    assert not [r for r in caplog.records if "DefaultGsubWorker" in r.getMessage()]
    assert [type(w) for w in workers.values()] == [GsubWorkerForLatin]


def test_show_text_dejavu_type0_applies_liga() -> None:
    content, workers = _show(_RESOURCES / "DejaVuSans.ttf", "fi office")
    assert [type(w) for w in workers.values()] == [GsubWorkerForLatin]
    # fi -> 5042 (0x13B2); "office": o, ffi ligature 5044 (0x13B4), c, e.
    assert content == b"BT\n/F1 12 Tf\n<13B20003005213B400460048> Tj\nET\n"


def test_set_font_cousine_type0_has_no_gsub_worker() -> None:
    content, workers = _show(_RESOURCES / "Cousine-Regular.ttf", "fi")
    assert workers == {}
    assert content == b"BT\n/F1 12 Tf\n(\x00I\x00L) Tj\nET\n"
