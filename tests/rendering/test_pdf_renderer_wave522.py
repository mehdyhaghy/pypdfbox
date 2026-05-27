from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (6, 6)) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
    renderer._draw.setantialias(True)  # noqa: SLF001
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw  # noqa: SLF001
    if draw is not None:
        draw.flush()


def _soft_mask(subtype: str, stream_data: bytes) -> PDSoftMask:
    stream = COSStream()
    stream.set_raw_data(stream_data)
    mask = PDSoftMask()
    mask.set_subtype(COSName.get_pdf_name(subtype))
    mask.set_group(stream)
    return mask


def test_soft_mask_luminosity_applies_transfer_lookup(monkeypatch: Any) -> None:
    doc, renderer = _prepared_renderer((2, 2))
    try:
        # Mask group paints grey 0.25 over its full bbox so coverage is 1
        # everywhere: luminance ~= 64, then the /TR lookup (255 - value) maps
        # 64 -> 191. (Wave 1434: the mask now needs full coverage to reach a
        # non-zero pre-transfer value — an uncovered region masks to 0, since
        # the luminosity is modulated by the group's coverage. The transfer
        # function is still applied to the modulated value, which this asserts.)
        mask = _soft_mask(
            "Luminosity", b"0.25 0.25 0.25 rg\n0 0 2 2 re\nf\n"
        )
        backdrop = COSArray()
        backdrop.add(COSFloat(0.25))
        mask.set_backdrop_color(backdrop)
        transfer = COSName.get_pdf_name("TRCustom")
        mask.set_transfer_function(transfer)
        seen: list[object] = []

        def _lookup(tr: object) -> list[int]:
            seen.append(tr)
            return [255 - value for value in range(256)]

        monkeypatch.setattr(PDFRenderer, "_build_transfer_lookup", staticmethod(_lookup))

        alpha = renderer._render_soft_mask_alpha(mask, (2, 2))  # noqa: SLF001

        assert alpha is not None
        assert seen == [transfer]
        # 0.25 grey -> luminance 64; transfer 255 - 64 = 191 (+/- 1 rounding).
        assert all(
            abs(alpha.getpixel((x, y)) - 191) <= 1
            for x in range(2)
            for y in range(2)
        )
    finally:
        _finish(renderer)
        doc.close()


def test_double_quote_text_operator_sets_spacing_moves_line_and_shows(
    monkeypatch: Any,
) -> None:
    shown: list[bytes] = []
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_leading = 4.0  # noqa: SLF001
        renderer._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 3.0, 9.0)  # noqa: SLF001
        renderer._gs.text_line_matrix = renderer._gs.text_matrix  # noqa: SLF001
        monkeypatch.setattr(renderer, "_show_string", lambda data: shown.append(data))

        renderer.process_operator(
            '"',
            [COSFloat(2.5), COSFloat(1.5), COSString(b"line")],
        )

        assert shown == [b"line"]
        assert renderer._gs.text_wordspace == 2.5  # noqa: SLF001
        assert renderer._gs.text_charspace == 1.5  # noqa: SLF001
        assert renderer._gs.text_matrix[4:] == (3.0, 5.0)  # noqa: SLF001
        assert renderer._gs.text_line_matrix[4:] == (3.0, 5.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_show_text_line_with_spacing_ignores_short_operands(
    monkeypatch: Any,
) -> None:
    shown: list[bytes] = []
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_wordspace = 8.0  # noqa: SLF001
        renderer._gs.text_charspace = 9.0  # noqa: SLF001
        renderer._gs.text_leading = 3.0  # noqa: SLF001
        renderer._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 1.0, 2.0)  # noqa: SLF001
        renderer._gs.text_line_matrix = renderer._gs.text_matrix  # noqa: SLF001
        monkeypatch.setattr(renderer, "_show_string", lambda data: shown.append(data))

        renderer.process_operator('"', [COSFloat(1.0), COSFloat(2.0)])

        assert shown == []
        assert renderer._gs.text_wordspace == 8.0  # noqa: SLF001
        assert renderer._gs.text_charspace == 9.0  # noqa: SLF001
        assert renderer._gs.text_matrix[4:] == (1.0, 2.0)  # noqa: SLF001
        assert renderer._gs.text_line_matrix[4:] == (1.0, 2.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_path_construction_ignores_segments_without_current_subpath() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer.process_operator("l", [COSFloat(1.0), COSFloat(1.0)])
        renderer.process_operator(
            "c",
            [
                COSFloat(1.0),
                COSFloat(2.0),
                COSFloat(3.0),
                COSFloat(4.0),
                COSFloat(5.0),
                COSFloat(6.0),
            ],
        )
        renderer.process_operator(
            "v",
            [COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)],
        )
        renderer.process_operator(
            "y",
            [COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)],
        )
        renderer.process_operator("h", [])

        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001
        assert renderer._current_point == (0.0, 0.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_fill_mask_with_rgb_noops_without_live_canvas() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._draw = None  # noqa: SLF001
        before = renderer._image.copy()  # noqa: SLF001

        renderer._fill_mask_with_rgb(  # noqa: SLF001
            Image.new("L", (6, 6), 255),
            (10, 20, 30),
        )

        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()
