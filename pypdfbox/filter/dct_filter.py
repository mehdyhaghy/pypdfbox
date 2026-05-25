"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.DCTFilter``.

The implementation lives in :mod:`pypdfbox.filter.dct_decode` and is
registered under the PDF ``/Filter`` name ``DCTDecode`` (and its
abbreviation ``DCT``). This module exposes the same codec under the
upstream-faithful Java class name :class:`DCTFilter`, so a direct port
from PDFBox source can write::

    from pypdfbox.filter.dct_filter import DCTFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO, NamedTuple

from PIL import Image

from .dct_decode import DCTDecode
from .filter_factory import FilterFactory

__all__ = ["DCTFilter", "Raster"]


# ----------------------------------------------------------------------
# Tiny raster value-type
# ----------------------------------------------------------------------
#
# Java AWT exposes a concrete ``java.awt.image.Raster`` whose pixel grid
# is mutable and indexable by band. Pillow has no equivalent — its
# ``Image`` is the only first-class raster surface and its byte layout
# is interleaved per-pixel. Rather than depend on AWT semantics we
# carry a minimal interleaved byte buffer plus geometry, which is
# enough to translate the byte-twiddling conversions upstream performs
# in :meth:`fromBGRtoRGB` and :meth:`fromYCCKtoCMYK`.


class Raster(NamedTuple):
    """Minimal interleaved-byte raster used by :class:`DCTFilter`.

    Mirrors the slice of ``java.awt.image.Raster`` exercised by
    upstream ``DCTFilter`` (``getPixel``/``setPixel``/``getPixels``/
    ``setPixels``/``getNumBands``/``getWidth``/``getHeight``). Stored
    as 8-bit interleaved samples in scan-line order so it round-trips
    one-to-one with :func:`PIL.Image.tobytes`.
    """

    samples: bytes
    width: int
    height: int
    num_bands: int

    def get_num_bands(self) -> int:
        return self.num_bands

    def get_width(self) -> int:
        return self.width

    def get_height(self) -> int:
        return self.height


class DCTFilter(DCTDecode):
    """Alias for :class:`DCTDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.DCTFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`DCTDecode`; this subclass exists primarily so the upstream
    Java-style import path resolves and so the per-step JPEG decode
    helpers (``read_image_raster``, ``get_adobe_transform``, ...)
    can be exercised individually for parity testing.
    """

    # Upstream uses ``"Adobe"`` as the APP14 segment signature and
    # the byte at offset 11 as the colour-transform tag.
    _ADOBE: bytes = b"Adobe"
    _POS_TRANSFORM: int = 11

    # ------------------------------------------------------------------
    # JPEG read helpers
    # ------------------------------------------------------------------

    def read_image_raster(self, reader: Image.Image, irp: Any = None) -> Raster:
        """Decode the open Pillow image to a flat interleaved raster.

        Mirrors ``DCTFilter#readImageRaster(ImageReader, ImageReadParam)``
        (DCTFilter.java lines 135-171). Upstream branches on metadata
        ``NumChannels`` to pick between ``ImageReader#read`` and
        ``ImageReader#readRaster``; Pillow already exposes raster bytes
        uniformly via :meth:`PIL.Image.Image.tobytes`, so the branch
        collapses to a single path here. The 4-channel CMYK fallback
        upstream guards against is unnecessary because Pillow honours
        the JPEG colour space directly.
        """
        num_channels = self.get_num_channels(reader)
        reader.load()
        mode = reader.mode
        bands = reader.getbands()
        # Pillow opens 4-component JPEGs as ``"CMYK"`` (or YCCK reported
        # as CMYK with the Adobe marker), 3-component as ``"RGB"`` and
        # 1-component as ``"L"``. ``getbands()`` is the source of truth.
        num_bands = len(bands)
        # ``num_channels`` is informational and may be empty if the
        # metadata path failed; fall through to ``getbands``.
        if num_channels.isdigit() and int(num_channels) != num_bands:
            # Trust Pillow's loader over the side-channel metadata.
            num_bands = len(bands)
        samples = reader.tobytes() if mode != "1" else reader.convert("L").tobytes()
        width, height = reader.size
        return Raster(samples=samples, width=width, height=height, num_bands=num_bands)

    def get_num_channels(self, reader: Image.Image) -> str:
        """Return the JPEG component count as a decimal string.

        Mirrors ``DCTFilter#getNumChannels(ImageReader)`` (lines
        312-334). Upstream pulls ``"NumChannels"`` from the
        ``javax_imageio_1.0`` metadata tree; Pillow surfaces the same
        value via :meth:`PIL.Image.Image.getbands`. Returns ``""`` on
        any failure so callers can treat the empty-string case as
        "metadata unavailable", matching upstream's empty-string
        sentinel.
        """
        try:
            bands = reader.getbands()
        except Exception:
            return ""
        if not bands:
            return ""
        return str(len(bands))

    # ------------------------------------------------------------------
    # APP14 / Adobe colour-transform discovery
    # ------------------------------------------------------------------

    def get_adobe_transform(self, metadata: Any) -> int:
        """Return the APP14 ``transform`` byte, or ``0`` if absent.

        Mirrors ``DCTFilter#getAdobeTransform(IIOMetadata)`` (lines
        181-200). Upstream walks the ``javax_imageio_jpeg_image_1.0``
        DOM tree looking for the ``app14Adobe`` element. Pillow
        exposes the same byte under
        :attr:`PIL.Image.Image.info`["adobe_transform"] when an
        ``Image`` is passed in; for direct dict input we look the key
        up unchanged.

        The valid values are ``0`` (Unknown / RGB or CMYK), ``1``
        (YCbCr) and ``2`` (YCCK). Upstream returns ``0`` when no
        marker is present.
        """
        if metadata is None:
            return 0
        if isinstance(metadata, Image.Image):
            info = metadata.info
        elif isinstance(metadata, dict):
            info = metadata
        else:
            # Best-effort access for arbitrary Pillow-like wrappers.
            info = getattr(metadata, "info", None) or {}
        value = info.get("adobe_transform")
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def get_adobe_transform_by_brute_force(self, iis: BinaryIO) -> int:
        """Scan ``iis`` byte-by-byte for an APP14 ``Adobe`` segment.

        Mirrors ``DCTFilter#getAdobeTransformByBruteForce(ImageInputStream)``
        (lines 204-244). Used as a fallback when
        :meth:`get_adobe_transform` raises (in Java because of a
        broken metadata tree). The scan walks the stream looking for
        the ASCII tag ``"Adobe"``, reverses 9 bytes to land on the
        ``0xFFEE`` APP14 marker and reads the transform byte at
        ``POS_TRANSFORM``.

        ``iis`` must be a seekable byte stream. The cursor is rewound
        to the start before scanning, matching upstream's
        ``iis.seek(0)``.
        """
        adobe = self._ADOBE
        adobe_len = len(adobe)
        a = 0
        try:
            iis.seek(0)
        except (AttributeError, io.UnsupportedOperation):
            return 0
        while True:
            byte = iis.read(1)
            if not byte:
                break
            by = byte[0]
            if adobe[a] == by:
                a += 1
                if a != adobe_len:
                    continue
                a = 0
                after_adobe_pos = iis.tell()
                iis.seek(after_adobe_pos - adobe_len - 4)
                tag_bytes = iis.read(2)
                if len(tag_bytes) < 2:
                    iis.seek(after_adobe_pos)
                    continue
                tag = (tag_bytes[0] << 8) | tag_bytes[1]
                if tag != 0xFFEE:
                    iis.seek(after_adobe_pos)
                    continue
                len_bytes = iis.read(2)
                if len(len_bytes) < 2:
                    iis.seek(after_adobe_pos)
                    continue
                seg_len = (len_bytes[0] << 8) | len_bytes[1]
                if seg_len >= self._POS_TRANSFORM + 1:
                    payload_size = max(seg_len, self._POS_TRANSFORM + 1)
                    app14 = iis.read(payload_size)
                    if len(app14) >= self._POS_TRANSFORM + 1:
                        return app14[self._POS_TRANSFORM]
                # Restore the cursor past the matched marker before rescanning,
                # mirroring the three guards above. Without this, a malformed
                # APP14 with seg_len < _POS_TRANSFORM + 1 leaves the cursor at
                # the start of the matched "Adobe" bytes and the scan re-matches
                # forever (infinite loop on crafted input).
                iis.seek(after_adobe_pos)
            else:
                a = 0
        return 0

    # ------------------------------------------------------------------
    # Colour-space conversions
    # ------------------------------------------------------------------

    def from_ycc_kto_cmyk(self, raster: Raster) -> Raster:
        """Convert a 4-band YCCK raster to CMYK, in place by value.

        Mirrors ``DCTFilter#fromYCCKtoCMYK(Raster)`` (lines 249-285).
        YCCK is an equivalent encoding for CMYK so no colour
        management is needed: convert YCbCr → RGB with the standard
        BT.601 coefficients, then take the naive ``255 - x`` per
        channel and copy the unchanged K channel.
        """
        if raster.num_bands != 4:
            raise ValueError("from_ycc_kto_cmyk requires a 4-band raster")
        width, height = raster.width, raster.height
        src = raster.samples
        out = bytearray(len(src))
        clamp = self.clamp
        for pos in range(0, width * height * 4, 4):
            y = src[pos]
            cb = src[pos + 1]
            cr = src[pos + 2]
            k = src[pos + 3]
            # YCCK -> RGB (Intel reference implementation, see
            # http://software.intel.com/en-us/node/442744).
            r = clamp(y + 1.402 * cr - 179.456)
            g = clamp(y - 0.34414 * cb - 0.71414 * cr + 135.45984)
            b = clamp(y + 1.772 * cb - 226.816)
            # naive RGB -> CMY, K passes through unchanged.
            out[pos] = 255 - r
            out[pos + 1] = 255 - g
            out[pos + 2] = 255 - b
            out[pos + 3] = k
        return Raster(samples=bytes(out), width=width, height=height, num_bands=4)

    def from_bg_rto_rgb(self, raster: Raster) -> Raster:
        """Swap the B and R bands of a 3-band BGR raster, returning RGB.

        Mirrors ``DCTFilter#fromBGRtoRGB(Raster)`` (lines 288-309).
        Operates one scan-line at a time to keep the working set
        small, matching the upstream comment ``BEWARE: handling the
        full image at a time is slower than one line at a time``.
        """
        if raster.num_bands != 3:
            raise ValueError("from_bg_rto_rgb requires a 3-band raster")
        width, height = raster.width, raster.height
        w3 = width * 3
        src = raster.samples
        out = bytearray(len(src))
        for y in range(height):
            line_start = y * w3
            for off in range(0, w3, 3):
                base = line_start + off
                out[base] = src[base + 2]
                out[base + 1] = src[base + 1]
                out[base + 2] = src[base]
        return Raster(samples=bytes(out), width=width, height=height, num_bands=3)

    # ------------------------------------------------------------------
    # Numeric helpers
    # ------------------------------------------------------------------

    def clamp(self, value: float) -> int:
        """Clamp a floating-point sample to the 0-255 integer range.

        Mirrors ``DCTFilter#clamp(float)`` (lines 337-340). Java
        truncates via ``(int)`` cast; we use :func:`int` which has
        the same toward-zero semantics for non-negative inputs.
        """
        if value < 0:
            return 0
        if value > 255:
            return 255
        return int(value)


# Register the upstream-named subclass alongside the existing
# ``DCTDecode`` registration. The PDF ``/Filter`` name (``DCTDecode``)
# and its abbreviation (``DCT``) continue to resolve to the original
# ``DCTDecode`` instance owned by ``dct_decode.py``.
FilterFactory.register("DCTFilter", DCTFilter())
