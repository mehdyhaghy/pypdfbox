"""Wave-1332 coverage-boost tests for ``pypdfbox.tools.imageio.tiff_util``.

Pre-wave coverage was 88% with the 6 missing lines being:

* 40-41  — the ``AttributeError`` swallow inside ``set_compression_type``;
* 54-55  — the ``meta_format is None`` short-circuit in ``update_metadata``;
* 71-72  — the ``.info["dpi"]`` branch for objects that expose ``.info``.

The tests below drive each path explicitly so the module reaches >=95%.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.tools.imageio.tiff_util import TIFFUtil

# ---------- ctor guard -----------------------------------------------------


def test_static_ctor_raises_type_error() -> None:
    with pytest.raises(TypeError):
        TIFFUtil()


# ---------- set_compression_type ------------------------------------------


def test_set_compression_type_bitonal() -> None:
    class _Img:
        mode = "1"

    param: dict[str, object] = {}
    TIFFUtil.set_compression_type(param, _Img())
    assert param["compressionType"] == "CCITT T.6"


def test_set_compression_type_rgb_defaults_to_lzw() -> None:
    class _Img:
        mode = "RGB"

    param: dict[str, object] = {}
    TIFFUtil.set_compression_type(param, _Img())
    assert param["compressionType"] == "LZW"


def test_set_compression_type_swallows_attribute_error() -> None:
    """An object whose ``mode == "1"`` comparison itself raises is swallowed.

    ``getattr(image, "mode", None)`` itself never raises (it has a
    default), so the ``except AttributeError`` only triggers when the
    *comparison* fires it. A ``mode`` descriptor that returns an object
    whose ``__eq__`` raises ``AttributeError`` exercises that branch.
    """

    class _RaisingEq:
        def __eq__(self, other: object) -> bool:
            raise AttributeError("kaboom")

        def __hash__(self) -> int:  # pragma: no cover - required for set membership
            return 0

    class _Img:
        mode = _RaisingEq()

    param: dict[str, object] = {}
    TIFFUtil.set_compression_type(param, _Img())
    assert param["compressionType"] == "LZW"


def test_set_compression_type_object_without_mode_defaults_to_lzw() -> None:
    param: dict[str, object] = {}
    TIFFUtil.set_compression_type(param, object())
    assert param["compressionType"] == "LZW"


# ---------- update_metadata: dict path ------------------------------------


def test_update_metadata_dict_populates_ifd() -> None:
    class _Img:
        mode = "RGB"
        size = (10, 20)
        height = 20

    meta: dict[str, object] = {}
    TIFFUtil.update_metadata(meta, _Img(), dpi=300)
    ifd = meta["TIFFIFD"]  # type: ignore[index]
    assert ifd[282]["value"] == "300/1"
    assert ifd[283]["value"] == "300/1"
    assert ifd[296]["value"] == 2
    assert ifd[278]["value"] == 20
    assert ifd[305]["value"] == "PDFBOX"
    # Non-bitonal: no 262 entry.
    assert 262 not in ifd


def test_update_metadata_dict_bitonal_adds_photometric() -> None:
    class _Img:
        mode = "1"
        size = (4, 4)
        height = 4

    meta: dict[str, object] = {}
    TIFFUtil.update_metadata(meta, _Img(), dpi=72)
    ifd = meta["TIFFIFD"]  # type: ignore[index]
    assert ifd[262]["value"] == 0


def test_update_metadata_dict_falls_back_to_size_height() -> None:
    """When ``height`` is missing, ``size[1]`` is used (default 1 if absent)."""

    class _Img:
        mode = "RGB"
        size = (8, 16)

    meta: dict[str, object] = {}
    TIFFUtil.update_metadata(meta, _Img(), dpi=72)
    assert meta["TIFFIFD"][278]["value"] == 16  # type: ignore[index]


# ---------- update_metadata: native_metadata_format_name path -------------


def test_update_metadata_no_format_short_circuits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When metadata is not a dict and has no ``native_metadata_format_name``."""

    class _Bare:
        pass

    with caplog.at_level(logging.DEBUG, logger="pypdfbox.tools.imageio.tiff_util"):
        TIFFUtil.update_metadata(_Bare(), object(), dpi=100)
    # No exception; debug-log emitted (best-effort assertion — debug is enabled).
    assert any("data format" in rec.message for rec in caplog.records)


def test_update_metadata_with_info_dict_sets_dpi() -> None:
    """A Pillow-style object with ``.info`` records the dpi tuple."""

    class _PillowLike:
        native_metadata_format_name = "javax_imageio_jpeg_image_1.0"
        info: dict[str, object] = {}

    pil = _PillowLike()
    TIFFUtil.update_metadata(pil, object(), dpi=144)
    assert pil.info["dpi"] == (144, 144)


def test_update_metadata_with_non_dict_info_skips_dpi() -> None:
    """A ``.info`` attribute that isn't a dict is left untouched."""

    class _Weird:
        native_metadata_format_name = "javax_imageio_jpeg_image_1.0"
        info = "not a dict"

    weird = _Weird()
    TIFFUtil.update_metadata(weird, object(), dpi=144)
    assert weird.info == "not a dict"


# ---------- field-builder helpers ------------------------------------------


def test_create_short_field_shape() -> None:
    f = TIFFUtil.create_short_field(296, "ResolutionUnit", 2)
    assert f == {"number": 296, "name": "ResolutionUnit", "type": "short", "value": 2}


def test_create_ascii_field_shape() -> None:
    f = TIFFUtil.create_ascii_field(305, "Software", "PDFBOX")
    assert f["type"] == "ascii" and f["value"] == "PDFBOX"


def test_create_long_field_shape() -> None:
    f = TIFFUtil.create_long_field(278, "RowsPerStrip", 256)
    assert f["type"] == "long" and f["value"] == 256


def test_create_rational_field_shape() -> None:
    f = TIFFUtil.create_rational_field(282, "XResolution", 300, 1)
    assert f["type"] == "rational" and f["value"] == "300/1"
