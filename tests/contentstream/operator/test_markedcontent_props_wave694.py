from __future__ import annotations

from pypdfbox.contentstream.operator.markedcontent import resolve_property_dict
from pypdfbox.cos import COSDictionary, COSName


class _Context:
    def __init__(self, resources: object) -> None:
        self.resources = resources

    def get_resources(self) -> object:
        return self.resources


class _PropertyList:
    def __init__(self, cos_object: object) -> None:
        self.cos_object = cos_object

    def get_cos_object(self) -> object:
        return self.cos_object


class _RaisingPropertyList:
    def get_cos_object(self) -> object:
        raise RuntimeError("synthetic malformed property list")


def test_resolve_property_dict_swallows_property_list_lookup_error() -> None:
    class _Resources:
        def get_property_list(self, name: COSName) -> object:
            del name
            raise RuntimeError("synthetic malformed resources")

    out = resolve_property_dict(
        [COSName.get_pdf_name("Span"), COSName.get_pdf_name("Broken")],
        _Context(_Resources()),
    )

    assert out is None


def test_resolve_property_dict_swallows_cos_object_lookup_error() -> None:
    class _Resources:
        def get_property_list(self, name: COSName) -> object:
            del name
            return _RaisingPropertyList()

    out = resolve_property_dict(
        [COSName.get_pdf_name("Span"), COSName.get_pdf_name("Broken")],
        _Context(_Resources()),
    )

    assert out is None


def test_resolve_property_dict_rejects_named_property_list_non_dict() -> None:
    class _Resources:
        def get_property_list(self, name: COSName) -> object:
            del name
            return _PropertyList(COSName.get_pdf_name("NotADictionary"))

    out = resolve_property_dict(
        [COSName.get_pdf_name("Span"), COSName.get_pdf_name("Named")],
        _Context(_Resources()),
    )

    assert out is None


def test_resolve_property_dict_accepts_named_property_list_dict() -> None:
    props = COSDictionary()

    class _Resources:
        def get_property_list(self, name: COSName) -> object:
            del name
            return _PropertyList(props)

    out = resolve_property_dict(
        [COSName.get_pdf_name("Span"), COSName.get_pdf_name("Named")],
        _Context(_Resources()),
    )

    assert out is props
