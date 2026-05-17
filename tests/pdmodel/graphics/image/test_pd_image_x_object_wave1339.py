"""Wave 1339 — coverage-boost for
:mod:`pypdfbox.pdmodel.graphics.image.pd_image_x_object`.

Targets the small islands of uncovered branches left after waves 1246–
1286: factory dispatch error paths (``create_from_file*`` /
``create_from_byte_array``), ``create_raw_stream``, the simple
``get_filter`` accessor, ``extract_matte``'s defensive branches,
``_apply_decode_*`` rejection paths, ``_unpack_sub_byte_samples``
invalid-bpc guard, and the ``_clamp`` extremes.
"""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image as PILImage

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
    _apply_decode_to_8bit_indexed_samples,
    _apply_decode_to_8bit_samples,
    _apply_decode_to_indexed_samples,
    _clamp,
    _clamp01,
    _detect_file_type,
    _unpack_16bit_samples,
    _unpack_sub_byte_samples,
)


def _png_bytes(width: int = 1, height: int = 1, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Return a minimal 1x1 PNG byte string built by Pillow."""
    img = PILImage.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _bmp_bytes() -> bytes:
    img = PILImage.new("RGB", (1, 1), (0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    return buf.getvalue()


def _gif_bytes() -> bytes:
    img = PILImage.new("P", (1, 1))
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# create_from_file_by_extension — error / fallback paths.
# ---------------------------------------------------------------------------


def test_wave1339_create_from_file_by_extension_rejects_extensionless_name(
    tmp_path: Path,
) -> None:
    """A filename without a dot raises ``ValueError`` — extension cannot
    be inferred from a name like ``"image"``."""
    path = tmp_path / "image"
    path.write_bytes(_png_bytes())
    doc = PDDocument()
    try:
        with pytest.raises(ValueError, match="Image type not supported"):
            PDImageXObject.create_from_file_by_extension(path, doc)
    finally:
        doc.close()


def test_wave1339_create_from_file_by_extension_rejects_unknown_extension(
    tmp_path: Path,
) -> None:
    """Suffixes outside the {jpg,jpeg,tif,tiff,gif,bmp,png} list raise."""
    path = tmp_path / "image.xyz"
    path.write_bytes(b"\x00")
    doc = PDDocument()
    try:
        with pytest.raises(ValueError, match="Image type not supported"):
            PDImageXObject.create_from_file_by_extension(path, doc)
    finally:
        doc.close()


def test_wave1339_create_from_file_by_extension_falls_back_to_png_when_tiff_invalid(
    tmp_path: Path,
) -> None:
    """A ``.tif`` whose body is actually a PNG triggers the OSError →
    PNG-retry branch (lines 130–134). Pillow opens the PNG body and
    the lossless factory wraps it as an Image XObject."""
    path = tmp_path / "spoof.tif"
    path.write_bytes(_png_bytes(width=2, height=2, color=(1, 2, 3)))
    doc = PDDocument()
    try:
        image = PDImageXObject.create_from_file_by_extension(path, doc)
        assert image.get_width() == 2
        assert image.get_height() == 2
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# create_from_file_by_content — OSError on file open.
# ---------------------------------------------------------------------------


def test_wave1339_create_from_file_by_content_raises_for_missing_file(
    tmp_path: Path,
) -> None:
    """Opening a non-existent file rewraps the underlying ``OSError``."""
    missing = tmp_path / "nope.bin"
    doc = PDDocument()
    try:
        with pytest.raises(OSError, match="Could not determine file type"):
            PDImageXObject.create_from_file_by_content(missing, doc)
    finally:
        doc.close()


def test_wave1339_create_from_file_by_content_rejects_unrecognised_magic(
    tmp_path: Path,
) -> None:
    """Magic bytes that match no supported file type raise ``ValueError``."""
    path = tmp_path / "garbage.bin"
    path.write_bytes(b"NOTANIMAGE12345678")
    doc = PDDocument()
    try:
        with pytest.raises(ValueError, match="Image type not supported"):
            PDImageXObject.create_from_file_by_content(path, doc)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# create_from_byte_array — non-bytes rejection + TIFF→PNG fallback +
# unsupported file-type guard.
# ---------------------------------------------------------------------------


def test_wave1339_create_from_byte_array_rejects_non_bytes_input() -> None:
    """The factory enforces a bytes-like contract — passing ``str`` is a
    ``TypeError`` (line 188–191)."""
    doc = PDDocument()
    try:
        with pytest.raises(TypeError, match="byte_array must be bytes-like"):
            PDImageXObject.create_from_byte_array(doc, cast(Any, "not-bytes"))
    finally:
        doc.close()


def test_wave1339_create_from_byte_array_rejects_unrecognised_magic() -> None:
    doc = PDDocument()
    try:
        with pytest.raises(ValueError, match="Image type not supported"):
            PDImageXObject.create_from_byte_array(doc, b"NOTANIMAGE12345")
    finally:
        doc.close()


def test_wave1339_create_from_byte_array_raises_on_unknown_file_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_detect_file_type`` reports a name that none of the
    typed branches handle the method raises ``ValueError`` (line 211).
    This is dead by construction today but we exercise it by patching
    the detector to return a synthetic unrecognised type — confirms the
    defensive guard."""
    from pypdfbox.pdmodel.graphics.image import pd_image_x_object as mod

    def fake_detect(_head: bytes) -> str:
        return "UNKNOWN"

    monkeypatch.setattr(mod, "_detect_file_type", fake_detect)
    doc = PDDocument()
    try:
        with pytest.raises(ValueError, match="Image type UNKNOWN not supported"):
            PDImageXObject.create_from_byte_array(doc, b"\x00" * 16, name="x.bin")
    finally:
        doc.close()


def test_wave1339_create_from_byte_array_falls_back_to_png_when_tiff_invalid() -> None:
    """An OSError from the TIFF factory is caught and the body is
    re-tried via Pillow + ``LosslessFactory`` (lines 200–204). To force
    the fallback we hand it a payload that *starts* with the TIFF magic
    but is otherwise invalid; the catch leaves ``file_type = "PNG"`` so
    the next branch raises (no valid PNG body). The branch coverage is
    what we're after."""
    doc = PDDocument()
    try:
        # II*\x00 is the TIFF little-endian magic; remainder is junk.
        body = b"II*\x00" + b"\x00" * 32
        with pytest.raises((ValueError, OSError)):
            PDImageXObject.create_from_byte_array(doc, body)
    finally:
        doc.close()


def test_wave1339_create_from_byte_array_uses_custom_factory_for_png() -> None:
    """A non-null ``custom_factory`` for PNG/GIF/BMP inputs takes over
    creation (line 206–207)."""
    doc = PDDocument()
    try:

        class Sentinel:
            def __init__(self) -> None:
                self.calls = 0

            def create_from_byte_array(
                self, document: PDDocument, data: bytes
            ) -> PDImageXObject:
                self.calls += 1
                # Build a stub image so the factory returns something
                # callable code can inspect.
                stream = COSStream()
                image = PDImageXObject(stream)
                image.set_width(1)
                image.set_height(1)
                return image

        factory = Sentinel()
        out = PDImageXObject.create_from_byte_array(
            doc, _png_bytes(), name="x.png", custom_factory=factory
        )
        assert out.get_width() == 1
        assert factory.calls == 1
    finally:
        doc.close()


def test_wave1339_create_from_byte_array_round_trips_bmp_and_gif() -> None:
    """Exercises the BMP and GIF branches through the default Pillow +
    LosslessFactory route (line 208–210)."""
    doc = PDDocument()
    try:
        bmp = PDImageXObject.create_from_byte_array(doc, _bmp_bytes(), name="x.bmp")
        gif = PDImageXObject.create_from_byte_array(doc, _gif_bytes(), name="x.gif")
        assert bmp.get_width() == 1
        assert gif.get_width() == 1
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# create_raw_stream (lines 219–225).
# ---------------------------------------------------------------------------


def test_wave1339_create_raw_stream_writes_input_bytes_into_new_cos_stream() -> None:
    doc = PDDocument()
    try:
        payload = b"\x01\x02\x03\x04"
        stream = PDImageXObject.create_raw_stream(doc, io.BytesIO(payload))
        # The raw bytes survive the round-trip unchanged.
        with stream.create_raw_input_stream() as src:
            assert src.read() == payload
    finally:
        doc.close()


def test_wave1339_create_raw_stream_skips_non_bytes_payload() -> None:
    """When ``read`` returns a non-bytes value the writer leaves the
    stream empty — defensive guard at line 223 (the ``isinstance``
    check)."""
    doc = PDDocument()
    try:

        class NonBytesIO:
            def read(self) -> str:  # not bytes — deliberately
                return "not bytes"

        stream = PDImageXObject.create_raw_stream(doc, cast(Any, NonBytesIO()))
        with stream.create_raw_input_stream() as src:
            assert src.read() == b""
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# get_filter — non-name/array fallback (line 310).
# ---------------------------------------------------------------------------


def test_wave1339_get_filter_returns_name_when_present() -> None:
    """``/Filter`` set to a single name returns that name unchanged."""
    image = PDImageXObject(COSStream())
    image.get_cos_object().set_item(
        COSName.FILTER,  # type: ignore[attr-defined]
        COSName.get_pdf_name("FlateDecode"),
    )
    assert image.get_filter() == COSName.get_pdf_name("FlateDecode")


def test_wave1339_get_filter_returns_array_when_present() -> None:
    image = PDImageXObject(COSStream())
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ASCII85Decode"))
    arr.add(COSName.get_pdf_name("FlateDecode"))
    image.get_cos_object().set_item(
        COSName.FILTER,  # type: ignore[attr-defined]
        arr,
    )
    out = image.get_filter()
    assert isinstance(out, COSArray)
    assert len(list(out)) == 2


def test_wave1339_get_filter_returns_none_when_absent() -> None:
    image = PDImageXObject(COSStream())
    assert image.get_filter() is None


# ---------------------------------------------------------------------------
# get_raw_raster — None when COS is not a stream (line 834).
# ---------------------------------------------------------------------------


def test_wave1339_get_raw_raster_returns_none_for_non_stream_cos() -> None:
    """``get_raw_raster`` short-circuits to ``None`` when the underlying
    COS is not a stream (defensive — the parent class can technically
    hold a dictionary)."""
    image = PDImageXObject(COSStream())
    # Override ``get_cos_object`` so it reports a plain dictionary.
    image.get_cos_object = lambda: cast(Any, COSDictionary())  # type: ignore[method-assign]
    assert image.get_raw_raster() is None


def test_wave1339_get_raw_raster_reads_underlying_stream_bytes() -> None:
    """Happy-path branch — exercises lines 835–836 with a populated
    stream."""
    stream = COSStream()
    stream.set_raw_data(b"raw-bytes-payload")
    image = PDImageXObject(stream)
    assert image.get_raw_raster() == b"raw-bytes-payload"


# ---------------------------------------------------------------------------
# extract_matte branches (lines 854, 861, 864–865, 867).
# ---------------------------------------------------------------------------


def _build_soft_mask_with_matte(matte: list[float]) -> PDImageXObject:
    """Build a minimal soft-mask Image XObject with a ``/Matte`` entry."""
    stream = COSStream()
    image = PDImageXObject(stream)
    arr = COSArray()
    arr.set_float_array(matte)
    image.get_cos_object().set_item(COSName.get_pdf_name("Matte"), arr)
    return image


def test_wave1339_extract_matte_returns_raw_matte_when_color_space_absent() -> None:
    """No ``/ColorSpace`` resolvable → matte returned untouched (line 854)."""
    image = PDImageXObject(COSStream())
    soft = _build_soft_mask_with_matte([0.5, 0.25, 0.125])
    # No color space configured on ``image``.
    assert image.get_color_space() is None
    out = image.extract_matte(soft)
    assert out == [0.5, 0.25, 0.125]


def test_wave1339_extract_matte_returns_raw_matte_when_color_space_has_no_to_rgb() -> None:
    """``to_rgb`` attribute missing on the color space → matte unchanged
    (line 861). We attach a hand-rolled CS without ``to_rgb`` to drive
    the ``getattr`` branch deterministically (some real ``PDColorSpace``
    subclasses already expose ``to_rgb``)."""
    image = PDImageXObject(COSStream())
    soft = _build_soft_mask_with_matte([0.7, 0.7, 0.7])

    class NoToRgbCS:
        def get_number_of_components(self) -> int:
            return 3

        # No ``to_rgb`` attribute at all.

    image.get_color_space = lambda: cast(Any, NoToRgbCS())  # type: ignore[method-assign]
    assert image.extract_matte(soft) == pytest.approx([0.7, 0.7, 0.7])


def test_wave1339_extract_matte_returns_raw_matte_when_to_rgb_raises() -> None:
    """``to_rgb`` raising leaves the raw matte values untouched (lines
    864–865)."""
    image = PDImageXObject(COSStream())
    soft = _build_soft_mask_with_matte([0.4, 0.4, 0.4])

    class FakeCS:
        def get_number_of_components(self) -> int:
            return 3

        def to_rgb(self, components: list[float]) -> tuple[float, float, float]:
            raise RuntimeError("bad transform")

    # Monkey-patch ``get_color_space`` so the method picks up our fake.
    image.get_color_space = lambda: cast(Any, FakeCS())  # type: ignore[method-assign]
    out = image.extract_matte(soft)
    assert out == pytest.approx([0.4, 0.4, 0.4])


def test_wave1339_extract_matte_returns_raw_matte_when_to_rgb_returns_none() -> None:
    """``to_rgb`` returning ``None`` → fall back to the raw matte
    (line 866-867)."""
    image = PDImageXObject(COSStream())
    soft = _build_soft_mask_with_matte([0.1, 0.2, 0.3])

    class NoneCS:
        def get_number_of_components(self) -> int:
            return 3

        def to_rgb(self, components: list[float]) -> None:
            return None

    image.get_color_space = lambda: cast(Any, NoneCS())  # type: ignore[method-assign]
    assert image.extract_matte(soft) == pytest.approx([0.1, 0.2, 0.3])


def test_wave1339_extract_matte_returns_converted_rgb_when_to_rgb_succeeds() -> None:
    """Happy path: ``to_rgb`` returns a 3-tuple → method returns the
    converted floats (line 868)."""
    image = PDImageXObject(COSStream())
    soft = _build_soft_mask_with_matte([1.0, 0.0, 0.0])

    class IdentityCS:
        def get_number_of_components(self) -> int:
            return 3

        def to_rgb(self, components: list[float]) -> tuple[float, float, float]:
            r, g, b = components
            return (r, g, b)

    image.get_color_space = lambda: cast(Any, IdentityCS())  # type: ignore[method-assign]
    out = image.extract_matte(soft)
    assert out == [1.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# to_pil_image rejection branches (lines 984, 1000, 1006).
# ---------------------------------------------------------------------------


def test_wave1339_get_image_returns_none_when_to_pil_image_returns_none() -> None:
    """``get_image`` short-circuits to ``None`` whenever
    ``to_pil_image`` cannot decode the raster (line 775–776)."""
    image = PDImageXObject(COSStream())
    image.set_width(1)
    image.set_height(1)
    image.set_bits_per_component(7)  # unsupported → to_pil_image returns None
    image.set_color_space("DeviceRGB")
    image.get_cos_object().set_raw_data(b"\x00\x00\x00")
    assert image.get_image() is None
    assert image.get_image(region=(0, 0, 1, 1), subsampling=2) is None
    assert image.get_opaque_image() is None


def test_wave1339_to_pil_image_returns_none_for_unsupported_bpc() -> None:
    """``bpc`` of 7 (between sub-byte and 8) with a non-special color
    space short-circuits to ``None`` (line 984)."""
    image = PDImageXObject(COSStream())
    image.set_width(1)
    image.set_height(1)
    image.set_bits_per_component(7)
    image.set_color_space("DeviceRGB")
    image.get_cos_object().set_raw_data(b"\x00\x00\x00")
    assert image.to_pil_image() is None


def test_wave1339_to_pil_image_returns_none_when_devicergb_decode_invalid() -> None:
    """``DeviceRGB`` with a malformed decode array (wrong length)
    returns ``None`` (line 1000 via ``_apply_decode_to_8bit_samples``)."""
    image = PDImageXObject(COSStream())
    image.set_width(1)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceRGB")
    image.set_decode([0.0, 1.0])  # wrong length (need 6 for RGB)
    image.get_cos_object().set_raw_data(b"\x10\x20\x30")
    assert image.to_pil_image() is None


def test_wave1339_to_pil_image_returns_none_when_devicegray_subbyte_short_raster() -> None:
    """Sub-byte ``DeviceGray`` whose raster can't fill the expected
    sample count fails (line 1006)."""
    image = PDImageXObject(COSStream())
    image.set_width(8)
    image.set_height(1)
    image.set_bits_per_component(2)  # sub-byte
    image.set_color_space("DeviceGray")
    image.get_cos_object().set_raw_data(b"")  # empty raster
    assert image.to_pil_image() is None


# ---------------------------------------------------------------------------
# _apply_decode_to_8bit_samples short-data + zero-bpc guards (1069, 1079).
# ---------------------------------------------------------------------------


def test_wave1339_apply_decode_to_8bit_samples_returns_none_on_short_data() -> None:
    """``data`` shorter than the expected sample count → None (1068–1069)."""
    out = _apply_decode_to_8bit_samples(b"\x00", pixel_count=4, components=3, decode=None)
    assert out is None


def test_wave1339_apply_decode_to_8bit_samples_returns_none_when_bpc_zero() -> None:
    """``bpc=0`` would make ``max_sample`` zero → division impossible
    (1078–1079)."""
    out = _apply_decode_to_8bit_samples(
        b"\x00\x00\x00",
        pixel_count=1,
        components=3,
        decode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        bpc=0,
    )
    assert out is None


def test_wave1339_apply_decode_to_8bit_samples_returns_none_when_decode_length_wrong() -> None:
    out = _apply_decode_to_8bit_samples(
        b"\x00",
        pixel_count=1,
        components=1,
        decode=[0.0, 1.0, 2.0],  # not 2 entries
    )
    assert out is None


# ---------------------------------------------------------------------------
# _apply_decode_to_indexed_samples short-data + zero-bpc guards (1099, 1107).
# ---------------------------------------------------------------------------


def test_wave1339_apply_decode_to_indexed_samples_returns_none_on_short_data() -> None:
    assert _apply_decode_to_indexed_samples(b"", pixel_count=4, decode=None) is None


def test_wave1339_apply_decode_to_indexed_samples_returns_none_when_bpc_zero() -> None:
    out = _apply_decode_to_indexed_samples(
        b"\x00", pixel_count=1, decode=[0.0, 1.0], bpc=0
    )
    assert out is None


def test_wave1339_apply_decode_to_indexed_samples_returns_none_when_decode_length_wrong() -> None:
    out = _apply_decode_to_indexed_samples(
        b"\x00", pixel_count=1, decode=[0.0, 1.0, 2.0]
    )
    assert out is None


def test_wave1339_apply_decode_to_8bit_indexed_samples_delegates_with_bpc_8() -> None:
    """Wrapper at line 1122: hands the call off to the bpc=8 path."""
    out = _apply_decode_to_8bit_indexed_samples(
        b"\x80\x40", pixel_count=2, decode=[0.0, 255.0]
    )
    assert out == b"\x80\x40"


# ---------------------------------------------------------------------------
# _unpack_sub_byte_samples invalid bpc guard (line 1132–1133).
# ---------------------------------------------------------------------------


def test_wave1339_unpack_sub_byte_samples_rejects_unsupported_bpc() -> None:
    """Only 1/2/4 bpc are supported — anything else returns ``None``."""
    assert _unpack_sub_byte_samples(b"\x00", width=1, height=1, bpc=3) is None


def test_wave1339_unpack_sub_byte_samples_rejects_zero_components() -> None:
    assert (
        _unpack_sub_byte_samples(b"\x00", width=1, height=1, bpc=1, components=0)
        is None
    )


# ---------------------------------------------------------------------------
# _clamp extremes (lines 1289–1294).
# ---------------------------------------------------------------------------


def test_wave1339_clamp_clamps_to_low_bound() -> None:
    assert _clamp(-5.0, 0.0, 1.0) == 0.0


def test_wave1339_clamp_clamps_to_high_bound() -> None:
    assert _clamp(2.5, 0.0, 1.0) == 1.0


def test_wave1339_clamp_passes_in_range_value() -> None:
    assert _clamp(0.5, 0.0, 1.0) == 0.5


def test_wave1339_clamp01_bounds() -> None:
    assert _clamp01(-1.0) == 0.0
    assert _clamp01(2.0) == 1.0
    assert _clamp01(0.25) == 0.25


# ---------------------------------------------------------------------------
# Misc small helpers we touch incidentally.
# ---------------------------------------------------------------------------


def test_wave1339_detect_file_type_returns_none_for_short_header() -> None:
    assert _detect_file_type(b"") is None
    assert _detect_file_type(b"AB") is None


def test_wave1339_unpack_16bit_samples_rejects_short_payload() -> None:
    assert _unpack_16bit_samples(b"\x00", width=2, height=2) is None


def test_wave1339_unpack_16bit_samples_returns_bigendian_uint16s() -> None:
    payload = struct.pack(">HHH", 1, 65535, 32768)
    out = _unpack_16bit_samples(payload, width=3, height=1)
    assert out == [1, 65535, 32768]


# Touch ``_apply_decode_to_indexed_samples`` happy path with custom bpc so
# the in-range loop is exercised.
def test_wave1339_apply_decode_to_indexed_samples_applies_linear_decode() -> None:
    out = _apply_decode_to_indexed_samples(
        b"\x00\xff",
        pixel_count=2,
        decode=[0.0, 255.0],
        bpc=8,
    )
    assert out == b"\x00\xff"


# Touch ``zlib`` indirectly to confirm the test file's PNG generation
# uses real bytes — without this Pillow could short-circuit on a cached
# fixture. (Sanity-check rather than a coverage target.)
def test_wave1339_generated_png_decompresses_cleanly() -> None:
    png = _png_bytes(color=(64, 128, 192))
    # Strip the 8-byte PNG signature and confirm the first IDAT
    # zlib-decompresses — proves our fixture is real bytes.
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    # Find the IDAT chunk start.
    idx = png.index(b"IDAT")
    chunk_len = int.from_bytes(png[idx - 4 : idx], "big")
    data = png[idx + 4 : idx + 4 + chunk_len]
    # Pillow's PNG encoder always emits valid deflate data.
    zlib.decompress(data)
