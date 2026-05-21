"""Wave 1370 — :class:`LangAlt` ``xml:lang`` + ``x-default`` semantics.

Tests the explicit :class:`pypdfbox.xmpbox.type.LangAlt` API plus parser
behaviour on a ``rdf:Alt`` with mixed language tags. The ``x-default``
entry must sort to the head of the array (parity with
``XMPSchema.reorganizeAltOrder``).
"""

from __future__ import annotations

import io

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.type.array_property import Cardinality
from pypdfbox.xmpbox.type.lang_alt import (
    LANG_ATTR_NAME,
    X_DEFAULT,
    XML_NS_URI,
    LangAlt,
)
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

# ---------------------------------------------------------------------------
# Constructor + class-level constants.
# ---------------------------------------------------------------------------


def test_lang_alt_default_cardinality_is_alt() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    assert la.get_array_type() is Cardinality.Alt


def test_lang_alt_module_level_constants() -> None:
    assert X_DEFAULT == "x-default"
    assert LANG_ATTR_NAME == "xml:lang"
    assert XML_NS_URI == "http://www.w3.org/XML/1998/namespace"
    assert LangAlt.X_DEFAULT == "x-default"


# ---------------------------------------------------------------------------
# set_language_value / get_language_value / get_languages / remove_language.
# ---------------------------------------------------------------------------


def test_lang_alt_set_get_round_trip() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("en", "Hello")
    la.set_language_value("fr", "Bonjour")
    la.set_language_value(None, "Default")  # None -> x-default
    assert la.get_language_value("en") == "Hello"
    assert la.get_language_value("fr") == "Bonjour"
    assert la.get_language_value(None) == "Default"
    assert la.get_language_value("x-default") == "Default"


def test_lang_alt_get_languages_includes_x_default() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("en", "Hello")
    la.set_language_value("x-default", "DefaultHello")
    langs = la.get_languages()
    assert set(langs) == {"en", "x-default"}


def test_lang_alt_remove_language() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("en", "Hi")
    la.set_language_value("fr", "Salut")
    la.remove_language("en")
    assert la.get_language_value("en") is None
    assert la.get_language_value("fr") == "Salut"


def test_lang_alt_remove_language_none_targets_x_default() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("x-default", "X")
    la.set_language_value("en", "Y")
    la.remove_language(None)
    assert la.get_language_value(None) is None
    assert la.get_language_value("en") == "Y"


def test_lang_alt_replace_existing_language() -> None:
    """Setting an already-present language replaces the value."""
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("en", "First")
    la.set_language_value("en", "Second")
    assert la.get_language_value("en") == "Second"
    # Only one entry for en.
    assert la.get_languages().count("en") == 1


# ---------------------------------------------------------------------------
# x-default reorganisation: x-default sorts to the head.
# ---------------------------------------------------------------------------


def test_lang_alt_x_default_moves_to_head() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    # Insert non-default first, then x-default — should reorganise.
    la.set_language_value("en", "EN")
    la.set_language_value("fr", "FR")
    la.set_language_value("x-default", "Default")
    langs = la.get_languages()
    assert langs[0] == "x-default"


def test_lang_alt_no_x_default_leaves_order_alone() -> None:
    """Without ``x-default``, insertion order is preserved."""
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("en", "EN")
    la.set_language_value("fr", "FR")
    la.set_language_value("de", "DE")
    assert la.get_languages() == ["en", "fr", "de"]


def test_lang_alt_x_default_at_head_already_no_change() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "urn:x", "x", "title")
    la.set_language_value("x-default", "D")
    la.set_language_value("en", "E")
    assert la.get_languages() == ["x-default", "en"]


# ---------------------------------------------------------------------------
# Helper covering the non-TextType branches in _get_text_language_attribute.
# ---------------------------------------------------------------------------


def test_lang_alt_non_text_type_child_has_no_language() -> None:
    """A non-TextType child has no xml:lang attribute lookup."""

    class _Bogus:
        pass

    bogus = _Bogus()
    result = LangAlt._get_text_language_attribute(bogus)
    assert result is None


def test_lang_alt_text_type_without_lang_attribute_returns_none() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    text = TextType(meta, "urn:x", "x", "child", "no-lang")
    assert LangAlt._get_text_language_attribute(text) is None


# ---------------------------------------------------------------------------
# Parser path: rdf:Alt with mixed langs round-trips into the schema.
# ---------------------------------------------------------------------------


_PACKET_HEADER = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
)
_PACKET_FOOTER = b"</x:xmpmeta><?xpacket end=\"w\"?>"


def test_parser_x_default_value_accessible_via_schema() -> None:
    body = (
        _PACKET_HEADER
        + b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b'<dc:title><rdf:Alt>'
        b'<rdf:li xml:lang="x-default">PrimaryTitle</rdf:li>'
        b'<rdf:li xml:lang="en">EnglishTitle</rdf:li>'
        b'</rdf:Alt></dc:title>'
        b'</rdf:Description></rdf:RDF>'
        + _PACKET_FOOTER
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(body)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_title("x-default") == "PrimaryTitle"
    assert dc.get_title("en") == "EnglishTitle"


# ---------------------------------------------------------------------------
# Serialize: x-default precedes the rest in output.
# ---------------------------------------------------------------------------


def test_serialize_lang_alt_x_default_first_in_output() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    dc = meta.create_and_add_dublin_core_schema()
    # set_title signature: (value, lang=None). Insert non-default first.
    dc.set_title_lang("en", "EnglishTitle")
    dc.set_title_lang("x-default", "MainTitle")
    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=False)
    blob = out.getvalue()
    main_pos = blob.find(b"MainTitle")
    en_pos = blob.find(b"EnglishTitle")
    assert main_pos != -1 and en_pos != -1
    # x-default sorts to the head of the serialised array (per upstream
    # reorganizeAltOrder).
    assert main_pos < en_pos
