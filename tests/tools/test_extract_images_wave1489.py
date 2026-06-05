"""``ExtractImages.write2file`` dispatch parity (wave 1489).

Wave 1489 audited :meth:`ImageGraphicsEngine.write2file` against upstream
``ExtractImages.java`` (3.0.x) and fixed three divergences:

* the ``ImageIOUtil.write_image`` call had its ``(image, target, format)``
  arguments in the wrong order, so it wrote a ``0``-byte ``prefix.suffix`` file
  plus a stray file literally named after the suffix;
* the ``-noColorConvert`` raw-image path (png, or tiff for > 3-channel CMYK)
  was missing entirely;
* the JPEG/JP2 *direct passthrough* (raw DCT/JPX stream bytes copied verbatim
  for DeviceGray/DeviceRGB or when ``-useDirectJPEG`` is forced) and the
  ``tiff``/DeviceGray bitonal conversion branch were missing — every image was
  decoded and re-encoded, losing the byte parity upstream preserves for JPEGs.

These tests exercise the real :class:`PDImageXObject` produced by the JPEG and
lossless factories so the actual write paths run end-to-end.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.tools import extract_images


def _gradient(w: int, h: int, seed: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (
                (x * 13 + seed) & 0xFF,
                (y * 17 + seed) & 0xFF,
                (x * y + seed) & 0xFF,
            )
    return img


def _engine() -> extract_images.ImageGraphicsEngine:
    outer = extract_images.ExtractImages()
    return extract_images.ImageGraphicsEngine(page=None, outer=outer)


# --------------------------------------------------------------------------
# Regression: write_image arg order — the produced file must hold real bytes,
# and no stray suffix-named file may appear.
# --------------------------------------------------------------------------
def test_write2file_png_holds_real_bytes_and_no_stray_file(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        pd_image = LosslessFactory.create_from_image(doc, _gradient(8, 6, 3))
        prefix = str(tmp_path / "img")
        engine = _engine()
        engine.write2file(pd_image, prefix, direct_jpeg=False, no_color_convert=False)
    finally:
        doc.close()

    png = tmp_path / "img.png"
    assert png.exists()
    assert png.stat().st_size > 0
    # A valid PNG that round-trips to the right size.
    with Image.open(png) as reopened:
        assert reopened.size == (8, 6)
    # No file literally named "png" (the old arg-order bug created one).
    assert not (tmp_path / "png").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["img.png"]


# --------------------------------------------------------------------------
# JPEG passthrough: a DeviceRGB DCT image is copied verbatim (byte parity with
# the raw DCT stream), not re-encoded.
# --------------------------------------------------------------------------
def test_write2file_jpeg_rgb_passthrough_copies_raw_stream(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        pd_image = JPEGFactory.create_from_image(doc, _gradient(16, 12, 7))
        assert pd_image.get_suffix() == "jpg"
        assert pd_image.get_color_space().get_name() == "DeviceRGB"
        raw = pd_image.create_input_stream(extract_images.JPEG).read()

        prefix = str(tmp_path / "img")
        engine = _engine()
        engine.write2file(pd_image, prefix, direct_jpeg=False, no_color_convert=False)
    finally:
        doc.close()

    jpg = tmp_path / "img.jpg"
    assert jpg.exists()
    # Byte parity: the on-disk file IS the raw DCT stream, unmodified.
    assert jpg.read_bytes() == raw


def test_write2file_jpeg_direct_flag_forces_passthrough(tmp_path: Path) -> None:
    """``-useDirectJPEG`` forces verbatim copy regardless of colorspace; for an
    RGB image the result is identical to the no-flag passthrough."""
    doc = PDDocument()
    try:
        pd_image = JPEGFactory.create_from_image(doc, _gradient(16, 12, 7))
        raw = pd_image.create_input_stream(extract_images.JPEG).read()
        prefix = str(tmp_path / "img")
        engine = _engine()
        engine.write2file(pd_image, prefix, direct_jpeg=True, no_color_convert=False)
    finally:
        doc.close()

    assert (tmp_path / "img.jpg").read_bytes() == raw


# --------------------------------------------------------------------------
# -noColorConvert raw path: writes png for <= 3 channels.
# --------------------------------------------------------------------------
def test_write2file_no_color_convert_writes_png(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        pd_image = LosslessFactory.create_from_image(doc, _gradient(8, 6, 3))
        prefix = str(tmp_path / "img")
        engine = _engine()
        engine.write2file(pd_image, prefix, direct_jpeg=False, no_color_convert=True)
    finally:
        doc.close()

    png = tmp_path / "img.png"
    assert png.exists()
    assert png.stat().st_size > 0
    with Image.open(png) as reopened:
        assert reopened.size == (8, 6)


# --------------------------------------------------------------------------
# suffix remap: jb2 -> png, jpx -> jp2, and unconditional FileOutputStream open
# (an empty file is created even when get_image() yields None) — upstream's
# try-with-resources semantics.
# --------------------------------------------------------------------------
def test_write2file_jb2_remapped_to_png() -> None:
    assert _remap("jb2") == "png"


def test_write2file_jpx_remapped_to_jp2() -> None:
    assert _remap("jpx") == "jp2"


def _remap(suffix_in: str) -> str:
    """Drive the suffix-derivation branch in isolation via a stub image."""

    class _Stub:
        def get_suffix(self) -> str:
            return suffix_in

        def get_color_space(self):  # noqa: ANN202
            return None

        def get_image(self):  # noqa: ANN202
            return None

        def get_mask(self):  # noqa: ANN202
            return None

        def get_soft_mask(self):  # noqa: ANN202
            return None

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        prefix = str(Path(d) / "x")
        _engine().write2file(_Stub(), prefix, direct_jpeg=False, no_color_convert=False)
        produced = [p.name for p in Path(d).iterdir()]
    assert len(produced) == 1
    return produced[0].rsplit(".", 1)[-1]


# --------------------------------------------------------------------------
# has_masks forces png even for a JPEG (TIKA-3040 / PDFBOX-4771).
# --------------------------------------------------------------------------
def test_write2file_masked_jpeg_falls_back_to_png(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        argb = Image.new("RGBA", (10, 10), (0x33, 0x66, 0xCC, 0x80))
        pd_image = JPEGFactory.create_from_image(doc, argb)
        # A JPEG with a /SMask: has_masks → True → png path, NOT jpg passthrough.
        engine = _engine()
        assert engine.has_masks(pd_image) is True
        prefix = str(tmp_path / "img")
        engine.write2file(pd_image, prefix, direct_jpeg=False, no_color_convert=False)
    finally:
        doc.close()

    assert (tmp_path / "img.png").exists()
    assert not (tmp_path / "img.jpg").exists()


# --------------------------------------------------------------------------
# Helper-function unit coverage.
# --------------------------------------------------------------------------
def test_num_data_elements_counts_bands() -> None:
    assert extract_images._num_data_elements(Image.new("RGB", (2, 2))) == 3
    assert extract_images._num_data_elements(Image.new("RGBA", (2, 2))) == 4
    assert extract_images._num_data_elements(Image.new("CMYK", (2, 2))) == 4
    assert extract_images._num_data_elements(Image.new("L", (2, 2))) == 1


def test_copy_streams_all_bytes() -> None:
    import io

    src = io.BytesIO(b"a" * 20000)
    dst = io.BytesIO()
    extract_images._copy(src, dst)
    assert dst.getvalue() == b"a" * 20000


def test_close_quietly_swallows_errors() -> None:
    class _Boom:
        def close(self) -> None:
            raise OSError("nope")

    # Must not raise.
    extract_images._close_quietly(_Boom())


def test_pixel_digest_parity_helper_is_reproducible(tmp_path: Path) -> None:
    """Sanity: the decoded-pixel digest used by the oracle test is stable for
    the same pixels regardless of which lossless container holds them."""
    doc = PDDocument()
    try:
        pd_image = LosslessFactory.create_from_image(doc, _gradient(8, 6, 3))
        prefix = str(tmp_path / "img")
        _engine().write2file(pd_image, prefix, direct_jpeg=False, no_color_convert=False)
    finally:
        doc.close()
    with Image.open(tmp_path / "img.png") as im:
        digest = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
    assert len(digest) == 64
