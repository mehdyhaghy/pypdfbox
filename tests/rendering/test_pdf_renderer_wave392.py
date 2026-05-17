from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 20.0, height: float = 20.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (20, 20)) -> tuple[PDDocument, PDFRenderer]:
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


def _minimal_image_xobject() -> PDImageXObject:
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_raw_data(bytes([0, 0, 0]))
    return PDImageXObject(stream)


def test_do_operator_handles_resource_and_image_decode_failures(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _RaisingResources:
        def get_x_object(self, _name: COSName) -> Any:
            raise RuntimeError("xobject boom")

    class _NoneResources:
        def get_x_object(self, _name: COSName) -> None:
            return None

    class _ImageResources:
        def get_x_object(self, _name: COSName) -> PDImageXObject:
            return _minimal_image_xobject()

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer.process_operator("Do", [])
        renderer.process_operator("Do", [COSFloat(1.0)])
        renderer._resources = None  # noqa: SLF001
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])

        renderer._resources = _RaisingResources()  # noqa: SLF001
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])
        assert "cannot resolve XObject Im0: xobject boom" in caplog.text

        renderer._resources = _NoneResources()  # noqa: SLF001
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])

        renderer._resources = _ImageResources()  # noqa: SLF001
        monkeypatch.setattr(
            renderer,
            "_decode_image_xobject",
            lambda _image: (_ for _ in ()).throw(RuntimeError("decode boom")),
        )
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])
        assert "cannot decode image: decode boom" in caplog.text

        monkeypatch.setattr(renderer, "_decode_image_xobject", lambda _image: None)
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])
    finally:
        _finish(renderer)
        doc.close()


def test_inline_image_operator_and_show_inline_image_defensive_paths(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _Op:
        def __init__(self, params: Any, data: bytes | None) -> None:
            self._params = params
            self._data = data

        def get_image_parameters(self) -> Any:
            return self._params

        def get_image_data(self) -> bytes | None:
            return self._data

    class _BadInlineCtor:
        def __init__(self, *_args: Any) -> None:
            raise RuntimeError("inline ctor boom")

    class _BadInlineImage:
        def to_pil_image(self) -> None:
            raise RuntimeError("helper boom")

        def get_cos_object(self) -> object:
            return object()

        def get_stream(self) -> bytes:
            return b"\x00"

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        renderer._op_inline_image(_Op(None, b"\x00"), [])  # noqa: SLF001
        renderer._op_inline_image(_Op(COSDictionary(), None), [])  # noqa: SLF001

        import pypdfbox.pdmodel.graphics.image.pd_inline_image as inline_mod

        monkeypatch.setattr(inline_mod, "PDInlineImage", _BadInlineCtor)
        renderer._op_inline_image(_Op(COSDictionary(), b"\x00"), [])  # noqa: SLF001
        assert "cannot construct inline image: inline ctor boom" in caplog.text

        renderer.show_inline_image(_BadInlineImage())
        assert "cannot decode inline image (helper): helper boom" in caplog.text
        assert "cannot decode inline image:" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_smask_application_backdrop_and_transfer_defensive_paths(
    caplog: Any,
) -> None:
    class _RaisingSMaskImage:
        def to_pil_image(self) -> Image.Image:
            raise RuntimeError("smask image boom")

    class _NoneSMaskImage:
        def to_pil_image(self) -> None:
            return None

    class _RGBSMaskImage:
        def to_pil_image(self) -> Image.Image:
            return Image.new("RGB", (1, 1), (255, 255, 255))

    class _Backdrop:
        def __init__(self, bc: Any) -> None:
            self._bc = bc

        def get_backdrop_color(self) -> Any:
            return self._bc

    class _BadArray:
        def to_float_array(self) -> list[float]:
            raise RuntimeError("bc boom")

    doc, renderer = _prepared_renderer()
    source = Image.new("RGB", (2, 2), (10, 20, 30))
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        assert renderer._apply_smask(source, _RaisingSMaskImage()) is source  # noqa: SLF001
        assert "cannot decode SMask: smask image boom" in caplog.text
        assert renderer._apply_smask(source, _NoneSMaskImage()) is source  # noqa: SLF001

        rgba = renderer._apply_smask(source, _RGBSMaskImage())  # noqa: SLF001
        assert rgba.mode == "RGBA"
        assert rgba.getpixel((1, 1))[3] == 255

        assert renderer._soft_mask_backdrop_rgb(_Backdrop(None)) == (0, 0, 0)  # noqa: SLF001
        assert renderer._soft_mask_backdrop_rgb(_Backdrop(_BadArray())) == (0, 0, 0)  # noqa: E501, SLF001

        gray = COSArray()
        gray.add(COSFloat(0.5))
        assert renderer._soft_mask_backdrop_rgb(_Backdrop(gray)) == (128, 128, 128)  # noqa: E501, SLF001

        cmyk = COSArray()
        for value in (0.0, 1.0, 0.0, 0.5):
            cmyk.add(COSFloat(value))
        assert renderer._soft_mask_backdrop_rgb(_Backdrop(cmyk)) == (128, 0, 128)  # noqa: E501, SLF001

        assert renderer._render_soft_mask_alpha(object(), (2, 2)) is None  # noqa: SLF001
        missing_group = PDSoftMask(COSDictionary())
        assert renderer._render_soft_mask_alpha(missing_group, (2, 2)) is None  # noqa: SLF001
        assert "soft mask /G missing or malformed" in caplog.text

        assert PDFRenderer._build_transfer_lookup(COSName.get_pdf_name("Identity")) is None  # noqa: E501, SLF001
        assert PDFRenderer._build_transfer_lookup(object()) is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_text_state_ops_spacing_arrays_and_font_resolution_cache() -> None:
    class _Resources:
        def __init__(self) -> None:
            self.calls = 0

        def get_font(self, _name: COSName) -> object:
            self.calls += 1
            return sentinel_font

    sentinel_font = object()
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_matrix = (2.0, 0.0, 0.0, 2.0, 5.0, 6.0)  # noqa: SLF001
        renderer.process_operator("BT", [])
        assert renderer._gs.text_matrix == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001

        renderer.process_operator("Tc", [COSFloat(2.0)])
        renderer.process_operator("Tw", [COSFloat(3.0)])
        renderer.process_operator("TL", [COSFloat(4.0)])
        renderer.process_operator("Tz", [COSFloat(50.0)])
        renderer.process_operator("Ts", [COSFloat(1.5)])
        assert renderer._gs.text_charspace == 2.0  # noqa: SLF001
        assert renderer._gs.text_wordspace == 3.0  # noqa: SLF001
        assert renderer._gs.text_leading == 4.0  # noqa: SLF001
        assert renderer._gs.text_horizontal_scaling == 50.0  # noqa: SLF001
        assert renderer._gs.text_rise == 1.5  # noqa: SLF001

        renderer.process_operator("Td", [COSFloat(10.0), COSFloat(5.0)])
        assert renderer._gs.text_matrix[4:] == (10.0, 5.0)  # noqa: SLF001
        renderer.process_operator("TD", [COSFloat(1.0), COSFloat(-7.0)])
        assert renderer._gs.text_leading == 7.0  # noqa: SLF001
        renderer.process_operator("Tm", [COSFloat(v) for v in (1, 2, 3, 4, 5, 6)])
        assert renderer._gs.text_line_matrix == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)  # noqa: E501, SLF001
        renderer.process_operator("T*", [])
        assert renderer._gs.text_matrix[5] == -22.0  # noqa: SLF001

        renderer.process_operator("Tj", [COSString(b"ignored-no-font")])
        renderer._gs.text_font_size = 10.0  # noqa: SLF001
        renderer._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
        renderer.process_operator("TJ", [COSString(b"not-array")])
        arr = COSArray()
        arr.add(COSFloat(200.0))
        renderer.process_operator("TJ", [arr])
        assert renderer._gs.text_matrix[4] == -1.0  # noqa: SLF001

        resources = _Resources()
        renderer._resources = resources  # noqa: SLF001
        font_name = COSName.get_pdf_name("F0")
        assert renderer._resolve_font(font_name) is sentinel_font  # noqa: SLF001
        assert renderer._resolve_font(font_name) is sentinel_font  # noqa: SLF001
        assert resources.calls == 1
    finally:
        _finish(renderer)
        doc.close()


def test_form_group_detection_and_knockout_restore_edge_branches() -> None:
    class _HelperRaises:
        def is_transparency_group(self) -> bool:
            raise RuntimeError("helper boom")

        def get_group(self) -> COSDictionary:
            group = COSDictionary()
            group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
            return group

    class _GroupRaises:
        def get_group(self) -> Any:
            raise RuntimeError("group boom")

    doc, renderer = _prepared_renderer()
    try:
        assert PDFRenderer._is_transparency_group(_HelperRaises()) is True  # noqa: SLF001
        assert PDFRenderer._is_transparency_group(_GroupRaises()) is False  # noqa: SLF001

        renderer._knockout_snapshot = None  # noqa: SLF001
        renderer._restore_knockout_snapshot()  # noqa: SLF001

        renderer._knockout_snapshot = Image.new("RGB", (20, 20), (1, 2, 3))  # noqa: SLF001
        renderer._image.paste((9, 9, 9), (0, 0, 20, 20))  # noqa: SLF001
        renderer._restore_knockout_snapshot()  # noqa: SLF001
        _finish(renderer)
        assert renderer._image.getpixel((5, 5)) == (1, 2, 3)  # noqa: SLF001
    finally:
        doc.close()
