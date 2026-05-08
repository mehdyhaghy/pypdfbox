from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_three_d import (
    PDAnnotation3D,
)

_3DD = COSName.get_pdf_name("3DD")
_3DV = COSName.get_pdf_name("3DV")
_3DA = COSName.get_pdf_name("3DA")
_3DI = COSName.get_pdf_name("3DI")
_3DB = COSName.get_pdf_name("3DB")


class _COSWrapper:
    def __init__(self, cos: COSDictionary) -> None:
        self._cos = cos

    def get_cos_object(self) -> COSDictionary:
        return self._cos


def test_three_d_subtype_constructor_and_dispatch() -> None:
    ann = PDAnnotation3D()

    assert PDAnnotation3D.SUB_TYPE == "3D"
    assert ann.get_subtype() == "3D"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]

    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "3D")  # type: ignore[attr-defined]

    wrapped = PDAnnotation3D(raw)
    dispatched = PDAnnotation.create(raw)

    assert wrapped.get_cos_object() is raw
    assert isinstance(dispatched, PDAnnotation3D)
    assert dispatched.get_cos_object() is raw


def test_three_d_stream_view_and_activation_accessors_round_trip() -> None:
    ann = PDAnnotation3D()
    stream = COSStream()
    view = COSDictionary()
    activation = COSDictionary()

    view.set_string("IN", "front")
    activation.set_name("A", "PV")

    ann.set_3dd(stream)
    ann.set_3dv(view)
    ann.set_3da(activation)

    assert ann.get_3dd() is stream
    assert ann.get_3dv() is view
    assert ann.get_3da() is activation
    assert ann.get_artwork() is stream
    assert ann.get_default_view() is view
    assert ann.get_activation_dictionary() is activation


def test_three_d_descriptive_aliases_store_wrapped_cos_objects() -> None:
    ann = PDAnnotation3D()
    artwork = COSStream()
    view = COSDictionary()
    activation = COSDictionary()

    ann.set_artwork(_COSWrapper(artwork))
    ann.set_default_view(_COSWrapper(view))
    ann.set_activation_dictionary(_COSWrapper(activation))

    assert ann.get_cos_object().get_dictionary_object(_3DD) is artwork
    assert ann.get_cos_object().get_dictionary_object(_3DV) is view
    assert ann.get_cos_object().get_dictionary_object(_3DA) is activation


def test_three_d_default_view_raw_selector_shapes_round_trip() -> None:
    ann = PDAnnotation3D()
    named_view = COSName.get_pdf_name("F")
    indexed_view = COSInteger.get(2)

    ann.set_default_view(named_view)
    assert ann.get_default_view() is named_view

    ann.set_default_view(indexed_view)
    assert ann.get_default_view() is indexed_view


def test_three_d_view_box_and_interactive_defaults_round_trip() -> None:
    ann = PDAnnotation3D()
    view_box = COSArray.of_cos_floats([1.0, 2.0, 30.0, 40.0])

    assert ann.is_interactive() is True

    ann.set_interactive(False)
    ann.set_3db(view_box)

    assert ann.is_interactive() is False
    assert ann.get_cos_object().get_dictionary_object(_3DI) is COSBoolean.FALSE
    assert ann.get_3db() is view_box

    ann.set_interactive(True)

    assert ann.is_interactive() is True
    assert ann.get_cos_object().get_dictionary_object(_3DI) is COSBoolean.TRUE


def test_three_d_clearing_removes_optional_entries_and_preserves_defaults() -> None:
    ann = PDAnnotation3D()

    ann.set_artwork(COSStream())
    ann.set_default_view(COSName.get_pdf_name("F"))
    ann.set_activation_dictionary(COSDictionary())
    ann.set_3db(COSArray.of_cos_floats([0.0, 0.0, 10.0, 10.0]))

    ann.set_artwork(None)
    ann.set_default_view(None)
    ann.set_activation_dictionary(None)
    ann.set_3db(None)

    assert not ann.get_cos_object().contains_key(_3DD)
    assert not ann.get_cos_object().contains_key(_3DV)
    assert not ann.get_cos_object().contains_key(_3DA)
    assert not ann.get_cos_object().contains_key(_3DB)
    assert ann.get_3dd() is None
    assert ann.get_3dv() is None
    assert ann.get_3da() is None
    assert ann.get_3db() is None
    assert ann.is_interactive() is True


def test_three_d_cos_dictionary_round_trip_preserves_raw_entries() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "3D")  # type: ignore[attr-defined]
    artwork = COSStream()
    view = COSDictionary()
    activation = COSDictionary()
    view_box = COSArray.of_cos_floats([5.0, 6.0, 70.0, 80.0])
    raw.set_item(_3DD, artwork)
    raw.set_item(_3DV, view)
    raw.set_item(_3DA, activation)
    raw.set_item(_3DB, view_box)
    raw.set_boolean(_3DI, False)

    ann = PDAnnotation3D(raw)

    assert ann.get_artwork() is artwork
    assert ann.get_default_view() is view
    assert ann.get_activation_dictionary() is activation
    assert ann.get_3db() is view_box
    assert ann.is_interactive() is False


def test_three_d_malformed_typed_shapes_do_not_raise() -> None:
    ann = PDAnnotation3D()

    ann.get_cos_object().set_name(_3DA, "NotADictionary")
    ann.get_cos_object().set_item(_3DB, COSDictionary())
    ann.get_cos_object().set_item(_3DI, COSDictionary())
    raw_artwork = COSName.get_pdf_name("NotAStream")
    raw_view = COSArray()
    ann.get_cos_object().set_item(_3DD, raw_artwork)
    ann.get_cos_object().set_item(_3DV, raw_view)

    assert ann.get_3da() is None
    assert ann.get_activation_dictionary() is None
    assert ann.get_3db() is None
    assert ann.is_interactive() is True
    assert ann.get_artwork() is raw_artwork
    assert ann.get_default_view() is raw_view
