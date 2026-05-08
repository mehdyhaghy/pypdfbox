"""Wave 276 focused coverage for :class:`PDSoftMask`.

Exercises the small COS-surface contract around Table 144 entries without
depending on renderer behavior.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.function.pd_function import PDFunctionTypeIdentity
from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2
from pypdfbox.pdmodel.graphics.form import PDTransparencyGroup
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

TYPE = COSName.get_pdf_name("Type")
MASK = COSName.get_pdf_name("Mask")
S = COSName.get_pdf_name("S")
G = COSName.get_pdf_name("G")
BC = COSName.get_pdf_name("BC")
TR = COSName.get_pdf_name("TR")
ALPHA = COSName.get_pdf_name("Alpha")
LUMINOSITY = COSName.get_pdf_name("Luminosity")
IDENTITY = COSName.get_pdf_name("Identity")


def _function_type2_dictionary() -> COSDictionary:
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    fn.set_item("Domain", COSArray([COSFloat(0.0), COSFloat(1.0)]))
    fn.set_item("N", COSInteger.get(1))
    return fn


def test_defaults_are_spec_lightweight() -> None:
    sm = PDSoftMask()
    cos = sm.get_cos_object()

    assert cos.get_dictionary_object(TYPE) == MASK
    assert sm.get_subtype() is None
    assert sm.get_group() is None
    assert sm.get_backdrop_color() is None
    assert sm.get_transfer_function() is None
    assert sm.get_transfer_function_typed() is None
    assert not sm.is_alpha()
    assert not sm.is_luminosity()


def test_subtype_accessors_and_predicates_round_trip() -> None:
    sm = PDSoftMask()

    sm.set_subtype(ALPHA)
    assert sm.get_subtype() == ALPHA
    assert sm.is_alpha()
    assert not sm.is_luminosity()

    sm.set_subtype(LUMINOSITY)
    assert sm.get_subtype() == LUMINOSITY
    assert not sm.is_alpha()
    assert sm.is_luminosity()


def test_backdrop_color_accessors_round_trip_and_clear() -> None:
    sm = PDSoftMask()
    backdrop = COSArray([COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)])

    sm.set_backdrop_color(backdrop)

    assert sm.get_backdrop_color() is backdrop
    assert sm.get_cos_object().get_dictionary_object(BC) is backdrop

    sm.set_backdrop_color(None)

    assert sm.get_backdrop_color() is None
    assert not sm.get_cos_object().contains_key(BC)


def test_transfer_function_accessors_round_trip_identity_function_and_clear() -> None:
    sm = PDSoftMask()

    sm.set_transfer_function(IDENTITY)
    assert sm.get_transfer_function() == IDENTITY
    assert isinstance(sm.get_transfer_function_typed(), PDFunctionTypeIdentity)

    function_dict = _function_type2_dictionary()
    sm.set_transfer_function(function_dict)

    assert sm.get_transfer_function() is function_dict
    assert isinstance(sm.get_transfer_function_typed(), PDFunctionType2)
    assert sm.get_cos_object().get_dictionary_object(TR) is function_dict

    sm.set_transfer_function(None)

    assert sm.get_transfer_function() is None
    assert sm.get_transfer_function_typed() is None
    assert not sm.get_cos_object().contains_key(TR)


def test_group_accessors_accept_stream_and_form_clear_and_thread_cache() -> None:
    cache = DefaultResourceCache()
    sm = PDSoftMask(resource_cache=cache)
    stream = COSStream()
    resources = COSDictionary()
    stream.set_item(COSName.RESOURCES, resources)  # type: ignore[attr-defined]

    sm.set_group(stream)
    group = sm.get_group()

    assert isinstance(group, PDFormXObject)
    assert group.get_cos_object() is stream
    group_resources = group.get_resources()
    assert group_resources is not None
    assert group_resources.get_resource_cache() is cache
    assert sm.get_cos_object().get_dictionary_object(G) is stream

    typed_form = PDFormXObject(COSStream())
    sm.set_group(typed_form)

    assert sm.get_cos_object().get_dictionary_object(G) is typed_form.get_cos_object()

    sm.set_group(None)

    assert sm.get_group() is None
    assert not sm.get_cos_object().contains_key(G)


def test_get_group_promotes_form_transparency_group_and_threads_cache() -> None:
    cache = DefaultResourceCache()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")  # type: ignore[attr-defined]
    stream.set_item(COSName.RESOURCES, COSDictionary())  # type: ignore[attr-defined]
    group_dict = COSDictionary()
    group_dict.set_item(S, COSName.get_pdf_name("Transparency"))
    stream.set_item(COSName.get_pdf_name("Group"), group_dict)
    dictionary = COSDictionary()
    dictionary.set_item(G, stream)

    group = PDSoftMask(dictionary, resource_cache=cache).get_group()

    assert isinstance(group, PDTransparencyGroup)
    assert group.get_cos_object() is stream
    resources = group.get_resources()
    assert resources is not None
    assert resources.get_resource_cache() is cache


def test_create_and_cos_dictionary_round_trip_preserve_raw_entries() -> None:
    stream = COSStream()
    backdrop = COSArray([COSFloat(0.0)])
    transfer = _function_type2_dictionary()
    dictionary = COSDictionary()
    dictionary.set_item(TYPE, MASK)
    dictionary.set_item(S, ALPHA)
    dictionary.set_item(G, stream)
    dictionary.set_item(BC, backdrop)
    dictionary.set_item(TR, transfer)

    sm = PDSoftMask.create(dictionary)

    assert isinstance(sm, PDSoftMask)
    assert sm.get_cos_object() is dictionary
    assert sm.get_subtype() == ALPHA
    assert sm.get_backdrop_color() is backdrop
    assert sm.get_transfer_function() is transfer
    group = sm.get_group()
    assert isinstance(group, PDFormXObject)
    assert group.get_cos_object() is stream


def test_create_defaults_and_malformed_shapes_are_graceful() -> None:
    assert PDSoftMask.create(None) is None
    assert PDSoftMask.create(COSName.get_pdf_name("None")) is None
    assert PDSoftMask.create(COSName.get_pdf_name("Alpha")) is None
    assert PDSoftMask.create(COSArray()) is None

    malformed = COSDictionary()
    malformed.set_item(S, COSArray())
    malformed.set_item(G, COSDictionary())
    malformed.set_item(BC, COSName.get_pdf_name("DeviceRGB"))
    malformed.set_item(TR, COSInteger.get(7))
    sm = PDSoftMask(malformed)

    assert sm.get_subtype() is None
    assert not sm.is_alpha()
    assert not sm.is_luminosity()
    assert sm.get_group() is None
    assert sm.get_backdrop_color() is None
    assert sm.get_transfer_function() == COSInteger.get(7)
    with pytest.raises(TypeError):
        sm.get_transfer_function_typed()


def test_constructor_and_group_setter_reject_invalid_shapes() -> None:
    with pytest.raises(TypeError):
        PDSoftMask(COSArray())  # type: ignore[arg-type]

    sm = PDSoftMask()
    with pytest.raises(TypeError):
        sm.set_group(COSDictionary())
