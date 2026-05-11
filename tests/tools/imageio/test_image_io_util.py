"""Tests for the imageio codec helpers."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.tools.imageio.image_io_util import ImageIOUtil
from pypdfbox.tools.imageio.jpeg_util import JPEGUtil
from pypdfbox.tools.imageio.meta_util import MetaUtil
from pypdfbox.tools.imageio.tiff_util import TIFFUtil


def _solid_image() -> Image.Image:
    return Image.new("RGB", (8, 8), (255, 0, 0))


def test_image_io_util_write_png_to_path(tmp_path: Path) -> None:
    out = tmp_path / "out.png"
    ok = ImageIOUtil.write_image(_solid_image(), out, 96)
    assert ok
    assert out.exists() and out.stat().st_size > 0


def test_image_io_util_write_jpg_to_stream() -> None:
    buf = io.BytesIO()
    ok = ImageIOUtil.write_image(_solid_image(), buf, "jpg")
    assert ok
    assert buf.getvalue().startswith(b"\xff\xd8")  # JPEG SOI


def test_image_io_util_get_writer_format_names() -> None:
    formats = ImageIOUtil.get_writer_format_names()
    assert "png" in formats
    assert "jpg" in formats
    assert "tiff" in formats


def test_image_io_util_has_icc_profile_false_for_plain() -> None:
    assert not ImageIOUtil.has_icc_profile(_solid_image())


def test_image_io_util_set_dpi() -> None:
    meta: dict = {}
    ImageIOUtil.set_dpi(meta, 200, "PNG")
    assert "Dimension" in meta


def test_image_io_util_get_as_deflated_bytes() -> None:
    blob = ImageIOUtil.get_as_deflated_bytes(b"x" * 100)
    assert isinstance(blob, bytes)
    assert blob != b"x" * 100


def test_jpeg_util_update_metadata_on_pil() -> None:
    img = _solid_image()
    JPEGUtil.update_metadata(img, 144)
    assert img.info.get("dpi") == (144, 144)


def test_jpeg_util_update_metadata_on_dict() -> None:
    meta: dict = {}
    JPEGUtil.update_metadata(meta, 144)
    assert meta["Xdensity"] == "144"
    assert meta["Ydensity"] == "144"
    assert meta["resUnits"] == "1"


def test_tiff_util_set_compression_type_bitonal() -> None:
    bitonal = Image.new("1", (4, 4), 1)
    param: dict = {}
    TIFFUtil.set_compression_type(param, bitonal)
    assert param["compressionType"] == "CCITT T.6"


def test_tiff_util_set_compression_type_color() -> None:
    param: dict = {}
    TIFFUtil.set_compression_type(param, _solid_image())
    assert param["compressionType"] == "LZW"


def test_tiff_util_update_metadata_dict() -> None:
    meta: dict = {}
    TIFFUtil.update_metadata(meta, _solid_image(), 300)
    assert "TIFFIFD" in meta
    assert 282 in meta["TIFFIFD"]  # XResolution


def test_meta_util_class_attributes() -> None:
    assert MetaUtil.STANDARD_METADATA_FORMAT == "javax_imageio_1.0"
    assert MetaUtil.JPEG_NATIVE_FORMAT == "javax_imageio_jpeg_image_1.0"
    assert MetaUtil.SUN_TIFF_FORMAT.endswith("tiff_image_1.0")


def test_static_constructors_rejected() -> None:
    with pytest.raises(TypeError):
        ImageIOUtil()
    with pytest.raises(TypeError):
        JPEGUtil()
    with pytest.raises(TypeError):
        TIFFUtil()
    with pytest.raises(TypeError):
        MetaUtil()
