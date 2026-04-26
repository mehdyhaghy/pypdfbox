from __future__ import annotations

from typing import BinaryIO

from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

from .cmap import CMap, _to_int
from .codespace_range import CodespaceRange

_MARK_END_OF_DICTIONARY = ">>"
_MARK_END_OF_ARRAY = "]"


class _LiteralName:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class _Operator:
    __slots__ = ("op",)

    def __init__(self, op: str) -> None:
        self.op = op


class CMapParser:
    """
    Parses a PostScript CMap (PDF 32000-1 §9.7) into a ``CMap`` instance.

    The parser is intentionally permissive: it tolerates the malformed
    whitespace patterns and bfrange off-by-one bugs described in the
    PDFBOX-* references in the upstream source.
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self._strict_mode = strict_mode

    # ---------- public API ----------

    def parse(self, source: RandomAccessRead | BinaryIO | bytes | bytearray) -> CMap:
        """Parse a CMap from a ``RandomAccessRead`` (PDFBox parity) or
        any bytes-like / file-like source. Returns the resulting
        ``CMap``."""
        ras = self._coerce(source)
        result = CMap()
        previous_token: object = None
        token = self._parse_next_token(ras)
        while token is not None:
            if isinstance(token, _Operator):
                op = token.op
                if op == "endcmap":
                    break
                if op == "usecmap" and isinstance(previous_token, _LiteralName):
                    self._parse_usecmap(previous_token, result)
                elif isinstance(previous_token, (int, float)):
                    if op == "begincodespacerange":
                        self._parse_begincodespacerange(int(previous_token), ras, result)
                    elif op == "beginbfchar":
                        self._parse_beginbfchar(int(previous_token), ras, result)
                    elif op == "beginbfrange":
                        self._parse_beginbfrange(int(previous_token), ras, result)
                    elif op == "begincidchar":
                        self._parse_begincidchar(int(previous_token), ras, result)
                    elif op == "begincidrange" and isinstance(previous_token, int):
                        self._parse_begincidrange(int(previous_token), ras, result)
            elif isinstance(token, _LiteralName):
                self._parse_literal_name(token, ras, result)
            previous_token = token
            token = self._parse_next_token(ras)
        return result

    @classmethod
    def parse_predefined(cls, name: str) -> CMap:
        """Load a predefined CMap by name. Cluster #4 ships only
        ``Identity-H`` and ``Identity-V`` programmatically; other
        predefined CMaps are added in a follow-up cluster."""
        identity = _build_identity_cmap(name)
        if identity is not None:
            return identity
        # Future clusters will add file-backed predefined CMap loading.
        raise OSError(
            f"Error: Could not find referenced cmap stream {name}"
        )

    # ---------- usecmap / literal name handling ----------

    def _parse_usecmap(self, use_cmap_name: _LiteralName, result: CMap) -> None:
        # Recursive predefined-CMap load. Cluster #4 only ships Identity-H/V,
        # so any other usecmap target raises here — extending this is the job
        # of the predefined-CMap follow-up cluster.
        use_cmap = type(self).parse_predefined(use_cmap_name.name)
        result.use_cmap(use_cmap)

    def _parse_literal_name(
        self, literal: _LiteralName, ras: RandomAccessRead, result: CMap
    ) -> None:
        name = literal.name
        if name == "WMode":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, int) and not isinstance(nxt, bool):
                result.set_wmode(nxt)
        elif name == "CMapName":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _LiteralName):
                result.set_name(nxt.name)
        elif name == "CMapVersion":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, (int, float)):
                result.set_version(str(nxt))
            elif isinstance(nxt, str):
                result.set_version(nxt)
        elif name == "CMapType":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, int) and not isinstance(nxt, bool):
                result.set_type(nxt)
        elif name == "Registry":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, str):
                result.set_registry(nxt)
        elif name == "Ordering":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, str):
                result.set_ordering(nxt)
        elif name == "Supplement":
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, int) and not isinstance(nxt, bool):
                result.set_supplement(nxt)

    # ---------- range / char body parsers ----------

    @staticmethod
    def _check_expected_operator(
        operator: _Operator, expected: str, range_name: str
    ) -> None:
        if operator.op != expected:
            raise OSError(
                f"Error : ~{range_name} contains an unexpected operator : {operator.op}"
            )

    def _parse_begincodespacerange(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        for _ in range(count):
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self._check_expected_operator(nxt, "endcodespacerange", "codespacerange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start range missing")
            start_range = bytes(nxt)
            end_range = self._parse_byte_array(ras)
            try:
                result.add_codespace_range(CodespaceRange(start_range, end_range))
            except ValueError as exc:
                raise OSError(str(exc)) from exc

    def _parse_beginbfchar(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        for _ in range(count):
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self._check_expected_operator(nxt, "endbfchar", "bfchar")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("input code missing")
            input_code = bytes(nxt)
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, (bytes, bytearray)):
                value = _create_string_from_bytes(bytes(nxt))
                result.add_base_font_character(input_code, value)
            elif isinstance(nxt, _LiteralName):
                result.add_base_font_character(input_code, nxt.name)
            else:
                raise OSError(
                    f"Error parsing CMap beginbfchar, expected{{COSString or COSName}} and not {nxt!r}"
                )

    def _parse_begincidrange(
        self, number_of_lines: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        for _ in range(number_of_lines):
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self._check_expected_operator(nxt, "endcidrange", "cidrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start code missing")
            start_code = bytes(nxt)
            end_code = self._parse_byte_array(ras)
            mapped_code = self._parse_integer(ras)
            if len(start_code) == len(end_code):
                if start_code == end_code:
                    # Single-value "range" — collapse into a CID mapping.
                    result.add_cid_mapping(start_code, mapped_code)
                else:
                    result.add_cid_range(start_code, end_code, mapped_code)
            else:
                raise OSError(
                    "Error : ~cidrange values must not have different byte lengths"
                )

    def _parse_begincidchar(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        for _ in range(count):
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self._check_expected_operator(nxt, "endcidchar", "cidchar")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("input code missing")
            input_code = bytes(nxt)
            mapped_cid = self._parse_integer(ras)
            result.add_cid_mapping(input_code, mapped_cid)

    def _parse_beginbfrange(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        for _ in range(count):
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self._check_expected_operator(nxt, "endbfrange", "bfrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start code missing")
            start_code = bytearray(nxt)
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self._check_expected_operator(nxt, "endbfrange", "bfrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("end code missing")
            end_code = bytes(nxt)
            start = _to_int(start_code)
            end = _to_int(end_code)
            if end < start:
                # PDFBOX-4550: likely corrupt stream — bail out of this range list.
                break
            nxt = self._parse_next_token(ras)
            if isinstance(nxt, list):
                # Array-form bfrange: [<u1> <u2> ...] one entry per code.
                array: list[bytes] = [bytes(x) for x in nxt if isinstance(x, (bytes, bytearray))]
                if array and len(array) >= end - start:
                    self._add_mapping_from_bfrange_list(result, start_code, array)
            elif isinstance(nxt, (bytes, bytearray)):
                token_bytes = bytearray(nxt)
                if len(token_bytes) > 0:
                    # PDFBOX-4720: the malformed identity bfrange <0000> <FFFF> <0000>
                    # is treated as a 65k-entry identity mapping.
                    if (
                        len(token_bytes) == 2
                        and start == 0
                        and end == 0xFFFF
                        and token_bytes[0] == 0
                        and token_bytes[1] == 0
                    ):
                        for i in range(256):
                            start_code[0] = i
                            start_code[1] = 0
                            token_bytes[0] = i
                            token_bytes[1] = 0
                            self._add_mapping_from_bfrange_count(
                                result, bytearray(start_code), 256, bytearray(token_bytes)
                            )
                    else:
                        self._add_mapping_from_bfrange_count(
                            result, start_code, end - start + 1, token_bytes
                        )
            # else: PDFBOX-3807 — ignore null-typed mapping value

    def _add_mapping_from_bfrange_list(
        self, cmap: CMap, start_code: bytearray, token_list: list[bytes]
    ) -> None:
        for token_bytes in token_list:
            value = _create_string_from_bytes(token_bytes)
            cmap.add_base_font_character(bytes(start_code), value)
            _increment(start_code, len(start_code) - 1, False)

    def _add_mapping_from_bfrange_count(
        self,
        cmap: CMap,
        start_code: bytearray,
        values: int,
        token_bytes: bytearray,
    ) -> None:
        for _ in range(values):
            value = _create_string_from_bytes(bytes(token_bytes))
            cmap.add_base_font_character(bytes(start_code), value)
            if not _increment(token_bytes, len(token_bytes) - 1, self._strict_mode):
                # overflow detected -> stop adding further mappings
                break
            _increment(start_code, len(start_code) - 1, False)

    # ---------- tokenizer ----------

    def _parse_next_token(self, ras: RandomAccessRead) -> object:
        next_byte = ras.read()
        # Skip whitespace (TAB / SPACE / CR / LF, matching upstream's narrow set).
        while next_byte in (0x09, 0x20, 0x0D, 0x0A):
            next_byte = ras.read()
        if next_byte == 0x25:  # '%'
            return self._read_line(ras, next_byte)
        if next_byte == 0x28:  # '('
            return self._read_string(ras)
        if next_byte == 0x3E:  # '>'
            if ras.read() == 0x3E:
                return _MARK_END_OF_DICTIONARY
            raise OSError("Error: expected the end of a dictionary.")
        if next_byte == 0x5D:  # ']'
            return _MARK_END_OF_ARRAY
        if next_byte == 0x5B:  # '['
            return self._read_array(ras)
        if next_byte == 0x3C:  # '<'
            return self._read_dictionary_or_hex(ras)
        if next_byte == 0x2F:  # '/'
            return self._read_literal_name(ras)
        if next_byte == -1:
            return None
        if 0x30 <= next_byte <= 0x39:  # digit
            return self._read_number(ras, next_byte)
        return self._read_operator(ras, next_byte)

    def _parse_integer(self, ras: RandomAccessRead) -> int:
        nxt = self._parse_next_token(ras)
        if nxt is None:
            raise OSError("expected integer value is missing")
        if isinstance(nxt, int) and not isinstance(nxt, bool):
            return nxt
        raise OSError("invalid type for next token")

    def _parse_byte_array(self, ras: RandomAccessRead) -> bytes:
        nxt = self._parse_next_token(ras)
        if nxt is None:
            raise OSError("expected byte[] value is missing")
        if isinstance(nxt, (bytes, bytearray)):
            return bytes(nxt)
        raise OSError("invalid type for next token")

    def _read_array(self, ras: RandomAccessRead) -> list[object]:
        out: list[object] = []
        nxt = self._parse_next_token(ras)
        while nxt is not None and nxt != _MARK_END_OF_ARRAY:
            out.append(nxt)
            nxt = self._parse_next_token(ras)
        return out

    @staticmethod
    def _read_string(ras: RandomAccessRead) -> str:
        # PostScript-flavored string: bytes up to ')'. Upstream does *not*
        # decode escapes here — every byte becomes a char via (char) cast.
        out = bytearray()
        b = ras.read()
        while b != -1 and b != 0x29:  # ')'
            out.append(b)
            b = ras.read()
        # Match Java's `(char) byte` widening — latin-1 is the byte-identity codec.
        return out.decode("latin-1")

    @staticmethod
    def _read_line(ras: RandomAccessRead, first_byte: int) -> str:
        # Comment line; read through EOL.
        out = bytearray([first_byte])
        b = ras.read()
        while b != -1 and b != 0x0D and b != 0x0A:
            out.append(b)
            b = ras.read()
        return out.decode("latin-1")

    @staticmethod
    def _read_literal_name(ras: RandomAccessRead) -> _LiteralName:
        out = bytearray()
        b = ras.read()
        while not _is_whitespace_or_eof(b) and not _is_delimiter(b):
            out.append(b)
            b = ras.read()
        if _is_delimiter(b):
            ras.rewind(1)
        return _LiteralName(out.decode("latin-1"))

    @staticmethod
    def _read_operator(ras: RandomAccessRead, first_byte: int) -> _Operator:
        out = bytearray([first_byte])
        b = ras.read()
        # Newline separator may be missing in malformed CMap files (PDFBOX-2035).
        while (
            not _is_whitespace_or_eof(b)
            and not _is_delimiter(b)
            and not (0x30 <= b <= 0x39)
        ):
            out.append(b)
            b = ras.read()
        if _is_delimiter(b) or (0x30 <= b <= 0x39):
            ras.rewind(1)
        return _Operator(out.decode("latin-1"))

    @staticmethod
    def _read_number(ras: RandomAccessRead, first_byte: int) -> int | float:
        out = bytearray([first_byte])
        b = ras.read()
        while not _is_whitespace_or_eof(b) and (0x30 <= b <= 0x39 or b == 0x2E):
            out.append(b)
            b = ras.read()
        if b != -1:
            ras.rewind(1)
        text = out.decode("latin-1")
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError as exc:
            raise OSError(f"Invalid number '{text}'") from exc

    def _read_dictionary_or_hex(self, ras: RandomAccessRead) -> object:
        the_next = ras.read()
        if the_next == 0x3C:  # '<'
            # Dictionary ``<< ... >>``.
            result: dict[str, object] = {}
            key = self._parse_next_token(ras)
            while isinstance(key, _LiteralName) and key.name != _MARK_END_OF_DICTIONARY:
                value = self._parse_next_token(ras)
                result[key.name] = value
                key = self._parse_next_token(ras)
            return result
        # Hex string ``< ... >`` — accumulate hex digits into bytes.
        buf = bytearray()
        multiplier = 16
        current = 0
        while the_next != -1 and the_next != 0x3E:
            if _is_whitespace_or_eof(the_next):
                the_next = ras.read()
                continue
            if 0x30 <= the_next <= 0x39:
                int_value = the_next - 0x30
            elif 0x41 <= the_next <= 0x46:
                int_value = 10 + the_next - 0x41
            elif 0x61 <= the_next <= 0x66:
                int_value = 10 + the_next - 0x61
            else:
                raise OSError(
                    f"Error: expected hex character and not {chr(the_next)}:{the_next}"
                )
            int_value *= multiplier
            if multiplier == 16:
                current = int_value
                multiplier = 1
            else:
                current += int_value
                buf.append(current & 0xFF)
                multiplier = 16
                current = 0
            the_next = ras.read()
        if multiplier == 1:
            # Odd hex digit at end — keep the high nibble (matches upstream).
            buf.append(current & 0xFF)
        return bytes(buf)

    # ---------- input coercion ----------

    @staticmethod
    def _coerce(source: object) -> RandomAccessRead:
        if isinstance(source, RandomAccessRead):
            return source
        if isinstance(source, (bytes, bytearray, memoryview)):
            return RandomAccessReadBuffer(bytes(source))
        if hasattr(source, "read"):
            return RandomAccessReadBuffer(source)  # type: ignore[arg-type]
        raise TypeError(f"unsupported source type: {type(source).__name__}")


# ---------- helpers ----------


def _is_whitespace_or_eof(b: int) -> bool:
    return b in (-1, 0x20, 0x0D, 0x0A)


def _is_delimiter(b: int) -> bool:
    return b in (0x28, 0x29, 0x3C, 0x3E, 0x5B, 0x5D, 0x7B, 0x7D, 0x2F, 0x25)


def _increment(data: bytearray, position: int, use_strict_mode: bool) -> bool:
    """In-place increment of the big-endian byte sequence ``data`` at
    ``position`` (with carry). Returns False if overflow was detected
    and the increment was suppressed. Mirrors PDFBox's recursive helper
    iteratively for clarity."""
    if position < 0:
        return False
    pos = position
    while True:
        if pos > 0 and (data[pos] & 0xFF) == 0xFF:
            # PDFBOX-4661 / PDFBOX-5090: avoid overflow on the lowest byte
            # in strict mode.
            if use_strict_mode:
                return False
            data[pos] = 0
            pos -= 1
            if pos < 0:
                return True
            continue
        data[pos] = (data[pos] + 1) & 0xFF
        return True


def _create_string_from_bytes(data: bytes) -> str:
    """Map a 1-4 byte sequence to its CMap string value. Per PDFBox:
    ≤2 bytes → 1-byte: latin-1 (one char per byte) / 2-byte: UTF-16BE;
    >2 bytes → UTF-16BE."""
    if len(data) == 1:
        return data.decode("latin-1")
    return data.decode("utf-16-be")


def _build_identity_cmap(name: str) -> CMap | None:
    """Construct ``Identity-H`` / ``Identity-V`` programmatically — both
    are 2-byte identity mappings of the full 0..0xFFFF range."""
    if name not in ("Identity-H", "Identity-V"):
        return None
    cmap = CMap(name)
    cmap.set_name(name)
    cmap.set_registry("Adobe")
    cmap.set_ordering("Identity")
    cmap.set_supplement(0)
    cmap.set_type(1)
    cmap.set_wmode(1 if name == "Identity-V" else 0)
    cmap.add_codespace_range(CodespaceRange(b"\x00\x00", b"\xff\xff"))
    # One CID range covering all 65536 codes — collapses into a single
    # _CIDRange entry rather than 65536 dict entries.
    cmap.add_cid_range(b"\x00\x00", b"\xff\xff", 0)
    return cmap
