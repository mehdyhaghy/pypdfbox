"""Branch-coverage round-out (wave 1367) for ``AdobePDFSchema``.

Exercises the typed-property cache invalidation logic, predicate helpers,
``clear()``, and ``get_known_properties`` snapshot path. Existing waves
exercise the simple string-form happy path; these tests pin the
two-way typed/string interop and absent-vs-empty-string distinction.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.adobe_pdf_schema import AdobePDFSchema
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> AdobePDFSchema:
    return AdobePDFSchema(XMPMetadata.create_xmp_metadata())


def _text(schema: AdobePDFSchema, name: str, value: str) -> TextType:
    return TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        name,
        value,
    )


def test_typed_setter_then_string_getter_round_trip(schema: AdobePDFSchema) -> None:
    schema.set_keywords_property(_text(schema, AdobePDFSchema.KEYWORDS, "alpha,beta"))
    assert schema.get_keywords() == "alpha,beta"
    # The typed getter hands back the same TextType instance we installed.
    typed = schema.get_keywords_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "alpha,beta"


def test_string_setter_invalidates_typed_cache(schema: AdobePDFSchema) -> None:
    schema.set_keywords_property(_text(schema, AdobePDFSchema.KEYWORDS, "old"))
    # Then write via the string form -> typed cache must rehydrate, not return stale.
    schema.set_keywords("new")
    typed = schema.get_keywords_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "new"


def test_typed_setter_with_none_clears_property(schema: AdobePDFSchema) -> None:
    schema.set_keywords("temp")
    schema.set_keywords_property(None)
    assert schema.get_keywords() is None
    assert schema.get_keywords_property() is None
    assert not schema.has_keywords()


def test_typed_setter_rejects_non_text_type(schema: AdobePDFSchema) -> None:
    with pytest.raises(TypeError):
        schema.set_keywords_property("not-a-text-type")  # type: ignore[arg-type]


def test_set_none_clears_through_string_form(schema: AdobePDFSchema) -> None:
    schema.set_pdf_version("1.7")
    assert schema.has_pdf_version()
    schema.set_pdf_version(None)
    assert not schema.has_pdf_version()
    assert schema.get_pdf_version() is None


def test_has_predicates_distinguish_absent_from_empty(schema: AdobePDFSchema) -> None:
    assert not schema.has_keywords()
    schema.set_keywords("")
    # Empty string still counts as "set" per upstream — getProperty returns it.
    assert schema.has_keywords()
    schema.set_keywords(None)
    assert not schema.has_keywords()


def test_clear_drops_only_modelled_properties(schema: AdobePDFSchema) -> None:
    schema.set_keywords("k")
    schema.set_pdf_version("1.4")
    schema.set_producer("p")
    # Stash an unmodelled property — clear must leave it alone.
    schema.set_property("CustomExtension", "untouched")
    schema.clear()
    assert schema.get_keywords() is None
    assert schema.get_pdf_version() is None
    assert schema.get_producer() is None
    assert schema.get_property("CustomExtension") == "untouched"


def test_get_known_properties_snapshot(schema: AdobePDFSchema) -> None:
    schema.set_pdf_version("1.7")
    schema.set_producer("pypdfbox")
    snapshot = schema.get_known_properties()
    assert snapshot == {"PDFVersion": "1.7", "Producer": "pypdfbox"}
    # Absent properties are omitted from the snapshot.
    assert "Keywords" not in snapshot


def test_typed_getter_rehydrates_after_string_setter(schema: AdobePDFSchema) -> None:
    # No typed setter was ever called; the typed getter should fabricate one
    # from the string store on demand.
    schema.set_producer("pypdfbox")
    typed = schema.get_producer_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "pypdfbox"


def test_typed_getter_returns_none_for_missing(schema: AdobePDFSchema) -> None:
    assert schema.get_keywords_property() is None
    assert schema.get_pdf_version_property() is None
    assert schema.get_producer_property() is None
