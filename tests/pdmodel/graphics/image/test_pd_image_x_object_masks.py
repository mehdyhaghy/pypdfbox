"""Mask / SMask / Thumb accessor coverage for PDImageXObject.

Mirrors upstream ``org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject``
mask methods: ``getMask``, ``getColorKeyMask``, ``getSoftMask``, plus the
``isStencil``/``setStencil`` aliases from the ``PDImage`` interface, and
the ``/Thumb`` accessor on ``PDPage`` (the PDF spec puts thumbnails on
the page, not the image XObject).
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_page import PDPage


def _make_image() -> PDImageXObject:
    return PDImageXObject(COSStream())


# ---------- /SMask ----------


def test_get_soft_mask_returns_none_when_absent() -> None:
    image = _make_image()
    assert image.get_soft_mask() is None


def test_get_soft_mask_wraps_stream() -> None:
    image = _make_image()
    smask_stream = COSStream()
    smask_stream.set_int(COSName.get_pdf_name("Width"), 4)
    smask_stream.set_int(COSName.get_pdf_name("Height"), 4)
    image.get_cos_object().set_item(COSName.get_pdf_name("SMask"), smask_stream)

    fetched = image.get_soft_mask()
    assert isinstance(fetched, PDImageXObject)
    assert fetched.get_cos_object() is smask_stream
    assert fetched.get_width() == 4
    assert fetched.get_height() == 4


def test_set_soft_mask_round_trip() -> None:
    image = _make_image()
    smask = _make_image()
    smask.set_width(8)
    smask.set_height(8)
    image.set_soft_mask(smask)

    assert image.get_soft_mask() is not None
    assert image.get_soft_mask().get_cos_object() is smask.get_cos_object()


def test_set_soft_mask_none_clears_entry() -> None:
    image = _make_image()
    image.set_soft_mask(_make_image())
    image.set_soft_mask(None)
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("SMask")) is None
    assert image.get_soft_mask() is None


# ---------- /Mask explicit-mask stream ----------


def test_get_mask_returns_none_when_absent() -> None:
    image = _make_image()
    assert image.get_mask() is None
    assert image.get_color_key_mask() is None


def test_get_mask_wraps_stream() -> None:
    image = _make_image()
    mask_stream = COSStream()
    mask_stream.set_int(COSName.get_pdf_name("Width"), 16)
    mask_stream.set_int(COSName.get_pdf_name("Height"), 16)
    mask_stream.set_boolean(COSName.get_pdf_name("ImageMask"), True)
    image.get_cos_object().set_item(COSName.get_pdf_name("Mask"), mask_stream)

    fetched = image.get_mask()
    assert isinstance(fetched, PDImageXObject)
    assert fetched.get_cos_object() is mask_stream
    # Upstream parity: when /Mask is a stream the color-key accessor is None.
    assert image.get_color_key_mask() is None


def test_set_mask_round_trip() -> None:
    image = _make_image()
    mask = _make_image()
    mask.set_width(2)
    mask.set_height(2)
    mask.set_image_mask(True)
    image.set_mask(mask)

    fetched = image.get_mask()
    assert fetched is not None
    assert fetched.get_cos_object() is mask.get_cos_object()


def test_set_mask_none_clears_entry() -> None:
    image = _make_image()
    image.set_mask(_make_image())
    image.set_mask(None)
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Mask")) is None
    assert image.get_mask() is None


# ---------- /Mask color-key array ----------


def test_color_key_mask_round_trip() -> None:
    image = _make_image()
    image.set_color_key_mask([0, 16, 240, 255])

    assert image.get_color_key_mask() == [0, 16, 240, 255]
    # Upstream parity: when /Mask is a color-key array, get_mask() is None.
    assert image.get_mask() is None


def test_color_key_mask_reads_pre_built_array() -> None:
    image = _make_image()
    array = COSArray()
    for value in (1, 2, 3, 4):
        array.add(COSInteger.get(value))
    image.get_cos_object().set_item(COSName.get_pdf_name("Mask"), array)

    assert image.get_color_key_mask() == [1, 2, 3, 4]


def test_set_color_key_mask_none_clears_entry() -> None:
    image = _make_image()
    image.set_color_key_mask([0, 255])
    image.set_color_key_mask(None)
    assert image.get_color_key_mask() is None
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Mask")) is None


def test_explicit_mask_replaces_color_key_array() -> None:
    """Setting a stream /Mask must overwrite a previous color-key array."""
    image = _make_image()
    image.set_color_key_mask([0, 10])
    assert image.get_color_key_mask() == [0, 10]

    explicit = _make_image()
    explicit.set_image_mask(True)
    image.set_mask(explicit)

    # Color-key form is gone, explicit-mask form is now resolvable.
    assert image.get_color_key_mask() is None
    assert image.get_mask() is not None
    assert image.get_mask().get_cos_object() is explicit.get_cos_object()


# ---------- stencil aliases ----------


def test_is_stencil_defaults_false() -> None:
    image = _make_image()
    assert image.is_stencil() is False
    assert image.is_image_mask() is False


def test_set_stencil_true_writes_image_mask_entry() -> None:
    image = _make_image()
    image.set_stencil(True)
    assert image.is_stencil() is True
    # Upstream stencil aliases drive /ImageMask.
    assert image.is_image_mask() is True
    assert image.get_cos_object().get_boolean(COSName.get_pdf_name("ImageMask"), False) is True


def test_set_stencil_false_clears_image_mask() -> None:
    image = _make_image()
    image.set_stencil(True)
    image.set_stencil(False)
    assert image.is_stencil() is False
    assert image.is_image_mask() is False


# ---------- /SMaskInData ----------


def test_smask_in_data_default_is_zero() -> None:
    image = _make_image()
    assert image.get_smask_in_data() == 0


@pytest.mark.parametrize("value", [0, 1, 2])
def test_set_smask_in_data_round_trip(value: int) -> None:
    image = _make_image()
    image.set_smask_in_data(value)
    assert image.get_smask_in_data() == value
    assert (
        image.get_cos_object().get_int(COSName.get_pdf_name("SMaskInData"), -1)
        == value
    )


@pytest.mark.parametrize("value", [-1, 3, 100])
def test_set_smask_in_data_rejects_out_of_range(value: int) -> None:
    image = _make_image()
    with pytest.raises(ValueError):
        image.set_smask_in_data(value)


# ---------- /Thumb on PDPage ----------


def _make_page() -> PDPage:
    page_dict = COSDictionary()
    page_dict.set_name(COSName.TYPE, "Page")  # type: ignore[attr-defined]
    return PDPage(page_dict)


def test_page_thumb_default_is_none() -> None:
    page = _make_page()
    assert page.get_thumb() is None


def test_page_thumb_round_trip() -> None:
    page = _make_page()
    thumb = _make_image()
    thumb.set_width(64)
    thumb.set_height(64)
    page.set_thumb(thumb)

    fetched = page.get_thumb()
    assert isinstance(fetched, PDImageXObject)
    assert fetched.get_cos_object() is thumb.get_cos_object()
    assert fetched.get_width() == 64
    assert fetched.get_height() == 64


def test_page_thumb_none_removes_entry() -> None:
    page = _make_page()
    page.set_thumb(_make_image())
    page.set_thumb(None)
    assert page.get_thumb() is None
    assert page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Thumb")) is None
