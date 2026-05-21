"""Wave 1337 coverage-boost tests for :mod:`pypdfbox.pdmodel.graphics.image.jpeg_factory`.

Targets the remaining branches around TypeError input validation, the
``P`` palette + 1-bit mode dispatch in ``get_color_image``, the
``BITMASK`` rejection in ``get_alpha_image``, and the module-level
``_retrieve_dimensions`` back-compat alias.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.color import (
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)
from pypdfbox.pdmodel.graphics.image import JPEGFactory
from pypdfbox.pdmodel.graphics.image.jpeg_factory import (
    _color_space_for_components,
    _pil_mode_to_components,
    _retrieve_dimensions,
    _split_alpha_for_smask,
)


def _rgb_jpeg_bytes(size: tuple[int, int] = (8, 8)) -> bytes:
    img = Image.new("RGB", size, color=(120, 80, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


# ---------- _color_space_for_components edge ----------


def test_color_space_for_components_unsupported_raises() -> None:
    """5+ component count → ValueError ("number of data elements not supported")."""
    with pytest.raises(ValueError, match="not supported"):
        _color_space_for_components(5)


def test_color_space_for_components_zero_raises() -> None:
    with pytest.raises(ValueError, match="not supported"):
        _color_space_for_components(0)


# ---------- _pil_mode_to_components branches ----------


def test_pil_mode_to_components_known_modes() -> None:
    assert _pil_mode_to_components("L") == 1
    assert _pil_mode_to_components("RGB") == 3
    assert _pil_mode_to_components("YCbCr") == 3
    assert _pil_mode_to_components("LAB") == 3
    assert _pil_mode_to_components("CMYK") == 4


def test_pil_mode_to_components_unknown_returns_zero() -> None:
    """Unknown modes return 0 so the caller can fall back."""
    assert _pil_mode_to_components("HSV") == 0
    assert _pil_mode_to_components("P") == 0


# ---------- _split_alpha_for_smask branches ----------


def test_split_alpha_for_smask_rgb_no_alpha() -> None:
    img = Image.new("RGB", (4, 4))
    color, alpha = _split_alpha_for_smask(img)
    assert color is img  # opaque image passes through unchanged
    assert alpha is None


def test_split_alpha_for_smask_rgba_split() -> None:
    img = Image.new("RGBA", (4, 4), color=(10, 20, 30, 128))
    color, alpha = _split_alpha_for_smask(img)
    assert color.mode == "RGB"
    assert alpha is not None
    assert alpha.mode == "L"


def test_split_alpha_for_smask_la_split() -> None:
    img = Image.new("LA", (4, 4), color=(50, 200))
    color, alpha = _split_alpha_for_smask(img)
    assert color.mode == "L"
    assert alpha is not None


def test_split_alpha_for_smask_pa_split() -> None:
    img = Image.new("PA", (4, 4))
    img.putpalette([0, 0, 0, 255, 255, 255] * 128)
    color, alpha = _split_alpha_for_smask(img)
    assert color.mode == "RGB"
    assert alpha is not None


def test_split_alpha_for_smask_p_with_transparency() -> None:
    img = Image.new("P", (4, 4))
    img.putpalette([0, 0, 0] * 256)
    img.info["transparency"] = bytes(range(256))
    color, alpha = _split_alpha_for_smask(img)
    assert color.mode == "RGB"
    assert alpha is not None


# ---------- get_alpha_image input-validation + BITMASK ----------


def test_get_alpha_image_rejects_non_pil() -> None:
    with pytest.raises(TypeError, match="must be a PIL"):
        JPEGFactory.get_alpha_image("not an image")  # type: ignore[arg-type]


def test_get_alpha_image_rejects_bitmask_transparency() -> None:
    """A 1-bit image with palette transparency must raise NotImplementedError —
    BITMASK transparency isn't a sensible JPEG input."""
    img = Image.new("1", (4, 4))
    img.info["transparency"] = b"\x00"
    with pytest.raises(NotImplementedError, match="BITMASK"):
        JPEGFactory.get_alpha_image(img)


def test_get_alpha_image_la_path() -> None:
    """The LA-mode arm returns the A channel."""
    img = Image.new("LA", (4, 4), color=(50, 128))
    alpha = JPEGFactory.get_alpha_image(img)
    assert alpha is not None
    assert alpha.mode == "L"


def test_get_alpha_image_pa_path() -> None:
    """The PA-mode arm converts to RGBA then extracts A."""
    img = Image.new("PA", (4, 4))
    img.putpalette([0, 0, 0, 255, 255, 255] * 128)
    alpha = JPEGFactory.get_alpha_image(img)
    assert alpha is not None


def test_get_alpha_image_p_with_transparency_path() -> None:
    img = Image.new("P", (4, 4))
    img.putpalette([0, 0, 0] * 256)
    img.info["transparency"] = bytes(range(256))
    alpha = JPEGFactory.get_alpha_image(img)
    assert alpha is not None


def test_get_alpha_image_p_without_transparency_returns_none() -> None:
    img = Image.new("P", (4, 4))
    img.putpalette([0, 0, 0] * 256)
    assert JPEGFactory.get_alpha_image(img) is None


# ---------- get_color_image input-validation + extra modes ----------


def test_get_color_image_rejects_non_pil() -> None:
    with pytest.raises(TypeError, match="must be a PIL"):
        JPEGFactory.get_color_image(42)  # type: ignore[arg-type]


def test_get_color_image_la_returns_l_channel() -> None:
    img = Image.new("LA", (4, 4), color=(50, 128))
    out = JPEGFactory.get_color_image(img)
    assert out.mode == "L"


def test_get_color_image_pa_returns_rgb() -> None:
    img = Image.new("PA", (4, 4))
    img.putpalette([0, 0, 0, 255, 255, 255] * 128)
    out = JPEGFactory.get_color_image(img)
    assert out.mode == "RGB"


def test_get_color_image_p_with_transparency_returns_rgb() -> None:
    img = Image.new("P", (4, 4))
    img.putpalette([0, 0, 0] * 256)
    img.info["transparency"] = bytes(range(256))
    out = JPEGFactory.get_color_image(img)
    assert out.mode == "RGB"


def test_get_color_image_p_without_transparency_returns_rgb() -> None:
    img = Image.new("P", (4, 4))
    img.putpalette([0, 0, 0] * 256)
    out = JPEGFactory.get_color_image(img)
    assert out.mode == "RGB"


def test_get_color_image_1_returns_l() -> None:
    """1-bit images get up-converted to L for JPEG encoding."""
    img = Image.new("1", (4, 4))
    out = JPEGFactory.get_color_image(img)
    assert out.mode == "L"


def test_get_color_image_unknown_falls_back_to_rgb() -> None:
    """An unfamiliar mode (e.g. HSV) gets best-effort converted to RGB."""
    img = Image.new("HSV", (4, 4), color=(128, 64, 200))
    out = JPEGFactory.get_color_image(img)
    assert out.mode == "RGB"


def test_get_color_image_cmyk_passes_through() -> None:
    img = Image.new("CMYK", (4, 4), color=(10, 20, 30, 40))
    out = JPEGFactory.get_color_image(img)
    assert out is img


def test_get_color_image_ycbcr_passes_through() -> None:
    img = Image.new("YCbCr", (4, 4))
    out = JPEGFactory.get_color_image(img)
    assert out is img


# ---------- get_color_space_from_awt input-validation ----------


def test_get_color_space_from_awt_rejects_non_pil() -> None:
    with pytest.raises(TypeError, match="must be a PIL"):
        JPEGFactory.get_color_space_from_awt("garbage")  # type: ignore[arg-type]


def test_get_color_space_from_awt_ycbcr_returns_rgb() -> None:
    img = Image.new("YCbCr", (4, 4))
    cs = JPEGFactory.get_color_space_from_awt(img)
    assert cs is PDDeviceRGB.INSTANCE


def test_get_color_space_from_awt_l_returns_gray() -> None:
    cs = JPEGFactory.get_color_space_from_awt(Image.new("L", (4, 4)))
    assert cs is PDDeviceGray.INSTANCE


def test_get_color_space_from_awt_cmyk() -> None:
    cs = JPEGFactory.get_color_space_from_awt(Image.new("CMYK", (4, 4)))
    assert cs is PDDeviceCMYK.INSTANCE


# ---------- encode_image_to_jpeg_stream input-validation ----------


def test_encode_image_to_jpeg_stream_rejects_non_pil() -> None:
    with pytest.raises(TypeError, match="must be a PIL"):
        JPEGFactory.encode_image_to_jpeg_stream(b"not a PIL image", 0.5, 72)  # type: ignore[arg-type]


# ---------- create_jpeg input-validation ----------


def test_create_jpeg_rejects_non_pil() -> None:
    with pytest.raises(TypeError, match="must be a PIL"):
        JPEGFactory.create_jpeg(None, 99, 0.7, 72)  # type: ignore[arg-type]


# ---------- module-level back-compat alias ----------


def test_module_level_retrieve_dimensions_alias() -> None:
    """The module-level ``_retrieve_dimensions`` is a bound reference to
    the classmethod retained for older waves' import-by-name."""
    data = _rgb_jpeg_bytes((12, 6))
    w, h, n = _retrieve_dimensions(data)
    assert (w, h, n) == (12, 6, 3)


# ---------- retrieve_dimensions fallback paths ----------


def test_retrieve_dimensions_unidentified_raises() -> None:
    """Garbage that PIL can't even sniff → ValueError."""
    with pytest.raises(ValueError, match="unreadable"):
        JPEGFactory.retrieve_dimensions(b"this is not a jpeg")


def test_get_num_components_from_image_metadata_attribute_error() -> None:
    """Mock a "reader" with no ``.mode`` to trigger the AttributeError
    fallback in ``get_num_components_from_image_metadata`` (lines
    286-287)."""

    class _NoModeReader:
        """A bogus reader with no .mode attribute — triggers AttributeError."""

        def __getattr__(self, item: str) -> object:
            raise AttributeError(item)

    result = JPEGFactory.get_num_components_from_image_metadata(_NoModeReader())
    assert result == 0


def test_retrieve_dimensions_mode_zero_components_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force ``_pil_mode_to_components`` to return 0 so
    ``retrieve_dimensions`` falls through to ``len(probe.getbands())``
    (lines 263 and 267)."""
    from pypdfbox.pdmodel.graphics.image import jpeg_factory as jf

    # Replace the helper to return 0 always.
    monkeypatch.setattr(jf, "_pil_mode_to_components", lambda mode: 0)

    data = _rgb_jpeg_bytes((10, 10))
    w, h, n = JPEGFactory.retrieve_dimensions(data)
    # PIL reports 3 bands for RGB JPEG; the fallback ``len(probe.getbands())``
    # returns 3.
    assert (w, h) == (10, 10)
    assert n == 3
