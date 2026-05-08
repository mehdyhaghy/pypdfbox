"""Shared PDF predictor (PNG / TIFF) encode + decode helpers.

Used by ``FlateDecode`` and ``LZWDecode`` for the per-row predictor
post-filter described in ISO 32000-1 §7.4.4.4 (referencing RFC 2083 PNG
filters and TIFF 6.0 §14 predictor 2).

Predictor values:

* ``1``  - none (passthrough)
* ``2``  - TIFF: subtract previous sample on the same row
* ``10`` - PNG None
* ``11`` - PNG Sub
* ``12`` - PNG Up
* ``13`` - PNG Average
* ``14`` - PNG Paeth
* ``15`` - PNG Optimum (per-row choice; on encode pick the heuristic
  minimum-sum-of-absolute-values filter type, RFC 2083 §9.6)
"""

from __future__ import annotations

# ---------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------


def _validate_geometry(columns: int, colors: int, bits_per_component: int) -> None:
    """Validate predictor image geometry before row math."""
    if columns <= 0:
        raise OSError(f"invalid /Columns {columns}")
    if colors <= 0:
        raise OSError(f"invalid /Colors {colors}")
    if bits_per_component <= 0:
        raise OSError(f"invalid /BitsPerComponent {bits_per_component}")


def _row_bytes(columns: int, colors: int, bits_per_component: int) -> int:
    """Width of one scanline in whole bytes (rounded up)."""
    return (columns * colors * bits_per_component + 7) // 8


def calculate_row_length(colors: int, bits_per_component: int, columns: int) -> int:
    """Public mirror of ``Predictor#calculateRowLength`` (Java).

    Returns the width of one scanline in whole bytes (rounded up). The
    parameter order matches the upstream Java signature
    ``(colors, bitsPerComponent, columns)`` rather than the internal
    helper's ``(columns, colors, bitsPerComponent)``.
    """
    return _row_bytes(columns, colors, bits_per_component)


def _bytes_per_pixel(colors: int, bits_per_component: int) -> int:
    """Bytes between adjacent pixels along a row, rounded up to >= 1.

    For sub-byte component widths this is 1 by PNG convention so the
    "left neighbor" lookup still works on a byte basis.
    """
    bits_per_pixel = colors * bits_per_component
    return max(1, (bits_per_pixel + 7) // 8)


def decode_predictor_row(
    predictor: int,
    colors: int,
    bits_per_component: int,
    columns: int,
    actline: bytearray,
    lastline: bytes | bytearray,
) -> None:
    """Decode a single predictor-encoded row in place.

    Mirrors ``org.apache.pdfbox.filter.Predictor#decodePredictorRow``.
    ``actline`` is the (mutable) current row to be decoded; ``lastline``
    is the *raw, already-decoded* previous row (use a zero-filled buffer
    of the same length when decoding the first row). For PNG predictors
    (``10..14``) the per-row filter-tag byte is *not* part of ``actline``
    — callers must strip it and pass it in via ``predictor`` (i.e. add
    10 to the tag byte). ``predictor == 1`` is a passthrough and leaves
    ``actline`` unchanged.
    """
    if predictor == 1:
        return
    rowlength = len(actline)
    if rowlength == 0:
        return
    _validate_geometry(columns, colors, bits_per_component)
    if predictor in (12, 13, 14) and len(lastline) < rowlength:
        raise OSError(
            f"previous predictor row too short ({len(lastline)} bytes, need {rowlength})"
        )
    bpp = _bytes_per_pixel(colors, bits_per_component)
    if predictor == 2:
        # TIFF Predictor 2 — delegate to bulk path on a 1-row buffer.
        actline[:] = _untiff(bytes(actline), columns, colors, bits_per_component)
        return
    if predictor == 10:
        # None — no transformation.
        return
    if predictor == 11:
        for p in range(bpp, rowlength):
            actline[p] = (actline[p] + actline[p - bpp]) & 0xFF
        return
    if predictor == 12:
        for p in range(rowlength):
            actline[p] = (actline[p] + lastline[p]) & 0xFF
        return
    if predictor == 13:
        for p in range(rowlength):
            left = actline[p - bpp] if p - bpp >= 0 else 0
            up = lastline[p]
            actline[p] = (actline[p] + (left + up) // 2) & 0xFF
        return
    if predictor == 14:
        for p in range(rowlength):
            left = actline[p - bpp] if p - bpp >= 0 else 0
            up = lastline[p]
            up_left = lastline[p - bpp] if p - bpp >= 0 else 0
            actline[p] = (actline[p] + _paeth(left, up, up_left)) & 0xFF
        return
    # Unknown predictor — upstream's switch falls through silently
    # (default: break). Match that behavior.


# ---------------------------------------------------------------------
# Decode side (post-decompression)
# ---------------------------------------------------------------------


def unpredict(
    data: bytes,
    predictor: int,
    columns: int,
    colors: int,
    bits_per_component: int,
) -> bytes:
    """Reverse the PDF predictor encoding applied prior to compression.

    Returns ``data`` unchanged when ``predictor == 1``. Raises
    ``OSError`` on unknown predictor values or unsupported PNG filter
    tags.
    """
    if predictor == 1:
        return data

    _validate_geometry(columns, colors, bits_per_component)
    bpp = _bytes_per_pixel(colors, bits_per_component)
    rb = _row_bytes(columns, colors, bits_per_component)

    if predictor == 2:
        return _untiff(data, columns, colors, bits_per_component)
    if 10 <= predictor <= 15:
        return _unpng(data, rb, bpp)
    raise OSError(f"unsupported /Predictor {predictor}")


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
        # Tolerate a short final row - pad with zeros so we still produce
        # a row of the declared width. PDFBox does the same.
        cur = bytearray(row[1 : 1 + row_bytes])
        if len(cur) < row_bytes:
            cur.extend(b"\x00" * (row_bytes - len(cur)))

        if filter_type == 0:
            # None - no transformation.
            pass
        elif filter_type == 1:
            # Sub - each byte is the previous byte (in the same row,
            # ``bytes_per_pixel`` to the left) added back.
            for i in range(bytes_per_pixel, row_bytes):
                cur[i] = (cur[i] + cur[i - bytes_per_pixel]) & 0xFF
        elif filter_type == 2:
            # Up - add the byte from the row above.
            for i in range(row_bytes):
                cur[i] = (cur[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:
            # Average - add floor((left + up) / 2).
            for i in range(row_bytes):
                left = cur[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = prev_row[i]
                cur[i] = (cur[i] + (left + up) // 2) & 0xFF
        elif filter_type == 4:
            # Paeth - add the Paeth predictor of (left, up, upper-left).
            for i in range(row_bytes):
                left = cur[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = prev_row[i]
                up_left = prev_row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                cur[i] = (cur[i] + _paeth(left, up, up_left)) & 0xFF
        else:
            raise OSError(f"unknown PNG filter type {filter_type}")

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
    for row_start in range(0, len(data), row_bytes):
        row = bytearray(data[row_start : row_start + row_bytes])
        if bits_per_component == 8:
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
            row[:] = _untiff_bits(bytes(row), columns, colors, bits_per_component)
        out.extend(row)
    return bytes(out)


def _untiff_bits(row: bytes, columns: int, colors: int, bits: int) -> bytes:
    """TIFF Predictor 2 for sub-byte component widths (1, 2, 4)."""
    mask = (1 << bits) - 1
    samples_per_row = columns * colors
    samples: list[int] = []
    for s in range(samples_per_row):
        bit_pos = s * bits
        byte_idx = bit_pos // 8
        bit_off = bit_pos % 8
        if byte_idx + 1 < len(row):
            window = (row[byte_idx] << 8) | row[byte_idx + 1]
        else:
            window = row[byte_idx] << 8
        shift = 16 - bit_off - bits
        samples.append((window >> shift) & mask)
    for i in range(colors, len(samples)):
        samples[i] = (samples[i] + samples[i - colors]) & mask
    out = bytearray(len(row))
    for s, value in enumerate(samples):
        bit_pos = s * bits
        byte_idx = bit_pos // 8
        bit_off = bit_pos % 8
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


# ---------------------------------------------------------------------
# Encode side (pre-compression)
# ---------------------------------------------------------------------


def predict(
    raw: bytes,
    predictor: int,
    columns: int,
    colors: int,
    bits_per_component: int,
) -> bytes:
    """Apply the PDF predictor encoding ``raw`` so a subsequent
    decompress + :func:`unpredict` round-trips back to the original.

    Returns ``raw`` unchanged when ``predictor == 1``. Raises
    ``OSError`` on unknown predictor values.
    """
    if predictor == 1:
        return raw
    if not raw:
        return b""

    _validate_geometry(columns, colors, bits_per_component)
    if predictor == 2:
        return _tiff_encode(raw, columns, colors, bits_per_component)
    if 10 <= predictor <= 15:
        return _png_encode(raw, predictor, columns, colors, bits_per_component)
    raise OSError(f"unsupported /Predictor {predictor}")


def _tiff_encode(
    raw: bytes,
    columns: int,
    colors: int,
    bits_per_component: int,
) -> bytes:
    """TIFF Predictor 2 encode: subtract the previous sample on the row."""
    rb = _row_bytes(columns, colors, bits_per_component)
    if rb == 0:
        return b""

    out = bytearray()
    for row_start in range(0, len(raw), rb):
        row = bytearray(raw[row_start : row_start + rb])
        if len(row) < rb:
            row.extend(b"\x00" * (rb - len(row)))
        if bits_per_component == 8:
            # Subtract back-to-front so each step sees the unmodified left.
            for i in range(len(row) - 1, colors - 1, -1):
                row[i] = (row[i] - row[i - colors]) & 0xFF
        elif bits_per_component == 16:
            for i in range(len(row) - 2, colors * 2 - 1, -2):
                cur = (row[i] << 8) | row[i + 1]
                left = (row[i - colors * 2] << 8) | row[i - colors * 2 + 1]
                v = (cur - left) & 0xFFFF
                row[i] = (v >> 8) & 0xFF
                row[i + 1] = v & 0xFF
        else:
            row[:] = _tiff_encode_bits(bytes(row), columns, colors, bits_per_component)
        out.extend(row)
    return bytes(out)


def _tiff_encode_bits(row: bytes, columns: int, colors: int, bits: int) -> bytes:
    """TIFF Predictor 2 encode for sub-byte component widths (1, 2, 4)."""
    mask = (1 << bits) - 1
    samples_per_row = columns * colors
    samples: list[int] = []
    for s in range(samples_per_row):
        bit_pos = s * bits
        byte_idx = bit_pos // 8
        bit_off = bit_pos % 8
        if byte_idx + 1 < len(row):
            window = (row[byte_idx] << 8) | row[byte_idx + 1]
        else:
            window = row[byte_idx] << 8
        shift = 16 - bit_off - bits
        samples.append((window >> shift) & mask)
    # Encode back-to-front so each step still sees the original left.
    for i in range(len(samples) - 1, colors - 1, -1):
        samples[i] = (samples[i] - samples[i - colors]) & mask
    out = bytearray(len(row))
    for s, value in enumerate(samples):
        bit_pos = s * bits
        byte_idx = bit_pos // 8
        bit_off = bit_pos % 8
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


# Mapping from PDF /Predictor (10..14) to PNG filter-type tag (0..4).
_PNG_TAG_FOR_PREDICTOR = {
    10: 0,  # None
    11: 1,  # Sub
    12: 2,  # Up
    13: 3,  # Average
    14: 4,  # Paeth
}


def _png_encode(
    raw: bytes,
    predictor: int,
    columns: int,
    colors: int,
    bits_per_component: int,
) -> bytes:
    """PNG predictor encode: prepend a 1-byte filter tag per row."""
    rb = _row_bytes(columns, colors, bits_per_component)
    bpp = _bytes_per_pixel(colors, bits_per_component)
    if rb == 0:
        return b""

    out = bytearray()
    prev_row = bytes(rb)
    for row_start in range(0, len(raw), rb):
        row = bytes(raw[row_start : row_start + rb])
        if len(row) < rb:
            row = row + b"\x00" * (rb - len(row))

        if predictor == 15:
            tag, encoded = _png_pick_optimum(row, prev_row, bpp)
        else:
            tag = _PNG_TAG_FOR_PREDICTOR[predictor]
            encoded = _png_apply_filter(tag, row, prev_row, bpp)

        out.append(tag)
        out.extend(encoded)
        prev_row = row
    return bytes(out)


def _png_apply_filter(
    tag: int,
    row: bytes,
    prev_row: bytes,
    bpp: int,
) -> bytes:
    """Encode ``row`` with PNG filter ``tag``; ``prev_row`` is the raw
    (un-filtered) previous scanline. Returns the filtered bytes (no tag)."""
    n = len(row)
    out = bytearray(n)
    if tag == 0:
        return bytes(row)
    if tag == 1:
        # Sub: cur - left.
        for i in range(n):
            left = row[i - bpp] if i >= bpp else 0
            out[i] = (row[i] - left) & 0xFF
        return bytes(out)
    if tag == 2:
        # Up: cur - up.
        for i in range(n):
            out[i] = (row[i] - prev_row[i]) & 0xFF
        return bytes(out)
    if tag == 3:
        # Average: cur - floor((left + up) / 2).
        for i in range(n):
            left = row[i - bpp] if i >= bpp else 0
            up = prev_row[i]
            out[i] = (row[i] - (left + up) // 2) & 0xFF
        return bytes(out)
    if tag == 4:
        # Paeth: cur - Paeth(left, up, upper-left).
        for i in range(n):
            left = row[i - bpp] if i >= bpp else 0
            up = prev_row[i]
            up_left = prev_row[i - bpp] if i >= bpp else 0
            out[i] = (row[i] - _paeth(left, up, up_left)) & 0xFF
        return bytes(out)
    raise OSError(f"unknown PNG filter type {tag}")


def _png_pick_optimum(
    row: bytes,
    prev_row: bytes,
    bpp: int,
) -> tuple[int, bytes]:
    """Pick the filter tag minimising sum of absolute *signed* byte values
    of the filtered row (RFC 2083 §9.6 minimum-sum-of-absolute-differences
    heuristic). Returns ``(tag, filtered_bytes)``.
    """
    best_tag = 0
    best_bytes = bytes(row)
    best_score = _signed_abs_sum(best_bytes)
    for tag in (1, 2, 3, 4):
        candidate = _png_apply_filter(tag, row, prev_row, bpp)
        score = _signed_abs_sum(candidate)
        if score < best_score:
            best_score = score
            best_tag = tag
            best_bytes = candidate
    return best_tag, best_bytes


def _signed_abs_sum(data: bytes) -> int:
    """Treat each byte as a signed 8-bit value and sum the absolute values.

    This is the standard PNG heuristic: a byte value of 200 is treated as
    -56 (its signed-8-bit interpretation) before taking |x|.
    """
    total = 0
    for b in data:
        total += b if b < 128 else 256 - b
    return total
