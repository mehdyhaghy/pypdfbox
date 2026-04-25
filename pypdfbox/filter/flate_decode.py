from __future__ import annotations

import zlib
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory


class FlateDecode(Filter):
    """
    ``/FlateDecode`` filter (ISO 32000-1 §7.4.4).

    Thin adapter over :mod:`zlib` for the deflate/inflate primitives;
    the post-decompression PNG/TIFF predictor unfiltering (§7.4.4.3) is
    original code. Predictor *encoding* is intentionally not supported,
    matching upstream PDFBox behaviour.

    Mirrors `org.apache.pdfbox.filter.FlateFilter`.
    """

    # ---------- public API ----------

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        try:
            inflated = zlib.decompress(encoded.read())
        except zlib.error as exc:
            # Surface decompression failures (truncated streams, bad
            # checksums, etc.) as ``OSError`` so callers can rely on
            # one I/O exception type per the Filter contract.
            raise OSError(f"FlateDecode: {exc}") from exc

        predictor = parameters.get_int("Predictor", 1) if parameters is not None else 1
        if predictor > 1:
            assert parameters is not None  # narrows for mypy
            columns = parameters.get_int("Columns", 1)
            colors = parameters.get_int("Colors", 1)
            bits_per_component = parameters.get_int("BitsPerComponent", 8)
            inflated = _unpredict(inflated, predictor, columns, colors, bits_per_component)

        bytes_written = decoded.write(inflated)
        out_params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        if parameters is not None:
            predictor = parameters.get_int("Predictor", 1)
            if predictor > 1:
                # Upstream PDFBox does not implement predictor encoding
                # either; both rely on consumers writing predictor-encoded
                # data themselves when they need it.
                raise NotImplementedError(
                    "FlateDecode: predictor encoding is not supported "
                    f"(/Predictor {predictor} requested)"
                )
        encoded.write(zlib.compress(raw.read()))


# ---------- predictor unfiltering (PDF spec §7.4.4.3) ----------


def _unpredict(
    data: bytes,
    predictor: int,
    columns: int,
    colors: int,
    bits_per_component: int,
) -> bytes:
    """Reverse the PDF predictor encoding applied prior to deflate.

    ``predictor`` values:

    * ``1`` — no prediction (caller should not have invoked this)
    * ``2`` — TIFF prediction: each sample is the difference from the
      previous sample on the same row
    * ``10..15`` — PNG prediction. Each row is preceded by a 1-byte
      filter tag (``None``/``Sub``/``Up``/``Average``/``Paeth``);
      ``15`` (``Optimum``) means "the encoder picked per-row, decode
      according to each row's actual tag".
    """

    # Bytes per pixel/sample, rounded up to whole bytes.
    bits_per_pixel = colors * bits_per_component
    bytes_per_pixel = max(1, (bits_per_pixel + 7) // 8)
    # Bytes per scanline (rounded up to full bytes for sub-byte components).
    row_bits = columns * bits_per_pixel
    row_bytes = (row_bits + 7) // 8

    if predictor == 2:
        return _untiff(data, columns, colors, bits_per_component)

    if 10 <= predictor <= 15:
        return _unpng(data, row_bytes, bytes_per_pixel)

    raise OSError(f"FlateDecode: unsupported /Predictor {predictor}")


def _unpng(data: bytes, row_bytes: int, bytes_per_pixel: int) -> bytes:
    """Reverse one of the five PNG row filters per row."""
    if row_bytes == 0:
        return b""

    stride = row_bytes + 1  # +1 for the per-row filter-tag byte
    out = bytearray()
    prev_row = bytearray(row_bytes)

    for row_start in range(0, len(data), stride):
        row = data[row_start : row_start + stride]
        if len(row) < 1:
            break
        filter_type = row[0]
        # Tolerate a short final row — pad with zeros so we still produce
        # a row of the declared width. PDFBox does the same.
        cur = bytearray(row[1 : 1 + row_bytes])
        if len(cur) < row_bytes:
            cur.extend(b"\x00" * (row_bytes - len(cur)))

        if filter_type == 0:
            # None — no transformation.
            pass
        elif filter_type == 1:
            # Sub — each byte is the previous byte (in the same row,
            # ``bytes_per_pixel`` to the left) added back.
            for i in range(bytes_per_pixel, row_bytes):
                cur[i] = (cur[i] + cur[i - bytes_per_pixel]) & 0xFF
        elif filter_type == 2:
            # Up — add the byte from the row above.
            for i in range(row_bytes):
                cur[i] = (cur[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:
            # Average — add floor((left + up) / 2).
            for i in range(row_bytes):
                left = cur[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = prev_row[i]
                cur[i] = (cur[i] + (left + up) // 2) & 0xFF
        elif filter_type == 4:
            # Paeth — add the Paeth predictor of (left, up, upper-left).
            for i in range(row_bytes):
                left = cur[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = prev_row[i]
                up_left = prev_row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                cur[i] = (cur[i] + _paeth(left, up, up_left)) & 0xFF
        else:
            raise OSError(f"FlateDecode: unknown PNG filter type {filter_type}")

        out.extend(cur)
        prev_row = cur

    return bytes(out)


def _paeth(a: int, b: int, c: int) -> int:
    """PNG Paeth predictor (RFC 2083 §6.6)."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _untiff(data: bytes, columns: int, colors: int, bits_per_component: int) -> bytes:
    """Reverse TIFF Predictor 2 (per-component subtraction along the row)."""
    bits_per_pixel = colors * bits_per_component
    row_bytes = (columns * bits_per_pixel + 7) // 8
    if row_bytes == 0 or not data:
        return b""

    out = bytearray()
    # Process row-by-row.
    for row_start in range(0, len(data), row_bytes):
        row = bytearray(data[row_start : row_start + row_bytes])
        if bits_per_component == 8:
            # Common, fast path.
            for i in range(colors, len(row)):
                row[i] = (row[i] + row[i - colors]) & 0xFF
        elif bits_per_component == 16:
            for i in range(colors * 2, len(row), 2):
                hi_prev = row[i - colors * 2]
                lo_prev = row[i - colors * 2 + 1]
                prev = (hi_prev << 8) | lo_prev
                cur = (row[i] << 8) | row[i + 1]
                v = (cur + prev) & 0xFFFF
                row[i] = (v >> 8) & 0xFF
                row[i + 1] = v & 0xFF
        else:
            # Bit-packed component widths (1, 2, 4) — process bit-by-bit.
            row[:] = _untiff_bits(bytes(row), columns, colors, bits_per_component)
        out.extend(row)
    return bytes(out)


def _untiff_bits(row: bytes, columns: int, colors: int, bits: int) -> bytes:
    """TIFF Predictor 2 for sub-byte component widths."""
    mask = (1 << bits) - 1
    samples_per_row = columns * colors
    # Unpack to per-component integers.
    samples: list[int] = []
    for s in range(samples_per_row):
        bit_pos = s * bits
        byte_idx = bit_pos // 8
        bit_off = bit_pos % 8
        # Read up to 16 bits straddling a byte boundary.
        if byte_idx + 1 < len(row):
            window = (row[byte_idx] << 8) | row[byte_idx + 1]
            shift = 16 - bit_off - bits
        else:
            window = row[byte_idx] << 8
            shift = 16 - bit_off - bits
        samples.append((window >> shift) & mask)
    # Differential decode within each row, per channel.
    for i in range(colors, len(samples)):
        samples[i] = (samples[i] + samples[i - colors]) & mask
    # Repack.
    out = bytearray(len(row))
    for s, value in enumerate(samples):
        bit_pos = s * bits
        byte_idx = bit_pos // 8
        bit_off = bit_pos % 8
        # Place ``value`` so its top bit lands at ``bit_off``.
        shift = 16 - bit_off - bits
        if byte_idx + 1 < len(out):
            window = (out[byte_idx] << 8) | out[byte_idx + 1]
            window |= (value & mask) << shift
            out[byte_idx] = (window >> 8) & 0xFF
            out[byte_idx + 1] = window & 0xFF
        else:
            window = out[byte_idx] << 8
            window |= (value & mask) << shift
            out[byte_idx] = (window >> 8) & 0xFF
    return bytes(out)


# Register both the long name and (implicitly via the factory's
# abbreviation map) the short ``/Fl`` form.
FilterFactory.register("FlateDecode", FlateDecode())
