"""Wave 1272: parity coverage for ``PDXFAResource`` upstream-named static
helpers ``get_bytes_from_packet`` / ``get_bytes_from_stream``."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSStream, COSString
from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource


def _stream(body: bytes) -> COSStream:
    stream = COSStream()
    stream.set_raw_data(body)
    return stream


def test_get_bytes_from_stream_returns_decoded_body() -> None:
    stream = _stream(b"<xdp:xdp/>")
    assert PDXFAResource.get_bytes_from_stream(stream) == b"<xdp:xdp/>"


def test_get_bytes_from_packet_concatenates_stream_halves() -> None:
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(_stream(b"<template/>"))
    arr.add(COSString("datasets"))
    arr.add(_stream(b"<datasets/>"))
    assert PDXFAResource.get_bytes_from_packet(arr) == b"<template/><datasets/>"


def test_get_bytes_from_packet_skips_non_stream_entries() -> None:
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(COSString("not-a-stream"))  # ignored — wrong type at odd index
    arr.add(COSString("datasets"))
    arr.add(_stream(b"<datasets/>"))
    assert PDXFAResource.get_bytes_from_packet(arr) == b"<datasets/>"


def test_get_bytes_uses_public_helpers() -> None:
    """The instance accessor delegates to the public static helpers so the
    public spelling is reachable from a real-world XFA payload."""
    stream = _stream(b"<form/>")
    res = PDXFAResource(stream)
    assert res.get_bytes() == PDXFAResource.get_bytes_from_stream(stream)
