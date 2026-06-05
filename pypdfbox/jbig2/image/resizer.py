"""Port of the JBIG2 filtered-zoom resampling pipeline.

Consolidates the upstream classes ``ParameterizedFilter``, ``Weighttab``,
``Scanline`` (its reachable ``BitmapScanline`` subclass) and ``Resizer`` from
``org.apache.pdfbox.jbig2.image``. Upstream splits them across one file each;
they are co-located here because, for the JBIG2 reader path, the *only*
``Scanline`` ever instantiated is ``BitmapScanline`` (a ``Bitmap`` source into a
single-band ``TYPE_BYTE`` raster). The other ``Scanline`` subclasses
(``ByteBGRScanline`` / ``IntegerSinglePixelPackedScanline`` /
``GenericRasterScanline``) are only used by upstream's generic ``ImageBridge``
which is not part of the JBIG2 read surface and so is not ported.

This implements the Schumacher "filtered zoom" resampler (Graphics Gems III). A
destination raster is produced by convolving the (inverted, bilevel-as-grayscale)
source with a separable resampling kernel in x and y. The output is an 8-bit
grayscale, single-band raster — modelled here as :class:`_Raster`, a row-major
``bytearray`` mirroring the ``DataBufferByte`` of upstream's interleaved
``TYPE_BYTE`` raster.

Java ``int`` arithmetic wraps at 32 bits and ``>>`` is an arithmetic shift; the
accumulator sums here can exceed 31 bits, so the relevant intermediate sums are
masked to a signed 32-bit value via :func:`_int32` before the arithmetic shift,
exactly reproducing the Java overflow/sign behaviour.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.filter import Filter, Point
from pypdfbox.jbig2.util import utils

_EPSILON = 1e-7
_SHORT_MIN = -32768
_SHORT_MAX = 32767


def _int32(value: int) -> int:
    """Wrap ``value`` to a signed 32-bit Java ``int``."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


def _arith_shift_right(value: int, count: int) -> int:
    """Java ``int >> count`` — arithmetic shift on a 32-bit signed value."""
    return _int32(value) >> count


class _Raster:
    """Single-band, row-major 8-bit raster (the ``DataBufferByte`` analogue).

    Mirrors the destination ``WritableRaster`` created via
    ``Raster.createInterleavedRaster(TYPE_BYTE, w, h, 1, ...)``: one byte per
    pixel, laid out row-major. Only the subset the resizer uses
    (``set_samples`` of a full scanline, ``get_data`` of the whole buffer) is
    implemented.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.data = bytearray(width * height)

    def set_samples(self, x: int, y: int, length: int, values: list[int]) -> None:
        base = y * self.width + x
        for i in range(length):
            self.data[base + i] = values[i] & 0xFF

    def get_data(self) -> bytes:
        return bytes(self.data)


class ParameterizedFilter:
    """Mirror ``org.apache.pdfbox.jbig2.image.ParameterizedFilter``."""

    def __init__(
        self,
        f: Filter,
        scale: float,
        support: float | None = None,
        width: int | None = None,
    ) -> None:
        self.filter = f
        if support is None:
            # ParameterizedFilter(Filter, double)
            # find scale of filter in a space (source space): when minifying,
            # ascale=1/scale, when magnifying, ascale=1
            self.scale = f.blur * max(1.0, 1.0 / scale)
            # find support radius of scaled filter; if <= .5 then point sampling
            self.support = max(0.5, self.scale * f.support)
            self.width = int(_ceil_double(2.0 * self.support))
        else:
            # ParameterizedFilter(Filter, double, double, int)
            self.scale = scale
            self.support = support
            self.width = width

    def eval(self, center: float, i: int) -> float:
        return self.filter.f_windowed((i + 0.5 - center) / self.scale)

    def min_index(self, center: float) -> int:
        return utils.floor(center - self.support)

    def max_index(self, center: float) -> int:
        return utils.ceil(center + self.support)


def _ceil_double(x: float) -> float:
    """``Math.ceil`` — used only for the (double) filter width computation."""
    import math

    return math.ceil(x)


class Weighttab:
    """Mirror ``org.apache.pdfbox.jbig2.image.Weighttab``.

    Samples the continuous filter, scaled and positioned at ``center``, over the
    clamped source range and normalises the integer weights so they sum to
    ``weight_one``.
    """

    def __init__(
        self,
        pf: ParameterizedFilter,
        weight_one: int,
        center: float,
        a0: int,
        a1: int,
        trimzeros: bool,
    ) -> None:
        i0 = max(pf.min_index(center), a0)
        i1 = min(pf.max_index(center), a1)

        # find scale factor to normalise the filter
        den = 0.0
        for i in range(i0, i1 + 1):
            den += pf.eval(center, i)

        scale = weight_one if den == 0.0 else weight_one / den

        if trimzeros:
            stillzero = trimzeros
            lastnonzero = 0
            for i in range(i0, i1 + 1):
                tr = utils.clamp(scale * pf.eval(center, i), _SHORT_MIN, _SHORT_MAX)
                t = _floor(tr + 0.5)
                if stillzero and t == 0:
                    i0 += 1  # find first nonzero
                else:
                    stillzero = False
                    if t != 0:
                        lastnonzero = i  # find last nonzero
            i1 = max(lastnonzero, i0)

        self.weights = [0] * (i1 - i0 + 1)

        total = 0
        for idx, i in enumerate(range(i0, i1 + 1)):
            tr = utils.clamp(scale * pf.eval(center, i), _SHORT_MIN, _SHORT_MAX)
            t = _floor(tr + 0.5)
            self.weights[idx] = t
            total += t

        if total == 0:
            i1 = i0
            self.weights[0] = weight_one
        elif total != weight_one:
            # fudge the center sample so the weights sum to weight_one exactly
            i = int(center + 0.5)
            if i >= i1:
                i = i1 - 1
            if i < i0:
                i = i0
            t = weight_one - total
            self.weights[i - i0] += t

        self.i0 = i0 - a0
        self.i1 = i1 - a0


def _floor(x: float) -> int:
    """``Math.floor`` cast to int — used for the weight quantisation."""
    import math

    return int(math.floor(x))


class BitmapScanline:
    """Mirror ``org.apache.pdfbox.jbig2.image.BitmapScanline``.

    A bilevel :class:`Bitmap` source fetched (inverted) into an int line buffer,
    convolved horizontally / vertically, and stored into a single-band
    :class:`_Raster` destination.
    """

    def __init__(self, src: Bitmap, dst: _Raster, width: int) -> None:
        self.length = width
        self.bitmap = src
        self.raster = dst
        self.line_buffer = [0] * self.length
        self.y = 0

    def clear(self) -> None:
        self.line_buffer = [0] * self.length

    def fetch(self, x: int, y: int) -> None:
        self.line_buffer = [0] * self.length
        src_byte_idx = self.bitmap.get_byte_index(x, y)
        while x < self.length:
            src_byte = (~self.bitmap.get_byte(src_byte_idx)) & 0xFF
            src_byte_idx += 1
            remaining = self.bitmap.get_width() - x
            bits = 8 if remaining > 8 else remaining
            for bit_position in range(bits - 1, -1, -1):
                if ((src_byte >> bit_position) & 0x1) != 0:
                    self.line_buffer[x] = 255
                x += 1

    def filter(
        self,
        pre_shift: list[int],
        post_shift: list[int],
        tabs: list[Weighttab],
        dst: BitmapScanline,
    ) -> None:
        dst_length = dst.length

        start = 1 << (post_shift[0] - 1)
        src_buffer = self.line_buffer
        dst_buffer = dst.line_buffer

        pre_shift0 = pre_shift[0]
        post_shift0 = post_shift[0]
        dst_index = 0
        if pre_shift0 != 0:
            for tab in range(dst_length):
                weight_tab = tabs[tab]
                weights = len(weight_tab.weights)
                total = start
                weight_index = 0
                src_index = weight_tab.i0
                while weight_index < weights and src_index < len(src_buffer):
                    total = _int32(
                        total
                        + weight_tab.weights[weight_index]
                        * _arith_shift_right(src_buffer[src_index], pre_shift0)
                    )
                    weight_index += 1
                    src_index += 1
                t = _arith_shift_right(total, post_shift0)
                dst_buffer[dst_index] = 0 if t < 0 else (255 if t > 255 else t)
                dst_index += 1
        else:
            for tab in range(dst_length):
                weight_tab = tabs[tab]
                weights = len(weight_tab.weights)
                total = start
                src_index = weight_tab.i0
                weight_index = 0
                while weight_index < weights and src_index < len(src_buffer):
                    total = _int32(
                        total + weight_tab.weights[weight_index] * src_buffer[src_index]
                    )
                    src_index += 1
                    weight_index += 1
                dst_buffer[dst_index] = _arith_shift_right(total, post_shift0)
                dst_index += 1

    def accumulate(self, weight: int, dst: BitmapScanline) -> None:
        src_buffer = self.line_buffer
        dst_buffer = dst.line_buffer
        for b in range(len(dst_buffer)):
            dst_buffer[b] = _int32(dst_buffer[b] + weight * src_buffer[b])

    def shift(self, shift: list[int]) -> None:
        shift0 = shift[0]
        half = 1 << (shift0 - 1)
        src_buffer = self.line_buffer
        for b in range(len(src_buffer)):
            pixel = _arith_shift_right(_int32(src_buffer[b] + half), shift0)
            src_buffer[b] = 0 if pixel < 0 else (255 if pixel > 255 else pixel)

    def store(self, x: int, y: int) -> None:
        self.raster.set_samples(x, y, self.length, self.line_buffer)


class _Mapping:
    """Mirror ``Resizer.Mapping`` (only the single-scale constructor is used)."""

    def __init__(self, scale_x: float) -> None:
        self.scale = scale_x
        self.offset = 0.5
        self.a0 = 0.0
        self.b0 = 0.0

    def map_pixel_center(self, b: int) -> float:
        return (b + self.offset - self.b0) / self.scale + self.a0

    def dst_to_src(self, b: float) -> float:
        return (b - self.b0) / self.scale + self.a0

    def src_to_dst(self, a: float) -> float:
        return (a - self.a0) * self.scale + self.b0


def _is_integer(x: float) -> bool:
    """Mirror ``Resizer.isInteger``."""
    import math

    return abs(x - math.floor(x + 0.5)) < _EPSILON


class Resizer:
    """Mirror ``org.apache.pdfbox.jbig2.image.Resizer`` (filtered zoom)."""

    _WEIGHT_BITS = 14
    _WEIGHT_ONE = 1 << _WEIGHT_BITS
    _BITS_PER_CHANNEL = [8, 8, 8]
    _NO_SHIFT = [0] * 16
    _FINAL_SHIFT = [
        2 * _WEIGHT_BITS - _BITS_PER_CHANNEL[0],
        2 * _WEIGHT_BITS - _BITS_PER_CHANNEL[1],
        2 * _WEIGHT_BITS - _BITS_PER_CHANNEL[2],
    ]

    def __init__(self, scale_x: float, scale_y: float | None = None) -> None:
        if scale_y is None:
            scale_y = scale_x
        self.coerce = True
        self.order = "AUTO"
        self.trim_zeros = True
        self.mapping_x = _Mapping(scale_x)
        self.mapping_y = _Mapping(scale_y)

    def _create_x_weights(
        self,
        src_bounds: tuple[int, int, int, int],
        dst_bounds: tuple[int, int, int, int],
        filter_: ParameterizedFilter,
    ) -> list[Weighttab]:
        src_x0 = src_bounds[0]
        src_x1 = src_bounds[0] + src_bounds[2]
        dst_x0 = dst_bounds[0]
        dst_x1 = dst_bounds[0] + dst_bounds[2]

        tabs: list[Weighttab] = [None] * dst_bounds[2]  # type: ignore[list-item]
        for dst_x in range(dst_x0, dst_x1):
            center = self.mapping_x.map_pixel_center(dst_x)
            tabs[dst_x - dst_x0] = Weighttab(
                filter_, self._WEIGHT_ONE, center, src_x0, src_x1 - 1, self.trim_zeros
            )
        return tabs

    def _simplify_filter(
        self, filter_: ParameterizedFilter, scale: float, offset: float
    ) -> ParameterizedFilter:
        if self.coerce and (
            filter_.support <= 0.5
            or (
                filter_.filter.cardinal
                and _is_integer(1.0 / filter_.scale)
                and _is_integer(1.0 / (scale * filter_.scale))
                and _is_integer((offset / scale - 0.5) / filter_.scale)
            )
        ):
            return ParameterizedFilter(Point(), 1.0, 0.5, 1)
        return filter_

    def _resize_x_first(
        self,
        src: Bitmap,
        src_bounds: tuple[int, int, int, int],
        dst: _Raster,
        dst_bounds: tuple[int, int, int, int],
        x_filter: ParameterizedFilter,
        y_filter: ParameterizedFilter,
    ) -> None:
        buffer = BitmapScanline(src, dst, src_bounds[2])
        accumulator = BitmapScanline(src, dst, dst_bounds[2])
        x_weights = self._create_x_weights(src_bounds, dst_bounds, x_filter)

        y_buffer_size = y_filter.width + 2
        line_buffer: list[BitmapScanline] = []
        for _y in range(y_buffer_size):
            sl = BitmapScanline(src, dst, dst_bounds[2])
            sl.y = -1
            line_buffer.append(sl)

        src_y0 = src_bounds[1]
        src_y1 = src_bounds[1] + src_bounds[3]
        dst_y0 = dst_bounds[1]
        dst_y1 = dst_bounds[1] + dst_bounds[3]

        y_fetched = -1
        for dst_y in range(dst_y0, dst_y1):
            y_weight = Weighttab(
                y_filter,
                self._WEIGHT_ONE,
                self.mapping_y.map_pixel_center(dst_y),
                src_y0,
                src_y1 - 1,
                True,
            )
            accumulator.clear()
            for src_y in range(y_weight.i0, y_weight.i1 + 1):
                src_buffer = line_buffer[src_y % y_buffer_size]
                if src_buffer.y != src_y:
                    src_buffer.y = src_y
                    if src_y0 + src_y <= y_fetched:
                        raise AssertionError(
                            f"Backtracking from line {y_fetched} to {src_y0 + src_y}"
                        )
                    buffer.fetch(src_bounds[0], src_y0 + src_y)
                    y_fetched = src_y0 + src_y
                    buffer.filter(
                        self._NO_SHIFT, self._BITS_PER_CHANNEL, x_weights, src_buffer
                    )
                src_buffer.accumulate(
                    y_weight.weights[src_y - y_weight.i0], accumulator
                )
            accumulator.shift(self._FINAL_SHIFT)
            accumulator.store(dst_bounds[0], dst_y)

    def _resize_y_first(
        self,
        src: Bitmap,
        src_bounds: tuple[int, int, int, int],
        dst: _Raster,
        dst_bounds: tuple[int, int, int, int],
        x_filter: ParameterizedFilter,
        y_filter: ParameterizedFilter,
    ) -> None:
        buffer = BitmapScanline(src, dst, dst_bounds[2])
        accumulator = BitmapScanline(src, dst, src_bounds[2])
        x_weights = self._create_x_weights(src_bounds, dst_bounds, x_filter)

        y_buffer_size = y_filter.width + 2
        line_buffer: list[BitmapScanline] = []
        for _y in range(y_buffer_size):
            sl = BitmapScanline(src, dst, src_bounds[2])
            sl.y = -1
            line_buffer.append(sl)

        src_y0 = src_bounds[1]
        src_y1 = src_bounds[1] + src_bounds[3]
        dst_y0 = dst_bounds[1]
        dst_y1 = dst_bounds[1] + dst_bounds[3]

        y_fetched = -1
        for dst_y in range(dst_y0, dst_y1):
            y_weight = Weighttab(
                y_filter,
                self._WEIGHT_ONE,
                self.mapping_y.map_pixel_center(dst_y),
                src_y0,
                src_y1 - 1,
                True,
            )
            accumulator.clear()
            for src_y in range(y_weight.i0, y_weight.i1 + 1):
                src_buffer = line_buffer[src_y % y_buffer_size]
                if src_buffer.y != src_y:
                    src_buffer.y = src_y
                    if src_y0 + src_y <= y_fetched:
                        raise AssertionError(
                            f"Backtracking from line {y_fetched} to {src_y0 + src_y}"
                        )
                    src_buffer.fetch(src_bounds[0], src_y0 + src_y)
                    y_fetched = src_y0 + src_y
                src_buffer.accumulate(
                    y_weight.weights[src_y - y_weight.i0], accumulator
                )
            accumulator.filter(
                self._BITS_PER_CHANNEL, self._FINAL_SHIFT, x_weights, buffer
            )
            buffer.store(dst_bounds[0], dst_y)

    def resize(
        self,
        src: Bitmap,
        src_bounds: tuple[int, int, int, int],
        dst: _Raster,
        dst_bounds: tuple[int, int, int, int],
        x_filter: Filter,
        y_filter: Filter,
    ) -> None:
        x_filter_p = ParameterizedFilter(x_filter, self.mapping_x.scale)
        y_filter_p = ParameterizedFilter(y_filter, self.mapping_y.scale)

        # find valid destination window (transformed source + support margin)
        x1 = utils.ceil(
            self.mapping_x.src_to_dst(src_bounds[0] - x_filter_p.support) + _EPSILON
        )
        y1 = utils.ceil(
            self.mapping_y.src_to_dst(src_bounds[1] - y_filter_p.support) + _EPSILON
        )
        x2 = utils.floor(
            self.mapping_x.src_to_dst(
                src_bounds[0] + src_bounds[2] + x_filter_p.support
            )
            - _EPSILON
        )
        y2 = utils.floor(
            self.mapping_y.src_to_dst(
                src_bounds[1] + src_bounds[3] + y_filter_p.support
            )
            - _EPSILON
        )
        # Rectangle.setFrameFromDiagonal(x1, y1, x2, y2)
        dst_region = (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

        dst_max_x = dst_bounds[0] + dst_bounds[2]
        dst_max_y = dst_bounds[1] + dst_bounds[3]
        region_max_x = dst_region[0] + dst_region[2]
        region_max_y = dst_region[1] + dst_region[3]
        if (
            dst_bounds[0] < dst_region[0]
            or dst_max_x > region_max_x
            or dst_bounds[1] < dst_region[1]
            or dst_max_y > region_max_y
        ):
            dst_bounds = _intersection(dst_bounds, dst_region)

        if (
            src_bounds[2] <= 0
            or src_bounds[3] <= 0
            or dst_bounds[2] <= 0
            or dst_bounds[3] <= 0
        ):
            return

        x_filter_p = self._simplify_filter(
            x_filter_p, self.mapping_x.scale, self.mapping_x.offset
        )
        y_filter_p = self._simplify_filter(
            y_filter_p, self.mapping_y.scale, self.mapping_y.offset
        )

        if self.order != "AUTO":
            order_xy = self.order == "XY"
        else:
            order_xy = dst_bounds[2] * (
                src_bounds[3] * x_filter_p.width + dst_bounds[3] * y_filter_p.width
            ) < dst_bounds[3] * (
                dst_bounds[2] * x_filter_p.width + src_bounds[2] * y_filter_p.width
            )

        if order_xy:
            self._resize_x_first(
                src, src_bounds, dst, dst_bounds, x_filter_p, y_filter_p
            )
        else:
            self._resize_y_first(
                src, src_bounds, dst, dst_bounds, x_filter_p, y_filter_p
            )


def _intersection(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """Mirror ``java.awt.Rectangle.intersection``."""
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])
    return (x1, y1, x2 - x1, y2 - y1)
