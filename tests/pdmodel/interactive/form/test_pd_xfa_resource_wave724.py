from __future__ import annotations

from typing import NoReturn

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSStream, COSString
from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource


def _stream(body: bytes) -> COSStream:
    stream = COSStream()
    stream.set_raw_data(body)
    return stream


def test_get_xfa_packet_ignores_non_text_packet_label() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(7))
    arr.add(_stream(b"<ignored/>"))
    arr.add(COSString("template"))
    arr.add(_stream(b"<template/>"))
    xfa = PDXFAResource(arr)

    assert xfa.get_xfa_packet("datasets") is None
    assert xfa.get_xfa_packet("template") == b"<template/>"


def test_is_dynamic_returns_false_when_bytes_raise_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xfa = PDXFAResource(_stream(b"<unused/>"))

    def raise_os_error() -> NoReturn:
        raise OSError("stream unavailable")

    monkeypatch.setattr(xfa, "get_bytes", raise_os_error)

    assert xfa.is_dynamic() is False


def test_is_dynamic_accepts_template_as_document_root() -> None:
    xfa = PDXFAResource(_stream(b'<template><subform layout="tb"/></template>'))

    assert xfa.is_dynamic() is True


def test_is_dynamic_finds_nested_template_by_tree_scan() -> None:
    body = (
        b"<xdp>"
        b"<wrapper>"
        b"<template><subform layout=\"rl-tb\"/></template>"
        b"</wrapper>"
        b"</xdp>"
    )
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is True


def test_is_dynamic_falls_back_when_template_has_no_subform() -> None:
    body = b"<xdp><template><field name=\"only-field\"/></template></xdp>"
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is False
