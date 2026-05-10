"""Wave 1275 parity test: FDFField.escape_xml public static helper."""

from __future__ import annotations

from pypdfbox.pdmodel.fdf.fdf_field import FDFField


def test_escape_xml_handles_standard_xml_specials() -> None:
    assert FDFField.escape_xml("<&>'\"") == "&lt;&amp;&gt;&apos;&quot;"


def test_escape_xml_emits_numeric_entity_for_non_ascii() -> None:
    # Char codes > 0x7E are emitted as numeric entities (matches upstream).
    assert FDFField.escape_xml("é") == "&#233;"


def test_escape_xml_passes_through_plain_ascii() -> None:
    assert FDFField.escape_xml("hello world 123") == "hello world 123"


def test_escape_xml_module_helper_still_delegates() -> None:
    from pypdfbox.pdmodel.fdf.fdf_field import _escape_xml

    assert _escape_xml("<x>") == FDFField.escape_xml("<x>")
