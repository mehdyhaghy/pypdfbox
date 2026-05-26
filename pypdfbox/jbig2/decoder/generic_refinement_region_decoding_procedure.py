"""Implements the JBIG2 Generic Refinement Region decoding procedure.

Port of
``org.apache.pdfbox.jbig2.decoder.GenericRefinementRegionDecodingProcedure``.

Implements ITU-T T.88, §6.3 including the core decoding loop defined in
§6.3.5.6. This class is purely algorithmic. It has no knowledge of how its
inputs are obtained and no dependency on segment headers or input streams. The
entry point is the static :meth:`decode` method; callers supply the
:class:`ArithmeticDecoder` and :class:`CX` context model directly, so they
decide whether to create fresh instances or share existing ones:

* :class:`~pypdfbox.jbig2.segments.generic_refinement_region.GenericRefinementRegion`
  creates its own ``ArithmeticDecoder`` and ``CX``, then calls ``decode()``.
* Symbol dictionary refinement (§6.5.8.2) passes the parent dictionary's
  shared ``ArithmeticDecoder`` and ``CX``.
* Text region refinement (§6.4) passes the parent text region's shared
  ``ArithmeticDecoder`` and ``CX``.

This class cannot be instantiated by callers. The private constructor and the
internal :meth:`_run` method exist solely to let the many private helper
methods share state through fields rather than through long parameter lists.

The Java original relies on the bounded width of ``int``. Python integers are
unbounded, so the rolling-window ``w``/``previous*``/``current*``/``next*``
registers are masked to 32 bits with ``& 0xFFFFFFFF`` after each left shift to
mirror Java ``int`` wraparound, and ``>>>`` (unsigned right shift) is rendered
as a plain right shift on those already-non-negative masked values. ``short``
casts of context bytes wrap to 16 bits via ``& 0xFFFF``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.bitmap import Bitmap

if TYPE_CHECKING:
    from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
    from pypdfbox.jbig2.decoder.arithmetic.cx import CX

_MASK32 = 0xFFFFFFFF

# §6.3.5.6, Figure 14
_SLTP_CONTEXT_TEMPLATE0 = 0x100
# §6.3.5.6, Figure 15
_SLTP_CONTEXT_TEMPLATE1 = 0x008


class Template:
    """Template-specific context bit formation and initial CX index selection.

    The two concrete implementations (:data:`T0`, :data:`T1`) correspond to
    GRTEMPLATE values 0 and 1 as defined in §6.3.3 / Figures 14-15.
    """

    def form(self, c1: int, c2: int, c3: int, c4: int, c5: int) -> int:
        raise NotImplementedError

    def set_index(self, cx: CX) -> None:
        raise NotImplementedError


class _Template0(Template):
    def form(self, c1: int, c2: int, c3: int, c4: int, c5: int) -> int:
        return ((c1 << 10) | (c2 << 7) | (c3 << 4) | (c4 << 1) | c5) & 0xFFFF

    def set_index(self, cx: CX) -> None:
        cx.set_index(_SLTP_CONTEXT_TEMPLATE0)


class _Template1(Template):
    def form(self, c1: int, c2: int, c3: int, c4: int, c5: int) -> int:
        return (
            ((c1 & 0x02) << 8) | (c2 << 6) | ((c3 & 0x03) << 4) | (c4 << 1) | c5
        ) & 0xFFFF

    def set_index(self, cx: CX) -> None:
        cx.set_index(_SLTP_CONTEXT_TEMPLATE1)


#: Singleton template 0 instance (stateless).
T0: Template = _Template0()

#: Singleton template 1 instance (stateless).
T1: Template = _Template1()


class GenericRefinementRegionDecodingProcedure:
    """Generic refinement region decoding procedure (§6.3.5.6)."""

    def __init__(self, arith_decoder: ArithmeticDecoder, cx: CX) -> None:
        # Construction is private; callers use the static decode() entry point.
        self.arith_decoder = arith_decoder
        self.cx = cx

        # Per-decode working state — reset by each run() call.
        self.template_id: int = 0
        self.template: Template = T0
        self.reference_bitmap: Bitmap | None = None
        self.reference_dx: int = 0
        self.reference_dy: int = 0
        self.gr_at_x: list[int] | None = None
        self.gr_at_y: list[int] | None = None
        self.override: bool = False
        self.gr_at_override: list[bool] | None = None

        # The bitmap being built; held as a field to avoid passing it around.
        self.region_bitmap: Bitmap | None = None

    @staticmethod
    def decode(
        arith_decoder: ArithmeticDecoder,
        cx: CX,
        width: int,
        height: int,
        gr_template: int,
        is_tpgr_on: bool,
        reference_bitmap: Bitmap,
        reference_dx: int,
        reference_dy: int,
        gr_at_x: list[int] | None,
        gr_at_y: list[int] | None,
    ) -> Bitmap:
        """Execute the procedure (§6.3.5.6) and return the decoded bitmap.

        A short-lived instance is created internally so that the many private
        helper methods can share state through fields rather than through long
        parameter lists. No state survives the return of this method.

        :param arith_decoder: the arithmetic decoder — shared with the parent
            when called from a symbol dictionary or text region, or freshly
            created when called from a standalone segment; must not be ``None``.
        :param cx: the context model — shared or fresh, as above; must not be
            ``None``.
        :param width: decoded bitmap width (GRW); must be > 0.
        :param height: decoded bitmap height (GRH); must be > 0.
        :param gr_template: template index: must be 0 or 1 (GRTEMPLATE).
        :param is_tpgr_on: whether typical prediction is enabled (TPGRON).
        :param reference_bitmap: the reference / base bitmap (GRREFERENCE);
            must not be ``None``.
        :param reference_dx: horizontal offset of reference bitmap (GRREFERENCEDX).
        :param reference_dy: vertical offset of reference bitmap (GRREFERENCEDY).
        :param gr_at_x: AT pixel X offsets; required for ``gr_template == 0``,
            must be a non-``None`` sequence of length 2 in that case; ignored
            for ``gr_template == 1``.
        :param gr_at_y: AT pixel Y offsets; same requirements as ``gr_at_x``.

        :return: the decoded bitmap.

        :raises ValueError: if any parameter constraint above is violated.
        :raises OSError: if an underlying I/O operation fails.
        """
        if arith_decoder is None:
            raise ValueError("arithDecoder must not be null")
        if cx is None:
            raise ValueError("cx must not be null")
        if reference_bitmap is None:
            raise ValueError("referenceBitmap must not be null")

        if gr_template != 0 and gr_template != 1:
            raise ValueError(f"grTemplate must be 0 or 1, got: {gr_template}")

        if gr_template == 0 and (
            gr_at_x is None
            or gr_at_y is None
            or len(gr_at_x) != 2
            or len(gr_at_y) != 2
        ):
            raise ValueError(
                "grAtX and grAtY must be non-null arrays of length 2 for template 0"
            )

        if width <= 0 or height <= 0:
            raise ValueError(
                f"width and height must be > 0, got: {width}x{height}"
            )

        return GenericRefinementRegionDecodingProcedure(arith_decoder, cx)._run(
            width,
            height,
            gr_template,
            is_tpgr_on,
            reference_bitmap,
            reference_dx,
            reference_dy,
            gr_at_x,
            gr_at_y,
        )

    def _run(
        self,
        width: int,
        height: int,
        gr_template: int,
        is_tpgr_on: bool,
        reference_bitmap: Bitmap,
        reference_dx: int,
        reference_dy: int,
        gr_at_x: list[int] | None,
        gr_at_y: list[int] | None,
    ) -> Bitmap:
        self.template_id = gr_template
        self.template = T0 if gr_template == 0 else T1
        self.reference_bitmap = reference_bitmap
        self.reference_dx = reference_dx
        self.reference_dy = reference_dy
        self.gr_at_x = gr_at_x
        self.gr_at_y = gr_at_y
        self.override = False
        self.gr_at_override = None

        # 6.3.5.6 - 2)
        self.region_bitmap = Bitmap(width, height)

        if self.template_id == 0:
            # AT pixels are only relevant for template 0
            self._update_override()

        padded_width = (width + 7) & -8
        delta_ref_stride = (
            -reference_dy * reference_bitmap.get_row_stride() if is_tpgr_on else 0
        )
        y_offset = delta_ref_stride + 1

        # 6.3.5.6 - 1)
        is_line_typical_predicted = 0  # LTP

        # 6.3.5.6 - 3)
        for y in range(height):
            # 6.3.5.6 - 3 b)
            if is_tpgr_on:
                is_line_typical_predicted ^= self._decode_sltp()

            if self.template_id == 1:
                if is_line_typical_predicted == 0:
                    self._decode_line_explicit_t1(y, width)
                else:
                    self._decode_line_tpgr_t1(y, width)
            else:
                # existing template 0 paths unchanged
                if is_line_typical_predicted == 0:
                    self._decode_optimized(
                        y,
                        width,
                        self.region_bitmap.get_row_stride(),
                        reference_bitmap.get_row_stride(),
                        padded_width,
                        delta_ref_stride,
                        y_offset,
                    )
                else:
                    self._decode_typical_predicted_line(
                        y,
                        width,
                        self.region_bitmap.get_row_stride(),
                        reference_bitmap.get_row_stride(),
                        padded_width,
                        delta_ref_stride,
                    )

        # 6.3.5.6 - 4)
        return self.region_bitmap

    # Pixel accessors — §6.3.5.2 out-of-bounds rule: all outside pixels = 0

    def _get_pixel_safe(self, bitmap: Bitmap, x: int, y: int) -> int:
        if x < 0 or y < 0:
            return 0
        if x >= bitmap.get_width() or y >= bitmap.get_height():
            return 0
        return bitmap.get_pixel(x, y)

    def _get_reference_bit(self, x: int, y: int) -> int:
        return self._get_pixel_safe(
            self.reference_bitmap, x - self.reference_dx, y - self.reference_dy
        )

    def _get_region_bit(self, x: int, y: int) -> int:
        return self._get_pixel_safe(self.region_bitmap, x, y)

    # Template 1 context formation — §6.3.5.6, Figure 13

    def _build_context_t1(self, x: int, y: int) -> int:
        return (
            (self._get_region_bit(x - 1, y - 1) << 9)
            | (self._get_region_bit(x, y - 1) << 8)
            | (self._get_region_bit(x + 1, y - 1) << 7)
            | (self._get_region_bit(x - 1, y) << 6)
            | (self._get_reference_bit(x, y - 1) << 5)
            | (self._get_reference_bit(x - 1, y) << 4)
            | (self._get_reference_bit(x, y) << 3)
            | (self._get_reference_bit(x + 1, y) << 2)
            | (self._get_reference_bit(x, y + 1) << 1)
            | (self._get_reference_bit(x + 1, y + 1))
        )

    # Template 1 — explicit decode (LTP=0 path, §6.3.5.6 step 3c)

    def _decode_line_explicit_t1(self, y: int, width: int) -> None:
        for x in range(width):
            self.cx.set_index(self._build_context_t1(x, y))
            self.region_bitmap.set_pixel(x, y, self.arith_decoder.decode(self.cx))

    # Template 1 — typical prediction decode (LTP=1 path, §6.3.5.6 step 3d)
    # TPGRPIX=1 when the 3x3 reference neighbourhood is uniform (§6.3.5.6 3d-i)

    def _decode_line_tpgr_t1(self, y: int, width: int) -> None:
        for x in range(width):
            center = self._get_reference_bit(x, y)
            uniform = True
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if self._get_reference_bit(x + dx, y + dy) != center:
                        uniform = False
                        break
                if not uniform:
                    break

            if uniform:
                bit = center
            else:
                self.cx.set_index(self._build_context_t1(x, y))
                bit = self.arith_decoder.decode(self.cx)
            self.region_bitmap.set_pixel(x, y, bit)

    # Private decoding helpers (§6.3.5.6 sub-steps)

    def _decode_sltp(self) -> int:
        self.template.set_index(self.cx)
        return self.arith_decoder.decode(self.cx)

    def _decode_optimized(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        ref_row_stride: int,
        padded_width: int,
        delta_ref_stride: int,
        line_offset: int,
    ) -> None:
        # Offset of the reference bitmap with respect to the bitmap being
        # decoded. For example: if referenceDY = -1, y is 1 HIGHER than currY.
        current_line = line_number - self.reference_dy
        reference_byte_index = self.reference_bitmap.get_byte_index(
            max(0, -self.reference_dx), current_line
        )
        byte_index = self.region_bitmap.get_byte_index(
            max(0, self.reference_dx), line_number
        )

        if self.template_id == 0:
            self._decode_template(
                line_number,
                width,
                row_stride,
                ref_row_stride,
                padded_width,
                delta_ref_stride,
                line_offset,
                byte_index,
                current_line,
                reference_byte_index,
                T0,
            )
        elif self.template_id == 1:
            self._decode_template(
                line_number,
                width,
                row_stride,
                ref_row_stride,
                padded_width,
                delta_ref_stride,
                line_offset,
                byte_index,
                current_line,
                reference_byte_index,
                T1,
            )

    def _decode_template(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        ref_row_stride: int,
        padded_width: int,
        delta_ref_stride: int,
        line_offset: int,
        byte_index: int,
        current_line: int,
        ref_byte_index: int,
        template_formation: Template,
    ) -> None:
        ref = self.reference_bitmap
        reg = self.region_bitmap

        w1 = w2 = w3 = w4 = 0

        if current_line >= 1 and (current_line - 1) < ref.get_height():
            w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
        if current_line >= 0 and current_line < ref.get_height():
            w2 = ref.get_byte_as_integer(ref_byte_index)
        if current_line >= -1 and current_line + 1 < ref.get_height():
            w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
        ref_byte_index += 1

        if line_number >= 1:
            w4 = reg.get_byte_as_integer(byte_index - row_stride)
        byte_index += 1

        mod_reference_dx = self.reference_dx % 8
        shift_offset = 6 + mod_reference_dx
        mod_ref_byte_idx = ref_byte_index % ref_row_stride

        if shift_offset >= 0:
            c1 = ((0 if shift_offset >= 8 else w1 >> shift_offset) & 0x07) & 0xFFFF
            c2 = ((0 if shift_offset >= 8 else w2 >> shift_offset) & 0x07) & 0xFFFF
            c3 = ((0 if shift_offset >= 8 else w3 >> shift_offset) & 0x07) & 0xFFFF
            if shift_offset == 6 and mod_ref_byte_idx > 1:
                if current_line >= 1 and (current_line - 1) < ref.get_height():
                    c1 |= (
                        ref.get_byte_as_integer(ref_byte_index - ref_row_stride - 2)
                        << 2
                    ) & 0x04
                if current_line >= 0 and current_line < ref.get_height():
                    c2 |= (ref.get_byte_as_integer(ref_byte_index - 2) << 2) & 0x04
                if current_line >= -1 and current_line + 1 < ref.get_height():
                    c3 |= (
                        ref.get_byte_as_integer(ref_byte_index + ref_row_stride - 2)
                        << 2
                    ) & 0x04
            if shift_offset == 0:
                w1 = w2 = w3 = 0
                if mod_ref_byte_idx < ref_row_stride - 1:
                    if current_line >= 1 and (current_line - 1) < ref.get_height():
                        w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
                    if current_line >= 0 and current_line < ref.get_height():
                        w2 = ref.get_byte_as_integer(ref_byte_index)
                    if current_line >= -1 and current_line + 1 < ref.get_height():
                        w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
                ref_byte_index += 1
        else:
            c1 = ((w1 << 1) & 0x07) & 0xFFFF
            c2 = ((w2 << 1) & 0x07) & 0xFFFF
            c3 = ((w3 << 1) & 0x07) & 0xFFFF
            w1 = w2 = w3 = 0
            if mod_ref_byte_idx < ref_row_stride - 1:
                if current_line >= 1 and (current_line - 1) < ref.get_height():
                    w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
                if current_line >= 0 and current_line < ref.get_height():
                    w2 = ref.get_byte_as_integer(ref_byte_index)
                if current_line >= -1 and current_line + 1 < ref.get_height():
                    w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
                ref_byte_index += 1
            c1 = (c1 | ((w1 >> 7) & 0x07)) & 0xFFFF
            c2 = (c2 | ((w2 >> 7) & 0x07)) & 0xFFFF
            c3 = (c3 | ((w3 >> 7) & 0x07)) & 0xFFFF

        c4 = (w4 >> 6) & 0xFFFF
        c5 = 0

        mod_bits_to_trim = (2 - mod_reference_dx) % 8
        w1 = (w1 << mod_bits_to_trim) & _MASK32
        w2 = (w2 << mod_bits_to_trim) & _MASK32
        w3 = (w3 << mod_bits_to_trim) & _MASK32

        w4 = (w4 << 2) & _MASK32

        for x in range(width):
            minor_x = x & 0x07

            tval = template_formation.form(c1, c2, c3, c4, c5)

            if self.override:
                self.cx.set_index(
                    self._override_at_template0(
                        tval,
                        x,
                        line_number,
                        reg.get_byte(reg.get_byte_index(x, line_number)),
                        minor_x,
                    )
                )
            else:
                self.cx.set_index(tval)
            bit = self.arith_decoder.decode(self.cx)
            reg.set_pixel(x, line_number, bit)

            c1 = (((c1 << 1) | (0x01 & (w1 >> 7))) & 0x07) & 0xFFFF
            c2 = (((c2 << 1) | (0x01 & (w2 >> 7))) & 0x07) & 0xFFFF
            c3 = (((c3 << 1) | (0x01 & (w3 >> 7))) & 0x07) & 0xFFFF
            c4 = (((c4 << 1) | (0x01 & (w4 >> 7))) & 0x07) & 0xFFFF
            c5 = bit & 0xFFFF

            if (x - self.reference_dx) % 8 == 5:
                if ((x - self.reference_dx) // 8) + 1 >= ref.get_row_stride():
                    w1 = w2 = w3 = 0
                else:
                    if current_line >= 1 and (current_line - 1 < ref.get_height()):
                        w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
                    else:
                        w1 = 0
                    if current_line >= 0 and current_line < ref.get_height():
                        w2 = ref.get_byte_as_integer(ref_byte_index)
                    else:
                        w2 = 0
                    if current_line >= -1 and (current_line + 1) < ref.get_height():
                        w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
                    else:
                        w3 = 0
                ref_byte_index += 1
            else:
                w1 = (w1 << 1) & _MASK32
                w2 = (w2 << 1) & _MASK32
                w3 = (w3 << 1) & _MASK32

            if minor_x == 5 and line_number >= 1:
                if (x >> 3) + 1 >= reg.get_row_stride():
                    w4 = 0
                else:
                    w4 = reg.get_byte_as_integer(byte_index - row_stride)
                byte_index += 1
            else:
                w4 = (w4 << 1) & _MASK32

    def _update_override(self) -> None:
        if self.gr_at_x is None or self.gr_at_y is None:
            return

        if len(self.gr_at_x) != len(self.gr_at_y):
            return

        self.gr_at_override = [False] * len(self.gr_at_x)

        if self.template_id == 0:
            if not (self.gr_at_x[0] == -1 and self.gr_at_y[0] == -1):
                self.gr_at_override[0] = True
                self.override = True

            if not (self.gr_at_x[1] == -1 and self.gr_at_y[1] == -1):
                self.gr_at_override[1] = True
                self.override = True
        elif self.template_id == 1:
            self.override = False

    def _decode_typical_predicted_line(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        ref_row_stride: int,
        padded_width: int,
        delta_ref_stride: int,
    ) -> None:
        # Offset of the reference bitmap with respect to the bitmap being
        # decoded. For example: if grReferenceDY = -1, y is 1 HIGHER than currY.
        current_line = line_number - self.reference_dy
        ref_byte_index = self.reference_bitmap.get_byte_index(0, current_line)
        byte_index = self.region_bitmap.get_byte_index(0, line_number)

        if self.template_id == 0:
            self._decode_typical_predicted_line_template0(
                line_number,
                width,
                row_stride,
                ref_row_stride,
                padded_width,
                delta_ref_stride,
                byte_index,
                current_line,
                ref_byte_index,
            )
        elif self.template_id == 1:
            self._decode_typical_predicted_line_template1(
                line_number,
                width,
                row_stride,
                ref_row_stride,
                padded_width,
                delta_ref_stride,
                byte_index,
                current_line,
                ref_byte_index,
            )

    def _decode_typical_predicted_line_template0(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        ref_row_stride: int,
        padded_width: int,
        delta_ref_stride: int,
        byte_index: int,
        current_line: int,
        ref_byte_index: int,
    ) -> None:
        ref = self.reference_bitmap
        reg = self.region_bitmap

        previous_line = (
            reg.get_byte_as_integer(byte_index - row_stride) if line_number > 0 else 0
        )

        if current_line > 0 and current_line <= ref.get_height():
            previous_reference_line = (
                ref.get_byte_as_integer(
                    ref_byte_index - ref_row_stride + delta_ref_stride
                )
                << 4
            )
        else:
            previous_reference_line = 0

        if current_line >= 0 and current_line < ref.get_height():
            current_reference_line = (
                ref.get_byte_as_integer(ref_byte_index + delta_ref_stride) << 1
            )
        else:
            current_reference_line = 0

        if current_line > -2 and current_line < (ref.get_height() - 1):
            next_reference_line = ref.get_byte_as_integer(
                ref_byte_index + ref_row_stride + delta_ref_stride
            )
        else:
            next_reference_line = 0

        context = (
            ((previous_line >> 5) & 0x6)
            | ((next_reference_line >> 2) & 0x30)
            | (current_reference_line & 0x180)
            | (previous_reference_line & 0xC00)
        )

        x = 0
        while x < padded_width:
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x
            read_next_byte = next_byte < width
            ref_read_next_byte = next_byte < ref.get_width()

            y_offset = delta_ref_stride + 1

            if line_number > 0:
                previous_line = ((previous_line << 8) & _MASK32) | (
                    reg.get_byte_as_integer(byte_index - row_stride + 1)
                    if read_next_byte
                    else 0
                )

            if current_line > 0 and current_line <= ref.get_height():
                previous_reference_line = ((previous_reference_line << 8) & _MASK32) | (
                    (
                        ref.get_byte_as_integer(
                            ref_byte_index - ref_row_stride + y_offset
                        )
                        << 4
                    )
                    if ref_read_next_byte
                    else 0
                )

            if current_line >= 0 and current_line < ref.get_height():
                current_reference_line = ((current_reference_line << 8) & _MASK32) | (
                    (ref.get_byte_as_integer(ref_byte_index + y_offset) << 1)
                    if ref_read_next_byte
                    else 0
                )

            if current_line > -2 and current_line < (ref.get_height() - 1):
                next_reference_line = ((next_reference_line << 8) & _MASK32) | (
                    ref.get_byte_as_integer(
                        ref_byte_index + ref_row_stride + y_offset
                    )
                    if ref_read_next_byte
                    else 0
                )

            for minor_x in range(minor_width):
                is_pixel_typical_predicted = False
                bit = 0

                # i)
                bitmap_value = (context >> 4) & 0x1FF

                if bitmap_value == 0x1FF:
                    is_pixel_typical_predicted = True
                    bit = 1
                elif bitmap_value == 0x00:
                    is_pixel_typical_predicted = True
                    bit = 0

                if not is_pixel_typical_predicted:
                    # iii) - is like 3 c) but for one pixel only
                    if self.override:
                        overridden_context = self._override_at_template0(
                            context, x + minor_x, line_number, result, minor_x
                        )
                        self.cx.set_index(overridden_context)
                    else:
                        self.cx.set_index(context)
                    bit = self.arith_decoder.decode(self.cx)

                to_shift = 7 - minor_x
                result |= bit << to_shift

                context = (
                    ((context & 0xDB6) << 1)
                    | bit
                    | ((previous_line >> (to_shift + 5)) & 0x002)
                    | ((next_reference_line >> (to_shift + 2)) & 0x010)
                    | ((current_reference_line >> to_shift) & 0x080)
                    | ((previous_reference_line >> to_shift) & 0x400)
                )
            reg.set_byte(byte_index, result)
            byte_index += 1
            ref_byte_index += 1
            x = next_byte

    def _decode_typical_predicted_line_template1(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        ref_row_stride: int,
        padded_width: int,
        delta_ref_stride: int,
        byte_index: int,
        current_line: int,
        ref_byte_index: int,
    ) -> None:
        ref = self.reference_bitmap
        reg = self.region_bitmap

        previous_line = (
            reg.get_byte_as_integer(byte_index - row_stride) if line_number > 0 else 0
        )

        if current_line > 0 and current_line <= ref.get_height():
            previous_reference_line = (
                ref.get_byte_as_integer(
                    ref_byte_index - ref_row_stride + delta_ref_stride
                )
                << 2
            )
        else:
            previous_reference_line = 0

        if current_line >= 0 and current_line < ref.get_height():
            current_reference_line = ref.get_byte_as_integer(
                ref_byte_index + delta_ref_stride
            )
        else:
            current_reference_line = 0

        if current_line > -2 and current_line < (ref.get_height() - 1):
            next_reference_line = ref.get_byte_as_integer(
                ref_byte_index + ref_row_stride + delta_ref_stride
            )
        else:
            next_reference_line = 0

        context = (
            ((previous_line >> 5) & 0x6)
            | ((next_reference_line >> 2) & 0x30)
            | (current_reference_line & 0xC0)
            | (previous_reference_line & 0x200)
        )

        gr_reference_value = (
            ((next_reference_line >> 2) & 0x70)
            | (current_reference_line & 0xC0)
            | (previous_reference_line & 0x700)
        )

        x = 0
        while x < padded_width:
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x
            read_next_byte = next_byte < width
            ref_read_next_byte = next_byte < ref.get_width()

            y_offset = delta_ref_stride + 1

            if line_number > 0:
                previous_line = ((previous_line << 8) & _MASK32) | (
                    reg.get_byte_as_integer(byte_index - row_stride + 1)
                    if read_next_byte
                    else 0
                )

            if current_line > 0 and current_line <= ref.get_height():
                previous_reference_line = ((previous_reference_line << 8) & _MASK32) | (
                    (
                        ref.get_byte_as_integer(
                            ref_byte_index - ref_row_stride + y_offset
                        )
                        << 2
                    )
                    if ref_read_next_byte
                    else 0
                )

            if current_line >= 0 and current_line < ref.get_height():
                current_reference_line = ((current_reference_line << 8) & _MASK32) | (
                    ref.get_byte_as_integer(ref_byte_index + y_offset)
                    if ref_read_next_byte
                    else 0
                )

            if current_line > -2 and current_line < (ref.get_height() - 1):
                next_reference_line = ((next_reference_line << 8) & _MASK32) | (
                    ref.get_byte_as_integer(
                        ref_byte_index + ref_row_stride + y_offset
                    )
                    if ref_read_next_byte
                    else 0
                )

            for minor_x in range(minor_width):
                # i)
                bitmap_value = (gr_reference_value >> 4) & 0x1FF

                if bitmap_value == 0x1FF:
                    bit = 1
                elif bitmap_value == 0x00:
                    bit = 0
                else:
                    self.cx.set_index(context)
                    bit = self.arith_decoder.decode(self.cx)

                to_shift = 7 - minor_x
                result |= bit << to_shift

                context = (
                    ((context & 0x0D6) << 1)
                    | bit
                    | ((previous_line >> (to_shift + 5)) & 0x002)
                    | ((next_reference_line >> (to_shift + 2)) & 0x010)
                    | ((current_reference_line >> to_shift) & 0x040)
                    | ((previous_reference_line >> to_shift) & 0x200)
                )

                gr_reference_value = (
                    ((gr_reference_value & 0x0DB) << 1)
                    | ((next_reference_line >> (to_shift + 2)) & 0x010)
                    | ((current_reference_line >> to_shift) & 0x080)
                    | ((previous_reference_line >> to_shift) & 0x400)
                )
            reg.set_byte(byte_index, result)
            byte_index += 1
            ref_byte_index += 1
            x = next_byte

    def _override_at_template0(
        self, context: int, x: int, y: int, result: int, minor_x: int
    ) -> int:
        if self.gr_at_override[0]:
            context &= 0xFFF7
            if self.gr_at_y[0] == 0 and self.gr_at_x[0] >= -minor_x:
                context |= ((result >> (7 - (minor_x + self.gr_at_x[0]))) & 0x1) << 3
            else:
                context |= (
                    self._get_pixel_safe(
                        self.region_bitmap, x + self.gr_at_x[0], y + self.gr_at_y[0]
                    )
                    << 3
                )

        if self.gr_at_override[1]:
            context &= 0xEFFF
            # 6.3.5.3
            # The AT pixel RA2 can be located anywhere in the range
            # (-128, -128) to (127, 127) in the reference bitmap. Make sure
            # that we do use the reference bitmap.
            context |= (
                self._get_pixel_safe(
                    self.reference_bitmap,
                    x + self.gr_at_x[1] + self.reference_dx,
                    y + self.gr_at_y[1] + self.reference_dy,
                )
                << 12
            )
        return context
