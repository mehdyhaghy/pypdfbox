from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics import PDXObject
from pypdfbox.pdmodel.graphics.pd_post_script_x_object import (
    PDPostScriptXObject,
)

_STRUCT_PARENT = COSName.get_pdf_name("StructParent")


def test_x_object_struct_parent_defaults_to_minus_one() -> None:
    xobject = PDXObject(COSStream(), COSName.get_pdf_name("Form"))

    assert xobject.get_struct_parent() == -1
    assert xobject.get_cos_object().get_dictionary_object(_STRUCT_PARENT) is None


def test_x_object_struct_parent_round_trip() -> None:
    xobject = PDXObject(COSStream(), COSName.get_pdf_name("Image"))

    xobject.set_struct_parent(0)
    assert xobject.get_struct_parent() == 0
    assert xobject.get_cos_object().get_int(_STRUCT_PARENT, -1) == 0

    xobject.set_struct_parent(42)
    assert xobject.get_struct_parent() == 42
    assert xobject.get_cos_object().get_int(_STRUCT_PARENT, -1) == 42


def test_post_script_x_object_inherits_struct_parent_accessors() -> None:
    xobject = PDPostScriptXObject(COSStream())

    xobject.set_struct_parent(7)

    assert xobject.get_struct_parent() == 7
    assert xobject.get_cos_object().get_int(_STRUCT_PARENT, -1) == 7
