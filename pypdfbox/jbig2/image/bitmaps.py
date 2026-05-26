"""Bitmap region/format helpers.

Partial port of ``org.apache.pdfbox.jbig2.image.Bitmaps``. Only the byte-level
region/composition primitives are ported here — :meth:`Bitmaps.extract`
(region-of-interest copy), :meth:`Bitmaps.combine_bytes` (logical byte combine)
and :meth:`Bitmaps.blit` (composite one bitmap onto another) — plus their
private byte helpers ``unpad`` / ``copyLine`` and the ``blit`` line workers.
These are the parts needed by the symbol-dictionary Huffman collective-bitmap
path (§6.5.9), the generic refinement region page-buffer reference path
(§7.4.7.4) and the pattern-dictionary / halftone-region procedures (§6.7,
§6.6.5). The image-conversion and dithering methods of upstream ``Bitmaps``
belong to the rendering wave and are not ported yet.

The region of interest is a plain ``(x, y, width, height)`` integer tuple,
mirroring the ``java.awt.Rectangle`` used upstream; ``get_max_y()`` is rendered
inline as ``y + height``.

Java byte arithmetic is masked to mirror the signed/unsigned ``byte`` behaviour:
the shifts that upstream performs on a (sign-extended) ``byte`` are reproduced
by masking the stored value to 8 bits before writing it back via
``Bitmap.set_byte`` (which itself masks ``& 0xFF``). Where upstream relies on
*signed* ``byte`` / ``short`` arithmetic (the arithmetic right shifts inside
``blit``), the operand is sign-extended first via :func:`_to_signed_byte` /
:func:`_to_signed_short` so the shift matches Java's ``>>``.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


class Bitmaps:
    """Static helpers operating on :class:`~pypdfbox.jbig2.bitmap.Bitmap`."""

    @staticmethod
    def extract(roi: tuple[int, int, int, int], src: Bitmap) -> Bitmap:
        """Extract the region of interest ``roi`` from ``src`` into a new bitmap.

        ``roi`` is ``(x, y, width, height)``.
        """
        roi_x, roi_y, roi_width, roi_height = roi

        dst = Bitmap(roi_width, roi_height)

        up_shift = roi_x & 0x07
        down_shift = 8 - up_shift
        dst_line_start_idx = 0

        padding = (8 - dst.get_width()) & 0x07
        src_line_start_idx = src.get_byte_index(roi_x, roi_y)
        src_line_end_idx = src.get_byte_index(roi_x + roi_width - 1, roi_y)
        use_padding = dst.get_row_stride() == src_line_end_idx + 1 - src_line_start_idx

        max_y = roi_y + roi_height
        for _y in range(roi_y, max_y):
            src_idx = src_line_start_idx
            dst_idx = dst_line_start_idx

            if src_line_start_idx == src_line_end_idx:
                pixels = (src.get_byte(src_idx) << up_shift) & 0xFF
                dst.set_byte(dst_idx, _unpad(padding, pixels))
            elif up_shift == 0:
                x = src_line_start_idx
                while x <= src_line_end_idx:
                    value = src.get_byte(src_idx)
                    src_idx += 1

                    if x == src_line_end_idx and use_padding:
                        value = _unpad(padding, value)

                    dst.set_byte(dst_idx, value)
                    dst_idx += 1
                    x += 1
            else:
                _copy_line(
                    src,
                    dst,
                    up_shift,
                    down_shift,
                    padding,
                    src_line_start_idx,
                    src_line_end_idx,
                    use_padding,
                    src_idx,
                    dst_idx,
                )

            src_line_start_idx += src.get_row_stride()
            src_line_end_idx += src.get_row_stride()
            dst_line_start_idx += dst.get_row_stride()

        return dst

    @staticmethod
    def combine_bytes(
        old_byte: int, new_byte: int, op: CombinationOperator
    ) -> int:
        """Combine two given bytes with a logical operator.

        The JBIG2 Standard specifies 5 possible combinations of bytes.

        :param old_byte: The old value that should be combined with ``new_byte``.
        :param new_byte: The new value that should be combined with ``old_byte``.
        :param op: The specified combination operator.
        :return: The combination result (as a signed Java ``byte``). In the case
            of :attr:`CombinationOperator.REPLACE`, ``new_byte`` is returned.
        """
        if op == CombinationOperator.OR:
            return _to_signed_byte(new_byte | old_byte)
        if op == CombinationOperator.AND:
            return _to_signed_byte(new_byte & old_byte)
        if op == CombinationOperator.XOR:  # 0 if equal, 1 if diff
            return _to_signed_byte(new_byte ^ old_byte)
        if op == CombinationOperator.XNOR:  # 0 if diff, 1 if equal
            return _to_signed_byte(~(old_byte ^ new_byte))
        # REPLACE and default: old value is replaced by new value.
        return _to_signed_byte(new_byte)

    @staticmethod
    def blit(
        src: Bitmap,
        dst: Bitmap,
        x: int,
        y: int,
        combination_operator: CombinationOperator,
    ) -> None:
        """Combine a given bitmap with another (destination) bitmap.

        Parts of the bitmap to blit that are outside of the target bitmap will
        be ignored.

        :param src: The bitmap that should be combined with the destination.
        :param dst: The destination bitmap.
        :param x: The x coordinate where the upper left corner of the bitmap to
            blit should be positioned.
        :param y: The y coordinate where the upper left corner of the bitmap to
            blit should be positioned.
        :param combination_operator: The combination operator for combining two
            pixels.
        """
        start_line = 0
        src_start_idx = 0
        src_end_idx = src.get_row_stride() - 1
        x1 = x
        y1 = y

        # Ignore those parts of the source bitmap which would be placed outside
        # the target bitmap.
        if x < 0:
            src_start_idx = -x
            x = 0
        elif x + src.get_width() > dst.get_width():
            src_end_idx -= src.get_width() + x - dst.get_width()

        if y < 0:
            start_line = -y
            y = 0
            src_start_idx += src.get_row_stride()
            src_end_idx += src.get_row_stride()
        elif y + src.get_height() > dst.get_height():
            start_line = src.get_height() + y - dst.get_height()

        shift_val1 = x & 0x07
        shift_val2 = 8 - shift_val1

        padding = src.get_width() & 0x07
        to_shift = shift_val2 - padding

        if (shift_val1 != 0 or padding != 0) and not (
            x1 == 0 and src.get_width() >= dst.get_width()
        ):
            # PDFBOX-6156: do it the hard way until the other methods are fixed.
            # Not needed if both have the same size (or if src larger) and x
            # starts at 0, but needed if start or end not at byte boundary.
            _blit_by_pixel(src, dst, x1, y1, combination_operator)
            return

        use_shift = (shift_val2 & 0x07) != 0
        special_case = (
            src.get_width() <= ((src_end_idx - src_start_idx) << 3) + shift_val2
        )

        dst_start_idx = dst.get_byte_index(x, y)

        last_line = min(src.get_height(), start_line + dst.get_height())

        if not use_shift:
            _blit_unshifted(
                src,
                dst,
                start_line,
                last_line,
                dst_start_idx,
                src_start_idx,
                src_end_idx,
                combination_operator,
            )
        elif special_case:
            _blit_special_shifted(
                src,
                dst,
                start_line,
                last_line,
                dst_start_idx,
                src_start_idx,
                src_end_idx,
                to_shift,
                shift_val1,
                shift_val2,
                combination_operator,
            )
        else:
            _blit_shifted(
                src,
                dst,
                start_line,
                last_line,
                dst_start_idx,
                src_start_idx,
                src_end_idx,
                to_shift,
                shift_val1,
                shift_val2,
                combination_operator,
                padding,
            )


def _to_signed_byte(value: int) -> int:
    """Interpret the low 8 bits of ``value`` as a signed Java ``byte``."""
    value &= 0xFF
    return value - 256 if value >= 128 else value


def _to_signed_short(value: int) -> int:
    """Interpret the low 16 bits of ``value`` as a signed Java ``short``."""
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def _unpad(padding: int, value: int) -> int:
    """Mask off ``padding`` low bits. Mirrors ``Bitmaps.unpad(int, byte)``.

    Upstream's ``value`` operand is a signed ``byte``; the ``value >> padding``
    is therefore an arithmetic shift on the sign-extended int. ``value`` is
    sign-extended first so the result matches when the high bit is set.
    """
    return ((_to_signed_byte(value) >> padding) << padding) & 0xFF


def _blit_unshifted(
    src: Bitmap,
    dst: Bitmap,
    start_line: int,
    last_line: int,
    dst_start_idx: int,
    src_start_idx: int,
    src_end_idx: int,
    op: CombinationOperator,
) -> None:
    length = src_end_idx - src_start_idx + 1  # src_end_idx is inclusive
    src_start_offset = src_start_idx
    dst_start_offset = dst_start_idx
    lines = last_line - start_line
    while lines > 0:
        src_idx = src_start_offset
        dst_idx = dst_start_offset
        count = length
        # Go through the bytes in a line of the symbol.
        if op in (
            CombinationOperator.OR,
            CombinationOperator.AND,
            CombinationOperator.XOR,
            CombinationOperator.XNOR,
        ):
            while count > 0:
                count -= 1
                dst.set_byte(
                    dst_idx,
                    Bitmaps.combine_bytes(
                        _to_signed_byte(src.get_byte(src_idx)),
                        _to_signed_byte(dst.get_byte(dst_idx)),
                        op,
                    ),
                )
                src_idx += 1
                dst_idx += 1
        elif op == CombinationOperator.REPLACE:
            Bitmap.arraycopy(src, src_idx, dst, dst_idx, count)
        src_start_offset += src.get_row_stride()
        dst_start_offset += dst.get_row_stride()
        lines -= 1


def _blit_special_shifted(
    src: Bitmap,
    dst: Bitmap,
    start_line: int,
    last_line: int,
    dst_start_idx: int,
    src_start_idx: int,
    src_end_idx: int,
    to_shift: int,
    shift_val1: int,
    shift_val2: int,
    op: CombinationOperator,
) -> None:
    for _dst_line in range(start_line, last_line):
        register = 0
        dst_idx = dst_start_idx

        # Go through the bytes in a line of the symbol.
        for src_idx in range(src_start_idx, src_end_idx + 1):
            old_byte = _to_signed_byte(dst.get_byte(dst_idx))
            register = _to_signed_short(
                (register | src.get_byte(src_idx) & 0xFF) << shift_val2
            )
            new_byte = _to_signed_byte(register >> 8)

            if src_idx == src_end_idx:
                new_byte = _unpad(to_shift, new_byte)

            dst.set_byte(dst_idx, Bitmaps.combine_bytes(old_byte, new_byte, op))
            dst_idx += 1
            register = _to_signed_short(register << shift_val1)

        dst_start_idx += dst.get_row_stride()
        src_start_idx += src.get_row_stride()
        src_end_idx += src.get_row_stride()


def _blit_shifted(
    src: Bitmap,
    dst: Bitmap,
    start_line: int,
    last_line: int,
    dst_start_idx: int,
    src_start_idx: int,
    src_end_idx: int,
    to_shift: int,
    shift_val1: int,
    shift_val2: int,
    op: CombinationOperator,
    padding: int,
) -> None:
    for _dst_line in range(start_line, last_line):
        register = 0
        dst_idx = dst_start_idx

        # Go through the bytes in a line of the symbol.
        for src_idx in range(src_start_idx, src_end_idx + 1):
            old_byte = _to_signed_byte(dst.get_byte(dst_idx))
            register = _to_signed_short(
                (register | src.get_byte(src_idx) & 0xFF) << shift_val2
            )

            new_byte = _to_signed_byte(register >> 8)
            dst.set_byte(dst_idx, Bitmaps.combine_bytes(old_byte, new_byte, op))
            dst_idx += 1

            register = _to_signed_short(register << shift_val1)

            if src_idx == src_end_idx:
                new_byte = _to_signed_byte(register >> (8 - shift_val2))

                if padding != 0:
                    new_byte = _unpad(8 + to_shift, new_byte)

                old_byte = _to_signed_byte(dst.get_byte(dst_idx))
                dst.set_byte(dst_idx, Bitmaps.combine_bytes(old_byte, new_byte, op))

        dst_start_idx += dst.get_row_stride()
        src_start_idx += src.get_row_stride()
        src_end_idx += src.get_row_stride()


def _blit_by_pixel(
    src: Bitmap,
    dst: Bitmap,
    x_dst_offset: int,
    y_dst_offset: int,
    combination_operator: CombinationOperator,
) -> None:
    y = 0
    while y < src.get_height() and y_dst_offset + y < dst.get_height():
        if y_dst_offset + y < 0:
            y += 1
            continue
        x = 0
        while x < src.get_width() and x_dst_offset + x < dst.get_width():
            if x_dst_offset + x < 0:
                x += 1
                continue
            result_bit = Bitmaps.combine_bytes(
                dst.get_pixel(x_dst_offset + x, y_dst_offset + y),
                src.get_pixel(x, y),
                combination_operator,
            )
            dst.set_pixel(x_dst_offset + x, y_dst_offset + y, result_bit)
            x += 1
        y += 1


def _copy_line(
    src: Bitmap,
    dst: Bitmap,
    source_up_shift: int,
    source_down_shift: int,
    padding: int,
    first_source_byte_of_line: int,
    last_source_byte_of_line: int,
    use_padding: bool,
    source_offset: int,
    target_offset: int,
) -> None:
    x = first_source_byte_of_line
    while x < last_source_byte_of_line:
        if source_offset + 1 < src.get_length():
            is_last_byte = x + 1 == last_source_byte_of_line
            # Mirror upstream byte expression:
            #   (byte)(src.getByte(sourceOffset++) << upShift
            #          | (src.getByte(sourceOffset) & 0xff) >>> downShift)
            # The post-increment reads the byte at the old offset, then the
            # second term reads the byte at the incremented offset.
            first_byte = src.get_byte(source_offset)
            source_offset += 1
            value = (
                ((first_byte << source_up_shift) & 0xFF)
                | ((src.get_byte(source_offset) & 0xFF) >> source_down_shift)
            ) & 0xFF

            if is_last_byte and not use_padding:
                value = _unpad(padding, value)

            dst.set_byte(target_offset, value)
            target_offset += 1

            if is_last_byte and use_padding:
                value = _unpad(
                    padding,
                    ((src.get_byte(source_offset) & 0xFF) << source_up_shift) & 0xFF,
                )
                dst.set_byte(target_offset, value)
        else:
            value = ((src.get_byte(source_offset) << source_up_shift) & 0xFF)
            source_offset += 1
            dst.set_byte(target_offset, value)
            target_offset += 1
        x += 1
