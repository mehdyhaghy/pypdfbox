"""Tests for :mod:`pypdfbox.filter.decode_options` and
:mod:`pypdfbox.filter.final_decode_options`.

Mirrors the upstream Java behaviour of ``DecodeOptions`` /
``DecodeOptions.FinalDecodeOptions``.
"""

from __future__ import annotations

import pytest

from pypdfbox.filter import DecodeOptions, FinalDecodeOptions
from pypdfbox.filter.decode_options import Rectangle


class TestDecodeOptionsConstructors:
    def test_default_constructor(self) -> None:
        opts = DecodeOptions()
        assert opts.get_source_region() is None
        assert opts.get_subsampling_x() == 1
        assert opts.get_subsampling_y() == 1
        assert opts.get_subsampling_offset_x() == 0
        assert opts.get_subsampling_offset_y() == 0
        assert opts.is_filter_subsampled() is False

    def test_rectangle_constructor(self) -> None:
        rect = Rectangle(1, 2, 30, 40)
        opts = DecodeOptions(rect)
        assert opts.get_source_region() is rect

    def test_coords_constructor(self) -> None:
        opts = DecodeOptions(1, 2, 30, 40)
        rect = opts.get_source_region()
        assert rect is not None
        assert (rect.x, rect.y, rect.width, rect.height) == (1, 2, 30, 40)

    def test_subsampling_constructor(self) -> None:
        opts = DecodeOptions(3)
        assert opts.get_subsampling_x() == 3
        assert opts.get_subsampling_y() == 3

    def test_invalid_args_raises(self) -> None:
        with pytest.raises(TypeError):
            DecodeOptions(1, 2, 3)  # type: ignore[call-arg]


class TestDecodeOptionsSettersGetters:
    def test_set_get_subsampling(self) -> None:
        opts = DecodeOptions()
        opts.set_subsampling_x(2)
        opts.set_subsampling_y(3)
        opts.set_subsampling_offset_x(4)
        opts.set_subsampling_offset_y(5)
        assert opts.get_subsampling_x() == 2
        assert opts.get_subsampling_y() == 3
        assert opts.get_subsampling_offset_x() == 4
        assert opts.get_subsampling_offset_y() == 5

    def test_set_source_region(self) -> None:
        opts = DecodeOptions()
        rect = Rectangle(0, 0, 100, 200)
        opts.set_source_region(rect)
        assert opts.get_source_region() is rect
        opts.set_source_region(None)
        assert opts.get_source_region() is None

    def test_filter_subsampled_flag(self) -> None:
        opts = DecodeOptions()
        assert not opts.is_filter_subsampled()
        opts.set_filter_subsampled(True)
        assert opts.is_filter_subsampled()


class TestFinalDecodeOptions:
    def test_default_is_filter_subsampled(self) -> None:
        assert DecodeOptions.DEFAULT.is_filter_subsampled() is True

    def test_default_is_immutable_setters_raise(self) -> None:
        d = DecodeOptions.DEFAULT
        with pytest.raises(NotImplementedError):
            d.set_source_region(Rectangle())
        with pytest.raises(NotImplementedError):
            d.set_subsampling_x(2)
        with pytest.raises(NotImplementedError):
            d.set_subsampling_y(2)
        with pytest.raises(NotImplementedError):
            d.set_subsampling_offset_x(1)
        with pytest.raises(NotImplementedError):
            d.set_subsampling_offset_y(1)

    def test_default_set_filter_subsampled_silently_ignored(self) -> None:
        d = DecodeOptions.DEFAULT
        d.set_filter_subsampled(False)
        # Still True — the setter is a no-op.
        assert d.is_filter_subsampled() is True

    def test_is_final_decode_options(self) -> None:
        # DEFAULT is constructed as a FinalDecodeOptions instance.
        assert isinstance(DecodeOptions.DEFAULT, FinalDecodeOptions)
