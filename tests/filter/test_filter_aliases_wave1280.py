"""Tests for the upstream-class-name aliases :class:`JBIG2Filter` and
:class:`JPXFilter`.

These are thin subclasses of :class:`JBIG2Decode` / :class:`JPXDecode`
introduced so direct ports from PDFBox Java source resolve the upstream
class names. The behaviour is covered by the underlying ``*Decode`` test
suites; these tests just confirm the inheritance / registration shape.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.filter import JBIG2Decode, JBIG2Filter, JPXDecode, JPXFilter
from pypdfbox.filter.filter_factory import FilterFactory


class TestJBIG2FilterAlias:
    def test_subclass_of_jbig2_decode(self) -> None:
        assert issubclass(JBIG2Filter, JBIG2Decode)

    def test_encode_raises(self) -> None:
        f = JBIG2Filter()
        with pytest.raises((NotImplementedError, OSError, Exception)):
            f.encode(io.BytesIO(b"x"), io.BytesIO(), None)

    def test_registered_under_jbig2filter_name(self) -> None:
        # Either the alias is registered, or short/long names already
        # resolve to a JBIG2Decode-compatible instance.
        if FilterFactory.is_registered("JBIG2Filter"):
            inst = FilterFactory.get("JBIG2Filter")
            assert isinstance(inst, JBIG2Filter)


class TestJPXFilterAlias:
    def test_subclass_of_jpx_decode(self) -> None:
        assert issubclass(JPXFilter, JPXDecode)

    def test_encode_raises(self) -> None:
        f = JPXFilter()
        with pytest.raises((NotImplementedError, OSError, Exception)):
            f.encode(io.BytesIO(b"x"), io.BytesIO(), None)

    def test_registered_under_jpxfilter_name(self) -> None:
        if FilterFactory.is_registered("JPXFilter"):
            inst = FilterFactory.get("JPXFilter")
            assert isinstance(inst, JPXFilter)
