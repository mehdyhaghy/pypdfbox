"""Coverage tests for :mod:`pypdfbox.xmpbox.xml.pdfa_extension_helper`.

The helper is a utility-class wrapper around the PDF/A extension
namespace declarations. We exercise:

* ``validate_naming`` happy / mismatch / empty paths.
* ``check_namespace_declaration`` (both branches).
* ``transform_value_type`` prefix-strip table + non-string fallthrough.
* ``require_non_null`` raises + supplier-callable branch.
* The stub static methods (``populate_*``) — call them to cover the
  parity-surface no-ops.
* The constructor raise (utility-class guard).
"""

from __future__ import annotations

from xml.dom.minidom import parseString

import pytest

from pypdfbox.xmpbox.xml import pdfa_extension_helper as helper_mod
from pypdfbox.xmpbox.xml.pdfa_extension_helper import (
    CLOSED_CHOICE,
    CLOSED_CHOICE_U,
    OPEN_CHOICE,
    OPEN_CHOICE_U,
    PdfaExtensionHelper,
)


def _make_description(xml: str):
    """Return the first ``<rdf:Description>`` element of ``xml``."""
    doc = parseString(xml)
    return doc.getElementsByTagNameNS(
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "Description"
    )[0]


def test_constructor_raises() -> None:
    with pytest.raises(TypeError):
        PdfaExtensionHelper()


def test_validate_naming_no_attrs_is_noop() -> None:
    """A description element with no attributes should validate as a no-op."""
    desc = _make_description(
        """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description/>
        </rdf:RDF>"""
    )
    # No raise.
    PdfaExtensionHelper.validate_naming(None, desc)  # type: ignore[arg-type]


def test_validate_naming_accepts_canonical_prefixes() -> None:
    desc = _make_description(
        """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description
            xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"
            xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"
            xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#"/>
        </rdf:RDF>"""
    )
    PdfaExtensionHelper.validate_naming(None, desc)  # type: ignore[arg-type]


def test_validate_naming_raises_for_wrong_prefix() -> None:
    desc = _make_description(
        """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description
            xmlns:wrong="http://www.aiim.org/pdfa/ns/extension/"/>
        </rdf:RDF>"""
    )
    with pytest.raises(OSError, match="Prefix mismatch"):
        PdfaExtensionHelper.validate_naming(None, desc)  # type: ignore[arg-type]


def test_validate_naming_raises_for_wrong_namespace_uri() -> None:
    desc = _make_description(
        """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description xmlns:pdfaExtension="http://example.com/wrong"/>
        </rdf:RDF>"""
    )
    with pytest.raises(OSError, match="Namespace mismatch"):
        PdfaExtensionHelper.validate_naming(None, desc)  # type: ignore[arg-type]


def test_validate_naming_skips_non_xmlns_attrs() -> None:
    """Attributes that aren't in the xmlns namespace are ignored."""
    desc = _make_description(
        """<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description rdf:about="x"/>
        </rdf:RDF>"""
    )
    PdfaExtensionHelper.validate_naming(None, desc)  # type: ignore[arg-type]


def test_populate_schema_mapping_is_noop() -> None:
    # Just calling the stub for coverage of the parity surface.
    PdfaExtensionHelper.populate_schema_mapping(None, strict_parsing=True)  # type: ignore[arg-type]
    PdfaExtensionHelper.populate_schema_mapping(None)  # type: ignore[arg-type]


def test_check_namespace_declaration_accepts_correct_prefix() -> None:
    class _Attr:
        value = "http://www.aiim.org/pdfa/ns/extension/"
        localName = "pdfaExtension"

    PdfaExtensionHelper.check_namespace_declaration(_Attr(), None)


def test_check_namespace_declaration_skips_unknown_uri() -> None:
    class _Attr:
        value = "http://example.com/unknown"
        localName = "foo"

    PdfaExtensionHelper.check_namespace_declaration(_Attr(), None)


def test_check_namespace_declaration_raises_on_mismatch() -> None:
    class _Attr:
        value = "http://www.aiim.org/pdfa/ns/extension/"
        localName = "wrong"

    with pytest.raises(OSError, match="Prefix mismatch"):
        PdfaExtensionHelper.check_namespace_declaration(_Attr(), None)


def test_check_namespace_declaration_missing_attrs_is_noop() -> None:
    class _Attr:
        value = None
        localName = None
        namespaceURI = None

    PdfaExtensionHelper.check_namespace_declaration(_Attr(), None)


def test_stub_populators_run_without_error() -> None:
    PdfaExtensionHelper.populate_pdfa_schema_type(None, None, None, False)  # type: ignore[arg-type]
    PdfaExtensionHelper.populate_pdfa_property_type(None, None, None)  # type: ignore[arg-type]
    PdfaExtensionHelper.populate_pdfa_type(None, None, None)  # type: ignore[arg-type]
    PdfaExtensionHelper.populate_pdfa_field_type(None, None)  # type: ignore[arg-type]


def test_transform_value_type_strips_closed_choice_prefix() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, CLOSED_CHOICE + "Text")
        == "Text"
    )
    assert (
        PdfaExtensionHelper.transform_value_type(None, CLOSED_CHOICE_U + "Text")
        == "Text"
    )


def test_transform_value_type_strips_open_choice_prefix() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, OPEN_CHOICE + "Integer")
        == "Integer"
    )
    assert (
        PdfaExtensionHelper.transform_value_type(None, OPEN_CHOICE_U + "Integer")
        == "Integer"
    )


def test_transform_value_type_passthrough_for_plain_type() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, "Date") == "Date"


def test_transform_value_type_returns_none_for_non_string() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, 42) is None  # type: ignore[arg-type]


def test_require_non_null_passes_when_value_present() -> None:
    PdfaExtensionHelper.require_non_null("ok", "should not raise")


def test_require_non_null_raises_with_plain_message() -> None:
    with pytest.raises(OSError, match="missing"):
        PdfaExtensionHelper.require_non_null(None, "missing")


def test_require_non_null_raises_with_callable_supplier() -> None:
    with pytest.raises(OSError, match="lazy message"):
        PdfaExtensionHelper.require_non_null(None, lambda: "lazy message")


def test_module_constants_exposed() -> None:
    assert helper_mod.CLOSED_CHOICE == "closed Choice of "
    assert helper_mod.OPEN_CHOICE == "open Choice of "
    assert helper_mod.CLOSED_CHOICE_U == "Closed Choice of "
    assert helper_mod.OPEN_CHOICE_U == "Open Choice of "
