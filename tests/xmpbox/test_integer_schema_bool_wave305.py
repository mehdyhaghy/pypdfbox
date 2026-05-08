from __future__ import annotations

import pytest

from pypdfbox.xmpbox import ExifSchema, PhotoshopSchema, TiffSchema, XMPMetadata


def test_tiff_integer_slots_reject_bool_values() -> None:
    schema = TiffSchema(XMPMetadata.create_xmp_metadata())

    with pytest.raises(TypeError):
        schema.set_image_width(True)

    schema.set_property(TiffSchema.IMAGE_WIDTH, True)
    assert schema.get_image_width() is None


def test_exif_integer_slots_reject_bool_values() -> None:
    schema = ExifSchema(XMPMetadata.create_xmp_metadata())

    with pytest.raises(TypeError):
        schema.set_color_space(False)

    schema.set_property(ExifSchema.COLOR_SPACE, False)
    assert schema.get_color_space() is None


def test_photoshop_integer_slots_reject_bool_values() -> None:
    schema = PhotoshopSchema(XMPMetadata.create_xmp_metadata())

    with pytest.raises(TypeError):
        schema.set_color_mode(True)

    schema.set_property(PhotoshopSchema.COLOR_MODE, True)
    assert schema.get_color_mode() is None
