from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.text import PDFTextStripper, TextPosition


def test_wave690_resolve_bookmark_returns_none_for_page_outside_document() -> None:
    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    outside_page = PDPage()

    bookmark = SimpleNamespace(
        find_destination_page=lambda _document: outside_page.get_cos_object()
    )

    try:
        assert PDFTextStripper._resolve_bookmark_page(  # noqa: SLF001
            cast(Any, bookmark), doc
        ) is None
    finally:
        doc.close()


def test_wave690_cmap_and_font_lookup_swallow_malformed_resource_access() -> None:
    stripper = PDFTextStripper()
    stripper._active_page = cast(  # noqa: SLF001
        Any,
        SimpleNamespace(
            get_resources=lambda: (_ for _ in ()).throw(RuntimeError("bad resources"))
        ),
    )

    assert stripper._get_cmap_for_font("F0") is None  # noqa: SLF001
    assert stripper._get_font_for("F0") is None  # noqa: SLF001


def test_wave690_decode_show_text_falls_back_when_simple_font_decode_fails() -> None:
    class BadDecodeFont(PDType1Font):
        def decode(self, _data: bytes) -> str:
            raise RuntimeError("bad decode")

    stripper = PDFTextStripper()
    stripper._active_font = BadDecodeFont()  # noqa: SLF001

    assert stripper._decode_show_text(b"\xffA") == "\xffA"  # noqa: SLF001


def test_wave690_average_advance_returns_none_for_zero_width_font() -> None:
    class ZeroAverageFont(PDType1Font):
        def get_average_font_width(self) -> float:
            return 0.0

    assert PDFTextStripper._compute_avg_advance(  # noqa: SLF001
        ZeroAverageFont(), 12.0
    ) is None


def test_wave690_partition_by_beads_returns_empty_when_bead_lookup_raises() -> None:
    stripper = PDFTextStripper()
    stripper._active_page = cast(  # noqa: SLF001
        Any,
        SimpleNamespace(
            get_thread_beads=lambda: (_ for _ in ()).throw(RuntimeError("bad beads"))
        ),
    )

    assert stripper._partition_by_beads(  # noqa: SLF001
        [TextPosition(text="x", x=1.0, y=1.0, font_size=1.0)]
    ) == []
