from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
)
from pypdfbox.io import RandomAccessWrite
from pypdfbox.pdmodel import PDDocument, PDResources
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from pypdfbox.pdmodel.pd_document import ExternalSigningSupport
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


class _BufferWrite(RandomAccessWrite):
    def __init__(self) -> None:
        self.data = bytearray()
        self.closed = False

    def write(self, b: int) -> None:
        self.data.append(b)

    def write_bytes(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        chunk = bytes(data)
        end = len(chunk) if length is None else offset + length
        self.data.extend(chunk[offset:end])

    def clear(self) -> None:
        self.data.clear()

    def close(self) -> None:
        self.closed = True

    def is_closed(self) -> bool:
        return self.closed


def test_wave507_deep_copy_breaks_cycles_and_preserves_scalar_instances() -> None:
    doc = PDDocument()
    parent = COSDictionary()
    child = COSArray()
    marker = COSInteger.get(7)
    parent.set_item(COSName.get_pdf_name("Child"), child)
    parent.set_item(COSName.get_pdf_name("Marker"), marker)
    child.add(parent)

    copied = doc._deep_copy_cos(parent, set())  # noqa: SLF001

    copied_child = copied.get_dictionary_object(COSName.get_pdf_name("Child"))
    assert isinstance(copied_child, COSArray)
    assert copied_child.get_object(0) is parent
    assert copied.get_dictionary_object(COSName.get_pdf_name("Marker")) is marker
    doc.close()


def test_wave507_signature_helpers_splice_extract_and_write_to_random_access() -> None:
    buffer = bytearray(b"abc000000def")
    signed = PDDocument._splice_signature(buffer, (3, 9), b"\x01\xaf")  # noqa: SLF001

    assert signed == b"abc01AF00def"
    assert PDDocument._extract_bracketed(signed, [0, 4, 9, 3]) == b"abc0def"  # noqa: SLF001

    sink = _BufferWrite()
    PDDocument._write_bytes_to_target(b"written", sink)  # noqa: SLF001

    assert bytes(sink.data) == b"written"


def test_wave507_signature_splice_rejects_oversized_der() -> None:
    with pytest.raises(ValueError, match="larger than reserved"):
        PDDocument._splice_signature(bytearray(b"0000"), (0, 4), b"\x00\x01\x02")  # noqa: SLF001


def test_wave507_external_signing_support_is_single_use_and_clears_staging() -> None:
    doc = PDDocument()
    doc._pending_signature = object()  # type: ignore[assignment]  # noqa: SLF001
    doc._pending_signature_interface = object()  # type: ignore[assignment]  # noqa: SLF001
    doc._pending_signature_options = object()  # noqa: SLF001
    output = io.BytesIO()
    handle = ExternalSigningSupport(
        document=doc,
        output=output,
        buffer=bytearray(b"xx0000yy"),
        contents_span=(2, 6),
        byte_range=[0, 2, 6, 2],
    )

    assert handle.get_content() == b"xxyy"
    assert handle.get_byte_range() == [0, 2, 6, 2]
    handle.set_signature(b"\xaa")

    assert output.getvalue() == b"xxAA00yy"
    assert doc.get_pending_signature() is None
    assert doc.get_signature_interface() is None
    assert doc.get_signature_options() is None
    with pytest.raises(RuntimeError, match="called twice"):
        handle.set_signature(b"\xbb")
    doc.close()


def test_wave507_set_encryption_dictionary_accepts_wrapper_and_creates_trailer() -> None:
    cos_doc = COSDocument()
    doc = PDDocument(cos_doc)

    class Encryption:
        def __init__(self) -> None:
            self.dictionary = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self.dictionary

    encryption = Encryption()
    doc.set_encryption_dictionary(encryption)

    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    assert trailer.get_dictionary_object(COSName.ENCRYPT) is encryption.dictionary  # type: ignore[attr-defined]
    assert doc.get_encryption() is encryption
    doc.close()


def test_wave507_resources_cache_indirect_ext_gstate_and_property_list() -> None:
    cache = DefaultResourceCache()
    ext_dict = COSDictionary()
    ext_ref = COSObject(11, 0, resolved=ext_dict)
    prop_dict = COSDictionary()
    prop_ref = COSObject(12, 0, resolved=prop_dict)
    resources = COSDictionary()
    ext_sub = COSDictionary()
    prop_sub = COSDictionary()
    ext_sub.set_item(COSName.get_pdf_name("GS0"), ext_ref)
    prop_sub.set_item(COSName.get_pdf_name("Prop0"), prop_ref)
    resources.set_item(PDResources.EXT_G_STATE, ext_sub)
    resources.set_item(PDResources.PROPERTIES, prop_sub)
    res = PDResources(resources, resource_cache=cache)

    first_ext = res.get_ext_gstate(COSName.get_pdf_name("GS0"))
    first_prop = res.get_property_list(COSName.get_pdf_name("Prop0"))

    assert isinstance(first_ext, PDExtendedGraphicsState)
    assert isinstance(first_prop, PDPropertyList)
    assert res.get_ext_g_state(COSName.get_pdf_name("GS0")) is first_ext
    assert res.get_properties(COSName.get_pdf_name("Prop0")) is first_prop


def test_wave507_resources_add_reuses_existing_indirect_and_allocates_ocg_prefix() -> None:
    res = PDResources()
    sub = COSDictionary()
    existing_value = COSDictionary()
    existing_ref = COSObject(21, 0, resolved=existing_value)
    existing_name = COSName.get_pdf_name("Prop0")
    sub.set_item(existing_name, existing_ref)
    res.get_cos_object().set_item(PDResources.PROPERTIES, sub)

    assert res.add(PDResources.PROPERTIES, existing_value) is existing_name

    ocg = PDOptionalContentGroup("Layer")
    ocg_name = res.add(ocg)

    # /Properties already holds Prop0 (size 1); createKey seeds from
    # keySet().size() and pre-increments → oc2 (not oc1).
    assert ocg_name.get_name() == "oc2"


@pytest.mark.parametrize(
    ("category", "name", "value", "getter"),
    [
        (PDResources.PATTERN, "P0", COSName.get_pdf_name("NotDict"), "get_pattern"),
        (PDResources.SHADING, "Sh0", COSName.get_pdf_name("NotDict"), "get_shading"),
        (
            PDResources.EXT_G_STATE,
            "GS0",
            COSName.get_pdf_name("NotDict"),
            "get_ext_gstate",
        ),
        (
            PDResources.PROPERTIES,
            "Prop0",
            COSName.get_pdf_name("NotDict"),
            "get_property_list",
        ),
    ],
)
def test_wave507_typed_resource_accessors_ignore_non_dictionary_entries(
    category: COSName,
    name: str,
    value: Any,
    getter: str,
) -> None:
    res = PDResources()
    key = COSName.get_pdf_name(name)
    res.put(category, key, value)

    assert getattr(res, getter)(key) is None
