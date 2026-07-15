from __future__ import annotations

from io import BytesIO
from typing import BinaryIO, Final

from pypdfbox.cos import COSDictionary

from ._decode_params import resolve_decode_params
from ._predictor import predict
from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory
from .predictor import Predictor

# Reserved LZW codes per ISO 32000-1 §7.4.4.
CLEAR_TABLE: Final[int] = 256
EOD: Final[int] = 257

# Code-table cap: codes are 9..12 bits, so 4096 entries max.
MAX_TABLE_SIZE: Final[int] = 4096


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


# ---------- decode-params resolution ---------------------------------


def _get_decode_params(parameters: COSDictionary | None, index: int) -> COSDictionary:
    """Resolve effective ``/DecodeParms`` for the filter at ``index``.

    PDF allows ``/DecodeParms`` to be either a single dictionary (when
    there is one filter) or an array parallel to ``/Filter``. Both long
    ``/DecodeParms`` and abbreviated ``/DP`` keys are accepted; missing
    array entries return an empty dict. Delegates to the shared resolver
    that mirrors upstream ``Filter#getDecodeParams`` — consulting
    ``/Filter`` so a single dict is never applied to a multi-filter chain.
    """
    return resolve_decode_params(parameters, index)


class LZWDecode(Filter):
    """
    PDF ``/LZWDecode`` filter per ISO 32000-1 §7.4.4.

    Implements variable-width (9..12 bit) LZW with the PDF-specific
    ``EarlyChange`` flag (default 1) and optional PNG/TIFF predictor
    post-processing via ``/Predictor`` in ``/DecodeParms``.

    Mirrors `org.apache.pdfbox.filter.LZWFilter`.
    """

    #: Reserved code that resets the dictionary to its initial 258-entry
    #: state. Mirrors upstream's ``public static final long CLEAR_TABLE = 256``
    #: so direct ports translating ``LZWFilter.CLEAR_TABLE`` resolve here
    #: without falling back to the module-level constant.
    CLEAR_TABLE: Final[int] = CLEAR_TABLE

    #: End-of-data marker per ISO 32000-1 §7.4.4. Mirrors upstream's
    #: ``public static final long EOD = 257``.
    EOD: Final[int] = EOD

    #: Code-table cap (12-bit codes → 4096 entries). Upstream keeps this
    #: as a private constant (``MAX_TABLE_SIZE``) but exposing it on the
    #: class makes the size assertion testable from outside the module.
    MAX_TABLE_SIZE: Final[int] = MAX_TABLE_SIZE

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
            # Route through ``PredictorOutputStream`` (``Predictor.wrapPredictor``)
            # exactly as upstream's ``LZWFilter.decode`` does, rather than the
            # standalone one-shot ``unpredict`` which diverged on malformed
            # geometry (unknown /Predictor passthrough, partial-row handling).
            buf = BytesIO()
            predictor_stream = Predictor.wrap_predictor(buf, decode_params)
            predictor_stream.write(raw_bytes)
            flush_pred = getattr(predictor_stream, "flush", None)
            if callable(flush_pred):
                flush_pred()
            raw_bytes = buf.getvalue()

        decoded.write(raw_bytes)
        flush = getattr(decoded, "flush", None)
        if callable(flush):
            flush()
        result_params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=result_params, bytes_written=len(raw_bytes))

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        # Pull all input up-front so we can run a predictor pre-pass when
        # /Predictor > 1 is requested via the decode-params dict.
        data = raw.read()
        decode_params = _get_decode_params(parameters, 0)
        predictor = decode_params.get_int("Predictor", 1)
        if predictor > 1:
            colors = min(decode_params.get_int("Colors", 1), 32)
            bits_per_component = decode_params.get_int("BitsPerComponent", 8)
            columns = decode_params.get_int("Columns", 1)
            data = predict(data, predictor, columns, colors, bits_per_component)
        raw_buffer = BytesIO(data)

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
            byte = raw_buffer.read(1)
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
        flush = getattr(encoded, "flush", None)
        if callable(flush):
            flush()

    # ------------------------------------------------------------------
    # Upstream parity helpers.
    #
    # Upstream's ``LZWFilter`` keeps ``calculateChunk``, ``findPatternCode``
    # and ``createCodeTable`` as ``private static`` methods. They're not
    # part of the Java public API but porters translating PDFBox code
    # often need to call them from a sibling class (or from a test).
    # Exposing snake-cased equivalents as public static methods on the
    # filter class avoids forcing porters to reach into the underscore-
    # prefixed module-level helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_chunk(tab_size: int, early_change: bool) -> int:
        """Return code-width (9..12) for the next code, given table size.

        Mirrors ``org.apache.pdfbox.filter.LZWFilter#calculateChunk``.
        """
        return _calculate_chunk(tab_size, early_change)

    @staticmethod
    def find_pattern_code(
        code_table: list[bytes | None], pattern: bytes
    ) -> int:
        """Return the index of ``pattern`` in ``code_table``, or -1.

        For single-byte patterns the answer is the byte value itself
        (the first 256 entries are byte literals). Reserved codes 256
        (``CLEAR_TABLE``) and 257 (``EOD``) are skipped because their
        slots are placeholders, not data patterns.

        Mirrors ``org.apache.pdfbox.filter.LZWFilter#findPatternCode``.
        """
        if len(pattern) == 1:
            return pattern[0]
        # Skip 256 + 2 reserved entries; they never match longer patterns.
        for i in range(258, len(code_table)):
            if code_table[i] == pattern:
                return i
        return -1

    @staticmethod
    def create_code_table() -> list[bytes | None]:
        """Build a fresh code table seeded with the 256 single-byte
        literals plus placeholders for ``CLEAR_TABLE`` (256) and
        ``EOD`` (257).

        Mirrors ``org.apache.pdfbox.filter.LZWFilter#createCodeTable``.
        """
        return _initial_code_table()

    @staticmethod
    def _do_lzw_decode(
        encoded: BinaryIO, decoded: BinaryIO, early_change: bool
    ) -> None:
        # Slurp the whole encoded stream once and drive an inline MSB-first bit
        # reader off a local cursor. This avoids a ``read(1)`` syscall-shaped
        # method call per input byte and a ``write`` call per decoded code:
        # output accumulates in a local ``bytearray`` and is written once at
        # the end. Behaviour is bit-for-bit identical to the ``_BitReader`` /
        # per-code ``decoded.write`` version — EarlyChange handling, 9→12-bit
        # width transitions, ClearTable(256)/EOD(257), KwKwK, and the lenient
        # premature-EOF / corrupt-code exit are all preserved exactly.
        src = encoded.read()
        src_len = len(src)
        pos = 0
        buffer = 0
        bits_in_buffer = 0

        code_table: list[bytes | None] = _initial_code_table()
        chunk = 9
        prev: bytes | None = None
        out = bytearray()
        # EarlyChange offset, inlined from ``_calculate_chunk`` (bit-identical):
        # width grows one entry sooner when EarlyChange is on (PDF default).
        ec_add = 1 if early_change else 0

        try:
            while True:
                # Inline ``_BitReader.read_bits(chunk)``: refill the bit buffer
                # from the local byte cursor (no per-byte method call), then
                # slice ``chunk`` bits off the high end.
                while bits_in_buffer < chunk:
                    if pos >= src_len:
                        raise EOFError("unexpected EOF in LZW bit stream")
                    buffer = (buffer << 8) | src[pos]
                    pos += 1
                    bits_in_buffer += 8
                shift = bits_in_buffer - chunk
                next_command = (buffer >> shift) & ((1 << chunk) - 1)
                buffer &= (1 << shift) - 1
                bits_in_buffer = shift

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
                        # Hit the placeholder for CLEAR/EOD as data. Upstream
                        # has no such placeholder (its initial table is 256
                        # entries, with CLEAR/EOD handled by the loop header),
                        # so a code landing here is a corrupt stream. Upstream
                        # treats every corrupt-code path as a premature EOF
                        # (``throw new EOFException`` caught + logged → stop),
                        # so raise ``EOFError`` to take the same lenient exit.
                        raise EOFError(
                            f"invalid LZW code references reserved entry: {next_command}"
                        )
                    curr = entry
                    out += curr
                    if prev is not None:
                        new_entry = prev + curr[:1]
                        code_table.append(new_entry)
                elif next_command == len(code_table) and prev is not None:
                    # KwKwK case: code points to the entry that's about
                    # to be created. The output is prev + first(prev).
                    curr = prev + prev[:1]
                    out += curr
                    code_table.append(curr)
                else:
                    # Corrupt stream: code out of range, or KwKwK with no
                    # previous string. Upstream throws ``EOFException`` here
                    # (LZWFilter.doLZWDecode line 119) which its own
                    # try/catch turns into a lenient "premature EOF" stop —
                    # whatever was decoded so far is kept, no exception
                    # propagates. Mirror that by raising ``EOFError`` so the
                    # surrounding handler stops gracefully instead of bubbling
                    # an ``OSError`` (a parity divergence: PDFBox yields the
                    # partial output, pypdfbox used to abort the whole decode).
                    raise EOFError(
                        f"invalid LZW code: {next_command} (table size {len(code_table)})"
                    )

                prev = curr
                # Inlined ``_calculate_chunk(len(code_table), early_change)``.
                _sz = len(code_table) + ec_add
                if _sz >= 2048:
                    chunk = 12
                elif _sz >= 1024:
                    chunk = 11
                elif _sz >= 512:
                    chunk = 10
                else:
                    chunk = 9
        except EOFError:
            # PDFBox logs a warning and stops when the stream ends before EOD
            # OR when a corrupt code is hit (both are EOFException upstream).
            pass

        decoded.write(bytes(out))


# Register at import time so ``FilterFactory.get("LZWDecode")`` works as
# soon as ``pypdfbox.filter`` is imported.
FilterFactory.register("LZWDecode", LZWDecode())
