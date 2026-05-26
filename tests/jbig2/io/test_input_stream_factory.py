from __future__ import annotations

import io

import pytest

from pypdfbox.jbig2.io.default_input_stream_factory import DefaultInputStreamFactory
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.input_stream_factory import InputStreamFactory


def test_default_factory_is_input_stream_factory() -> None:
    assert issubclass(DefaultInputStreamFactory, InputStreamFactory)


def test_input_stream_factory_is_abstract() -> None:
    with pytest.raises(TypeError):
        InputStreamFactory()  # cannot instantiate abstract base


def test_wraps_bytes() -> None:
    factory = DefaultInputStreamFactory()
    iis = factory.get_input_stream(b"\xde\xad\xbe\xef")
    assert isinstance(iis, ImageInputStream)
    assert iis.read_unsigned_int() == 0xDEADBEEF


def test_wraps_file_like() -> None:
    factory = DefaultInputStreamFactory()
    iis = factory.get_input_stream(io.BytesIO(b"\x01\x02\x03"))
    assert isinstance(iis, ImageInputStream)
    assert iis.length() == 3


def test_custom_factory_subclass() -> None:
    class _Factory(InputStreamFactory):
        def get_input_stream(self, is_):  # type: ignore[override]
            return ImageInputStream(bytes(is_))

    iis = _Factory().get_input_stream(b"\xaa")
    assert iis.read_unsigned_byte() == 0xAA
