from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# Reserved LZW codes per ISO 32000-1 §7.4.4.
CLEAR_TABLE = 256
EOD = 257

# Code-table cap: codes are 9..12 bits, so 4096 entries max.
MAX_TABLE_SIZE = 4096


class _BitReader:
    """MSB-first bit reader over a binary stream.

    PDF's LZW packs codes most-significant-bit first within each byte; a
    9-bit code spans the high bits of byte 0 plus the top of byte 1. This
    reader buffers whole bytes and slices arbitrary bit-widths off the
    high end of the buffer.
    """

    __slots__ = ("_src", "_buffer", "_bits_in_buffer", "_eof")

    def __init__(self, src: BinaryIO) -> None:
        self._src = src
        self._buffer = 0
        self._bits_in_buffer = 0
        self._eof = False

    def read_bits(self, n: int) -> int:
        """Return the next ``n`` bits as a non-negative int.

        Raises ``EOFError`` if the underlying stream runs out before
        ``n`` bits could be assembled.
        """
        while self._bits_in_buffer < n:
            chunk = self._src.read(1)
            if not chunk:
                self._eof = True
                raise EOFError("unexpected EOF in LZW bit stream")
            self._buffer = (self._buffer << 8) | chunk[0]
            self._bits_in_buffer += 8
        shift = self._bits_in_buffer - n
        result = (self._buffer >> shift) & ((1 << n) - 1)
        self._buffer &= (1 << shift) - 1
        self._bits_in_buffer = shift
        return result


class _BitWriter:
    """MSB-first bit writer to a binary stream.

    Mirrors the bit ordering used by ``_BitReader`` so that an
    encode/decode round-trip is bit-for-bit symmetric. A trailing
    ``flush`` zero-pads the last partial byte (PDF spec leaves trailing
    bits unspecified after the EOD marker).
    """

    __slots__ = ("_dst", "_buffer", "_bits_in_buffer")

    def __init__(self, dst: BinaryIO) -> None:
        self._dst = dst
        self._buffer = 0
        self._bits_in_buffer = 0

    def write_bits(self, value: int, n: int) -> None:
        self._buffer = (self._buffer << n) | (value & ((1 << n) - 1))
        self._bits_in_buffer += n
        while self._bits_in_buffer >= 8:
            shift = self._bits_in_buffer - 8
            byte = (self._buffer >> shift) & 0xFF
            self._dst.write(bytes((byte,)))
            self._buffer &= (1 << shift) - 1
            self._bits_in_buffer = shift

    def flush(self) -> None:
        if self._bits_in_buffer > 0:
            byte = (self._buffer << (8 - self._bits_in_buffer)) & 0xFF
            self._dst.write(bytes((byte,)))
            self._buffer = 0
            self._bits_in_buffer = 0


def _calculate_chunk(table_size: int, early_change: bool) -> int:
    """Return code-width (9..12) for the next code, given table size.

    With EarlyChange=1 (PDF default) the width grows one entry sooner
    than canonical LZW: when ``table_size`` would hit 511/1023/2047 the
    next code is already emitted at the wider width. Mirrors PDFBox's
    ``LZWFilter.calculateChunk``.
    """
    i = table_size + (1 if early_change else 0)
    if i >= 2048:
        return 12
    if i >= 1024:
        return 11
    if i >= 512:
        return 10
    return 9


def _initial_code_table() -> list[bytes | None]:
    """Build a fresh code table with the 256 single-byte literals plus
    placeholders for the two reserved codes 256/257."""
    table: list[bytes | None] = [bytes((i,)) for i in range(256)]
    table.append(None)  # CLEAR_TABLE (256)
    table.append(None)  # EOD (257)
    return table


# ---------- predictor support (PNG/TIFF row predictors) ---------------
#
# Note for the parent agent during consolidation: this predictor logic
# is duplicated here (inline) and is also needed by FlateDecode. When
# both filters land, factor this into ``pypdfbox/filter/_predictor.py``
# and have FlateDecode import the same helpers. Kept inline now to avoid
# coupling cluster #1 and cluster #3.


def _row_length(colors: int, bits_per_component: int, columns: int) -> int:
    bits_per_pixel = colors * bits_per_component
    return (columns * bits_per_pixel + 7) // 8


def _decode_predictor_row(
    predictor: int,
    colors: int,
    bits_per_component: int,
    columns: int,
    actline: bytearray,
    lastline: bytes,
) -> None:
    """Inverse PNG/TIFF predictor over one row, in place on ``actline``."""
    if predictor == 1 or predictor == 10:
        return
    bits_per_pixel = colors * bits_per_component
    bytes_per_pixel = max(1, (bits_per_pixel + 7) // 8)
    rowlength = len(actline)

    if predictor == 2:
        # TIFF Sub. 8-bit fast path; fall back to a generic byte-wise
        # SUB for 16-bit so that round-tripping common cases stays
        # correct. Sub-byte components for predictor 2 are uncommon
        # in the wild for LZW image streams; if needed we can extend.
        if bits_per_component == 8:
            for p in range(bytes_per_pixel, rowlength):
                actline[p] = (actline[p] + actline[p - bytes_per_pixel]) & 0xFF
            return
        if bits_per_component == 16:
            for p in range(bytes_per_pixel, rowlength - 1, 2):
                sub = (actline[p] << 8) | actline[p + 1]
                left = (actline[p - bytes_per_pixel] << 8) | actline[p - bytes_per_pixel + 1]
                total = (sub + left) & 0xFFFF
                actline[p] = (total >> 8) & 0xFF
                actline[p + 1] = total & 0xFF
            return
        raise OSError(f"unsupported TIFF predictor bit depth: {bits_per_component}")

    if predictor == 11:
        # PNG Sub
        for p in range(bytes_per_pixel, rowlength):
            actline[p] = (actline[p] + actline[p - bytes_per_pixel]) & 0xFF
        return
    if predictor == 12:
        # PNG Up
        for p in range(rowlength):
            actline[p] = (actline[p] + lastline[p]) & 0xFF
        return
    if predictor == 13:
        # PNG Average
        for p in range(rowlength):
            left = actline[p - bytes_per_pixel] if p - bytes_per_pixel >= 0 else 0
            up = lastline[p]
            actline[p] = (actline[p] + (left + up) // 2) & 0xFF
        return
    if predictor == 14:
        # PNG Paeth
        for p in range(rowlength):
            a = actline[p - bytes_per_pixel] if p - bytes_per_pixel >= 0 else 0
            b = lastline[p]
            c = lastline[p - bytes_per_pixel] if p - bytes_per_pixel >= 0 else 0
            value = a + b - c
            absa = abs(value - a)
            absb = abs(value - b)
            absc = abs(value - c)
            if absa <= absb and absa <= absc:
                pred = a
            elif absb <= absc:
                pred = b
            else:
                pred = c
            actline[p] = (actline[p] + pred) & 0xFF
        return
    # Unknown predictor: leave data as-is rather than corrupt it. This
    # matches PDFBox's permissive behavior in ``decodePredictorRow``.


def _apply_predictor(
    raw: bytes,
    predictor: int,
    colors: int,
    bits_per_component: int,
    columns: int,
) -> bytes:
    """Apply the inverse predictor to ``raw`` and return decoded bytes."""
    if predictor == 1:
        return raw
    rowlen = _row_length(colors, bits_per_component, columns)
    if rowlen <= 0:
        raise OSError(f"invalid predictor row length: {rowlen}")
    png_per_row = predictor >= 10
    out = bytearray()
    lastline = bytes(rowlen)
    pos = 0
    n = len(raw)
    while pos < n:
        current_predictor = predictor
        if png_per_row:
            if pos >= n:
                break
            current_predictor = raw[pos] + 10
            pos += 1
        end = pos + rowlen
        actline = bytearray(rowlen)
        if end <= n:
            actline[: rowlen] = raw[pos:end]
            pos = end
        else:
            actline[: n - pos] = raw[pos:n]
            pos = n
        _decode_predictor_row(
            current_predictor, colors, bits_per_component, columns, actline, lastline
        )
        out.extend(actline)
        lastline = bytes(actline)
    return bytes(out)


def _get_decode_params(parameters: COSDictionary | None, index: int) -> COSDictionary:
    """Resolve effective ``/DecodeParms`` for the filter at ``index``.

    PDF allows ``/DecodeParms`` to be either a single dictionary (when
    there is one filter) or an array parallel to ``/Filter``. For now
    we accept only the single-dict form and the ``/DP``/``/DecodeParms``
    keys; missing entries return an empty dict.
    """
    if parameters is None:
        return COSDictionary()
    from pypdfbox.cos import COSArray

    for key in ("DecodeParms", "DP"):
        params = parameters.get_dictionary_object(key)
        if isinstance(params, COSDictionary):
            return params
        if isinstance(params, COSArray):
            try:
                entry = params.get(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
            return COSDictionary()
    # Fall back: treat top-level dict as the params dict (some callers
    # pass the decode-params dictionary directly).
    return parameters


class LZWDecode(Filter):
    """
    PDF ``/LZWDecode`` filter per ISO 32000-1 §7.4.4.

    Implements variable-width (9..12 bit) LZW with the PDF-specific
    ``EarlyChange`` flag (default 1) and optional PNG/TIFF predictor
    post-processing via ``/Predictor`` in ``/DecodeParms``.

    Mirrors `org.apache.pdfbox.filter.LZWFilter`.
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        decode_params = _get_decode_params(parameters, index)
        early_change = decode_params.get_int("EarlyChange", 1) != 0
        predictor = decode_params.get_int("Predictor", 1)

        raw_buffer = BytesIO()
        self._do_lzw_decode(encoded, raw_buffer, early_change)
        raw_bytes = raw_buffer.getvalue()

        if predictor > 1:
            colors = min(decode_params.get_int("Colors", 1), 32)
            bits_per_component = decode_params.get_int("BitsPerComponent", 8)
            columns = decode_params.get_int("Columns", 1)
            raw_bytes = _apply_predictor(
                raw_bytes, predictor, colors, bits_per_component, columns
            )

        decoded.write(raw_bytes)
        result_params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=result_params, bytes_written=len(raw_bytes))

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        # Encoder always emits an EarlyChange=1 stream (the PDF default);
        # decoder honors the parameter for streams produced elsewhere.
        early_change = True
        writer = _BitWriter(encoded)
        code_table: list[bytes | None] = _initial_code_table()
        # Lookup map for fast longest-match: pattern bytes -> code index.
        lookup: dict[bytes, int] = {bytes((i,)): i for i in range(256)}

        chunk = 9
        writer.write_bits(CLEAR_TABLE, chunk)

        input_pattern: bytes | None = None
        found_code = -1

        while True:
            byte = raw.read(1)
            if not byte:
                break
            b = byte[0]
            if input_pattern is None:
                input_pattern = bytes((b,))
                found_code = b
                continue
            new_pattern = input_pattern + bytes((b,))
            new_code = lookup.get(new_pattern, -1)
            if new_code == -1:
                # Emit code for the longest known prefix and create a new
                # entry for the (prev + b) pattern.
                chunk = _calculate_chunk(len(code_table) - 1, early_change)
                writer.write_bits(found_code, chunk)
                code_table.append(new_pattern)
                lookup[new_pattern] = len(code_table) - 1

                if len(code_table) == MAX_TABLE_SIZE:
                    # Table full — emit CLEAR and start over.
                    chunk = _calculate_chunk(len(code_table) - 1, early_change)
                    writer.write_bits(CLEAR_TABLE, chunk)
                    code_table = _initial_code_table()
                    lookup = {bytes((i,)): i for i in range(256)}

                input_pattern = bytes((b,))
                found_code = b
            else:
                input_pattern = new_pattern
                found_code = new_code

        if found_code != -1:
            chunk = _calculate_chunk(len(code_table) - 1, early_change)
            writer.write_bits(found_code, chunk)

        # PDFBOX-1977: the decoder will grow the table by one entry
        # immediately after reading the final data code, so the EOD
        # marker must be written at the *post-growth* chunk width.
        chunk = _calculate_chunk(len(code_table), early_change)
        writer.write_bits(EOD, chunk)
        writer.flush()

    @staticmethod
    def _do_lzw_decode(
        encoded: BinaryIO, decoded: BinaryIO, early_change: bool
    ) -> None:
        reader = _BitReader(encoded)
        code_table: list[bytes | None] = _initial_code_table()
        chunk = 9
        prev: bytes | None = None

        try:
            while True:
                next_command = reader.read_bits(chunk)
                if next_command == EOD:
                    break
                if next_command == CLEAR_TABLE:
                    chunk = 9
                    code_table = _initial_code_table()
                    prev = None
                    continue

                if next_command < len(code_table):
                    entry = code_table[next_command]
                    if entry is None:
                        # Hit the placeholder for CLEAR/EOD as data —
                        # only legal as the literal CLEAR/EOD sentinels
                        # which we already handled above.
                        raise OSError(
                            f"invalid LZW code references reserved entry: {next_command}"
                        )
                    curr = entry
                    decoded.write(curr)
                    if prev is not None:
                        new_entry = prev + curr[:1]
                        code_table.append(new_entry)
                elif next_command == len(code_table) and prev is not None:
                    # KwKwK case: code points to the entry that's about
                    # to be created. The output is prev + first(prev).
                    curr = prev + prev[:1]
                    decoded.write(curr)
                    code_table.append(curr)
                else:
                    raise OSError(
                        f"invalid LZW code: {next_command} (table size {len(code_table)})"
                    )

                prev = curr
                chunk = _calculate_chunk(len(code_table), early_change)
        except EOFError as exc:
            # Premature EOF without an EOD code — treat as a truncated
            # stream. PDFBox logs a warning and stops; we surface the
            # situation as an OSError so callers can decide.
            raise OSError("premature EOF in LZW stream, EOD code missing") from exc


# Register at import time so ``FilterFactory.get("LZWDecode")`` works as
# soon as ``pypdfbox.filter`` is imported.
FilterFactory.register("LZWDecode", LZWDecode())
