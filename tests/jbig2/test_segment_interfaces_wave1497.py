"""Behavioural tests for the JBIG2 abstract segment interfaces.

``SegmentData``, ``Region`` and ``Dictionary`` are ports of upstream Java
interfaces. Each declares abstract methods whose bodies ``raise
NotImplementedError`` — the standard ABC pattern for "interface method with no
default". These pin (a) that the bases cannot be instantiated and (b) that a
subclass delegating to ``super()`` hits the NotImplementedError body, matching
the upstream "abstract / interface" contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.dictionary import Dictionary
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segment_data import SegmentData


def test_segment_data_is_abstract():
    with pytest.raises(TypeError):
        SegmentData()  # type: ignore[abstract]


def test_region_is_abstract():
    with pytest.raises(TypeError):
        Region()  # type: ignore[abstract]


def test_dictionary_is_abstract():
    with pytest.raises(TypeError):
        Dictionary()  # type: ignore[abstract]


def test_region_extends_segment_data():
    assert issubclass(Region, SegmentData)


def test_dictionary_extends_segment_data():
    assert issubclass(Dictionary, SegmentData)


def test_segment_data_init_super_raises_not_implemented():
    class _Concrete(SegmentData):
        def init(self, header, sis):  # type: ignore[override]
            return super().init(header, sis)

    with pytest.raises(NotImplementedError):
        _Concrete().init(None, None)


def test_region_super_methods_raise_not_implemented():
    class _Concrete(Region):
        def init(self, header, sis):  # type: ignore[override]
            return None

        def get_region_bitmap(self):  # type: ignore[override]
            return super().get_region_bitmap()

        def get_region_info(self):  # type: ignore[override]
            return super().get_region_info()

    region = _Concrete()
    with pytest.raises(NotImplementedError):
        region.get_region_bitmap()
    with pytest.raises(NotImplementedError):
        region.get_region_info()


def test_dictionary_super_method_raises_not_implemented():
    class _Concrete(Dictionary):
        def init(self, header, sis):  # type: ignore[override]
            return None

        def get_dictionary(self):  # type: ignore[override]
            return super().get_dictionary()

    with pytest.raises(NotImplementedError):
        _Concrete().get_dictionary()


def test_input_stream_factory_super_method_raises_not_implemented():
    from pypdfbox.jbig2.io.input_stream_factory import InputStreamFactory

    class _Concrete(InputStreamFactory):
        def get_input_stream(self, is_):  # type: ignore[override]
            return super().get_input_stream(is_)

    with pytest.raises(NotImplementedError):
        _Concrete().get_input_stream(b"\x00")
