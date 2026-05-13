"""Tests for :class:`StringPane` and :func:`get_text_string`."""

from __future__ import annotations

from pypdfbox.cos import COSString
from pypdfbox.debugger.stringpane.string_pane import StringPane, get_text_string


def test_printable_ascii_returns_decoded_string() -> None:
    cos = COSString("hello world")
    assert get_text_string(cos) == "hello world"


def test_tab_newline_cr_are_preserved() -> None:
    cos = COSString("a\tb\nc\rd")
    assert get_text_string(cos) == "a\tb\nc\rd"


def test_unprintable_control_falls_back_to_hex() -> None:
    cos = COSString(b"hi\x01there")
    result = get_text_string(cos)
    assert result.startswith("<") and result.endswith(">")
    # The hex form should round-trip the bytes.
    assert result.strip("<>").lower() == cos.to_hex_string().lower()


def test_string_pane_creates_two_tabs(tk_root) -> None:
    cos = COSString("hello")
    pane = StringPane(tk_root, cos)
    assert len(pane.get_pane().tabs()) == 2


def test_string_pane_text_tab_shows_decoded_string(tk_root) -> None:
    cos = COSString("decoded")
    pane = StringPane(tk_root, cos)
    body = pane.text.get("1.0", "end-1c")
    assert body == "decoded"


def test_string_pane_text_tab_disabled_for_readonly(tk_root) -> None:
    cos = COSString("abc")
    pane = StringPane(tk_root, cos)
    assert str(pane.text.cget("state")) == "disabled"


def test_string_pane_unprintable_string_shows_hex(tk_root) -> None:
    cos = COSString(b"\x01\x02\x03")
    pane = StringPane(tk_root, cos)
    body = pane.text.get("1.0", "end-1c")
    assert body.startswith("<")
