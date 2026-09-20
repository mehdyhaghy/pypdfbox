"""Hand-written cover for ``FDFUtils.escape_xml10`` and its call sites.

PDFBOX-5660 lifted the private ``FDFField.escapeXML`` into ``FDFUtils`` and
wired ``FDFDictionary.writeXML`` / ``FDFField.writeXML`` (including the field
*name*) through it. PDFBOX-6242 then made the escaper XML 1.0 safe: code points
XML 1.0 forbids outright are replaced with U+FFFD instead of being emitted raw
or as an (equally illegal) numeric character reference.
"""

import io
import logging

import pytest

from pypdfbox.pdmodel.fdf import FDFDictionary, FDFField, FDFUtils
from pypdfbox.pdmodel.fdf.fdf_utils import _is_valid_xml10_char

_LOGGER = "pypdfbox.pdmodel.fdf.fdf_utils"


# ---------------------------------------------------------------------------
# XML 1.0 validity classification (upstream's private isValidXML10Char).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code_point",
    [0x9, 0xA, 0xD, 0x20, 0x41, 0xD7FF, 0xE000, 0xFFFD, 0x10000, 0x10FFFF],
    ids=[
        "tab",
        "lf",
        "cr",
        "space",
        "A",
        "last_bmp_before_surrogates",
        "first_after_surrogates",
        "replacement_char",
        "first_supplementary",
        "last_supplementary",
    ],
)
def test_valid_xml10_code_points(code_point: int) -> None:
    assert _is_valid_xml10_char(code_point)


@pytest.mark.parametrize(
    "code_point",
    [0x0, 0x8, 0xB, 0xC, 0xE, 0x1F, 0xD800, 0xDFFF, 0xFFFE, 0xFFFF],
    ids=[
        "nul",
        "backspace",
        "vertical_tab",
        "form_feed",
        "shift_out",
        "unit_separator",
        "first_surrogate",
        "last_surrogate",
        "fffe",
        "ffff",
    ],
)
def test_invalid_xml10_code_points(code_point: int) -> None:
    assert not _is_valid_xml10_char(code_point)


# ---------------------------------------------------------------------------
# escape_xml10 — control characters illegal in XML 1.0.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a\x00b", "a�b"),
        ("a\x08b", "a�b"),
        ("a\x0bb", "a�b"),
        ("a\x0cb", "a�b"),
        ("a\x1fb", "a�b"),
        ("a￾b", "a�b"),
        ("a￿b", "a�b"),
    ],
    ids=["nul", "backspace", "vtab", "formfeed", "us", "fffe", "ffff"],
)
def test_illegal_characters_become_replacement_character(
    value: str, expected: str
) -> None:
    assert FDFUtils.escape_xml10(value) == expected


def test_illegal_characters_are_counted_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert FDFUtils.escape_xml10("\x00\x0b\x0c") == "���"
    assert any(
        "Replaced 3 character(s) invalid in XML 1.0" in record.getMessage()
        for record in caplog.records
    )


def test_clean_input_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        FDFUtils.escape_xml10("clean <text>")
    assert caplog.records == []


def test_escaped_output_is_parseable_xml() -> None:
    """The point of PDFBOX-6242: the result can actually be parsed."""
    from xml.dom.minidom import parseString

    payload = "before\x0bafter & <stuff>"
    xml = f"<value>{FDFUtils.escape_xml10(payload)}</value>"
    doc = parseString(xml)
    assert doc.documentElement.tagName == "value"


def test_replacement_character_itself_survives() -> None:
    # U+FFFD is legal in XML 1.0, so it is escaped as a numeric reference
    # rather than replaced again.
    assert FDFUtils.escape_xml10("�") == "&#65533;"


def test_boundary_characters_are_escaped_not_replaced() -> None:
    assert FDFUtils.escape_xml10("퟿") == "&#55295;"
    assert FDFUtils.escape_xml10("") == "&#57344;"


def test_utils_class_is_not_instantiable() -> None:
    with pytest.raises(TypeError):
        FDFUtils()


# ---------------------------------------------------------------------------
# Call sites.
# ---------------------------------------------------------------------------


def test_fdf_field_escape_xml_delegates_to_utils() -> None:
    assert FDFField.escape_xml("a\x0bb<") == FDFUtils.escape_xml10("a\x0bb<")


def test_module_level_escape_xml_alias_delegates() -> None:
    from pypdfbox.pdmodel.fdf.fdf_field import _escape_xml

    assert _escape_xml("a\x0bb") == "a�b"


def test_field_write_xml_escapes_name_and_value() -> None:
    field = FDFField()
    field.set_partial_field_name("a<b&c")
    field.set_value("x\x0by>")

    out = io.StringIO()
    field.write_xml(out)
    xml = out.getvalue()

    assert '<field name="a&lt;b&amp;c">' in xml
    assert "<value>x�y&gt;</value>" in xml
    assert "\x0b" not in xml


def test_dictionary_write_xml_escapes_file_href() -> None:
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
        PDSimpleFileSpecification,
    )

    fdf_dict = FDFDictionary()
    spec = PDSimpleFileSpecification()
    spec.set_file('a&b"c\x0bd')
    fdf_dict.set_file(spec)

    out = io.StringIO()
    fdf_dict.write_xml(out)
    xml = out.getvalue()

    assert '<f href="a&amp;b&quot;c�d" />' in xml


def test_dictionary_write_xml_skips_f_element_without_file_name() -> None:
    """PDFBOX-5660 also made the ``<f>`` element conditional on a file name."""
    from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
        PDComplexFileSpecification,
    )

    spec = PDComplexFileSpecification()
    assert spec.get_file() is None  # no /F entry
    fdf_dict = FDFDictionary()
    fdf_dict.set_file(spec)

    out = io.StringIO()
    fdf_dict.write_xml(out)
    assert "<f href=" not in out.getvalue()
