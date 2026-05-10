"""Upstream-faithful unit tests for :class:`pypdfbox.filter.DCTFilter`.

Apache PDFBox does not ship a dedicated ``DCTFilterTest.java`` under
``pdfbox/src/test/java/org/apache/pdfbox/filter`` (DCT decoding is
exercised end-to-end through ``PDImageXObjectTest`` and
``PDJPEGFactoryTest``). The tests below cover each helper that
upstream ``DCTFilter.java`` defines as a private method, so a future
re-sync against an upstream test addition will diff cleanly.

Method line numbers reference ``pdfbox/src/main/java/org/apache/pdfbox/
filter/DCTFilter.java`` on the 3.0.x branch.
"""

from __future__ import annotations

import io
import struct

import pytest
from PIL import Image

from pypdfbox.filter import DCTFilter
from pypdfbox.filter.dct_filter import Raster

# ----------------------------------------------------------------------
# clamp (DCTFilter.java lines 337-340)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-1.0, 0),
        (-0.0001, 0),
        (0.0, 0),
        (127.7, 127),
        (255.0, 255),
        (255.0001, 255),
        (300.0, 255),
    ],
)
def test_clamp_truncates_into_byte_range(value: float, expected: int) -> None:
    assert DCTFilter().clamp(value) == expected


# ----------------------------------------------------------------------
# from_bg_rto_rgb (DCTFilter.java lines 288-309)
# ----------------------------------------------------------------------


def test_from_bg_rto_rgb_swaps_first_and_third_band() -> None:
    raster = Raster(samples=b"\x10\x20\x30\xa0\xb0\xc0", width=2, height=1, num_bands=3)

    out = DCTFilter().from_bg_rto_rgb(raster)

    assert out.samples == b"\x30\x20\x10\xc0\xb0\xa0"
    assert out.width == 2 and out.height == 1 and out.num_bands == 3


def test_from_bg_rto_rgb_handles_multi_row_raster() -> None:
    raster = Raster(
        samples=b"\x00\x00\xff\xff\x00\x00",
        width=1,
        height=2,
        num_bands=3,
    )

    out = DCTFilter().from_bg_rto_rgb(raster)

    assert out.samples == b"\xff\x00\x00\x00\x00\xff"


def test_from_bg_rto_rgb_rejects_non_three_band_input() -> None:
    raster = Raster(samples=b"\x00\xff", width=2, height=1, num_bands=1)

    with pytest.raises(ValueError):
        DCTFilter().from_bg_rto_rgb(raster)


# ----------------------------------------------------------------------
# from_ycc_kto_cmyk (DCTFilter.java lines 249-285)
# ----------------------------------------------------------------------


def test_from_ycc_kto_cmyk_pure_black_round_trips_to_zero_cmy_full_k() -> None:
    # Y=0 Cb=128 Cr=128 K=255 -> RGB ~= (0, 0, 0) -> CMYK ~= (255, 255, 255, 255)
    raster = Raster(samples=bytes([0, 128, 128, 255]), width=1, height=1, num_bands=4)

    out = DCTFilter().from_ycc_kto_cmyk(raster)

    cyan, magenta, yellow, k = out.samples
    assert k == 255
    # YCbCr formula with Cb=Cr=128 yields tiny offsets: tolerate +/-1.
    assert cyan == 255
    assert magenta in (255, 254)
    assert yellow == 255


def test_from_ycc_kto_cmyk_preserves_k_channel() -> None:
    raster = Raster(samples=bytes([200, 100, 100, 42]), width=1, height=1, num_bands=4)

    out = DCTFilter().from_ycc_kto_cmyk(raster)

    assert out.samples[3] == 42
    assert out.num_bands == 4


def test_from_ycc_kto_cmyk_rejects_non_four_band_input() -> None:
    raster = Raster(samples=b"\x00\x00\x00", width=1, height=1, num_bands=3)

    with pytest.raises(ValueError):
        DCTFilter().from_ycc_kto_cmyk(raster)


# ----------------------------------------------------------------------
# get_adobe_transform (DCTFilter.java lines 181-200)
# ----------------------------------------------------------------------


def test_get_adobe_transform_returns_zero_for_missing_marker() -> None:
    assert DCTFilter().get_adobe_transform({}) == 0


def test_get_adobe_transform_returns_zero_when_metadata_is_none() -> None:
    assert DCTFilter().get_adobe_transform(None) == 0


def test_get_adobe_transform_reads_dict_value_directly() -> None:
    assert DCTFilter().get_adobe_transform({"adobe_transform": 2}) == 2


def test_get_adobe_transform_coerces_string_value() -> None:
    assert DCTFilter().get_adobe_transform({"adobe_transform": "1"}) == 1


def test_get_adobe_transform_returns_zero_for_unparseable_value() -> None:
    assert DCTFilter().get_adobe_transform({"adobe_transform": "junk"}) == 0


def test_get_adobe_transform_reads_pillow_image_info() -> None:
    image = Image.new("RGB", (1, 1))
    image.info["adobe_transform"] = 1

    assert DCTFilter().get_adobe_transform(image) == 1


# ----------------------------------------------------------------------
# get_adobe_transform_by_brute_force (DCTFilter.java lines 204-244)
# ----------------------------------------------------------------------


def _synthesize_adobe_app14(transform: int, segment_padding: int = 0) -> bytes:
    """Build a minimal stream containing a valid APP14 ``Adobe`` segment.

    Layout matches the JFIF APP14 spec referenced upstream::

        FF EE  | length (BE, includes its own 2 bytes)
        "Adobe" | DCTEncode version (2)
        flags0 (2) | flags1 (2) | transform (1)
    """
    # Segment payload after the length bytes: "Adobe" + 6 bytes (version,
    # flags0, flags1, transform). Total payload length excludes the
    # length-field prefix in pre-3.0 JPEG specs but upstream's brute
    # force reader tolerates the inclusive length used by Pillow.
    body = b"Adobe" + b"\x01\x01" + b"\x00\x00" + b"\x00\x00" + bytes([transform])
    body += b"\x00" * segment_padding
    seg_len = 2 + len(body)
    return b"\xff\xee" + struct.pack(">H", seg_len) + body


def test_get_adobe_transform_by_brute_force_returns_zero_for_no_marker() -> None:
    iis = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 32)

    assert DCTFilter().get_adobe_transform_by_brute_force(iis) == 0


def test_get_adobe_transform_by_brute_force_reads_transform_byte() -> None:
    iis = io.BytesIO(b"\xff\xd8" + _synthesize_adobe_app14(transform=2))

    assert DCTFilter().get_adobe_transform_by_brute_force(iis) == 2


def test_get_adobe_transform_by_brute_force_handles_padded_segment() -> None:
    iis = io.BytesIO(
        b"\x00\x00\x00\xff\xd8" + _synthesize_adobe_app14(transform=1, segment_padding=4)
    )

    assert DCTFilter().get_adobe_transform_by_brute_force(iis) == 1


def test_get_adobe_transform_by_brute_force_returns_zero_when_tag_mismatched() -> None:
    # Inject the literal ``Adobe`` string but without the preceding
    # ``0xFFEE`` marker — upstream falls through and continues scanning.
    iis = io.BytesIO(b"prefix Adobe is here without a marker")

    assert DCTFilter().get_adobe_transform_by_brute_force(iis) == 0


# ----------------------------------------------------------------------
# get_num_channels (DCTFilter.java lines 312-334)
# ----------------------------------------------------------------------


def test_get_num_channels_reports_three_for_rgb_image() -> None:
    image = Image.new("RGB", (1, 1))

    assert DCTFilter().get_num_channels(image) == "3"


def test_get_num_channels_reports_one_for_grayscale_image() -> None:
    image = Image.new("L", (1, 1))

    assert DCTFilter().get_num_channels(image) == "1"


def test_get_num_channels_reports_four_for_cmyk_image() -> None:
    image = Image.new("CMYK", (1, 1))

    assert DCTFilter().get_num_channels(image) == "4"


def test_get_num_channels_returns_empty_string_when_reader_raises() -> None:
    class _Broken:
        def getbands(self) -> tuple[str, ...]:
            raise RuntimeError("metadata broken")

    assert DCTFilter().get_num_channels(_Broken()) == ""  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# read_image_raster (DCTFilter.java lines 135-171)
# ----------------------------------------------------------------------


def test_read_image_raster_returns_three_band_raster_for_rgb_image() -> None:
    image = Image.new("RGB", (2, 1), color=(10, 20, 30))

    raster = DCTFilter().read_image_raster(image)

    assert raster.num_bands == 3
    assert raster.width == 2 and raster.height == 1
    assert raster.samples == b"\x0a\x14\x1e\x0a\x14\x1e"


def test_read_image_raster_returns_one_band_raster_for_grayscale_image() -> None:
    image = Image.new("L", (3, 1), color=200)

    raster = DCTFilter().read_image_raster(image)

    assert raster.num_bands == 1
    assert raster.samples == b"\xc8\xc8\xc8"


def test_read_image_raster_returns_four_band_raster_for_cmyk_image() -> None:
    image = Image.new("CMYK", (1, 1), color=(10, 20, 30, 40))

    raster = DCTFilter().read_image_raster(image)

    assert raster.num_bands == 4
    assert raster.samples == b"\x0a\x14\x1e\x28"
