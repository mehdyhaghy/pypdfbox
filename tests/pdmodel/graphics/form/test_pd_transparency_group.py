from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form import (
    PDFormXObject,
    PDTransparencyGroup,
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_GROUP = COSName.get_pdf_name("Group")
_S = COSName.get_pdf_name("S")
_TRANSPARENCY = COSName.get_pdf_name("Transparency")


def _form_stream_with_transparency() -> COSStream:
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    group = COSDictionary()
    group.set_name(_S, "Transparency")
    stream.set_item(_GROUP, group)
    return stream


# ---------- inheritance ----------


def test_extends_pd_form_x_object() -> None:
    # PDTransparencyGroup is a *form* X-Object subclass; isinstance must
    # remain compatible with the parent so existing PDFormXObject call
    # sites continue to accept transparency-group instances.
    tg = PDTransparencyGroup(COSStream())
    assert isinstance(tg, PDFormXObject)
    assert isinstance(tg, PDXObject)


# ---------- constructors ----------


def test_constructor_with_cos_stream_stamps_form_subtype() -> None:
    tg = PDTransparencyGroup(COSStream())
    cos = tg.get_cos_object()
    # Type/Subtype come from the parent PDFormXObject constructor — must
    # remain /Type /XObject and /Subtype /Form (transparency group is an
    # *attribute* of the form, not a separate /Subtype).
    assert cos.get_name(_TYPE) == "XObject"
    assert cos.get_name(_SUBTYPE) == "Form"


def test_constructor_accepts_pd_stream() -> None:
    pds = PDStream(COSStream())
    tg = PDTransparencyGroup(pds)
    assert tg.get_stream() is pds
    assert tg.get_subtype() == "Form"


def test_constructor_accepts_pd_document() -> None:
    # Mirrors upstream PDTransparencyGroup(PDDocument) — allocates a
    # blank form stream owned by the document.
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    tg = PDTransparencyGroup(document)
    cos = tg.get_cos_object()
    assert cos.get_name(_TYPE) == "XObject"
    assert cos.get_name(_SUBTYPE) == "Form"
    # FormType still defaults to 1.
    assert tg.get_form_type() == 1


def test_constructor_threads_resource_cache() -> None:
    # The cache parameter is passed through to PDFormXObject and surfaces
    # via ``get_resources().get_resource_cache()``.
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
    from pypdfbox.pdmodel.pd_resources import PDResources

    cache = DefaultResourceCache()
    tg = PDTransparencyGroup(COSStream(), cache=cache)
    tg.set_resources(PDResources())
    res = tg.get_resources()
    assert res is not None
    assert res.get_resource_cache() is cache


# ---------- factory dispatch (PDXObject.create_x_object) ----------


def test_factory_returns_transparency_group_when_group_s_transparency() -> None:
    stream = _form_stream_with_transparency()
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDTransparencyGroup)
    # Group attributes are still discoverable on the instance.
    attrs = obj.get_group_attributes()
    assert attrs is not None
    assert isinstance(attrs, PDTransparencyGroupAttributes)


def test_factory_returns_plain_form_when_no_group() -> None:
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    obj = PDXObject.create_x_object(stream)
    # No /Group entry — must NOT be a transparency group.
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


def test_factory_returns_plain_form_when_group_s_not_transparency() -> None:
    # /Group dict is present but /S is something other than /Transparency
    # — upstream still returns a plain PDFormXObject.
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    group = COSDictionary()
    group.set_name(_S, "OtherGroup")
    stream.set_item(_GROUP, group)
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


def test_factory_returns_plain_form_when_group_missing_s() -> None:
    # /Group dict present but no /S entry — without /S /Transparency the
    # form is not a transparency group.
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    stream.set_item(_GROUP, COSDictionary())
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


def test_factory_returns_plain_form_when_group_is_not_dictionary() -> None:
    # Defensive: if /Group is present but isn't a dictionary (malformed
    # input), upstream's getCOSDictionary would return null and the
    # form-X-object fallback applies.
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    stream.set_name(_GROUP, "NotADict")
    obj = PDXObject.create_x_object(stream)
    assert isinstance(obj, PDFormXObject)
    assert not isinstance(obj, PDTransparencyGroup)


# ---------- inherited PDFormXObject surface still works ----------


def test_inherited_group_attributes_round_trip() -> None:
    stream = _form_stream_with_transparency()
    tg = PDTransparencyGroup(stream)
    attrs = tg.get_group_attributes()
    assert attrs is not None
    assert attrs.is_isolated() is False
    assert attrs.is_knockout() is False


def test_inherited_form_type_default() -> None:
    tg = PDTransparencyGroup(COSStream())
    # FormType defaults to 1 just like the parent.
    assert tg.get_form_type() == 1
