"""Wave 1370 — :class:`PdfaExtensionHelper` populate / validate surface.

Targets the ``populate_schema_mapping`` no-op semantics, the
``transform_value_type`` prefix-strip table edge cases (``None``,
empty string, non-string input), the ``check_namespace_declaration``
mirror-of-private upstream helper, and ``require_non_null``'s
callable-message branch.
"""

from __future__ import annotations

from xml.dom.minidom import parseString

import pytest

from pypdfbox.xmpbox.xml.pdfa_extension_helper import (
    CLOSED_CHOICE,
    CLOSED_CHOICE_U,
    OPEN_CHOICE,
    OPEN_CHOICE_U,
    PdfaExtensionHelper,
)
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

# ---------------------------------------------------------------------------
# populate_schema_mapping — no-op idempotent.
# ---------------------------------------------------------------------------


def test_populate_schema_mapping_no_op_strict_false() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    # Must accept strict=False without raising.
    PdfaExtensionHelper.populate_schema_mapping(meta, strict_parsing=False)


def test_populate_schema_mapping_no_op_strict_true() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    PdfaExtensionHelper.populate_schema_mapping(meta, strict_parsing=True)


def test_populate_schema_mapping_default_strict_false() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    PdfaExtensionHelper.populate_schema_mapping(meta)


def test_populate_schema_mapping_repeated_calls_safe() -> None:
    """Calling the populator multiple times must remain idempotent."""
    meta = XMPMetadata.create_xmp_metadata()
    for _ in range(3):
        PdfaExtensionHelper.populate_schema_mapping(meta, strict_parsing=True)


# ---------------------------------------------------------------------------
# transform_value_type — prefix strip + edge cases.
# ---------------------------------------------------------------------------


def test_transform_value_type_strips_lowercase_closed_choice() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, CLOSED_CHOICE + "Text")
        == "Text"
    )


def test_transform_value_type_strips_uppercase_closed_choice() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, CLOSED_CHOICE_U + "Integer")
        == "Integer"
    )


def test_transform_value_type_strips_lowercase_open_choice() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, OPEN_CHOICE + "Real")
        == "Real"
    )


def test_transform_value_type_strips_uppercase_open_choice() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, OPEN_CHOICE_U + "Date")
        == "Date"
    )


def test_transform_value_type_passthrough_when_no_prefix() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, "GpsCoordinate")
        == "GpsCoordinate"
    )


def test_transform_value_type_none_input_returns_none() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, None) is None  # type: ignore[arg-type]


def test_transform_value_type_non_string_input_returns_none() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, 42) is None  # type: ignore[arg-type]


def test_transform_value_type_empty_string_returns_empty_string() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, "") == ""


# ---------------------------------------------------------------------------
# check_namespace_declaration — both pass and mismatch.
# ---------------------------------------------------------------------------


def _xmlns_attr_node(xml_attrs: str):
    """Build an ``xmlns:foo="bar"`` attribute node from an inline xml
    string and return its first xmlns attribute."""
    desc = parseString(
        f'<?xml version="1.0"?><root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        f' {xml_attrs}/>'
    ).documentElement
    attrs = desc.attributes
    for i in range(attrs.length):
        attr = attrs.item(i)
        if (
            attr.namespaceURI == "http://www.w3.org/2000/xmlns/"
            and attr.localName != "rdf"
        ):
            return attr
    raise AssertionError("xmlns attribute missing from fixture")


def test_check_namespace_declaration_canonical_prefix_ok() -> None:
    attr = _xmlns_attr_node(
        'xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"'
    )
    # No raise.
    PdfaExtensionHelper.check_namespace_declaration(attr, object)


def test_check_namespace_declaration_wrong_prefix_raises() -> None:
    attr = _xmlns_attr_node(
        'xmlns:badPrefix="http://www.aiim.org/pdfa/ns/extension/"'
    )
    with pytest.raises(OSError, match="Prefix mismatch"):
        PdfaExtensionHelper.check_namespace_declaration(attr, object)


def test_check_namespace_declaration_unknown_uri_silently_passes() -> None:
    """A xmlns attribute pointing at a URI outside the PDF/A canonical
    namespaces is ignored — we don't speak for unrelated namespaces."""
    attr = _xmlns_attr_node('xmlns:foo="urn:vendor:foo"')
    # No raise.
    PdfaExtensionHelper.check_namespace_declaration(attr, object)


def test_check_namespace_declaration_missing_value_is_noop() -> None:
    class _Stub:
        value = None
        namespaceURI = None
        localName = "p"

    PdfaExtensionHelper.check_namespace_declaration(_Stub(), object)


# ---------------------------------------------------------------------------
# require_non_null — callable supplier + plain string.
# ---------------------------------------------------------------------------


def test_require_non_null_callable_supplier_raises_with_supplied_text() -> None:
    invoked: list[bool] = []

    def supplier() -> str:
        invoked.append(True)
        return "missing field"

    with pytest.raises(OSError, match="missing field"):
        PdfaExtensionHelper.require_non_null(None, supplier)
    assert invoked == [True]


def test_require_non_null_plain_string_message() -> None:
    with pytest.raises(OSError, match="no value"):
        PdfaExtensionHelper.require_non_null(None, "no value")


def test_require_non_null_value_present_is_noop() -> None:
    PdfaExtensionHelper.require_non_null("anything", "should not raise")
    PdfaExtensionHelper.require_non_null(0, "zero is non-null")
    PdfaExtensionHelper.require_non_null("", "empty string is non-null")
    PdfaExtensionHelper.require_non_null(False, "False is non-null")


# ---------------------------------------------------------------------------
# Class-level constants are exposed on the class for upstream parity.
# ---------------------------------------------------------------------------


def test_class_level_constants_match_module_level() -> None:
    assert PdfaExtensionHelper.CLOSED_CHOICE == CLOSED_CHOICE
    assert PdfaExtensionHelper.CLOSED_CHOICE_U == CLOSED_CHOICE_U
    assert PdfaExtensionHelper.OPEN_CHOICE == OPEN_CHOICE
    assert PdfaExtensionHelper.OPEN_CHOICE_U == OPEN_CHOICE_U


# ---------------------------------------------------------------------------
# Stub population helpers — parity surface no-ops.
# ---------------------------------------------------------------------------


def test_populate_pdfa_schema_type_stub_does_not_raise() -> None:
    PdfaExtensionHelper.populate_pdfa_schema_type(None, None, None, False)


def test_populate_pdfa_property_type_stub_does_not_raise() -> None:
    PdfaExtensionHelper.populate_pdfa_property_type(None, None, None)


def test_populate_pdfa_type_stub_does_not_raise() -> None:
    PdfaExtensionHelper.populate_pdfa_type(None, None, None)


def test_populate_pdfa_field_type_stub_does_not_raise() -> None:
    PdfaExtensionHelper.populate_pdfa_field_type(None, None)
