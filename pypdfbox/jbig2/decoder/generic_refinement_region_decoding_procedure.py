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

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import (
    QE_DECODE,
    RENORM_SHIFTS,
    ArithmeticDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX

_MASK32 = 0xFFFFFFFF


def _java_mod(a: int, b: int) -> int:
    """Java ``%`` (remainder, truncated toward zero).

    Python's ``%`` follows the sign of the divisor, so ``-1 % 8 == 7``, whereas
    Java's remainder follows the sign of the dividend, so ``-1 % 8 == -1``. The
    refinement template's ``referenceDX % 8`` (and the values derived from it)
    must use Java semantics: a negative ``referenceDX`` (which arises when the
    text-region refinement reference offset ``(RDW >> 1) + RDX`` is negative,
    e.g. on large symbol dictionaries) selects a different context-shift branch
    under Java's truncated remainder, and matching that is required for
    bit-exact decode.
    """
    r = abs(a) % abs(b)
    return -r if a < 0 else r

def _row_bits(bitmap: Bitmap, y: int, x0: int, n: int) -> list[int]:
    """Return the ``n`` pixel values of row ``y`` for ``x = x0 .. x0 + n - 1``.

    Pixels outside the bitmap are 0 (§6.3.5.2), as ``_get_pixel_safe``.
    """
    out = [0] * n
    if y < 0 or y >= bitmap.height:
        return out
    data = bitmap.bitmap_bytes
    base = y * bitmap.row_stride
    for x in range(max(x0, 0), min(x0 + n, bitmap.width)):
        out[x - x0] = (data[base + (x >> 3)] >> (7 - (x & 7))) & 1
    return out


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
        # Same context bits as _build_context_t1, read from per-line bit rows
        # (zero outside the bitmaps, §6.3.5.2) instead of per-pixel accessors.
        above, ref_above, ref_row, ref_below = self._t1_line_rows(y, width)
        reg = self.region_bitmap
        reg_bytes = reg.bitmap_bytes
        reg_row = y * reg.row_stride
        cx = self.cx
        set_index = cx.set_index
        decode = self.arith_decoder.decode
        left = 0
        for x in range(width):
            set_index(
                (above[x] << 9)
                | (above[x + 1] << 8)
                | (above[x + 2] << 7)
                | (left << 6)
                | (ref_above[x + 1] << 5)
                | (ref_row[x] << 4)
                | (ref_row[x + 1] << 3)
                | (ref_row[x + 2] << 2)
                | (ref_below[x + 1] << 1)
                | ref_below[x + 2]
            )
            bit = decode(cx)
            pixel_index = reg_row + (x >> 3)
            if bit & 1:
                reg_bytes[pixel_index] |= 0x80 >> (x & 7)
                left = 1
            else:
                reg_bytes[pixel_index] &= ~(0x80 >> (x & 7)) & 0xFF
                left = 0

    # Template 1 — typical prediction decode (LTP=1 path, §6.3.5.6 step 3d)
    # TPGRPIX=1 when the 3x3 reference neighbourhood is uniform (§6.3.5.6 3d-i)

    def _decode_line_tpgr_t1(self, y: int, width: int) -> None:
        above, ref_above, ref_row, ref_below = self._t1_line_rows(y, width)
        reg = self.region_bitmap
        reg_bytes = reg.bitmap_bytes
        reg_row = y * reg.row_stride
        cx = self.cx
        set_index = cx.set_index
        decode = self.arith_decoder.decode
        left = 0
        for x in range(width):
            center = ref_row[x + 1]
            if (
                ref_above[x] == center
                and ref_above[x + 1] == center
                and ref_above[x + 2] == center
                and ref_row[x] == center
                and ref_row[x + 2] == center
                and ref_below[x] == center
                and ref_below[x + 1] == center
                and ref_below[x + 2] == center
            ):
                bit = center
            else:
                set_index(
                    (above[x] << 9)
                    | (above[x + 1] << 8)
                    | (above[x + 2] << 7)
                    | (left << 6)
                    | (ref_above[x + 1] << 5)
                    | (ref_row[x] << 4)
                    | (ref_row[x + 1] << 3)
                    | (ref_row[x + 2] << 2)
                    | (ref_below[x + 1] << 1)
                    | ref_below[x + 2]
                )
                bit = decode(cx)
            pixel_index = reg_row + (x >> 3)
            if bit & 1:
                reg_bytes[pixel_index] |= 0x80 >> (x & 7)
                left = 1
            else:
                reg_bytes[pixel_index] &= ~(0x80 >> (x & 7)) & 0xFF
                left = 0

    def _t1_line_rows(
        self, y: int, width: int
    ) -> tuple[list[int], list[int], list[int], list[int]]:
        """Return the template-1 neighbour rows for line ``y``.

        Each list holds ``width + 2`` pixel values for ``x = -1 .. width``
        (entry ``k`` is column ``x = k - 1``): the region row ``y - 1`` and the
        reference rows ``y - 1``, ``y``, ``y + 1`` (in region coordinates,
        i.e. shifted by the reference offsets). Pixels outside a bitmap are 0,
        exactly as :meth:`_get_pixel_safe` returns them.
        """
        n = width + 2
        rdx = self.reference_dx
        rdy = self.reference_dy
        ref = self.reference_bitmap
        return (
            _row_bits(self.region_bitmap, y - 1, -1, n),
            _row_bits(ref, y - 1 - rdy, -1 - rdx, n),
            _row_bits(ref, y - rdy, -1 - rdx, n),
            _row_bits(ref, y + 1 - rdy, -1 - rdx, n),
        )

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
        elif self.template_id == 1:  # pragma: no cover
            # Unreachable: upstream's run() (GenericRefinementRegionDecodingProcedure.java
            # lines 256-277) dispatches template 1 exclusively through the per-pixel
            # decodeLineExplicitT1 / decodeLineTPGRT1, never through decodeOptimized's
            # case 1. This faithful port of upstream's never-called template-1 fast
            # path is kept for upstream-structure fidelity (see PROVENANCE).
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

        mod_reference_dx = _java_mod(self.reference_dx, 8)
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

        # Java's ``int <<`` masks the shift count to its low 5 bits, so a
        # negative ``modBitsToTrim`` (which Java's truncated remainder can yield
        # when ``modReferenceDX`` exceeds 2) shifts by ``count & 0x1F`` rather
        # than raising; mirror that here.
        mod_bits_to_trim = _java_mod(2 - mod_reference_dx, 8) & 0x1F
        w1 = (w1 << mod_bits_to_trim) & _MASK32
        w2 = (w2 << mod_bits_to_trim) & _MASK32
        w3 = (w3 << mod_bits_to_trim) & _MASK32

        w4 = (w4 << 2) & _MASK32

        # Per-pixel loop with the reference/region bitmap accessors, the
        # template-0 context formation and the MQ DECODE procedure of
        # ArithmeticDecoder.decode inlined (registers in locals, written back
        # after the line). The line-constant reference-row bounds checks are
        # hoisted; ``_java_mod(x - referenceDX, 8) == 5`` is only possible for
        # a non-negative dividend, where it equals ``(x - referenceDX) & 7``.
        ref_bytes = ref.bitmap_bytes
        reg_bytes = reg.bitmap_bytes
        ref_height = ref.height
        reg_stride = reg.row_stride
        has_w1 = current_line >= 1 and (current_line - 1 < ref_height)
        has_w2 = current_line >= 0 and current_line < ref_height
        has_w3 = current_line >= -1 and (current_line + 1) < ref_height
        reference_dx = self.reference_dx
        is_t0 = template_formation is T0
        form = template_formation.form
        override = self.override
        override_at = self._override_at_template0
        reg_row = line_number * reg_stride

        dec = self.arith_decoder
        cx = self.cx
        # The inlined DECODE needs the concrete decoder / context classes; any
        # other decoder object is driven through its ``decode`` method.
        inline = type(dec) is ArithmeticDecoder and type(cx) is CX
        cx_arr = cx._cx if inline else None
        mps_arr = cx._mps if inline else None
        qe_table = QE_DECODE
        renorm_shifts = RENORM_SHIFTS
        a = dec.a if inline else 0
        c = dec.c if inline else 0
        ct = dec.ct if inline else 0
        index = cx.index

        for x in range(width):
            minor_x = x & 0x07

            if is_t0:
                tval = ((c1 << 10) | (c2 << 7) | (c3 << 4) | (c4 << 1) | c5) & 0xFFFF
            else:
                tval = form(c1, c2, c3, c4, c5)

            if override:
                index = override_at(
                    tval, x, line_number, reg_bytes[reg_row + (x >> 3)], minor_x
                )
            else:
                index = tval

            if not inline:
                cx.set_index(index)
                bit = dec.decode(cx)
            else:
                # Inlined ArithmeticDecoder.decode (E.3.2).
                row = qe_table[cx_arr[index] & 0x7F]
                qe_value = row[0]
                a -= qe_value
                if c < row[4]:
                    # LPS_EXCHANGE
                    mps = mps_arr[index]
                    if a < qe_value:
                        cx_arr[index] = row[1]
                        bit = mps
                    else:
                        if row[3] == 1:
                            mps_arr[index] = mps ^ 1
                        cx_arr[index] = row[2]
                        bit = 1 - mps
                    a = qe_value
                    # RENORMD
                    n = renorm_shifts[a]
                    if ct >= n:
                        a <<= n
                        c = (c << n) & _MASK32
                        ct -= n
                    else:
                        while True:
                            if ct == 0:
                                dec.c = c
                                dec._byte_in()
                                c = dec.c
                                ct = dec.ct
                            a <<= 1
                            c = (c << 1) & _MASK32
                            ct -= 1
                            if a & 0x8000:
                                break
                else:
                    c -= row[4]
                    if a & 0x8000:
                        bit = mps_arr[index]
                    else:
                        # MPS_EXCHANGE
                        mps = mps_arr[index]
                        if a < qe_value:
                            if row[3] == 1:
                                mps_arr[index] = mps ^ 1
                            cx_arr[index] = row[2]
                            bit = 1 - mps
                        else:
                            cx_arr[index] = row[1]
                            bit = mps
                        # RENORMD
                        n = renorm_shifts[a]
                        if ct >= n:
                            a <<= n
                            c = (c << n) & _MASK32
                            ct -= n
                        else:
                            while True:
                                if ct == 0:
                                    dec.c = c
                                    dec._byte_in()
                                    c = dec.c
                                    ct = dec.ct
                                a <<= 1
                                c = (c << 1) & _MASK32
                                ct -= 1
                                if a & 0x8000:
                                    break

            # reg.set_pixel(x, line_number, bit)
            pixel_index = reg_row + (x >> 3)
            if bit & 1:
                reg_bytes[pixel_index] |= 0x80 >> minor_x
            else:
                reg_bytes[pixel_index] &= ~(0x80 >> minor_x) & 0xFF

            c1 = ((c1 << 1) | (0x01 & (w1 >> 7))) & 0x07
            c2 = ((c2 << 1) | (0x01 & (w2 >> 7))) & 0x07
            c3 = ((c3 << 1) | (0x01 & (w3 >> 7))) & 0x07
            c4 = ((c4 << 1) | (0x01 & (w4 >> 7))) & 0x07
            c5 = bit & 0xFFFF

            ref_x = x - reference_dx
            if ref_x >= 0 and (ref_x & 0x07) == 5:
                if (ref_x >> 3) + 1 >= ref_row_stride:
                    w1 = w2 = w3 = 0
                else:
                    w1 = ref_bytes[ref_byte_index - ref_row_stride] if has_w1 else 0
                    w2 = ref_bytes[ref_byte_index] if has_w2 else 0
                    w3 = ref_bytes[ref_byte_index + ref_row_stride] if has_w3 else 0
                ref_byte_index += 1
            else:
                w1 = (w1 << 1) & _MASK32
                w2 = (w2 << 1) & _MASK32
                w3 = (w3 << 1) & _MASK32

            if minor_x == 5 and line_number >= 1:
                w4 = 0 if (x >> 3) + 1 >= reg_stride else reg_bytes[byte_index - row_stride]
                byte_index += 1
            else:
                w4 = (w4 << 1) & _MASK32

        if inline:
            dec.a = a
            dec.c = c
            dec.ct = ct
            cx.index = index

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
        elif self.template_id == 1:  # pragma: no cover
            # Unreachable: _update_override is only invoked from run() when
            # template_id == 0 (AT pixels are template-0-only). Faithful to
            # upstream's switch, which carries the same never-taken case 1.
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
        elif self.template_id == 1:  # pragma: no cover
            # Unreachable: see _decode_optimized's case-1 note. run() never reaches
            # decodeTypicalPredictedLine for template 1 (per-pixel path is used
            # instead); kept faithful to upstream's never-called fast path.
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
            minor_width = min(width - x, 8)
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

    def _decode_typical_predicted_line_template1(  # pragma: no cover
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
        # Unreachable in upstream and in this port: the optimized template-1
        # typical-prediction byte-blit (GenericRefinementRegionDecodingProcedure.java
        # decodeTypicalPredictedLineTemplate1). run() dispatches template-1 TPGR
        # lines through the per-pixel decodeLineTPGRT1 instead. Ported verbatim for
        # upstream-structure fidelity; excluded from coverage as structurally dead.
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
            minor_width = min(width - x, 8)
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
                # Java's ``int >>`` masks the shift count to its low 5 bits, so a
                # negative ``7 - (minor_x + gr_at_x[0])`` (which arises when an AT
                # pixel pushes ``minor_x + gr_at_x[0]`` past 7) shifts by
                # ``count & 0x1F`` rather than raising; mirror that here.
                shift = (7 - (minor_x + self.gr_at_x[0])) & 0x1F
                context |= ((result >> shift) & 0x1) << 3
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
