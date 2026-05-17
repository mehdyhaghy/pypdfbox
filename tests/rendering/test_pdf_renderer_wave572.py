from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 5.0, height: float = 5.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (5, 5)) -> tuple[PDDocument, PDFRenderer]:
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


def test_paste_image_routes_active_blend_with_transformed_bbox_and_alpha(
    monkeypatch: Any,
) -> None:
    class _BlendMode:
        name = "Multiply"

    calls: list[tuple[Image.Image, Image.Image | None, tuple[int, int, int, int]]] = []
    doc, renderer = _prepared_renderer((6, 6))
    try:
        renderer._gs.blend_mode = _BlendMode()  # noqa: SLF001
        renderer._gs.ctm = (2.0, 0.0, 0.0, 3.0, 1.0, 1.0)  # noqa: SLF001

        def _capture_blend(
            flipped_rgb: Image.Image,
            alpha: Image.Image | None,
            bbox: tuple[int, int, int, int],
            clip_mask: Image.Image | None,
            blend_mode: object,
        ) -> None:
            assert clip_mask is None
            assert blend_mode is renderer._gs.blend_mode  # noqa: SLF001
            calls.append((flipped_rgb.copy(), alpha.copy() if alpha else None, bbox))

        monkeypatch.setattr(renderer, "_paste_image_with_blend", _capture_blend)

        source = Image.new("RGBA", (1, 2), (10, 20, 30, 40))
        source.putpixel((0, 1), (90, 80, 70, 160))
        renderer._paste_image(source)  # noqa: SLF001

        assert len(calls) == 1
        flipped_rgb, alpha, bbox = calls[0]
        assert bbox == (1, 1, 2, 3)
        assert flipped_rgb.size == (2, 3)
        top = flipped_rgb.getpixel((0, 0))
        bottom = flipped_rgb.getpixel((0, 2))
        assert top[0] > bottom[0]
        assert top[1] > bottom[1]
        assert top[2] > bottom[2]
        assert alpha is not None
        assert alpha.getpixel((0, 0)) > alpha.getpixel((0, 2))
    finally:
        _finish(renderer)
        doc.close()


def test_show_inline_image_returns_without_live_canvas_or_decoded_image(
    monkeypatch: Any,
) -> None:
    class _InlineImage:
        def to_pil_image(self) -> None:
            return None

        def get_cos_object(self) -> object:
            return object()

        def get_stream(self) -> bytes:
            return b""

    doc, renderer = _prepared_renderer()
    try:
        calls: list[object] = []
        monkeypatch.setattr(renderer, "_paste_image", lambda image: calls.append(image))

        renderer._draw = None  # noqa: SLF001
        renderer.show_inline_image(_InlineImage())
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(True)  # noqa: SLF001
        renderer.show_inline_image(_InlineImage())

        assert calls == []
    finally:
        _finish(renderer)
        doc.close()


def test_decode_image_xobject_returns_none_for_non_stream_cos_object() -> None:
    class _ImageXObject:
        def get_cos_object(self) -> object:
            return object()

    doc, renderer = _prepared_renderer()
    try:
        assert renderer._decode_image_xobject(_ImageXObject()) is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_code_to_gid_falls_back_to_unicode_cmap_when_font_methods_fail(
    caplog: Any,
) -> None:
    class _Font:
        def code_to_gid(self, code: int) -> int:
            assert code == 65
            raise RuntimeError("gid boom")

    class _CMap:
        def get_glyph_id(self, code: int) -> int:
            assert code == 65
            return 123

    class _TTF:
        def get_unicode_cmap_subtable(self) -> _CMap:
            return _CMap()

    caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")

    assert PDFRenderer._code_to_gid(_Font(), 65, _TTF()) == 123  # noqa: SLF001
    assert "code_to_gid failed for 65: gid boom" in caplog.text


def test_maybe_warn_standard14_only_logs_once(
    caplog: Any, monkeypatch: Any,
) -> None:
    """Wave 1305 — every Standard 14 name now has a bundled substitute
    (Liberation for the Latin branches, DejaVu Sans for Symbol /
    ZapfDingbats), so the placeholder branch is unreachable in normal
    installs. Force the "no substitute" path by patching
    :meth:`Standard14Fonts.get_substitute_ttf` so we can exercise the
    once-per-font de-dup contract."""
    from pypdfbox.pdmodel.font import standard14_fonts as s14  # noqa: PLC0415

    class _StubFont:
        def get_name(self) -> str:
            return "Helvetica"

    monkeypatch.setattr(s14.Standard14Fonts, "get_substitute_ttf",
                        classmethod(lambda cls, _name: None))

    doc, renderer = _prepared_renderer()
    try:
        stub_font = _StubFont()
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")

        # Placeholder branch fires once per font, never per glyph.
        renderer._maybe_warn_standard14(stub_font)  # noqa: SLF001
        renderer._maybe_warn_standard14(stub_font)  # noqa: SLF001
        assert caplog.text.count("Helvetica is a Standard 14 font") == 1
    finally:
        _finish(renderer)
        doc.close()


def test_maybe_warn_standard14_silent_when_substitute_available(
    caplog: Any,
) -> None:
    """All 14 canonical names resolve to a bundled substitute after
    Wave 1305 — none should trigger the placeholder log under default
    install conditions."""
    class _Font:
        def __init__(self, name: str) -> None:
            self._name = name

        def get_name(self) -> str:
            return self._name

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
        for name in ("Helvetica", "Symbol", "ZapfDingbats", "Courier"):
            renderer._maybe_warn_standard14(_Font(name))  # noqa: SLF001
            assert f"{name} is a Standard 14 font" not in caplog.text
    finally:
        _finish(renderer)
        doc.close()
