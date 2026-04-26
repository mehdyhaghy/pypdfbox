from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDRectangle, PDResources
from pypdfbox.pdmodel.graphics.form import PDFormXObject


def test_form_xobject_defaults_and_metadata() -> None:
    form = PDFormXObject(COSStream())

    assert form.get_cos_object().get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert form.get_cos_object().get_name(COSName.SUBTYPE) == "Form"  # type: ignore[attr-defined]
    assert form.get_form_type() == 1
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert form.get_bbox() is None
    assert form.get_resources() is None


def test_form_bbox_matrix_and_resources_round_trip() -> None:
    form = PDFormXObject(COSStream())
    resources = PDResources()

    form.set_b_box(PDRectangle.from_width_height(100, 50))
    form.set_matrix([2, 0, 0, 2, 10, 20])
    form.set_resources(resources)

    bbox = form.get_b_box()
    assert bbox is not None
    assert bbox.get_width() == 100
    assert bbox.get_height() == 50
    assert form.get_matrix() == [2.0, 0.0, 0.0, 2.0, 10.0, 20.0]
    assert form.get_resources() is not None
    assert form.get_resources().get_cos_object() is resources.get_cos_object()  # type: ignore[union-attr]


def test_form_rejects_malformed_matrix_length() -> None:
    form = PDFormXObject(COSStream())
    with pytest.raises(ValueError):
        form.set_matrix([1, 0, 0])


def test_form_resources_self_reference_guard_returns_empty_resources() -> None:
    form = PDFormXObject(COSStream())
    form.get_cos_object().set_item(COSName.RESOURCES, COSName.RESOURCES)  # type: ignore[attr-defined]
    resources = form.get_resources()
    assert resources is not None
    assert resources.get_cos_object().size() == 0
