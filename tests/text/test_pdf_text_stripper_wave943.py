from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def test_wave943_process_page_restores_active_text_state_when_extraction_raises() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (boom) Tj ET")

    class FailingStripper(PDFTextStripper):
        def _extract_positions(self, body: bytes) -> list[TextPosition]:
            assert body
            assert self._active_page is page  # noqa: SLF001
            self._active_cmap = cast(Any, object())  # noqa: SLF001
            self._active_font = cast(Any, object())  # noqa: SLF001
            self._active_avg_advance = 12.0  # noqa: SLF001
            raise RuntimeError("parser failed")

    stripper = FailingStripper()
    stripper._active_page = cast(Any, object())  # noqa: SLF001
    stripper._cmap_cache = {"old": cast(Any, object())}  # noqa: SLF001
    stripper._font_cache = {"old": cast(Any, object())}  # noqa: SLF001

    try:
        with pytest.raises(RuntimeError, match="parser failed"):
            stripper.process_page(page)

        assert stripper._active_page is None  # noqa: SLF001
        assert stripper._active_cmap is None  # noqa: SLF001
        assert stripper._active_font is None  # noqa: SLF001
        assert stripper._active_avg_advance is None  # noqa: SLF001
        assert stripper._cmap_cache == {}  # noqa: SLF001
        assert stripper._font_cache == {}  # noqa: SLF001
    finally:
        doc.close()


def test_wave943_bead_partition_emits_residual_bucket_after_valid_beads() -> None:
    stripper = PDFTextStripper()
    stripper.set_line_separator("|")
    stripper._active_page = cast(  # noqa: SLF001
        Any,
        SimpleNamespace(
            get_thread_beads=lambda: [
                SimpleNamespace(get_rectangle=lambda: PDRectangle(0.0, 0.0, 10.0, 10.0)),
                SimpleNamespace(get_rectangle=lambda: PDRectangle(20.0, 0.0, 30.0, 10.0)),
            ]
        ),
    )
    first = TextPosition(text="first", x=5.0, y=5.0, font_size=10.0)
    residual = TextPosition(text="outside", x=15.0, y=5.0, font_size=10.0)
    second = TextPosition(text="second", x=25.0, y=5.0, font_size=10.0)

    assert stripper._partition_by_beads([first, residual, second]) == [  # noqa: SLF001
        [first],
        [second],
        [residual],
    ]
    assert stripper._format_positions([first, residual, second]) == "first|second|outside"  # noqa: SLF001
