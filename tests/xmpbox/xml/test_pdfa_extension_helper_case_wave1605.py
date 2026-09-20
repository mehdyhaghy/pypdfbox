"""PDFBOX-6257 — the PDF/A extension "closed/open choice of" prefix check is
case-insensitive.

Upstream carried two constants per prefix (``"closed Choice of "`` and
``"Closed Choice of "``) and tested both with ``startsWith``; any other casing
slipped through and left the prefix glued to the value type. It now lower-cases
the value type once and tests a single lower-case constant.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.xml import pdfa_extension_helper as helper_mod
from pypdfbox.xmpbox.xml.pdfa_extension_helper import PdfaExtensionHelper


@pytest.mark.parametrize(
    "prefix",
    [
        "closed Choice of ",
        "Closed Choice of ",
        "closed choice of ",
        "CLOSED CHOICE OF ",
        "cLoSeD ChOiCe Of ",
    ],
    ids=["upstream_lower", "upstream_upper", "all_lower", "all_upper", "mixed"],
)
def test_closed_choice_prefix_stripped_regardless_of_case(prefix: str) -> None:
    assert PdfaExtensionHelper.transform_value_type(None, prefix + "Text") == "Text"


@pytest.mark.parametrize(
    "prefix",
    [
        "open Choice of ",
        "Open Choice of ",
        "open choice of ",
        "OPEN CHOICE OF ",
        "oPeN ChOiCe Of ",
    ],
    ids=["upstream_lower", "upstream_upper", "all_lower", "all_upper", "mixed"],
)
def test_open_choice_prefix_stripped_regardless_of_case(prefix: str) -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, prefix + "Integer") == "Integer"
    )


def test_remainder_keeps_its_original_case() -> None:
    """Only the prefix is matched case-insensitively; the payload is sliced
    out of the *original* string, so its casing survives."""
    assert (
        PdfaExtensionHelper.transform_value_type(None, "CLOSED CHOICE OF GpsCoord")
        == "GpsCoord"
    )


def test_value_type_without_prefix_passes_through() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, "Choice of Text") == (
        "Choice of Text"
    )
    assert PdfaExtensionHelper.transform_value_type(None, "Text") == "Text"


def test_partial_prefix_is_not_stripped() -> None:
    assert (
        PdfaExtensionHelper.transform_value_type(None, "closed Choice ofText")
        == "closed Choice ofText"
    )


def test_non_string_input_returns_none() -> None:
    assert PdfaExtensionHelper.transform_value_type(None, None) is None  # type: ignore[arg-type]
    assert PdfaExtensionHelper.transform_value_type(None, 42) is None  # type: ignore[arg-type]


def test_prefix_constants_are_lower_case_and_private() -> None:
    assert helper_mod._CLOSED_CHOICE == "closed choice of "
    assert helper_mod._OPEN_CHOICE == "open choice of "
    # PDFBOX-6257 dropped the public/cased variants.
    for removed in ("CLOSED_CHOICE", "CLOSED_CHOICE_U", "OPEN_CHOICE", "OPEN_CHOICE_U"):
        assert not hasattr(helper_mod, removed)
        assert not hasattr(PdfaExtensionHelper, removed)
