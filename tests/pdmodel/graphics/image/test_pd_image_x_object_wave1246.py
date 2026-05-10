"""Wave 1246 — tighten 1:1 parity for ``PDImageXObject``.

Covers the static factory dispatchers
(``create_from_byte_array`` / ``create_from_file`` /
``create_from_file_by_extension`` / ``create_from_file_by_content``),
the rendering-surface mirrors (``get_image`` / ``get_opaque_image`` /
``get_stencil_image`` / ``get_raw_image`` / ``get_raw_raster``) plus
the private ``_extract_matte`` / ``_apply_mask`` / ``_scale_image`` /
``_clamp_color`` helpers. These methods bring pypdfbox's
``PDImageXObject`` surface up to upstream-method-name parity for the
public/protected API.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import _detect_file_type
from pypdfbox.pdmodel.pd_document import PDDocument

# ---------- static factory dispatchers ----------


def _png_bytes(size: tuple[int, int] = (3, 4), color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes(
    size: tuple[int, int] = (5, 7),
    color: tuple[int, int, int] = (40, 60, 80),
) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _gif_bytes(size: tuple[int, int] = (3, 4)) -> bytes:
    image = Image.new("P", size, color=2)
    image.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0])
    buffer = io.BytesIO()
    image.save(buffer, format="GIF")
    return buffer.getvalue()


def _bmp_bytes(size: tuple[int, int] = (3, 4)) -> bytes:
    image = Image.new("RGB", size, color=(50, 60, 70))
    buffer = io.BytesIO()
    image.save(buffer, format="BMP")
    return buffer.getvalue()


def test_create_from_byte_array_detects_jpeg() -> None:
    document = PDDocument()
    image = PDImageXObject.create_from_byte_array(document, _jpeg_bytes(), "src.jpg")
    assert image.get_width() == 5
    assert image.get_height() == 7
    assert image.get_suffix() == "jpg"


def test_create_from_byte_array_detects_png() -> None:
    document = PDDocument()
    image = PDImageXObject.create_from_byte_array(document, _png_bytes(), "src.png")
    assert image.get_width() == 3
    assert image.get_height() == 4


def test_create_from_byte_array_detects_gif() -> None:
    document = PDDocument()
    image = PDImageXObject.create_from_byte_array(document, _gif_bytes(), "src.gif")
    assert image.get_width() == 3
    assert image.get_height() == 4


def test_create_from_byte_array_detects_bmp() -> None:
    document = PDDocument()
    image = PDImageXObject.create_from_byte_array(document, _bmp_bytes(), "src.bmp")
    assert image.get_width() == 3
    assert image.get_height() == 4


def test_create_from_byte_array_unsupported_raises_value_error() -> None:
    document = PDDocument()
    with pytest.raises(ValueError, match="Image type not supported"):
        PDImageXObject.create_from_byte_array(document, b"not-an-image", "stub.dat")


def test_create_from_byte_array_rejects_non_bytes() -> None:
    document = PDDocument()
    with pytest.raises(TypeError):
        PDImageXObject.create_from_byte_array(document, "string-not-bytes", "x.jpg")  # type: ignore[arg-type]


def test_create_from_byte_array_routes_custom_factory_for_png() -> None:
    document = PDDocument()
    captured: dict[str, object] = {}

    class _Custom:
        @staticmethod
        def create_from_byte_array(doc: PDDocument, data: bytes) -> PDImageXObject:
            captured["doc"] = doc
            captured["len"] = len(data)
            stream = COSStream()
            xobject = PDImageXObject(stream)
            xobject.set_width(1)
            xobject.set_height(1)
            return xobject

    image = PDImageXObject.create_from_byte_array(
        document, _png_bytes(), "src.png", _Custom()
    )
    assert image.get_width() == 1
    assert captured["doc"] is document
    assert captured["len"] == len(_png_bytes())


def test_create_from_file_by_extension_dispatches_jpeg(tmp_path: Path) -> None:
    file = tmp_path / "src.jpg"
    file.write_bytes(_jpeg_bytes())
    document = PDDocument()
    image = PDImageXObject.create_from_file_by_extension(file, document)
    assert image.get_width() == 5
    assert image.get_suffix() == "jpg"


def test_create_from_file_by_extension_dispatches_png(tmp_path: Path) -> None:
    file = tmp_path / "src.png"
    file.write_bytes(_png_bytes())
    document = PDDocument()
    image = PDImageXObject.create_from_file_by_extension(file, document)
    assert image.get_width() == 3


def test_create_from_file_by_extension_unknown_extension(tmp_path: Path) -> None:
    file = tmp_path / "noext"
    file.write_bytes(_png_bytes())
    document = PDDocument()
    with pytest.raises(ValueError, match="Image type not supported"):
        PDImageXObject.create_from_file_by_extension(file, document)


def test_create_from_file_dispatches_via_extension(tmp_path: Path) -> None:
    file = tmp_path / "src.png"
    file.write_bytes(_png_bytes())
    document = PDDocument()
    image = PDImageXObject.create_from_file(str(file), document)
    assert image.get_width() == 3


def test_create_from_file_by_content_uses_magic_bytes(tmp_path: Path) -> None:
    file = tmp_path / "mislabelled.dat"
    file.write_bytes(_png_bytes())
    document = PDDocument()
    image = PDImageXObject.create_from_file_by_content(file, document)
    assert image.get_width() == 3


def test_create_from_file_by_content_rejects_unknown(tmp_path: Path) -> None:
    file = tmp_path / "stub.dat"
    file.write_bytes(b"not-an-image")
    document = PDDocument()
    with pytest.raises(ValueError, match="Image type not supported"):
        PDImageXObject.create_from_file_by_content(file, document)


# ---------- file-type detection ----------


def test_detect_file_type_recognises_supported_formats() -> None:
    assert _detect_file_type(_jpeg_bytes()) == "JPEG"
    assert _detect_file_type(_png_bytes()) == "PNG"
    assert _detect_file_type(_gif_bytes()) == "GIF"
    assert _detect_file_type(_bmp_bytes()) == "BMP"
    assert _detect_file_type(b"II*\x00abcdefgh") == "TIFF"
    assert _detect_file_type(b"MM\x00*abcdefgh") == "TIFF"
    assert _detect_file_type(b"random-not-image") is None
    assert _detect_file_type(b"a") is None


# ---------- rendering surface ----------


def _gray_image(data: bytes, *, width: int, height: int, bpc: int = 8) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    image.set_color_space("DeviceGray")
    image.get_cos_object().set_raw_data(data)
    return image


def test_get_image_returns_pillow_image() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    rendered = image.get_image()
    assert rendered is not None
    assert rendered.size == (2, 1)


def test_get_image_applies_subsampling() -> None:
    image = _gray_image(bytes([0, 64, 128, 192]), width=4, height=1)
    rendered = image.get_image(subsampling=2)
    assert rendered is not None
    assert rendered.width == 2


def test_get_image_applies_region_crop() -> None:
    image = _gray_image(bytes([0, 64, 128, 192]), width=4, height=1)
    rendered = image.get_image(region=(1, 0, 2, 1))
    assert rendered is not None
    assert rendered.size == (2, 1)


def test_get_opaque_image_matches_get_image_when_no_masks() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    a = image.get_opaque_image()
    b = image.get_image()
    assert a is not None and b is not None
    assert a.tobytes() == b.tobytes()


def test_get_stencil_image_requires_stencil() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    with pytest.raises(ValueError, match="not a stencil"):
        image.get_stencil_image(paint=None)


def test_get_stencil_image_returns_pillow_when_stencil() -> None:
    image = PDImageXObject(COSStream())
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(1)
    image.set_image_mask(True)
    image.get_cos_object().set_raw_data(b"\x80")
    out = image.get_stencil_image(paint=None)
    assert out is not None
    assert out.size == (2, 1)


def test_get_raw_image_falls_back_to_pil_decode() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    raw = image.get_raw_image()
    assert raw is not None
    assert raw.size == (2, 1)


def test_get_raw_raster_returns_decoded_bytes() -> None:
    image = _gray_image(bytes([0, 64, 128, 192]), width=4, height=1)
    raw = image.get_raw_raster()
    assert raw == bytes([0, 64, 128, 192])


# ---------- private helpers ----------


def test_clamp_color_clamps_to_byte_range() -> None:
    assert PDImageXObject.clamp_color(-10) == 0
    assert PDImageXObject.clamp_color(0) == 0
    assert PDImageXObject.clamp_color(127) == 127
    assert PDImageXObject.clamp_color(255) == 255
    assert PDImageXObject.clamp_color(300) == 255


def test_init_jpx_values_is_a_no_op_for_non_jpx_image() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    assert image.init_jpx_values() is None


def test_extract_matte_returns_none_when_softmask_has_no_matte() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    image.set_color_space("DeviceRGB")
    soft_mask = _gray_image(bytes([0, 255]), width=2, height=1)
    assert image.extract_matte(soft_mask) is None


def test_extract_matte_returns_none_when_matte_short_for_colorspace() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    image.set_color_space("DeviceRGB")  # 3 components
    soft_mask = _gray_image(bytes([0, 255]), width=2, height=1)
    arr = COSArray()
    arr.add(COSFloat(0.5))  # only 1 component, too short
    soft_mask.get_cos_object().set_item(COSName.get_pdf_name("Matte"), arr)
    assert image.extract_matte(soft_mask) is None


def test_extract_matte_passes_through_when_devicegray_to_rgb_unavailable() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    soft_mask = _gray_image(bytes([0, 255]), width=2, height=1)
    soft_mask.set_matte([0.5])
    matte = image.extract_matte(soft_mask)
    assert matte is not None
    assert len(matte) >= 1


def test_apply_mask_returns_image_when_mask_is_none() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    pil = Image.new("RGB", (2, 1), color=(10, 20, 30))
    out = image.apply_mask(pil, None, interpolate_mask=False, is_soft=False, matte=None)
    assert out is pil


def test_apply_mask_composes_alpha_for_soft_mask() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    rgb = Image.new("RGB", (2, 1), color=(10, 20, 30))
    mask = Image.new("L", (2, 1), color=128)
    out = image.apply_mask(rgb, mask, interpolate_mask=False, is_soft=True, matte=None)
    assert out.mode == "RGBA"
    pixel = out.getpixel((0, 0))
    assert isinstance(pixel, tuple)
    assert pixel[3] == 128  # alpha taken straight from mask


def test_apply_mask_inverts_alpha_for_stencil_mask() -> None:
    image = _gray_image(bytes([0, 255]), width=2, height=1)
    rgb = Image.new("RGB", (2, 1), color=(10, 20, 30))
    mask = Image.new("L", (2, 1), color=64)
    out = image.apply_mask(rgb, mask, interpolate_mask=False, is_soft=False, matte=None)
    assert out.mode == "RGBA"
    pixel = out.getpixel((0, 0))
    assert isinstance(pixel, tuple)
    assert pixel[3] == 255 - 64  # stencil masks invert alpha


def test_scale_image_resizes_with_pillow() -> None:
    src = Image.new("RGB", (4, 4), color=(10, 20, 30))
    out = PDImageXObject.scale_image(src, 8, 8, "RGBA", interpolate=True)
    assert out.size == (8, 8)
    assert out.mode == "RGBA"


def test_scale_image_nearest_when_no_interpolation() -> None:
    src = Image.new("L", (2, 2), color=128)
    out = PDImageXObject.scale_image(src, 1, 1, "L", interpolate=False)
    assert out.size == (1, 1)
    assert out.mode == "L"
