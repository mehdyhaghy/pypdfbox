"""Ported upstream tests from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObjectTest.java``.

Translated from JUnit 5 to pytest per CLAUDE.md §"Test Porting Conventions".

Scope: convenience-method parity for ``createFromFile`` /
``createFromFileByExtension`` / ``createFromFileByContent`` /
``createFromByteArray`` (with and without a ``CustomFactory``). Upstream
asserts that the convenience method's output matches the underlying
factory method's output for both ``getSuffix()`` and per-pixel ARGB
buffers. We compare ``getSuffix()`` and ``getWidth()/getHeight()`` —
per-pixel ARGB parity belongs to the rendering cluster which is not yet
ported (see ``PDImageXObject.get_image``: it falls back to
``to_pil_image`` and does not yet composite masks).

Skipped upstream tests (require fixtures or rendering work that is
intentionally out of scope for this change):

- ``checkIdentARGB`` round-trips — depend on ``BufferedImage`` ARGB
  parity. We compare width/height/suffix only.
- ``ccittg4.tif`` / ``jpegcmyk.jpg`` / ``gif-1bit-transparent.gif`` /
  ``png_indexed_8bit_alpha.png`` / ``lzw.tif`` — Java ports rely on
  the upstream ``src/test/resources`` corpus we do not redistribute.
  We synthesise minimal PNG/JPEG/GIF/BMP fixtures via Pillow to cover
  the dispatch logic without binary fixtures.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.image import (
    JPEGFactory,
    LosslessFactory,
    PDImageXObject,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def _png_bytes() -> bytes:
    image = Image.new("RGB", (3, 4), color=(10, 20, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes() -> bytes:
    image = Image.new("RGB", (5, 7), color=(40, 60, 80))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _gif_bytes() -> bytes:
    image = Image.new("P", (3, 4), color=2)
    image.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0])
    buffer = io.BytesIO()
    image.save(buffer, format="GIF")
    return buffer.getvalue()


def _compare_lossless(file: Path) -> None:
    """Mirror upstream ``testCompareCreatedFileByExtensionWithCreatedByLosslessFactory``
    for the suffix/width/height side. Upstream additionally calls
    ``checkIdentARGB`` — see file docstring."""
    document = PDDocument()
    image = PDImageXObject.create_from_file_by_extension(file, document)
    with Image.open(file) as source:
        source.load()
        expected = LosslessFactory.create_from_image(document, source)
    assert image.get_suffix() == expected.get_suffix()
    assert image.get_width() == expected.get_width()
    assert image.get_height() == expected.get_height()


def _compare_jpeg(file: Path) -> None:
    """Mirror upstream ``testCompareCreatedFileByExtensionWithCreatedByJPEGFactory``."""
    document = PDDocument()
    image = PDImageXObject.create_from_file_by_extension(file, document)
    with file.open("rb") as fh:
        expected = JPEGFactory.create_from_stream(document, fh)
    assert image.get_suffix() == expected.get_suffix()
    assert image.get_width() == expected.get_width()
    assert image.get_height() == expected.get_height()


def test_create_from_file_by_extension(tmp_path: Path) -> None:
    """Ported from ``testCreateFromFileByExtension`` (Java line 58).
    The Java test exercises ccittg4.tif / jpeg.jpg / jpegcmyk.jpg /
    gif.gif / gif-1bit-transparent.gif / png_indexed_8bit_alpha.png /
    png.png / lzw.tif. We use synthesised PNG/JPEG/GIF fixtures here
    (binary fixtures left to a follow-up wave)."""
    jpeg_file = tmp_path / "jpeg.jpg"
    jpeg_file.write_bytes(_jpeg_bytes())
    _compare_jpeg(jpeg_file)

    png_file = tmp_path / "png.png"
    png_file.write_bytes(_png_bytes())
    _compare_lossless(png_file)

    gif_file = tmp_path / "gif.gif"
    gif_file.write_bytes(_gif_bytes())
    _compare_lossless(gif_file)


def test_create_from_file(tmp_path: Path) -> None:
    """Ported from ``testCreateFromFile`` (Java line 78). Confirms
    ``createFromFile`` (string-path overload) routes through
    ``createFromFileByExtension`` for the dispatch."""
    png_file = tmp_path / "png.png"
    png_file.write_bytes(_png_bytes())
    document = PDDocument()
    image = PDImageXObject.create_from_file(str(png_file), document)
    assert image.get_suffix() == "png"
    assert image.get_width() == 3
    assert image.get_height() == 4


def test_create_from_file_by_content(tmp_path: Path) -> None:
    """Ported from ``testCreateFromFileByContent`` (Java line 99).
    Identical dispatch to extension-based form, but format is keyed off
    the magic bytes rather than the suffix."""
    file = tmp_path / "mislabelled.dat"
    file.write_bytes(_png_bytes())
    document = PDDocument()
    image = PDImageXObject.create_from_file_by_content(file, document)
    assert image.get_suffix() == "png"
    assert image.get_width() == 3
    assert image.get_height() == 4


def test_create_from_byte_array(tmp_path: Path) -> None:
    """Ported from ``testCreateFromByteArray`` (Java line 120). The
    Java test compares per-pixel ARGB; we compare width/height/suffix
    against the underlying factory."""
    document = PDDocument()
    data = _jpeg_bytes()
    image = PDImageXObject.create_from_byte_array(document, data, "jpeg.jpg")
    expected = JPEGFactory.create_from_byte_array(document, data)
    assert image.get_suffix() == expected.get_suffix()
    assert image.get_width() == expected.get_width()
    assert image.get_height() == expected.get_height()


def test_create_from_byte_array_with_custom_factory() -> None:
    """Ported from ``testCreateFromByteArrayWithCustomFactory`` (Java line 140).
    Verifies the four-arg ``createFromByteArray`` overload routes
    BMP/GIF/PNG inputs through the supplied custom factory rather than
    the default ``LosslessFactory`` path."""

    class _Factory:
        @staticmethod
        def create_from_byte_array(doc: PDDocument, data: bytes) -> PDImageXObject:
            with Image.open(io.BytesIO(data)) as bim:
                bim.load()
                return JPEGFactory.create_from_image(doc, bim.convert("RGB"))

    document = PDDocument()
    image = PDImageXObject.create_from_byte_array(
        document, _png_bytes(), "src.png", _Factory()
    )
    # Custom factory routed through JPEGFactory → /Filter is /DCTDecode.
    assert image.get_suffix() == "jpg"


def test_create_from_byte_array_unsupported_raises() -> None:
    """Ported from upstream's ``IllegalArgumentException`` branches in
    ``createFromByteArray`` (Java line 371). Upstream uses
    ``IllegalArgumentException``; pypdfbox uses the closest Python
    equivalent ``ValueError``."""
    document = PDDocument()
    with pytest.raises(ValueError, match="Image type not supported"):
        PDImageXObject.create_from_byte_array(document, b"not-an-image", "stub")
