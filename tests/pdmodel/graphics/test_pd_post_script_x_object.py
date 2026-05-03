from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics import PDXObject
from pypdfbox.pdmodel.graphics.pd_post_script_x_object import (
    PDPostScriptXObject,
)


def test_post_script_x_object_stamps_type_and_subtype() -> None:
    stream = COSStream()
    obj = PDPostScriptXObject(stream)

    assert obj.get_cos_object() is stream
    assert stream.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert stream.get_name(COSName.SUBTYPE) == "PS"  # type: ignore[attr-defined]


def test_post_script_x_object_get_subtype_reports_ps() -> None:
    obj = PDPostScriptXObject(COSStream())
    assert obj.get_subtype() == "PS"
    assert obj.get_sub_type() == "PS"


def test_post_script_x_object_is_pd_xobject() -> None:
    obj = PDPostScriptXObject(COSStream())
    assert isinstance(obj, PDXObject)


def test_post_script_x_object_round_trip_via_existing_dict() -> None:
    # Build a stream that already carries /Subtype /PS, wrap it, then
    # round-trip through the factory and confirm we get back a typed
    # wrapper over the same COSStream.
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "PS")  # type: ignore[attr-defined]

    direct = PDPostScriptXObject(stream)
    assert direct.get_cos_object() is stream

    via_factory = PDXObject.create_x_object(stream)
    assert isinstance(via_factory, PDPostScriptXObject)
    assert via_factory.get_cos_object() is stream
    # The /Subtype entry stays a single /PS name (no double-stamp / churn).
    assert stream.get_name(COSName.SUBTYPE) == "PS"  # type: ignore[attr-defined]


def test_post_script_x_object_factory_dispatch_returns_typed_instance() -> None:
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "PS")  # type: ignore[attr-defined]

    obj = PDXObject.create_x_object(stream)

    assert isinstance(obj, PDPostScriptXObject)
    assert obj.get_subtype() == "PS"
