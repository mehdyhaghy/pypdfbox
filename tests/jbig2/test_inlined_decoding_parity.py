"""The inlined JBIG2 decoding loops match the reference call-per-decision code.

The production MQ decoder, integer decoder, generic-region template loops,
refinement loops, unshifted blit, MMR line fill and halftone gray-scale steps
inline the per-decision / per-pixel calls of their straightforward versions.
``tests/jbig2/helpers/reference_decoding.py`` keeps those straightforward
versions verbatim; every test here decodes the same input with both and
requires identical bitmaps and identical decoder / context state afterwards.
Arithmetic-coded inputs are random byte strings: the MQ decoder accepts any
byte sequence, so random data drives every LPS / MPS / exchange / byte-stuffing
branch with no encoder needed.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import (
    QE,
    QE_DECODE,
    RENORM_SHIFTS,
    ArithmeticDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    ArithmeticIntegerDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure,
)
from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import MMRDecompressor
from pypdfbox.jbig2.image.bitmaps import _blit_unshifted
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from pypdfbox.jbig2.segments.generic_region import GenericRegion
from pypdfbox.jbig2.segments.halftone_region import HalftoneRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator
from tests.jbig2.helpers.reference_decoding import (
    RefArithmeticDecoder,
    RefArithmeticIntegerDecoder,
    RefGenericRegion,
    ref_blit_unshifted,
    ref_combine_gray_scale_planes,
    ref_compute_gray_scale_values,
    ref_fill_bitmap,
    ref_refinement_decode,
)

FIXTURES = Path(__file__).parent / "fixtures"

NOMINAL_AT = {
    0: ([3, -3, 2, -2], [-1, -1, -2, -2]),
    1: ([3], [-1]),
    2: ([2], [-1]),
    3: ([2], [-1]),
}
NOMINAL_EXT_AT = (
    [-2, 0, -2, -1, 1, 2, -3, -4, 2, 3, -2, -3],
    [0, -2, -1, -2, -2, -1, 0, 0, -2, -1, -2, -1],
)


def _random_data(rng: random.Random, n: int) -> bytes:
    # Bias towards 0xFF so the BYTEIN marker / stuffing branches are hit.
    return bytes(0xFF if rng.random() < 0.08 else rng.randrange(256) for _ in range(n))


def _random_bitmap(rng: random.Random, width: int, height: int) -> Bitmap:
    bm = Bitmap(width, height)
    bm.bitmap_bytes[:] = bytes(rng.randrange(256) for _ in range(len(bm.bitmap_bytes)))
    return bm


def _outcome(fn, *args):
    """Run ``fn``; return ``("ok", result)`` or ``("error", exception type)``."""
    try:
        return ("ok", fn(*args))
    except (IndexError, ValueError, OSError) as exc:
        return ("error", type(exc))


def _decoder_state(dec, iis) -> tuple:
    return (dec.a, dec.c, dec.ct, dec.b, iis.get_stream_position())


def _cx_state(cx: CX) -> tuple:
    return (bytes(cx._cx), bytes(cx._mps), cx.index)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


def test_decode_tables_match_qe() -> None:
    assert len(QE_DECODE) == len(QE)
    for row, ext in zip(QE, QE_DECODE, strict=True):
        assert ext[:4] == row
        assert ext[4] == row[0] << 16
    for a in range(1, 0x8000):
        n = RENORM_SHIFTS[a]
        assert (a << n) & 0x8000
        assert not (a << (n - 1)) & 0x8000


# --------------------------------------------------------------------------
# MQ decoder and integer decoder
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(12))
def test_arithmetic_decoder_matches_reference(seed: int) -> None:
    rng = random.Random(seed)
    data = _random_data(rng, rng.randint(0, 300))
    iis_new = ImageInputStream(data)
    iis_ref = ImageInputStream(data)
    dec = ArithmeticDecoder(iis_new)
    ref = RefArithmeticDecoder(iis_ref)
    cx = CX(64, 0)
    cx_ref = CX(64, 0)
    for _ in range(4000):
        index = rng.randrange(64) if rng.random() < 0.5 else rng.randrange(4)
        cx.set_index(index)
        cx_ref.set_index(index)
        assert dec.decode(cx) == ref.decode(cx_ref)
        assert _decoder_state(dec, iis_new) == _decoder_state(ref, iis_ref)
    assert _cx_state(cx) == _cx_state(cx_ref)


@pytest.mark.parametrize("seed", range(10))
def test_integer_decoder_matches_reference(seed: int) -> None:
    rng = random.Random(100 + seed)
    data = _random_data(rng, rng.randint(1, 400))
    iis_new = ImageInputStream(data)
    iis_ref = ImageInputStream(data)
    dec = ArithmeticDecoder(iis_new)
    ref = RefArithmeticDecoder(iis_ref)
    int_new = ArithmeticIntegerDecoder(dec)
    int_ref = RefArithmeticIntegerDecoder(ref)
    contexts = [CX(512, 1) for _ in range(3)]
    contexts_ref = [CX(512, 1) for _ in range(3)]
    iaid = CX(1 << 10, 1)
    iaid_ref = CX(1 << 10, 1)
    for _ in range(600):
        if rng.random() < 0.7:
            k = rng.randrange(3)
            assert int_new.decode(contexts[k]) == int_ref.decode(contexts_ref[k])
        else:
            code_len = rng.randint(0, 10)
            assert int_new.decode_iaid(iaid, code_len) == int_ref.decode_iaid(
                iaid_ref, code_len
            )
        assert _decoder_state(dec, iis_new) == _decoder_state(ref, iis_ref)
    for got, want in zip(contexts + [iaid], contexts_ref + [iaid_ref], strict=True):
        assert _cx_state(got) == _cx_state(want)
    # A ``None`` context gets a fresh CX in both.
    assert int_new.decode(None) == int_ref.decode(None)
    assert _decoder_state(dec, iis_new) == _decoder_state(ref, iis_ref)


class _IndexHashDecoder:
    """A non-MQ decoder: the bit is a hash of the context index."""

    def __init__(self) -> None:
        self.calls = 0

    def decode(self, cx: CX) -> int:
        self.calls += 1
        return ((cx.index * 2654435761 + self.calls * 40503) >> 13) & 1


def test_integer_decoder_drives_foreign_decoder_through_decode() -> None:
    new = ArithmeticIntegerDecoder(_IndexHashDecoder())
    ref = RefArithmeticIntegerDecoder(_IndexHashDecoder())
    for code_len in range(12):
        cx_a, cx_b = CX(512, 1), CX(512, 1)
        assert new.decode(cx_a) == ref.decode(cx_b)
        assert _cx_state(cx_a) == _cx_state(cx_b)
        id_a, id_b = CX(1 << 11, 1), CX(1 << 11, 1)
        assert new.decode_iaid(id_a, code_len) == ref.decode_iaid(id_b, code_len)
        assert _cx_state(id_a) == _cx_state(id_b)


# --------------------------------------------------------------------------
# Generic region (6.2.5.7)
# --------------------------------------------------------------------------


def _generic_region(
    cls,
    data: bytes,
    width: int,
    height: int,
    template: int,
    ext: bool,
    tpgdon: bool,
    at: tuple[list[int], list[int]],
    h_skip: Bitmap | None,
) -> GenericRegion:
    sis = SubInputStream(ImageInputStream(data), 0, len(data))
    region = cls(sis)
    region.set_parameters(
        False,
        0,
        len(data),
        height,
        width,
        template,
        tpgdon,
        h_skip is not None,
        h_skip,
        list(at[0]),
        list(at[1]),
    )
    region.use_ext_templates = ext
    return region


def _random_at(rng: random.Random, template: int, ext: bool) -> tuple[list[int], list[int]]:
    nominal = NOMINAL_EXT_AT if ext else NOMINAL_AT[template]
    xs, ys = list(nominal[0]), list(nominal[1])
    if rng.random() < 0.5:
        for i in range(len(xs)):
            if rng.random() < 0.5:
                ys[i] = rng.randint(-3, 0)
                xs[i] = rng.randint(-9, 9)
    return xs, ys


_GENERIC_CASES = [
    (template, ext)
    for template in range(4)
    for ext in ((False, True) if template == 0 else (False,))
]


@pytest.mark.parametrize(
    ("template", "ext"),
    _GENERIC_CASES,
    ids=[f"t{t}{'ext' if e else ''}" for t, e in _GENERIC_CASES],
)
def test_generic_region_matches_reference(template: int, ext: bool) -> None:
    rng = random.Random(template * 10 + ext)
    for trial in range(40):
        width = rng.choice([1, 2, 7, 8, 9, 15, 16, 17, 31, 33, rng.randint(1, 70)])
        height = rng.randint(1, 14)
        tpgdon = rng.random() < 0.4
        at = _random_at(rng, template, ext)
        h_skip = _random_bitmap(rng, width, height) if rng.random() < 0.25 else None
        data = _random_data(rng, rng.randint(0, 200))

        new = _generic_region(GenericRegion, data, width, height, template, ext, tpgdon, at, h_skip)
        ref = _generic_region(
            RefGenericRegion, data, width, height, template, ext, tpgdon, at, h_skip
        )
        got = new.get_region_bitmap()
        want = ref.get_region_bitmap()
        context = (trial, width, height, tpgdon, at, h_skip is not None)
        assert got.bitmap_bytes == want.bitmap_bytes, context
        assert new.override == ref.override
        assert _decoder_state(new.arith_decoder, new.sub_input_stream) == _decoder_state(
            ref.arith_decoder, ref.sub_input_stream
        ), context
        assert _cx_state(new.cx) == _cx_state(ref.cx), context


@pytest.mark.parametrize(
    ("template", "ext"),
    _GENERIC_CASES,
    ids=[f"t{t}{'ext' if e else ''}" for t, e in _GENERIC_CASES],
)
def test_generic_template_line_methods_match_reference(template: int, ext: bool) -> None:
    # The per-line ``_decode_template*`` entry points, called line by line.
    rng = random.Random(500 + template * 10 + ext)
    name = {0: "_decode_template0b" if ext else "_decode_template0a"}.get(
        template, f"_decode_template{template}"
    )
    for _ in range(15):
        width = rng.randint(1, 50)
        height = rng.randint(1, 8)
        at = _random_at(rng, template, ext)
        data = _random_data(rng, 120)
        regions = []
        for cls, dec_cls in (
            (GenericRegion, ArithmeticDecoder),
            (RefGenericRegion, RefArithmeticDecoder),
        ):
            region = _generic_region(cls, data, width, height, template, ext, False, at, None)
            region._update_override_flags()
            region.arith_decoder = dec_cls(region.sub_input_stream)
            region.cx = CX(65536, 1)
            region.region_bitmap = Bitmap(width, height)
            stride = region.region_bitmap.get_row_stride()
            for line in range(height):
                getattr(region, name)(
                    line, width, stride, (width + 7) & -8, line * stride, (line - 1) * stride
                )
            regions.append(region)
        new, ref = regions
        assert new.region_bitmap.bitmap_bytes == ref.region_bitmap.bitmap_bytes
        assert _cx_state(new.cx) == _cx_state(ref.cx)


@pytest.mark.parametrize("template", range(4))
def test_generic_region_with_foreign_decoder_matches_reference(template: int) -> None:
    rng = random.Random(900 + template)
    for _ in range(20):
        width = rng.randint(1, 40)
        height = rng.randint(1, 8)
        at = _random_at(rng, template, False)
        h_skip = _random_bitmap(rng, width, height) if rng.random() < 0.3 else None
        tpgdon = rng.random() < 0.5
        bitmaps = []
        for cls in (GenericRegion, RefGenericRegion):
            region = _generic_region(cls, b"", width, height, template, False, tpgdon, at, h_skip)
            region.arith_decoder = _IndexHashDecoder()
            region.cx = CX(65536, 1)
            bitmaps.append(bytes(region.get_region_bitmap().bitmap_bytes))
        assert bitmaps[0] == bitmaps[1]


# --------------------------------------------------------------------------
# Refinement (6.3.5.6)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("gr_template", [0, 1])
@pytest.mark.parametrize("tpgr", [False, True], ids=["plain", "tpgr"])
def test_refinement_matches_reference(gr_template: int, tpgr: bool) -> None:
    rng = random.Random(gr_template * 2 + tpgr)
    for trial in range(40):
        width = rng.randint(1, 45)
        height = rng.randint(1, 12)
        ref_w = max(1, width + rng.randint(-4, 4))
        ref_h = max(1, height + rng.randint(-3, 3))
        reference = _random_bitmap(rng, ref_w, ref_h)
        if rng.random() < 0.3:
            # Large uniform areas make the TPGR typical-pixel branch fire.
            fill = rng.choice([0x00, 0xFF])
            reference.bitmap_bytes[:] = bytes([fill]) * len(reference.bitmap_bytes)
        dx = rng.randint(-10, 10)
        dy = rng.randint(-3, 3)
        if gr_template == 0 and rng.random() < 0.5:
            at_x = [rng.randint(-4, 4), rng.randint(-4, 4)]
            at_y = [rng.randint(-2, 0), rng.randint(-2, 2)]
        else:
            at_x, at_y = [-1, -1], [-1, -1]
        data = _random_data(rng, rng.randint(0, 200))
        iis_new = ImageInputStream(data)
        iis_ref = ImageInputStream(data)
        dec = ArithmeticDecoder(iis_new)
        ref_dec = RefArithmeticDecoder(iis_ref)
        cx = CX(8192, 1)
        cx_ref = CX(8192, 1)
        status, got = _outcome(
            GenericRefinementRegionDecodingProcedure.decode,
            dec, cx, width, height, gr_template, tpgr, reference, dx, dy, at_x, at_y,
        )
        ref_status, want = _outcome(
            ref_refinement_decode,
            ref_dec, cx_ref, width, height, gr_template, tpgr, reference, dx, dy, at_x, at_y,
        )
        context = (trial, width, height, ref_w, ref_h, dx, dy, at_x, at_y)
        # Some random geometries make the (unchanged) TPGR template-0 line
        # reader index past the reference bitmap; both must then fail alike.
        assert (status, ref_status) in (("ok", "ok"), ("error", "error")), context
        if status == "error":
            assert got == want, context
            continue
        assert got.bitmap_bytes == want.bitmap_bytes, context
        assert _decoder_state(dec, iis_new) == _decoder_state(ref_dec, iis_ref), context
        assert _cx_state(cx) == _cx_state(cx_ref), context


@pytest.mark.parametrize("gr_template", [0, 1])
def test_refinement_with_foreign_decoder_matches_reference(gr_template: int) -> None:
    rng = random.Random(77 + gr_template)
    for _ in range(20):
        width = rng.randint(1, 30)
        height = rng.randint(1, 8)
        reference = _random_bitmap(rng, width + 2, height + 1)
        dx, dy = rng.randint(-3, 3), rng.randint(-2, 2)
        tpgr = rng.random() < 0.5
        status, got = _outcome(
            GenericRefinementRegionDecodingProcedure.decode,
            _IndexHashDecoder(), CX(8192, 1), width, height, gr_template, tpgr,
            reference, dx, dy, [-1, 2], [-1, 1],
        )
        ref_status, want = _outcome(
            ref_refinement_decode,
            _IndexHashDecoder(), CX(8192, 1), width, height, gr_template, tpgr,
            reference, dx, dy, [-1, 2], [-1, 1],
        )
        assert status == ref_status
        if status == "ok":
            assert got.bitmap_bytes == want.bitmap_bytes
        else:
            assert got == want


# --------------------------------------------------------------------------
# Bulk byte operations
# --------------------------------------------------------------------------


@pytest.mark.parametrize("op", list(CombinationOperator), ids=lambda o: o.name)
def test_blit_unshifted_matches_reference(op: CombinationOperator) -> None:
    rng = random.Random(op.value + 1000)
    for _ in range(200):
        src = _random_bitmap(rng, rng.randint(1, 80), rng.randint(1, 10))
        dst = _random_bitmap(rng, rng.randint(1, 120), rng.randint(1, 14))
        lines = rng.randint(0, min(src.height, dst.height))
        start_line = rng.randint(0, 3)
        src_start = rng.randint(0, src.row_stride - 1)
        src_end = rng.randint(src_start - 1, src.row_stride - 1)
        dst_start = rng.randint(0, max(0, dst.row_stride - (src_end - src_start + 1)))
        expected = Bitmap(dst.width, dst.height)
        expected.bitmap_bytes[:] = dst.bitmap_bytes
        args = (start_line, start_line + lines, dst_start, src_start, src_end, op)
        want = _outcome(ref_blit_unshifted, src, expected, *args)
        got = _outcome(_blit_unshifted, src, dst, *args)
        assert got == want
        if got[0] == "ok":
            assert dst.bitmap_bytes == expected.bitmap_bytes


def test_blit_unshifted_out_of_range_keeps_reference_behavior() -> None:
    # A span running past the destination falls back to the per-byte loop,
    # which raises ``IndexError`` exactly as before.
    src = Bitmap(64, 2)
    src.bitmap_bytes[:] = bytes(range(16))
    for impl in (_blit_unshifted, ref_blit_unshifted):
        dst = Bitmap(16, 2)
        with pytest.raises(IndexError):
            impl(src, dst, 0, 2, 0, 0, 7, CombinationOperator.OR)


def test_mmr_fill_bitmap_matches_reference() -> None:
    rng = random.Random(4242)
    decompressor = MMRDecompressor(8, 1, ImageInputStream(b"\x00" * 8))
    for _ in range(400):
        width = rng.randint(1, 200)
        height = rng.randint(1, 4)
        line = rng.randrange(height)
        count = rng.randint(0, 12)
        offsets = sorted(rng.randint(-2, width + 1) for _ in range(count))
        if rng.random() < 0.2:
            rng.shuffle(offsets)
        new = _random_bitmap(rng, width, height)
        ref = Bitmap(width, height)
        ref.bitmap_bytes[:] = new.bitmap_bytes
        error_new = error_ref = None
        try:
            decompressor.fill_bitmap(new, line, offsets, count)
        except IndexError as exc:
            error_new = type(exc)
        try:
            ref_fill_bitmap(ref, line, offsets, count)
        except IndexError as exc:
            error_ref = type(exc)
        assert error_new == error_ref
        assert new.bitmap_bytes == ref.bitmap_bytes, (width, line, offsets)


def test_halftone_gray_scale_steps_match_reference() -> None:
    rng = random.Random(31337)
    for _ in range(60):
        width = rng.randint(1, 40)
        height = rng.randint(1, 9)
        bits = rng.randint(1, 8)
        planes = [_random_bitmap(rng, width, height) for _ in range(bits)]
        planes_ref = []
        for plane in planes:
            copy = Bitmap(width, height)
            copy.bitmap_bytes[:] = plane.bitmap_bytes
            planes_ref.append(copy)
        region = HalftoneRegion()
        region.h_grid_width = width
        region.h_grid_height = height
        for j in range(bits - 2, -1, -1):
            region._combine_gray_scale_planes(planes, j)
            ref_combine_gray_scale_planes(planes_ref, j)
        assert [p.bitmap_bytes for p in planes] == [p.bitmap_bytes for p in planes_ref]
        assert region._compute_gray_scale_values(planes, bits) == (
            ref_compute_gray_scale_values(width, height, planes_ref, bits)
        )


# --------------------------------------------------------------------------
# Whole-file decode pins
# --------------------------------------------------------------------------

_FIXTURE_DIGESTS = [
    ("003.jb2", None, "1cbd3f2491b3087dc6752ee3cc217e6f49a35d6d373d8f6a533beeb5cc9109b2"),
    ("005.jb2", None, "22c37cad3db25a482a62e2dc38d169787ff64c9dfdd07905e91c717c58e73455"),
    ("006.jb2", None, "7d54f615b432c699a9bb798a0cb962dc2d2f9009ddf911eff321fb95d37b03a0"),
    (
        "20123110001.jb2",
        None,
        "5fb56dbdbfc3be816cf8e3600ee4777a4539bb3800e41fedb62079a2ce31f23f",
    ),
    ("21.jb2", "21.glob", "b3025c05a0894e09a4c4f610b038f89fd844783df07523bca87d110efa6979cf"),
]


@pytest.mark.parametrize(
    ("name", "glob", "digest"), _FIXTURE_DIGESTS, ids=[n for n, _, _ in _FIXTURE_DIGESTS]
)
def test_fixture_page_bitmaps_unchanged(name: str, glob: str | None, digest: str) -> None:
    # Digests of the page bitmaps as decoded before the loops were inlined.
    global_segments = (
        JBIG2Document(ImageInputStream((FIXTURES / glob).read_bytes())).get_global_segments()
        if glob
        else None
    )
    doc = JBIG2Document(ImageInputStream((FIXTURES / name).read_bytes()), global_segments)
    h = hashlib.sha256()
    for page in range(1, doc.get_amount_of_pages() + 1):
        h.update(bytes(doc.get_page(page).get_bitmap().get_byte_array()))
    assert h.hexdigest() == digest
