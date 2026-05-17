"""Coverage-boost for ``pypdfbox.util.xml_util`` (wave 1320).

Targets:

* ``_read_all`` — the stream-read branch (line 21).
* ``XMLUtil.parse`` — DOCTYPE rejection (line 44), the generic exception
  wrap that re-raises as :class:`OSError` (lines 51-54).
* ``XMLUtil.get_node_value`` — element + non-text children mix.

The defusedxml fallback (line 48) is unreachable on this dev machine
(``defusedxml`` is not installed) and is documented as such; the test
file does not attempt to install it.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.util.xml_util import XMLUtil, _read_all

# --------------------------------------------------------------- _read_all


def test_read_all_accepts_bytes() -> None:
    assert _read_all(b"<a/>") == b"<a/>"


def test_read_all_accepts_bytearray() -> None:
    assert _read_all(bytearray(b"<a/>")) == b"<a/>"


def test_read_all_reads_stream() -> None:
    """Stream branch — line 21."""
    stream = io.BytesIO(b"<root/>")
    assert _read_all(stream) == b"<root/>"


# --------------------------------------------------------------- parse


def test_parse_accepts_bytes_input() -> None:
    doc = XMLUtil.parse(b"<root/>")
    assert doc.documentElement.tagName == "root"


def test_parse_accepts_stream_input() -> None:
    doc = XMLUtil.parse(io.BytesIO(b"<root/>"))
    assert doc.documentElement.tagName == "root"


def test_parse_rejects_doctype_declaration() -> None:
    """Line 44 — DOCTYPE rejection raises ``OSError`` before parse."""
    data = b"<!DOCTYPE root SYSTEM 'http://example.com/x.dtd'><root/>"
    with pytest.raises(OSError, match="DOCTYPE"):
        XMLUtil.parse(data)


def test_parse_rejects_doctype_lowercase() -> None:
    data = b"<!doctype root><root/>"
    with pytest.raises(OSError, match="DOCTYPE"):
        XMLUtil.parse(data)


def test_parse_doctype_check_uses_head_only() -> None:
    """The DOCTYPE guard inspects only the first 2 KiB. A document with
    no DOCTYPE in the head is allowed through to the underlying parser."""
    payload = b" " * 2100 + b"<root/>"
    doc = XMLUtil.parse(payload)
    assert doc.documentElement.tagName == "root"


def test_parse_wraps_parse_failure_as_oserror() -> None:
    """Lines 53-54 — anything not OSError gets wrapped in OSError."""
    with pytest.raises(OSError):
        XMLUtil.parse(b"<not-well-formed")


def test_parse_oserror_re_raised_unchanged() -> None:
    """Lines 51-52 — OSError propagates without re-wrap."""

    class _RaisingStream:
        def read(self) -> bytes:
            raise OSError("stream read failure")

    with pytest.raises(OSError, match="stream read failure"):
        XMLUtil.parse(_RaisingStream())  # type: ignore[arg-type]


def test_parse_round_trip_preserves_root_attribute() -> None:
    doc = XMLUtil.parse(b'<root attr="value"><child/></root>')
    root = doc.documentElement
    assert root.getAttribute("attr") == "value"
    assert root.childNodes[0].tagName == "child"


def test_constructor_raises_type_error() -> None:
    """Utility class — direct construction is forbidden."""
    with pytest.raises(TypeError):
        XMLUtil()


# --------------------------------------------------------------- get_node_value


def test_get_node_value_concatenates_text_children() -> None:
    doc = XMLUtil.parse(b"<root>hello world</root>")
    assert XMLUtil.get_node_value(doc.documentElement) == "hello world"


def test_get_node_value_ignores_non_text_children() -> None:
    """Element children are skipped — only direct TEXT_NODE children
    contribute to the concatenated result."""
    doc = XMLUtil.parse(b"<root>hi<child>nested</child>!</root>")
    # The 'nested' text is one level deeper and must NOT show up.
    assert XMLUtil.get_node_value(doc.documentElement) == "hi!"


def test_get_node_value_empty_element_returns_empty_string() -> None:
    doc = XMLUtil.parse(b"<root/>")
    assert XMLUtil.get_node_value(doc.documentElement) == ""
