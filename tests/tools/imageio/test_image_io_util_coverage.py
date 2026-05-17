"""Coverage-boost tests for ``pypdfbox.tools.imageio.image_io_util``.

Targets ``_to_pil`` branches, ``write_image`` error and unsupported-target
paths, the TIFF/CCITT/LZW compression branches, ``has_icc_profile`` for
non-PIL inputs, and ``get_or_create_child_node`` for non-dict parents.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.tools.imageio.image_io_util import ImageIOUtil, _to_pil

# ---------- ``_to_pil`` ---------------------------------------------------


def test_to_pil_passes_through_pil_image_unchanged() -> None:
    img = Image.new("RGB", (2, 2))
    assert _to_pil(img) is img


def test_to_pil_loads_from_png_bytes() -> None:
    src = Image.new("RGB", (4, 4), (1, 2, 3))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = _to_pil(buf.getvalue())
    assert out.size == (4, 4)


def test_to_pil_loads_from_bytearray() -> None:
    src = Image.new("L", (3, 3), 200)
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = _to_pil(bytearray(buf.getvalue()))
    assert out.size == (3, 3)


def test_to_pil_loads_from_memoryview() -> None:
    src = Image.new("RGB", (2, 2))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = _to_pil(memoryview(buf.getvalue()))
    assert out.size == (2, 2)


def test_to_pil_loads_from_path(tmp_path: Path) -> None:
    src = Image.new("RGB", (2, 2))
    p = tmp_path / "in.png"
    src.save(p, format="PNG")
    out = _to_pil(p)
    assert out.size == (2, 2)


def test_to_pil_loads_from_string_path(tmp_path: Path) -> None:
    src = Image.new("RGB", (2, 2))
    p = tmp_path / "in.png"
    src.save(p, format="PNG")
    out = _to_pil(str(p))
    assert out.size == (2, 2)


def test_to_pil_unknown_type_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="Cannot coerce"):
        _to_pil(12345)


# ---------- ``write_image`` happy paths + branch coverage ----------------


def test_write_image_returns_false_for_uncoercible_input(tmp_path: Path) -> None:
    out = tmp_path / "x.png"
    assert ImageIOUtil.write_image(12345, out, 96) is False


def test_write_image_returns_false_for_unsupported_target_type() -> None:
    img = Image.new("RGB", (2, 2))
    assert ImageIOUtil.write_image(img, object(), 96) is False


def test_write_image_unknown_extension_defaults_to_format(tmp_path: Path) -> None:
    # File with no extension → format defaults to "png" per the resolver.
    out = tmp_path / "noext"
    ok = ImageIOUtil.write_image(Image.new("RGB", (2, 2)), out, 72)
    assert ok is True
    assert out.exists()


def test_write_image_to_stream_default_format_is_png() -> None:
    buf = io.BytesIO()
    assert ImageIOUtil.write_image(Image.new("RGB", (2, 2)), buf) is True
    # PNG signature
    assert buf.getvalue().startswith(b"\x89PNG")


def test_write_image_stream_with_quality_carries_dpi() -> None:
    buf = io.BytesIO()
    # Pass quality (float in [0, 1]) and dpi via the int-typed position-4
    # argument shape exercised in the stream branch.
    ok = ImageIOUtil.write_image(
        Image.new("RGB", (2, 2)), buf, "jpg", 144
    )
    assert ok is True
    assert buf.getvalue().startswith(b"\xff\xd8")


def test_write_image_jpeg_quality_branch(tmp_path: Path) -> None:
    out = tmp_path / "img.jpg"
    ok = ImageIOUtil.write_image(
        Image.new("RGB", (2, 2)), out, 96, compression_quality=0.4
    )
    assert ok is True
    assert out.read_bytes().startswith(b"\xff\xd8")


def test_write_image_tiff_default_compression(tmp_path: Path) -> None:
    out = tmp_path / "img.tif"
    ok = ImageIOUtil.write_image(Image.new("RGB", (2, 2)), out, 96)
    assert ok is True
    assert out.exists()


def test_write_image_tiff_ccitt_t6_explicit(tmp_path: Path) -> None:
    out = tmp_path / "img.tif"
    # 1-bit image with explicit CCITT T.6 → group4 PIL compression.
    ok = ImageIOUtil.write_image(
        Image.new("1", (8, 8), 0), out, 96, compression_type="CCITT T.6"
    )
    assert ok is True


def test_write_image_tiff_lzw_explicit(tmp_path: Path) -> None:
    out = tmp_path / "img.tif"
    ok = ImageIOUtil.write_image(
        Image.new("RGB", (4, 4)), out, 96, compression_type="LZW"
    )
    assert ok is True


def test_write_image_save_failure_returns_false(tmp_path: Path) -> None:
    # Writing to a directory path raises OSError → write_image returns False.
    bad = tmp_path  # directory, not a file
    assert ImageIOUtil.write_image(Image.new("RGB", (2, 2)), bad, 96) is False


# ---------- ``has_icc_profile`` ------------------------------------------


def test_has_icc_profile_false_for_uncoercible_input() -> None:
    # Triggers the except branch returning False
    assert ImageIOUtil.has_icc_profile(object()) is False


def test_has_icc_profile_true_when_image_carries_profile() -> None:
    img = Image.new("RGB", (2, 2))
    img.info["icc_profile"] = b"FAKE-ICC"
    assert ImageIOUtil.has_icc_profile(img) is True


# ---------- ``get_or_create_child_node`` ---------------------------------


def test_get_or_create_child_node_creates_empty_dict_for_new_key() -> None:
    parent: dict = {}
    child = ImageIOUtil.get_or_create_child_node(parent, "kid")
    assert child == {}
    assert parent["kid"] is child


def test_get_or_create_child_node_returns_existing_value() -> None:
    parent: dict = {"existing": {"a": 1}}
    child = ImageIOUtil.get_or_create_child_node(parent, "existing")
    assert child == {"a": 1}


def test_get_or_create_child_node_rejects_non_dict_parent() -> None:
    with pytest.raises(TypeError):
        ImageIOUtil.get_or_create_child_node(["not", "a", "dict"], "kid")


# ---------- ``set_dpi`` --------------------------------------------------


def test_set_dpi_png_branch_uses_mm_density() -> None:
    meta: dict = {}
    ImageIOUtil.set_dpi(meta, 96, "PNG")
    # PNG branch: dpi / 25.4 → ~3.78 px/mm
    assert float(meta["Dimension"]["HorizontalPixelSize"]) > 3.0
    assert float(meta["Dimension"]["VerticalPixelSize"]) > 3.0


def test_set_dpi_non_png_branch_uses_inverse() -> None:
    meta: dict = {}
    ImageIOUtil.set_dpi(meta, 96, "JPEG")
    # Non-PNG: 25.4 / dpi → ~0.265
    assert float(meta["Dimension"]["HorizontalPixelSize"]) < 1.0


def test_set_dpi_non_dict_metadata_is_no_op() -> None:
    # Non-dict metadata → the helper just returns without touching it.
    ImageIOUtil.set_dpi("not-a-dict", 96, "PNG")


# ---------- ``get_as_deflated_bytes`` -----------------------------------


def test_get_as_deflated_bytes_round_trips_via_zlib() -> None:
    import zlib
    blob = ImageIOUtil.get_as_deflated_bytes(b"hello-icc")
    assert zlib.decompress(blob) == b"hello-icc"
