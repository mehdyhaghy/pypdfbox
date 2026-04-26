from __future__ import annotations

from pypdfbox.cos import COSArray, COSStream, COSString
from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource


def _stream(body: bytes) -> COSStream:
    s = COSStream()
    s.set_raw_data(body)
    return s


def test_get_bytes_from_cos_stream() -> None:
    body = b"<xfa>...</xfa>"
    xfa = PDXFAResource(_stream(body))

    assert xfa.get_bytes() == body
    assert xfa.get_cos_object().__class__.__name__ == "COSStream"


def test_get_bytes_from_tagged_packet_array() -> None:
    arr = COSArray()
    arr.add(COSString("preamble"))
    arr.add(_stream(b"<a/>"))
    arr.add(COSString("config"))
    arr.add(_stream(b"<b/>"))

    xfa = PDXFAResource(arr)

    assert xfa.get_bytes() == b"<a/><b/>"
    assert xfa.get_cos_object() is arr


def test_get_bytes_returns_empty_for_unsupported_cos_type() -> None:
    xfa = PDXFAResource(COSString("just a string"))
    assert xfa.get_bytes() == b""


def test_is_dynamic_detects_marker() -> None:
    xfa = PDXFAResource(_stream(b'<xdp:xdp xmlns:xdp="..."><xfa:datasets/></xdp:xdp>'))
    assert xfa.is_dynamic() is True


def test_is_dynamic_false_for_plain_payload() -> None:
    xfa = PDXFAResource(_stream(b"<plain/>"))
    assert xfa.is_dynamic() is False


def test_is_dynamic_false_for_empty_xfa() -> None:
    xfa = PDXFAResource(COSArray())
    assert xfa.is_dynamic() is False
