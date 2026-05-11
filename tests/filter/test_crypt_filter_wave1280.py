"""Tests for :class:`CryptFilter`."""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import CryptFilter


class TestCryptFilterDecode:
    def test_decode_no_name_is_passthrough(self) -> None:
        cf = CryptFilter()
        src = io.BytesIO(b"plain bytes")
        dst = io.BytesIO()
        cf.decode(src, dst, COSDictionary(), 0)
        assert dst.getvalue() == b"plain bytes"

    def test_decode_identity_name_is_passthrough(self) -> None:
        cf = CryptFilter()
        params = COSDictionary()
        params.set_item("Name", COSName.get_pdf_name("Identity"))
        src = io.BytesIO(b"more bytes")
        dst = io.BytesIO()
        cf.decode(src, dst, params, 0)
        assert dst.getvalue() == b"more bytes"

    def test_decode_unknown_name_raises(self) -> None:
        cf = CryptFilter()
        params = COSDictionary()
        params.set_item("Name", COSName.get_pdf_name("StdCF"))
        with pytest.raises(OSError):
            cf.decode(io.BytesIO(b"x"), io.BytesIO(), params, 0)

    def test_decode_returns_decode_result(self) -> None:
        cf = CryptFilter()
        result = cf.decode(io.BytesIO(b"abc"), io.BytesIO(), COSDictionary(), 0)
        assert result is not None
        assert result.get_parameters() is not None


class TestCryptFilterEncode:
    def test_encode_no_name_passthrough(self) -> None:
        cf = CryptFilter()
        src = io.BytesIO(b"raw bytes")
        dst = io.BytesIO()
        cf.encode(src, dst, COSDictionary())
        assert dst.getvalue() == b"raw bytes"

    def test_encode_identity_passthrough(self) -> None:
        cf = CryptFilter()
        params = COSDictionary()
        params.set_item("Name", COSName.get_pdf_name("Identity"))
        src = io.BytesIO(b"more raw bytes")
        dst = io.BytesIO()
        cf.encode(src, dst, params)
        assert dst.getvalue() == b"more raw bytes"

    def test_encode_unknown_name_raises(self) -> None:
        cf = CryptFilter()
        params = COSDictionary()
        params.set_item("Name", COSName.get_pdf_name("StdCF"))
        with pytest.raises(OSError):
            cf.encode(io.BytesIO(b"x"), io.BytesIO(), params)
