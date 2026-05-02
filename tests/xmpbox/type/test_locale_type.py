from __future__ import annotations

import pytest

from pypdfbox.xmpbox import LocaleType, TextType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_locale_is_text_subclass() -> None:
    assert issubclass(LocaleType, TextType)


def test_locale_round_trip(metadata: XMPMetadata) -> None:
    loc = LocaleType(metadata, "ns", "p", "lang", "en-US")
    assert loc.get_value() == "en-US"
    assert loc.get_string_value() == "en-US"
    assert loc.get_namespace() == "ns"
    assert loc.get_prefix() == "p"
    assert loc.get_property_name() == "lang"


def test_locale_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        LocaleType(metadata, "ns", "p", "lang", 42)


def test_locale_registry_returns_locale_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "lang", "fr-FR", "Locale"
    )
    assert isinstance(instance, LocaleType)


def test_create_locale_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_locale("ns", "p", "lang", "de-DE")
    assert isinstance(instance, LocaleType)
    assert instance.get_value() == "de-DE"
