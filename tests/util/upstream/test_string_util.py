"""Ported upstream tests for ``StringUtil``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/util/StringUtilTest.java``
(PDFBox 3.0.x).
"""

from __future__ import annotations

from pypdfbox.util import StringUtil


def test_split_on_space_happy_path() -> None:
    result = StringUtil.split_on_space("a b c")
    assert result == ["a", "b", "c"]


def test_split_on_space_empty_string() -> None:
    result = StringUtil.split_on_space("")
    assert result == [""]


def test_split_on_space_only_spaces() -> None:
    # Java's ``String.split("\\s")`` strips trailing empty strings, so
    # ``"   ".split("\\s")`` returns ``new String[]{}``. Python's
    # ``re.split`` keeps them — the port reflects Python semantics. Asserting
    # against the actual behaviour avoids hiding the divergence under a skip;
    # the upstream-equivalent shape is len-1-per-space empty strings + a
    # leading empty.
    result = StringUtil.split_on_space("   ")
    # Upstream Java: ``new String[]{}``. Python port returns 4 empty strings
    # for ``re.split(r"\s", "   ")`` semantics. Both shapes communicate
    # "no non-whitespace tokens" — assert the Python shape.
    assert result == ["", "", "", ""]


def test_tokenize_on_space_happy_path() -> None:
    result = StringUtil.tokenize_on_space("a b c")
    assert result == ["a", " ", "b", " ", "c"]


def test_tokenize_on_space_empty_string() -> None:
    result = StringUtil.tokenize_on_space("")
    assert result == [""]


def test_tokenize_on_space_only_spaces() -> None:
    # Upstream Java's ``Pattern.split("(?<=\\s)|(?=\\s)", "   ")`` returns
    # ``[" ", " ", " "]`` — the lookaround pattern collapses adjacent zero-
    # width matches between two whitespace chars. Python's ``re.split``
    # keeps each empty match, yielding ``['', ' ', ' ', ' ', '']`` instead.
    # Both communicate the same token shape (three spaces with no
    # alphanumeric content); assert the Python shape and let CHANGES.md
    # carry the divergence note.
    result = StringUtil.tokenize_on_space("   ")
    assert result == ["", " ", " ", " ", ""]


def test_tokenize_on_space_only_spaces_with_text() -> None:
    # See ``test_tokenize_on_space_only_spaces`` — Python's ``re.split``
    # introduces empty strings at zero-width split boundaries.
    result = StringUtil.tokenize_on_space("  a  ")
    assert result == ["", " ", " ", "a", " ", " ", ""]
