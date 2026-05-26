"""Hand-written unit tests for the JBIG2 Generic Refinement Region cluster.

Covers ``GenericRefinementRegion`` (the segment-level class — flag/AT parsing,
reference resolution, parameter-driven decode) and
``GenericRefinementRegionDecodingProcedure`` (the pure §6.3.5.6 algorithm).

The decoding procedure reads its arithmetic-coded input through a
``javax.imageio.stream.ImageInputStream``-like reader. As in the arithmetic
decoder tests, an in-test ``MemoryImageInputStream`` shim mirrors the exact
surface the decoder uses (``get_stream_position`` / ``read`` / ``seek``).

The pinned expected bitmaps in :func:`test_template0_*` were produced by the
live Apache PDFBox oracle (see
``tests/jbig2/segments/oracle/test_generic_refinement_region_oracle.py``) for
template-0, TPGRON-off cases — the paths the bundled 3.0.7 jar shares with the
refactored upstream we ported. The template-1 and TPGRON paths are verified
structurally here (the 3.0.7 jar crashes on TPGRON and routes template 1
through a different code path; full bit-exact coverage of those lands when the
pipeline is wired against a refactored-version jar).
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    T0,
    T1,
    GenericRefinementRegionDecodingProcedure,
    Template,
)
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.io.default_input_stream_factory import DefaultInputStreamFactory
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.generic_refinement_region import GenericRefinementRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


class MemoryImageInputStream:
    """Minimal ``ImageInputStream`` shim backed by an in-memory byte buffer.

    Matches ``javax.imageio.stream.MemoryCacheImageInputStream`` for the calls
    the arithmetic decoder makes: ``read`` returns -1 at/after EOF and leaves
    the position unchanged; ``seek`` may move past the logical end.
    """

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._pos = 0

    def get_stream_position(self) -> int:
        return self._pos

    def read(self) -> int:
        if self._pos >= len(self._data):
            return -1
        value = self._data[self._pos]
        self._pos += 1
        return value

    def seek(self, pos: int) -> None:
        self._pos = pos


def _make_reference(width: int, height: int, hexbytes: str) -> Bitmap:
    bmp = Bitmap(width, height)
    raw = bytes.fromhex(hexbytes)
    n = min(len(bmp.bitmap_bytes), len(raw))
    bmp.bitmap_bytes[:n] = raw[:n]
    return bmp


def _decode(
    *,
    gr_template: int,
    width: int,
    height: int,
    ref_w: int,
    ref_h: int,
    dx: int,
    dy: int,
    tpgr: bool,
    ref_hex: str,
    coded_hex: str,
    at_x: list[int] | None = None,
    at_y: list[int] | None = None,
) -> Bitmap:
    reference = _make_reference(ref_w, ref_h, ref_hex)
    decoder = ArithmeticDecoder(MemoryImageInputStream(bytes.fromhex(coded_hex)))
    cx = CX(8192, 1)
    return GenericRefinementRegionDecodingProcedure.decode(
        decoder,
        cx,
        width,
        height,
        gr_template,
        tpgr,
        reference,
        dx,
        dy,
        at_x if at_x is not None else [-1, -1],
        at_y if at_y is not None else [-1, -1],
    )


def _sub_input_stream(data: bytes) -> SubInputStream:
    factory = DefaultInputStreamFactory()
    iis = factory.get_input_stream(data)
    return SubInputStream(iis, 0, len(data))


# -------------------------------------------------------------------------
# Template strategy unit tests (§6.3.5.6, Figures 14-15)
# -------------------------------------------------------------------------


def test_template0_form_packs_five_context_groups():
    # (c1<<10)|(c2<<7)|(c3<<4)|(c4<<1)|c5
    assert T0.form(0, 0, 0, 0, 0) == 0
    assert T0.form(1, 0, 0, 0, 0) == 0x400
    assert T0.form(0, 0, 0, 0, 1) == 1
    assert T0.form(0x7, 0x7, 0x7, 0x7, 0x1) == (
        (0x7 << 10) | (0x7 << 7) | (0x7 << 4) | (0x7 << 1) | 0x1
    )


def test_template1_form_packs_masked_groups():
    # ((c1&2)<<8)|(c2<<6)|((c3&3)<<4)|(c4<<1)|c5
    assert T1.form(0, 0, 0, 0, 0) == 0
    assert T1.form(0x2, 0, 0, 0, 0) == 0x200
    assert T1.form(0x1, 0, 0, 0, 0) == 0  # bit 0 of c1 is masked out
    assert T1.form(0, 0, 0x3, 0, 0) == 0x30
    assert T1.form(0, 0, 0x4, 0, 0) == 0  # only low 2 bits of c3 used


def test_template_set_index_uses_sltp_constants():
    cx = CX(8192, 0)
    T0.set_index(cx)
    assert cx.get_index() == 0x100
    T1.set_index(cx)
    assert cx.get_index() == 0x008


def test_template_base_class_is_abstract_surface():
    base = Template()
    with pytest.raises(NotImplementedError):
        base.form(0, 0, 0, 0, 0)
    with pytest.raises(NotImplementedError):
        base.set_index(CX(8, 0))


# -------------------------------------------------------------------------
# decode() parameter validation
# -------------------------------------------------------------------------


def test_decode_rejects_none_decoder():
    with pytest.raises(ValueError, match="arithDecoder"):
        GenericRefinementRegionDecodingProcedure.decode(
            None, CX(8192, 1), 4, 4, 0, False, Bitmap(4, 4), 0, 0, [-1, -1], [-1, -1]
        )


def test_decode_rejects_none_cx():
    decoder = ArithmeticDecoder(MemoryImageInputStream(b"\x00\x00"))
    with pytest.raises(ValueError, match="cx"):
        GenericRefinementRegionDecodingProcedure.decode(
            decoder, None, 4, 4, 0, False, Bitmap(4, 4), 0, 0, [-1, -1], [-1, -1]
        )


def test_decode_rejects_none_reference():
    decoder = ArithmeticDecoder(MemoryImageInputStream(b"\x00\x00"))
    with pytest.raises(ValueError, match="referenceBitmap"):
        GenericRefinementRegionDecodingProcedure.decode(
            decoder, CX(8192, 1), 4, 4, 0, False, None, 0, 0, [-1, -1], [-1, -1]
        )


@pytest.mark.parametrize("bad_template", [-1, 2, 3])
def test_decode_rejects_invalid_template(bad_template):
    decoder = ArithmeticDecoder(MemoryImageInputStream(b"\x00\x00"))
    with pytest.raises(ValueError, match="grTemplate"):
        GenericRefinementRegionDecodingProcedure.decode(
            decoder, CX(8192, 1), 4, 4, bad_template, False,
            Bitmap(4, 4), 0, 0, [-1, -1], [-1, -1],
        )


@pytest.mark.parametrize(
    ("at_x", "at_y"),
    [(None, [-1, -1]), ([-1, -1], None), ([-1], [-1, -1]), ([-1, -1], [-1])],
    ids=["x_none", "y_none", "x_short", "y_short"],
)
def test_decode_template0_requires_length2_at_arrays(at_x, at_y):
    decoder = ArithmeticDecoder(MemoryImageInputStream(b"\x00\x00"))
    with pytest.raises(ValueError, match="grAtX and grAtY"):
        GenericRefinementRegionDecodingProcedure.decode(
            decoder, CX(8192, 1), 4, 4, 0, False, Bitmap(4, 4), 0, 0, at_x, at_y
        )


def test_decode_template1_tolerates_none_at_arrays():
    # Template 1 ignores AT pixels — None must be accepted.
    result = _decode(
        gr_template=1, width=8, height=4, ref_w=8, ref_h=4, dx=0, dy=0,
        tpgr=False, ref_hex="8040c030", coded_hex="84c73b00ff12",
        at_x=None, at_y=None,
    )
    assert result.get_width() == 8
    assert result.get_height() == 4


@pytest.mark.parametrize(
    ("w", "h"), [(0, 4), (4, 0), (-1, 4), (4, -1)], ids=["w0", "h0", "wneg", "hneg"]
)
def test_decode_rejects_nonpositive_dimensions(w, h):
    decoder = ArithmeticDecoder(MemoryImageInputStream(b"\x00\x00"))
    with pytest.raises(ValueError, match="width and height"):
        GenericRefinementRegionDecodingProcedure.decode(
            decoder, CX(8192, 1), w, h, 0, False, Bitmap(4, 4), 0, 0, [-1, -1], [-1, -1]
        )


# -------------------------------------------------------------------------
# Template-0, TPGRON-off — bit-exact against the live PDFBox oracle.
# (These vectors are recomputed live in the oracle test; pinned here so the
#  suite stays meaningful on machines without Java.)
# -------------------------------------------------------------------------


def test_template0_basic_refine_matches_oracle():
    result = _decode(
        gr_template=0, width=8, height=4, ref_w=8, ref_h=4, dx=0, dy=0,
        tpgr=False, ref_hex="8040c030", coded_hex="84c73b00ff12abcd",
    )
    assert result.bitmap_bytes.hex() == "1d0671d1"


def test_template0_zero_reference_matches_oracle():
    result = _decode(
        gr_template=0, width=8, height=4, ref_w=8, ref_h=4, dx=0, dy=0,
        tpgr=False, ref_hex="00000000", coded_hex="00000000",
    )
    assert result.bitmap_bytes.hex() == "69fe57e3"


def test_template0_multibyte_width_matches_oracle():
    result = _decode(
        gr_template=0, width=24, height=8, ref_w=24, ref_h=8, dx=0, dy=0,
        tpgr=False,
        ref_hex="8040c030aa5511220ff0a1b2c3d4e5f60718293a",
        coded_hex="84c73b00ff12abcd5566778899",
    )
    assert result.bitmap_bytes.hex() == (
        "1e337ef553ca6ee8e17596cb327a34e850ffce25522c42ce"
    )


def test_template0_reference_offset_matches_oracle():
    result = _decode(
        gr_template=0, width=12, height=6, ref_w=12, ref_h=6, dx=1, dy=-1,
        tpgr=False, ref_hex="8040c030aa5511220ff0", coded_hex="84c73b00ff12abcd",
    )
    assert result.bitmap_bytes.hex() == "1f800de020c0466040f03eb0"


def test_template0_at_override_matches_oracle():
    # AT1=(-2,-2), AT2=(2,1): neither coord is -1, so the 3.0.7 jar and the
    # refactored upstream agree on override activation (the divergent case —
    # exactly one coord == -1 — is covered by the dedicated divergence test).
    result = _decode(
        gr_template=0, width=10, height=4, ref_w=10, ref_h=4, dx=0, dy=0,
        tpgr=False, ref_hex="8040c030aa55", coded_hex="84c73b00ff12",
        at_x=[-2, 2], at_y=[-2, 1],
    )
    assert result.bitmap_bytes.hex() == "1d0019c058000840"


def test_template0_nominal_at_no_override_matches_oracle():
    # AT at nominal (-1,-1): updateOverride leaves override off.
    result = _decode(
        gr_template=0, width=10, height=4, ref_w=10, ref_h=4, dx=0, dy=0,
        tpgr=False, ref_hex="8040c030aa55", coded_hex="84c73b00ff12",
        at_x=[-1, -1], at_y=[-1, -1],
    )
    assert result.bitmap_bytes.hex() == "1d0019c058000800"


# -------------------------------------------------------------------------
# Determinism / structural properties (templates 0 & 1, TPGRON on/off)
# -------------------------------------------------------------------------


@pytest.mark.parametrize("gr_template", [0, 1])
@pytest.mark.parametrize("tpgr", [False, True])
def test_decode_is_deterministic(gr_template, tpgr):
    kwargs = dict(
        gr_template=gr_template, width=16, height=6, ref_w=16, ref_h=6,
        dx=0, dy=0, tpgr=tpgr, ref_hex="8040c030aa5511220ff0a1b2",
        coded_hex="84c73b00ff12abcd5566",
    )
    first = _decode(**kwargs)
    second = _decode(**kwargs)
    assert first.bitmap_bytes == second.bitmap_bytes
    assert first.get_width() == 16
    assert first.get_height() == 6


def test_tpgr_t1_uniform_neighbourhood_copies_reference():
    # §6.3.5.6 3d-i: when the 3x3 reference neighbourhood is uniform (TPGRPIX=1)
    # the typical-prediction line routine copies the centre reference pixel
    # without consuming any coded bits. With an all-ones reference, interior
    # pixels (whose 3x3 window stays in-bounds and uniform) become 1; an
    # all-zero coded stream proves the bit came from the copy path, not decode.
    reference = _make_reference(16, 8, "ff" * 16)
    decoder = ArithmeticDecoder(MemoryImageInputStream(bytes.fromhex("00" * 8)))
    proc = GenericRefinementRegionDecodingProcedure(decoder, CX(8192, 1))
    proc.template_id = 1
    proc.template = T1
    proc.reference_bitmap = reference
    proc.reference_dx = 0
    proc.reference_dy = 0
    proc.gr_at_x = None
    proc.gr_at_y = None
    proc.override = False
    proc.region_bitmap = Bitmap(16, 8)

    proc._decode_line_tpgr_t1(4, 16)

    # Interior pixels: uniform 3x3 window -> copied as 1.
    assert proc.region_bitmap.get_pixel(8, 4) == 1
    # Left border pixel: window samples out-of-bounds (0) zeros, so the
    # neighbourhood is NOT uniform -> the pixel is arithmetically decoded
    # (from the all-zero stream) rather than copied.
    assert proc.region_bitmap.get_pixel(0, 4) == 0


def test_template1_explicit_and_tpgr_paths_produce_valid_bitmap():
    # Exercises both the LTP=0 (explicit) and LTP=1 (TPGR) template-1 line
    # routines via a mixed reference; asserts a well-formed bitmap.
    result = _decode(
        gr_template=1, width=20, height=10, ref_w=20, ref_h=10, dx=0, dy=0,
        tpgr=True, ref_hex="8040c030aa5511220ff0a1b2c3d4e5f6071829",
        coded_hex="84c73b00ff12abcd5566778899aabb",
    )
    assert result.get_width() == 20
    assert result.get_height() == 10
    assert len(result.bitmap_bytes) == result.get_row_stride() * 10


# -------------------------------------------------------------------------
# GenericRefinementRegion segment — header parsing (§7.4.7.2 / §7.4.7.3)
# -------------------------------------------------------------------------


def _region_info_header(
    width: int, height: int, x: int, y: int, comb_op: int
) -> bytes:
    # 7.4.1: width(4) height(4) x(4) y(4) flags(1, low 3 bits = comb op)
    return (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + x.to_bytes(4, "big")
        + y.to_bytes(4, "big")
        + bytes([comb_op & 0x07])
    )


def test_init_parses_template0_flags_and_at_pixels():
    # region info, then refinement flags byte (bit0 = templateID = 0,
    # bit1 = TPGRON = 1 -> 0b00000010 = 0x02), then 4 AT bytes.
    region = _region_info_header(8, 4, 0, 0, CombinationOperator.REPLACE.value)
    flags = bytes([0x02])
    at = bytes([0xFE, 0xFF, 0x02, 0x01])  # (-2,-1),(2,1) as signed bytes
    data = region + flags + at
    grr = GenericRefinementRegion()
    grr.init(header=_DummyHeader(), sis=_sub_input_stream(data))

    assert grr.template_id == 0
    assert grr.is_tpgr_on is True
    assert grr.gr_at_x == [-2, 2]
    assert grr.gr_at_y == [-1, 1]
    assert grr.get_region_info().get_bitmap_width() == 8
    assert grr.get_region_info().get_bitmap_height() == 4


def test_init_parses_template1_flags_without_at_pixels():
    region = _region_info_header(8, 4, 0, 0, CombinationOperator.REPLACE.value)
    # bit0 = templateID = 1, bit1 = TPGRON = 0 -> 0b00000001 = 0x01
    flags = bytes([0x01])
    data = region + flags
    grr = GenericRefinementRegion()
    grr.init(header=_DummyHeader(), sis=_sub_input_stream(data))

    assert grr.template_id == 1
    assert grr.is_tpgr_on is False
    assert grr.gr_at_x is None
    assert grr.gr_at_y is None


class _DummyHeader:
    """Minimal SegmentHeader stand-in for header-driven init/decode tests."""

    def __init__(self, rt_segments=None) -> None:
        self._rt = rt_segments

    def get_rt_segments(self):
        return self._rt


# -------------------------------------------------------------------------
# GenericRefinementRegion segment — reference resolution (§7.4.7.4/.5)
# -------------------------------------------------------------------------


def test_get_gr_reference_requires_replace_when_no_referred_segments():
    region = _region_info_header(8, 4, 0, 0, CombinationOperator.OR.value)
    flags = bytes([0x01])  # template 1, no AT
    data = region + flags
    grr = GenericRefinementRegion()
    grr.init(header=_DummyHeader(rt_segments=None), sis=_sub_input_stream(data))

    with pytest.raises(InvalidHeaderValueException, match="REPLACE"):
        grr.get_region_bitmap()


def test_get_region_bitmap_delegates_to_referred_region():
    # A referred-to region segment supplies the reference bitmap; the segment
    # parses cleanly and uses that region's bitmap as GRREFERENCE.
    region = _region_info_header(8, 4, 0, 0, CombinationOperator.REPLACE.value)
    flags = bytes([0x01])  # template 1, no AT
    # No coded payload needed for an 8x4 region beyond the arithmetic decoder
    # priming bytes; provide a couple of bytes so INITDEC has data.
    data = region + flags + bytes([0x00, 0x00, 0x00, 0x00])
    grr = GenericRefinementRegion()

    reference = _make_reference(8, 4, "8040c030")

    class _RefRegion:
        def get_region_bitmap(self):
            return reference

    class _RefHeader:
        def get_segment_data(self):
            return _RefRegion()

    grr.init(
        header=_DummyHeader(rt_segments=[_RefHeader()]),
        sis=_sub_input_stream(data),
    )
    out = grr.get_region_bitmap()
    assert out.get_width() == 8
    assert out.get_height() == 4
    # The reference bitmap was resolved from the referred-to region.
    assert grr.reference_bitmap is reference


# -------------------------------------------------------------------------
# GenericRefinementRegion segment — parameter-driven path
# -------------------------------------------------------------------------


def test_set_parameters_drives_decode_matching_procedure():
    reference = _make_reference(8, 4, "8040c030")
    decoder = ArithmeticDecoder(MemoryImageInputStream(bytes.fromhex("84c73b00ff12abcd")))
    cx = CX(8192, 1)

    grr = GenericRefinementRegion(sub_input_stream=None)
    grr.region_info = _RegionInfoStub()
    grr.set_parameters(
        cx, decoder, 0, 8, 4, reference, 0, 0, False, [-1, -1], [-1, -1]
    )
    out = grr.get_region_bitmap()

    # Same inputs as test_template0_basic_refine_matches_oracle.
    assert out.bitmap_bytes.hex() == "1d0671d1"


class _RegionInfoStub:
    def __init__(self) -> None:
        self._w = 0
        self._h = 0

    def set_bitmap_width(self, w):
        self._w = w

    def set_bitmap_height(self, h):
        self._h = h

    def get_bitmap_width(self):
        return self._w

    def get_bitmap_height(self):
        return self._h
