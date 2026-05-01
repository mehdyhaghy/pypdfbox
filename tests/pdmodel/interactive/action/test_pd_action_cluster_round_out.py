"""Round-out parity tests for the action cluster covering small gaps
relative to upstream PDFBox: ``PDActionGoTo#setDestination`` validation,
``PDActionURI#getURI`` UTF-8 fallback, and ``PDActionJavaScript`` string
constructor."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull, COSString
from pypdfbox.pdmodel.interactive.action import (
    PDActionGoTo,
    PDActionJavaScript,
    PDActionURI,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_xyz_destination import (
    PDPageXYZDestination,
)

_URI: COSName = COSName.get_pdf_name("URI")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_JS: COSName = COSName.get_pdf_name("JS")


# ---------------------------------------------------------------------------
# PDActionGoTo.set_destination — page-dictionary validation
# ---------------------------------------------------------------------------


def test_set_destination_with_page_dict_target_succeeds() -> None:
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    page = COSDictionary()
    page.set_name(COSName.TYPE, "Page")
    dest.set_page(page)

    action.set_destination(dest)

    assert action.get_destination() is not None


def test_set_destination_rejects_non_dict_page_target() -> None:
    """Mirror of upstream ``IllegalArgumentException`` when the first array
    element is not a page dictionary."""
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    arr = dest.get_cos_object()
    # Corrupt the array: first element must be a page dictionary, not COSNull.
    arr.set(0, COSNull.NULL)

    with pytest.raises(ValueError, match="page dictionary"):
        action.set_destination(dest)


def test_set_destination_named_string_unchanged() -> None:
    """String-form named destinations bypass page-dict validation."""
    action = PDActionGoTo()
    action.set_destination("MySection")

    assert action.get_destination() == "MySection"


# ---------------------------------------------------------------------------
# PDActionURI.get_uri — UTF-8 fallback (no BOM) parity with upstream
# ---------------------------------------------------------------------------


def test_get_uri_decodes_utf8_when_no_bom() -> None:
    """Upstream ``PDActionURI.getURI()`` decodes a non-BOM ``COSString``
    body as UTF-8 (not PDFDocEncoding)."""
    action = PDActionURI()
    cos = action.get_cos_object()
    cos.set_item(_URI, COSString(b"https://example.com/caf\xc3\xa9"))

    assert action.get_uri() == "https://example.com/café"


def test_get_uri_decodes_utf16_be_with_bom() -> None:
    action = PDActionURI()
    cos = action.get_cos_object()
    payload = "https://example.com/é".encode("utf-16-be")
    cos.set_item(_URI, COSString(b"\xfe\xff" + payload))

    assert action.get_uri() == "https://example.com/é"


def test_get_uri_returns_none_when_entry_absent() -> None:
    action = PDActionURI()
    assert action.get_uri() is None


def test_get_uri_returns_none_when_entry_is_not_string() -> None:
    action = PDActionURI()
    action.get_cos_object().set_item(_URI, COSArray())
    assert action.get_uri() is None


# ---------------------------------------------------------------------------
# PDActionJavaScript — string constructor overload
# ---------------------------------------------------------------------------


def test_javascript_string_constructor_writes_js_entry() -> None:
    """Mirror of upstream ``PDActionJavaScript(String js)``."""
    action = PDActionJavaScript("app.alert('hi');")

    assert action.get_sub_type() == "JavaScript"
    assert action.get_action() == "app.alert('hi');"
    assert action.get_cos_object().contains_key(_JS)


def test_javascript_no_arg_constructor_does_not_set_js() -> None:
    action = PDActionJavaScript()
    assert action.get_sub_type() == "JavaScript"
    assert not action.get_cos_object().contains_key(_JS)


def test_javascript_dict_constructor_preserves_existing_entry() -> None:
    raw = COSDictionary()
    raw.set_string(_JS, "console.log(1);")
    action = PDActionJavaScript(raw)

    assert action.get_action() == "console.log(1);"
