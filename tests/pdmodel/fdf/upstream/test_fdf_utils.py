"""Upstream-derived tests for ``FDFUtils``.

Translated from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/fdf/FDFUtilsTest.java``
(PDFBox 3.0 branch, PDFBOX-6242) — the XML 1.0 escaping performed by
``FDFUtils.escapeXML10()``.
"""

from pypdfbox.pdmodel.fdf.fdf_utils import FDFUtils


def test_plain_ascii_is_unchanged() -> None:
    value = "Hello World 123"
    assert FDFUtils.escape_xml10(value) == value


def test_empty_string_returns_empty_string() -> None:
    assert FDFUtils.escape_xml10("") == ""


def test_escapes_less_than_sign() -> None:
    assert FDFUtils.escape_xml10("<") == "&lt;"


def test_escapes_greater_than_sign() -> None:
    assert FDFUtils.escape_xml10(">") == "&gt;"


def test_escapes_ampersand() -> None:
    assert FDFUtils.escape_xml10("&") == "&amp;"


def test_escapes_double_quote() -> None:
    assert FDFUtils.escape_xml10('"') == "&quot;"


def test_escapes_single_quote() -> None:
    assert FDFUtils.escape_xml10("'") == "&apos;"


def test_escapes_all_special_characters_in_one_string() -> None:
    value = "<tag attr=\"value\" other='x'>&</tag>"
    expected = (
        "&lt;tag attr=&quot;value&quot; other=&apos;x&apos;&gt;&amp;&lt;/tag&gt;"
    )
    assert FDFUtils.escape_xml10(value) == expected


def test_legal_whitespace_control_characters_pass_through_unescaped() -> None:
    # Tab (0x9), line feed (0xA) and carriage return (0xD) are explicitly
    # legal XML 1.0 characters and are not part of the escaped set.
    value = "line1\tline2\nline3\rline4"
    assert FDFUtils.escape_xml10(value) == value


def test_non_ascii_bmp_character_is_escaped_as_numeric_reference() -> None:
    # 'é' is U+00E9 (233 decimal)
    assert FDFUtils.escape_xml10("café") == "caf&#233;"


def test_multiple_non_ascii_characters_are_each_escaped() -> None:
    # 'é' = 233, 'è' = 232
    assert FDFUtils.escape_xml10("éè") == "&#233;&#232;"


def test_illegal_control_character_is_not_passed_through_raw() -> None:
    # 0x0B (vertical tab) is not a legal XML 1.0 character and must not
    # appear unescaped in the output.
    result = FDFUtils.escape_xml10("a\u000bb")
    assert "\u000b" not in result, (
        "Illegal control character must not appear raw in escaped output"
    )
    assert result == "a�b"


def test_supplementary_character_produces_single_valid_reference() -> None:
    # U+1F600 (GRINNING FACE) is a surrogate pair in Java. It must be escaped
    # as a single reference to its code point (128512), not as two references
    # to the individual (illegal) surrogate values.
    assert FDFUtils.escape_xml10("\U0001f600") == "&#128512;"
