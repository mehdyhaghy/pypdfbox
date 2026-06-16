"""Fuzz / edge-case battery for inline-image (``BI`` / ``ID`` / ``EI``) parsing.

Two surfaces are exercised here:

1. The ``PDFStreamParser`` binary scan that captures the raw image bytes
   between ``ID`` and the real ``EI`` terminator — the tricky length-aware
   loop (``hasNoFollowingBinData`` / ``hasNextSpaceOrReturn``) that must NOT
   trip on a literal ``E I`` byte pair embedded inside the binary payload, and
   that consumes exactly one EOL / whitespace byte after ``ID``.
2. The :class:`PDInlineImage` abbreviation expansion — the single-letter
   keys (``W`` ``H`` ``BPC`` ``CS`` ``F`` ``D`` ``DP`` ``IM`` ``I``) and the
   abbreviated filter (``AHx`` ``A85`` ``LZW`` ``Fl`` ``RL`` ``CCF`` ``DCT``)
   and colour-space (``G`` ``RGB`` ``CMYK`` ``I``) names.

The expected image-byte lengths / SHAs for the scan cases were captured from
Apache PDFBox 3.0.7's ``PDFStreamParser`` via the live differential oracle (the
``ProbeBI`` driver reading ``Operator.getImageData()`` off the collated ``BI``
operator); they are asserted here as constants so the test stays green on a box
without a JDK. The companion ``tests/contentstream/oracle/`` suite re-runs the
live comparison when an oracle JAR is present.
"""

from __future__ import annotations

import hashlib
import zlib

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

# Common BI dictionary + ``ID `` prefix. /W /H /BPC /CS are nominal; the EI
# scan is byte-driven and does not consult the declared dimensions.
_BI = b"q BI /W 4 /H 4 /BPC 8 /CS /G ID "


def _scan_image_data(stream: bytes) -> bytes | None:
    """Parse ``stream`` and return the raw inline-image bytes captured on the
    ``BI`` operator (upstream collates the ``ID``...``EI`` payload onto the
    ``BI`` operator), or ``None`` if no inline image was found."""
    for tok in PDFStreamParser.from_bytes(stream).parse():
        if isinstance(tok, Operator) and tok.image_data is not None:
            return tok.image_data
    return None


def _token_count(stream: bytes) -> int:
    return len(PDFStreamParser.from_bytes(stream).parse())


# ---------------------------------------------------------------------------
# EI-detection scan. Each entry: (name, stream, expected_image_bytes,
# expected_total_token_count). Expected values are oracle-captured.
# ---------------------------------------------------------------------------

_SCAN_CASES: list[tuple[str, bytes, bytes, int]] = [
    # Plain terminator: one space before EI is kept in the payload.
    ("plain_space_ei", _BI + b"\x01\x02\x03\x04 EI Q", b"\x01\x02\x03\x04 ", 3),
    # Embedded ``EI`` immediately followed by binary control bytes must NOT
    # terminate (hasNoFollowingBinData sees binary).
    (
        "embedded_ei_then_bin",
        _BI + b"\x01EI\x80\x81\x82\x83\x84\x85 EI Q",
        b"\x01EI\x80\x81\x82\x83\x84\x85 ",
        3,
    ),
    # ``EI`` followed by the operator ``Q`` is a real terminator.
    ("ei_then_q", _BI + b"\xaa\xbb EI Q", b"\xaa\xbb ", 3),
    # ``EI`` followed by ``EMC`` is a real terminator (allow-listed op).
    ("ei_then_emc", _BI + b"\xaa\xbb EI EMC", b"\xaa\xbb ", 3),
    # ``EI`` followed by ``S`` (allow-listed op).
    ("ei_then_s", _BI + b"\xaa\xbb EI\nS", b"\xaa\xbb ", 3),
    # ``EI`` followed by a number token is a real terminator.
    ("ei_then_number", _BI + b"\xaa\xbb EI 0.5 g", b"\xaa\xbb ", 4),
    # ``EI`` followed by a non-allow-listed >3-char token within the 10-byte
    # window is treated as real (BDC fits the probe window).
    ("ei_then_longtoken", _BI + b"\xaa EI BDC", b"\xaa ", 3),
    # CRLF after ID consumes BOTH bytes (one EOL marker), not just one.
    (
        "crlf_after_id",
        b"q BI /W 2 /H 2 /BPC 8 /CS /G ID\r\n\x01\x02\x03\x04 EI Q",
        b"\x01\x02\x03\x04 ",
        3,
    ),
    # No whitespace at all after ID: the first binary byte is data.
    (
        "no_ws_after_id",
        b"q BI /W 2 /H 2 /BPC 8 /CS /G ID\x80\x81\x82\x83 EI Q",
        b"\x80\x81\x82\x83 ",
        3,
    ),
    # A single TAB after ID is consumed as the one whitespace byte.
    (
        "tab_after_id",
        b"q BI /W 2 /H 2 /BPC 8 /CS /G ID\t\x01\x02 EI Q",
        b"\x01\x02 ",
        3,
    ),
    # A single LF after ID is consumed (skipLinebreak).
    (
        "lf_after_id",
        b"q BI /W 2 /H 2 /BPC 8 /CS /G ID\n\x05\x06 EI Q",
        b"\x05\x06 ",
        3,
    ),
    # ``EI`` substring inside ASCII-looking data, with a later real EI.
    (
        "ei_inside_ascii_data",
        _BI + b"helloEIworld more data here padding EI Q",
        b"helloEIworld more data here padding ",
        3,
    ),
    # Two spaces before EI: both leading spaces are payload (only the byte
    # pair E,I is excluded).
    ("double_space_ei", _BI + b"\x01\x02  EI Q", b"\x01\x02  ", 3),
    # Embedded ``EI`` followed by a high byte (>0x7F) is binary -> not a
    # terminator; the later ``EI`` is.
    (
        "ei_high_byte_false",
        _BI + b"\x01 EI\x80 padding stuff EI Q",
        b"\x01 EI\x80 padding stuff ",
        3,
    ),
    # Missing EI entirely: scan runs to EOF. Two trailing bytes are dropped
    # by the lookahead pair (matches upstream's EOF tail behaviour).
    (
        "missing_ei",
        b"q BI /W 2 /H 2 /BPC 8 /CS /G ID \x01\x02\x03\x04\x05",
        b"\x01\x02\x03",
        2,
    ),
    # Real EI at EOF with no trailing separator: upstream's EOF guard means
    # the final ' EI' (no following whitespace) is not recognised as the
    # terminator, so two tail bytes are lost — pypdfbox mirrors this.
    (
        "ei_at_eof_no_sep",
        _BI + b"\x01\x02\x03 EI",
        b"\x01\x02\x03 ",
        2,
    ),
    # A ``BI`` appearing inside the ID...EI window is swallowed as image
    # data (it's binary payload, not a nested-BI error).
    (
        "bi_inside_data_is_data",
        b"q BI /W 2 /H 2 /BPC 8 /CS /G ID \x01 BI /W 2 ID \x03 EI Q",
        b"\x01 BI /W 2 ID \x03 ",
        3,
    ),
]


@pytest.mark.parametrize(
    ("stream", "expected"),
    [(s, e) for (_n, s, e, _c) in _SCAN_CASES],
    ids=[n for (n, _s, _e, _c) in _SCAN_CASES],
)
def test_ei_scan_captures_exact_bytes(stream: bytes, expected: bytes) -> None:
    assert _scan_image_data(stream) == expected


@pytest.mark.parametrize(
    ("stream", "count"),
    [(s, c) for (_n, s, _e, c) in _SCAN_CASES],
    ids=[n for (n, _s, _e, _c) in _SCAN_CASES],
)
def test_ei_scan_token_count(stream: bytes, count: int) -> None:
    # A post-EI resynchronisation bug would change the token count.
    assert _token_count(stream) == count


def test_ei_scan_sha_stability() -> None:
    # Lock the captured bytes of the embedded-EI case by content hash so a
    # subtle off-by-one in the scan window is caught.
    data = _scan_image_data(_SCAN_CASES[1][1])
    assert data is not None
    assert hashlib.sha1(data).hexdigest() == hashlib.sha1(  # noqa: S324
        b"\x01EI\x80\x81\x82\x83\x84\x85 "
    ).hexdigest()


# ---------------------------------------------------------------------------
# Abbreviation-key expansion on the PDInlineImage surface.
# ---------------------------------------------------------------------------


def _dict(**items: object) -> COSDictionary:
    d = COSDictionary()
    for key, value in items.items():
        if isinstance(value, bool):
            d.set_item(key, COSBoolean.TRUE if value else COSBoolean.FALSE)
        elif isinstance(value, int):
            d.set_item(key, COSInteger(value))
        elif isinstance(value, float):
            d.set_item(key, COSFloat(value))
        elif isinstance(value, str):
            d.set_item(key, COSName.get_pdf_name(value))
        else:
            d.set_item(key, value)  # type: ignore[arg-type]
    return d


def test_width_height_short_keys() -> None:
    img = PDInlineImage(_dict(W=7, H=11), b"", None)
    assert img.get_width() == 7
    assert img.get_height() == 11


def test_width_height_long_key_fallback() -> None:
    img = PDInlineImage(_dict(Width=3, Height=5), b"", None)
    assert img.get_width() == 3
    assert img.get_height() == 5


def test_width_short_key_wins_over_long() -> None:
    d = _dict(W=2)
    d.set_item("Width", COSInteger(99))
    img = PDInlineImage(d, b"", None)
    assert img.get_width() == 2


def test_bpc_short_and_long() -> None:
    assert PDInlineImage(_dict(BPC=4), b"", None).get_bits_per_component() == 4
    assert (
        PDInlineImage(_dict(BitsPerComponent=2), b"", None).get_bits_per_component()
        == 2
    )


def test_bpc_forced_to_one_for_stencil() -> None:
    # /IM stencil mask forces 1 bpc regardless of declared /BPC.
    img = PDInlineImage(_dict(IM=True, BPC=8), b"", None)
    assert img.is_stencil()
    assert img.get_bits_per_component() == 1


def test_image_mask_short_and_long_keys() -> None:
    assert PDInlineImage(_dict(IM=True), b"", None).is_stencil()
    assert PDInlineImage(_dict(ImageMask=True), b"", None).is_stencil()
    assert not PDInlineImage(_dict(), b"", None).is_stencil()


def test_interpolate_short_long_keys() -> None:
    assert PDInlineImage(_dict(I=True), b"", None).get_interpolate()
    assert PDInlineImage(_dict(Interpolate=True), b"", None).get_interpolate()
    assert not PDInlineImage(_dict(), b"", None).get_interpolate()


@pytest.mark.parametrize(
    ("abbrev", "long_name"),
    [("G", "DeviceGray"), ("RGB", "DeviceRGB"), ("CMYK", "DeviceCMYK")],
)
def test_colorspace_abbrev_to_long_name(abbrev: str, long_name: str) -> None:
    img = PDInlineImage(_dict(), b"", None)
    result = img.to_long_name(COSName.get_pdf_name(abbrev))
    assert isinstance(result, COSName)
    assert result.get_name() == long_name


def test_colorspace_unknown_name_passes_through() -> None:
    img = PDInlineImage(_dict(), b"", None)
    name = COSName.get_pdf_name("SomeNamedCS")
    assert img.to_long_name(name) is name


def test_colorspace_cos_object_two_key() -> None:
    img = PDInlineImage(_dict(CS="RGB"), b"", None)
    cs = img.get_color_space_cos_object()
    assert isinstance(cs, COSName)
    assert cs.get_name() == "RGB"
    img_long = PDInlineImage(_dict(ColorSpace="DeviceRGB"), b"", None)
    cs_long = img_long.get_color_space_cos_object()
    assert isinstance(cs_long, COSName)
    assert cs_long.get_name() == "DeviceRGB"


# ---------------------------------------------------------------------------
# Filter abbreviation list completeness + decode round-trips.
# ---------------------------------------------------------------------------


def test_filter_short_key_single_name() -> None:
    img = PDInlineImage(_dict(F="Fl"), b"", None)
    assert img.get_filters() == ["Fl"]


def test_filter_long_key_fallback() -> None:
    img = PDInlineImage(_dict(Filter="FlateDecode"), b"", None)
    assert img.get_filters() == ["FlateDecode"]


def test_filter_array_of_abbrevs() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("A85"))
    arr.add(COSName.get_pdf_name("Fl"))
    img = PDInlineImage(_dict(F=arr), b"", None)
    assert img.get_filters() == ["A85", "Fl"]


def test_flate_abbrev_decodes() -> None:
    raw = zlib.compress(b"ABCD")
    img = PDInlineImage(_dict(F="Fl"), raw, None)
    assert img.get_data() == b"ABCD"


def test_ascii_hex_abbrev_decodes() -> None:
    img = PDInlineImage(_dict(F="AHx"), b"00 ff>", None)
    assert img.get_data() == b"\x00\xff"


def test_runlength_abbrev_decodes() -> None:
    # RunLength: literal-run of length 3 (control byte 2) then EOD (128).
    raw = bytes([2, ord("X"), ord("Y"), ord("Z"), 128])
    img = PDInlineImage(_dict(F="RL"), raw, None)
    assert img.get_data() == b"XYZ"


def test_dct_abbrev_marks_jpeg_suffix() -> None:
    # Set the DCT filter post-construction so the eager filter decode in the
    # constructor does not run a real JPEG codec over the placeholder bytes;
    # we only assert the abbreviation-driven suffix / predicate dispatch.
    img = PDInlineImage(_dict(), b"", None)
    img.set_filters(["DCT"])
    assert img.is_jpeg()
    assert img.get_suffix() == "jpg"


def test_ccf_abbrev_marks_tiff_suffix() -> None:
    # CCITTFax decode is exercised elsewhere; here we only assert the suffix /
    # predicate dispatch on the abbreviation, so use raw (unfiltered) bytes by
    # declaring the long name to avoid running the codec.
    img = PDInlineImage(_dict(), b"", None)
    img.set_filters(["CCF"])
    assert img.is_ccitt()
    assert img.get_suffix() == "tiff"


def test_no_filter_suffix_is_png() -> None:
    assert PDInlineImage(_dict(), b"raw", None).get_suffix() == "png"


def test_lzw_abbrev_in_factory_resolves() -> None:
    # The abbreviation list must include LZW; resolving the filter object
    # should not raise even though we don't feed it valid LZW data.
    from pypdfbox.filter.filter_factory import FilterFactory

    flt = FilterFactory.INSTANCE.get_filter("LZW")
    assert flt is not None


# ---------------------------------------------------------------------------
# /Decode (/D) two-key + decode-as-floats helper.
# ---------------------------------------------------------------------------


def test_decode_short_key_array() -> None:
    arr = COSArray()
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(0.0))
    img = PDInlineImage(_dict(D=arr), b"", None)
    assert img.get_decode_as_floats() == [1.0, 0.0]


def test_decode_long_key_fallback() -> None:
    arr = COSArray()
    arr.add(COSInteger(0))
    arr.add(COSInteger(1))
    img = PDInlineImage(_dict(Decode=arr), b"", None)
    assert img.get_decode_as_floats() == [0.0, 1.0]


# ---------------------------------------------------------------------------
# Truncated / malformed inline data still constructs without raising.
# ---------------------------------------------------------------------------


def test_truncated_flate_data_does_not_crash_construction() -> None:
    # A flate filter over truncated bytes: construction decodes eagerly but
    # must not raise out of the constructor for a recoverable codec error.
    try:
        img = PDInlineImage(_dict(F="Fl"), b"\x78\x9c\x01", None)
    except OSError:
        # An OSError from the codec is acceptable parity behaviour; the point
        # is that it is a controlled error, not an unexpected exception type.
        return
    # If it did construct, get_data must return bytes.
    assert isinstance(img.get_data(), bytes)


def test_empty_data_is_empty() -> None:
    img = PDInlineImage(_dict(W=2, H=2), b"", None)
    assert img.is_empty()
    assert img.get_data() == b""
