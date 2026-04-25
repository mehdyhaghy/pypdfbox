"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/UnmodifiableCOSDictionaryTest.java

pypdfbox does not yet ship ``COSDictionary.as_unmodifiable_dictionary()``;
the read-only view is part of the pdmodel hardening pass that lands with
the catalog/page-tree work. Tests are kept here as skipped placeholders.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_unmodifiable_cos_dictionary() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_item() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_boolean() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_name() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_date() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_embedded_date() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_string() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_embedded_string() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_int() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_embedded_int() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_long() -> None:
    pass


@pytest.mark.skip(reason="as_unmodifiable_dictionary not yet implemented")
def test_set_float() -> None:
    pass
