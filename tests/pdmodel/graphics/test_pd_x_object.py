from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common import PDStream
from pypdfbox.pdmodel.graphics import PDXObject
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject


def test_xobject_stamps_type_and_subtype_on_cos_stream() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Custom"))

    assert xobject.get_cos_object() is stream
    assert xobject.get_stream().get_cos_object() is stream
    assert stream.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert stream.get_name(COSName.SUBTYPE) == "Custom"  # type: ignore[attr-defined]


def test_xobject_accepts_pd_stream_wrapper() -> None:
    pd_stream = PDStream(input_data=b"body")
    xobject = PDXObject(pd_stream, COSName.get_pdf_name("Image"))
    assert xobject.get_stream() is pd_stream


# ---------- PDXObject.create_x_object factory ----------
#
# Mirrors upstream's ``PDXObject.createXObject(COSBase, PDResources)``
# static dispatch on /Subtype.


def test_create_x_object_returns_none_for_none_base() -> None:
    # Upstream's TODO-marked branch returns null when base is null.
    assert PDXObject.create_x_object(None) is None


def test_create_x_object_dispatches_form_subtype() -> None:
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert obj.get_cos_object() is stream


def test_create_x_object_dispatches_image_subtype() -> None:
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDImageXObject)
    assert obj.get_cos_object() is stream


def test_create_x_object_unknown_subtype_raises_oserror() -> None:
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Bogus")  # type: ignore[attr-defined]
    with pytest.raises(OSError, match="Invalid XObject Subtype"):
        PDXObject.create_x_object(stream)


def test_create_x_object_non_stream_raises_oserror() -> None:
    # COSDictionary is not a COSStream — upstream would throw IOException
    # ("Unexpected object type: ...") here.
    with pytest.raises(OSError, match="Unexpected object type"):
        PDXObject.create_x_object(COSDictionary())


def test_create_x_object_dispatches_postscript_subtype() -> None:
    # PDPostScriptXObject is now ported; the factory should return a
    # typed wrapper instead of raising.
    from pypdfbox.pdmodel.graphics.pd_post_script_x_object import (
        PDPostScriptXObject,
    )

    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "PS")  # type: ignore[attr-defined]
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDPostScriptXObject)
    assert obj.get_cos_object() is stream
