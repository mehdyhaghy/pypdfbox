from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

from .cmap import CMap, _to_int
from .codespace_range import CodespaceRange

_RESOURCES_DIR = Path(__file__).parent / "resources"

_MARK_END_OF_DICTIONARY = ">>"
_MARK_END_OF_ARRAY = "]"

type CMapSource = RandomAccessRead | BinaryIO | bytes | bytearray | memoryview


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

    def parse(self, source: CMapSource) -> CMap:
        """Parse a CMap from a ``RandomAccessRead`` (PDFBox parity) or
        any bytes-like / file-like source. Returns the resulting
        ``CMap``."""
        ras = self._coerce(source)
        result = CMap()
        previous_token: object = None
        token = self.parse_next_token(ras)
        while token is not None:
            if isinstance(token, str) and token.startswith("%"):
                token = self.parse_next_token(ras)
                continue
            if isinstance(token, _Operator):
                op = token.op
                if op == "endcmap":
                    break
                if op == "usecmap" and isinstance(previous_token, _LiteralName):
                    self.parse_usecmap(previous_token, result)
                elif isinstance(previous_token, (int, float)):
                    if op == "begincodespacerange":
                        self.parse_begincodespacerange(int(previous_token), ras, result)
                    elif op == "beginbfchar":
                        self.parse_beginbfchar(int(previous_token), ras, result)
                    elif op == "beginbfrange":
                        self.parse_beginbfrange(int(previous_token), ras, result)
                    elif op == "begincidchar":
                        self.parse_begincidchar(int(previous_token), ras, result)
                    elif op == "begincidrange" and isinstance(previous_token, int):
                        self.parse_begincidrange(int(previous_token), ras, result)
                    elif op == "beginnotdefchar":
                        self._parse_beginnotdefchar(int(previous_token), ras, result)
                    elif op == "beginnotdefrange":
                        self._parse_beginnotdefrange(int(previous_token), ras, result)
            elif isinstance(token, _LiteralName):
                self.parse_literal_name(token, ras, result)
            previous_token = token
            token = self.parse_next_token(ras)
        return result

    @classmethod
    def parse_predefined(cls, name: str) -> CMap:
        """Load a predefined CMap by name.

        Resolution order mirrors upstream ``CMapParser.parsePredefined``:

        1. Programmatic ``Identity-H`` / ``Identity-V`` builders — these
           are full 0..0xFFFF identity mappings that don't depend on a
           bundled resource file.
        2. File-backed lookup against the bundled resources directory
           ``pypdfbox/fontbox/cmap/resources/``. A curated subset of the
           upstream Adobe predefined CMaps is bundled (the four
           ``*-UCS2`` Unicode-mapping CMaps, ``Identity-H`` /
           ``Identity-V``, and the most commonly referenced CJK
           encoding CMaps — ``UniCNS-UTF16-H/V``, ``UniGB-UTF16-H/V``,
           ``UniJIS-UTF16-H/V``, ``UniKS-UTF16-H/V``, plus the legacy
           ``GB-EUC-H/V``, ``B5pc-H/V``, ``90ms-RKSJ-H/V``,
           ``KSC-EUC-H/V``); any other name raises :class:`OSError`
           matching the upstream "Could not find referenced cmap stream"
           message.
        """
        identity = _build_identity_cmap(name)
        if identity is not None:
            return identity
        # Strict mode is deactivated for predefined CMaps (matches upstream).
        parser = cls(strict_mode=False)
        with parser.get_external_c_map(name) as ras:
            return parser.parse(ras)

    def parse_unicode_cmap(
        self, cmap_bytes: bytes | bytearray | memoryview
    ) -> CMap:
        """Parse a /ToUnicode CMap stream (PDF 32000-1 §9.10.3).

        Convenience wrapper around :meth:`parse` matching the upstream
        ``parseUnicodeCMap(byte[])`` helper used by ``PDFont`` to
        materialise embedded ToUnicode mappings.
        """
        if cmap_bytes is None:
            raise OSError("ToUnicode CMap data is missing")
        return self.parse(bytes(cmap_bytes))

    @classmethod
    def get_cmap_for_name(cls, name: str) -> CMap | None:
        """Load and cache a predefined CMap by name.

        Mirrors the upstream ``CMapManager.getCMap`` accessor (exposed
        via ``CMapParser`` for parity with downstream callers): returns
        the cached instance on subsequent calls, or ``None`` when the
        requested CMap is not available in this build.
        """
        cached = _PREDEFINED_CACHE.get(name)
        if cached is not None:
            return cached
        try:
            cmap = cls.parse_predefined(name)
        except OSError:
            return None
        _PREDEFINED_CACHE[name] = cmap
        return cmap

    @staticmethod
    def add_codespace_range(
        cmap: CMap, low: bytes | bytearray, high: bytes | bytearray
    ) -> None:
        """Public helper that registers a codespace range on ``cmap``.

        Mirrors the upstream ``addCodespaceRange`` hook so callers that
        synthesise a ``CMap`` (e.g. tests, font builders) do not have to
        construct a ``CodespaceRange`` by hand.
        """
        cmap.add_codespace_range(CodespaceRange(bytes(low), bytes(high)))

    def parse_chunk(
        self,
        source: CMapSource,
        cmap: CMap | None = None,
    ) -> CMap:
        """Parse an additional CMap fragment and merge it into ``cmap``.

        Parity hook for upstream's internal chunked-parse entry point.
        When ``cmap`` is ``None`` a fresh ``CMap`` is returned; otherwise
        any mappings discovered in ``source`` are folded into the
        supplied instance via :meth:`CMap.use_cmap` and the same
        instance is returned.
        """
        parsed = self.parse(source)
        if cmap is None:
            return parsed
        cmap.use_cmap(parsed)
        return cmap

    # ---------- usecmap / literal name handling ----------

    def parse_usecmap(self, use_cmap_name: _LiteralName, result: CMap) -> None:
        """Resolve a ``usecmap`` directive: load the referenced CMap and
        fold its state into ``result``. Mirrors upstream
        ``CMapParser#parseUsecmap`` (private in Java; promoted here as a
        protected hook so subclasses can override CMap resolution)."""
        # Recursive predefined-CMap load. Bundled set covers the H/V pairs the
        # V variants reference (Uni*-UTF16-V → Uni*-UTF16-H, GB-EUC-V → GB-EUC-H,
        # etc.). Names outside the bundled set raise OSError here, matching
        # upstream's behaviour when the referenced cmap stream is not found.
        # Fast-path the programmatic Identity-H/V builder so we don't have to
        # round-trip through a synthetic byte stream just to satisfy `usecmap`.
        identity = _build_identity_cmap(use_cmap_name.name)
        if identity is not None:
            result.use_cmap(identity)
            return
        with self.get_external_c_map(use_cmap_name.name) as ras:
            use_cmap = self.parse(ras)
        result.use_cmap(use_cmap)

    def get_external_c_map(self, name: str) -> RandomAccessRead:
        """Open a ``RandomAccessRead`` over the bundled CMap resource ``name``.

        Mirrors upstream ``CMapParser#getExternalCMap`` — used by
        ``parse_predefined`` and the ``usecmap`` directive to resolve
        bundled Adobe CMap files. Raises :class:`OSError` (upstream
        throws ``IOException``) when the resource is not bundled.
        """
        resource = _RESOURCES_DIR / name
        if not resource.is_file():
            raise OSError(
                f"Error: Could not find referenced cmap stream {name}"
            )
        return RandomAccessReadBuffer(resource.read_bytes())

    def parse_literal_name(
        self, literal: _LiteralName, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Dispatch a top-level ``/Name`` literal to the matching CMap
        setter (``WMode``, ``CMapName``, ``Registry``, ``Ordering``,
        ``Supplement``, ``CIDSystemInfo``, ...). Mirrors upstream
        ``CMapParser#parseLiteralName``."""
        name = literal.name
        if name == "WMode":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, int) and not isinstance(nxt, bool):
                result.set_wmode(nxt)
        elif name == "CMapName":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _LiteralName):
                result.set_name(nxt.name)
        elif name == "CMapVersion":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, (int, float)):
                result.set_version(str(nxt))
            elif isinstance(nxt, str):
                result.set_version(nxt)
        elif name == "CMapType":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, int) and not isinstance(nxt, bool):
                result.set_type(nxt)
        elif name == "Registry":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, str):
                result.set_registry(nxt)
        elif name == "Ordering":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, str):
                result.set_ordering(nxt)
        elif name == "Supplement":
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, int) and not isinstance(nxt, bool):
                result.set_supplement(nxt)
        elif name == "CIDSystemInfo":
            # Some CMaps express the CIDSystemInfo as a single dict
            # ``/CIDSystemInfo << /Registry (...) /Ordering (...) /Supplement N >> def``
            # rather than three top-level literals. Extract the inner
            # values when we see the dict form so downstream callers
            # observe identical CMap state either way.
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, dict):
                registry = nxt.get("Registry")
                if isinstance(registry, str):
                    result.set_registry(registry)
                ordering = nxt.get("Ordering")
                if isinstance(ordering, str):
                    result.set_ordering(ordering)
                supplement = nxt.get("Supplement")
                if isinstance(supplement, int) and not isinstance(supplement, bool):
                    result.set_supplement(supplement)

    # ---------- range / char body parsers ----------

    @staticmethod
    def check_expected_operator(
        operator: _Operator, expected: str, range_name: str
    ) -> None:
        """Raise ``OSError`` if ``operator.op`` differs from ``expected``.

        Mirrors upstream ``CMapParser#checkExpectedOperator`` — provides
        a uniform error message for the various ``end<rangetype>``
        sentinels the body parsers expect."""
        if operator.op != expected:
            raise OSError(
                f"Error : ~{range_name} contains an unexpected operator : {operator.op}"
            )

    def parse_begincodespacerange(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse ``count`` codespace-range entries and register each on
        ``result``. Mirrors upstream ``parseBegincodespacerange``."""
        for _ in range(count):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endcodespacerange", "codespacerange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start range missing")
            start_range = bytes(nxt)
            end_range = self.parse_byte_array(ras)
            try:
                result.add_codespace_range(CodespaceRange(start_range, end_range))
            except ValueError as exc:
                raise OSError(str(exc)) from exc

    def parse_beginbfchar(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse ``count`` ``beginbfchar`` entries (one-to-one Unicode
        mappings). Mirrors upstream ``parseBeginbfchar``."""
        for _ in range(count):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endbfchar", "bfchar")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("input code missing")
            input_code = bytes(nxt)
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, (bytes, bytearray)):
                value = self.create_string_from_bytes(bytes(nxt))
                result.add_base_font_character(input_code, value)
            elif isinstance(nxt, _LiteralName):
                result.add_base_font_character(input_code, nxt.name)
            else:
                raise OSError(
                    "Error parsing CMap beginbfchar, expected"
                    f"{{COSString or COSName}} and not {nxt!r}"
                )

    def parse_begincidrange(
        self, number_of_lines: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse ``number_of_lines`` ``begincidrange`` entries (CID
        mappings whose dst CID increments across the range). Mirrors
        upstream ``parseBegincidrange``."""
        for _ in range(number_of_lines):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endcidrange", "cidrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start code missing")
            start_code = bytes(nxt)
            end_code = self.parse_byte_array(ras)
            mapped_code = self.parse_integer(ras)
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

    def parse_begincidchar(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse ``count`` ``begincidchar`` entries (single CID
        mappings). Mirrors upstream ``parseBegincidchar``."""
        for _ in range(count):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endcidchar", "cidchar")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("input code missing")
            input_code = bytes(nxt)
            mapped_cid = self.parse_integer(ras)
            result.add_cid_mapping(input_code, mapped_cid)

    def _parse_beginnotdefchar(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse a ``beginnotdefchar`` block (pypdfbox extension).

        Each entry is ``<inputCode> <substituteCID>`` and registers a
        substitute CID for an undefined character code. Upstream PDFBox
        4.0 currently does not handle this directive at all — we add it
        here so ``CMap.to_cid`` returns the .notdef CID for unmapped
        codes that fall in a notdef range. See ``CHANGES.md`` for the
        divergence note.
        """
        for _ in range(count):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endnotdefchar", "notdefchar")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("input code missing")
            input_code = bytes(nxt)
            mapped_cid = self.parse_integer(ras)
            result.add_cid_mapping(input_code, mapped_cid)

    def _parse_beginnotdefrange(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse a ``beginnotdefrange`` block (pypdfbox extension).

        Each entry is ``<startCode> <endCode> <substituteCID>`` and
        assigns the *same* substitute CID to every input code in the
        range (as opposed to ``begincidrange`` which increments). We
        therefore expand the range into individual ``add_cid_mapping``
        calls rather than reusing ``add_cid_range``.
        """
        for _ in range(count):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endnotdefrange", "notdefrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start code missing")
            start_code = bytes(nxt)
            end_code = self.parse_byte_array(ras)
            mapped_cid = self.parse_integer(ras)
            if len(start_code) != len(end_code):
                raise OSError(
                    "Error : ~notdefrange values must not have different byte lengths"
                )
            start_int = _to_int(start_code)
            end_int = _to_int(end_code)
            if end_int < start_int:
                # Corrupt range — skip silently (matches PDFBOX-4550 spirit).
                continue
            length = len(start_code)
            for code_int in range(start_int, end_int + 1):
                code_bytes = bytearray(length)
                v = code_int
                for i in range(length - 1, -1, -1):
                    code_bytes[i] = v & 0xFF
                    v >>= 8
                result.add_cid_mapping(bytes(code_bytes), mapped_cid)

    def parse_beginbfrange(
        self, count: int, ras: RandomAccessRead, result: CMap
    ) -> None:
        """Parse ``count`` ``beginbfrange`` entries (Unicode range or
        array form). Mirrors upstream ``parseBeginbfrange`` including
        the PDFBOX-4550 / PDFBOX-3807 / PDFBOX-3450 / PDFBOX-4720 /
        PDFBOX-4661 / PDFBOX-5090 quirks called out in the upstream
        comments."""
        for _ in range(count):
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endbfrange", "bfrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("start code missing")
            start_code = bytearray(nxt)
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, _Operator):
                self.check_expected_operator(nxt, "endbfrange", "bfrange")
                break
            if not isinstance(nxt, (bytes, bytearray)):
                raise OSError("end code missing")
            end_code = bytes(nxt)
            start = _to_int(start_code)
            end = _to_int(end_code)
            if end < start:
                # PDFBOX-4550: likely corrupt stream — bail out of this range list.
                break
            nxt = self.parse_next_token(ras)
            if isinstance(nxt, list):
                # Array-form bfrange: [<u1> <u2> ...] one entry per code.
                # Upstream guard is `array.size() >= end - start` (not +1) — match
                # it verbatim so off-by-one tolerant CMaps parse identically.
                array: list[bytes] = [bytes(x) for x in nxt if isinstance(x, (bytes, bytearray))]
                if array and len(array) >= end - start:
                    self.add_mapping_frombfrange(result, start_code, array)
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
                            self.add_mapping_frombfrange(
                                result, bytearray(start_code), 256, bytearray(token_bytes)
                            )
                    else:
                        self.add_mapping_frombfrange(
                            result, start_code, end - start + 1, token_bytes
                        )
            # else: PDFBOX-3807 — ignore null-typed mapping value

    def add_mapping_frombfrange(
        self,
        cmap: CMap,
        start_code: bytearray,
        values_or_list: int | list[bytes] | list[bytearray],
        token_bytes: bytearray | None = None,
    ) -> None:
        """Register the bfrange mapping rows discovered by
        :meth:`parse_beginbfrange`.

        Mirrors the two upstream Java overloads of
        ``addMappingFrombfrange``:

        * ``addMappingFrombfrange(cmap, startCode, List<byte[]>)`` — the
          array form with one explicit dst per src. Pass ``token_bytes``
          as ``None`` and ``values_or_list`` as the list of dst byte
          sequences (this is the only call form when no count is
          supplied).
        * ``addMappingFrombfrange(cmap, startCode, int values, byte[]
          tokenBytes)`` — the count form with a single dst that
          increments alongside ``startCode``. Pass ``values_or_list`` as
          the integer count and ``token_bytes`` as the dst buffer.
        """
        if token_bytes is None:
            # List-form overload.
            if not isinstance(values_or_list, list):
                raise TypeError(
                    "add_mapping_frombfrange list form requires a list of dst bytes"
                )
            for entry in values_or_list:
                value = self.create_string_from_bytes(bytes(entry))
                cmap.add_base_font_character(bytes(start_code), value)
                self.increment(start_code, len(start_code) - 1, False)
            return
        # Count-form overload.
        if not isinstance(values_or_list, int):
            raise TypeError(
                "add_mapping_frombfrange count form requires an int count"
            )
        for _ in range(values_or_list):
            value = self.create_string_from_bytes(bytes(token_bytes))
            cmap.add_base_font_character(bytes(start_code), value)
            if not self.increment(token_bytes, len(token_bytes) - 1, self._strict_mode):
                # overflow detected -> stop adding further mappings
                break
            self.increment(start_code, len(start_code) - 1, False)

    # ---------- tokenizer ----------

    def parse_next_token(self, ras: RandomAccessRead) -> object:
        """Read one PostScript token from ``ras`` and return its native
        Python representation (``int`` / ``float`` / ``bytes`` /
        ``str`` / ``list`` / ``dict`` / :class:`_LiteralName` /
        :class:`_Operator` / ``None`` at EOF). Mirrors upstream
        ``parseNextToken``."""
        next_byte = ras.read()
        while True:
            # Skip PDF whitespace and comments at token boundaries. The
            # whitespace set is intentionally broader than upstream (which
            # only skips 0x09 / 0x20 / 0x0D / 0x0A) so we tolerate NUL /
            # FF padding seen in a few wild ToUnicode streams.
            while _is_whitespace(next_byte):
                next_byte = ras.read()
            if next_byte != 0x25:  # '%'
                break
            self.read_line(ras, next_byte)
            next_byte = ras.read()
        if next_byte == 0x28:  # '('
            return self.read_string(ras)
        if next_byte == 0x3E:  # '>'
            if ras.read() == 0x3E:
                return _MARK_END_OF_DICTIONARY
            raise OSError("Error: expected the end of a dictionary.")
        if next_byte == 0x5D:  # ']'
            return _MARK_END_OF_ARRAY
        if next_byte == 0x5B:  # '['
            return self.read_array(ras)
        if next_byte == 0x3C:  # '<'
            return self.read_dictionary(ras)
        if next_byte == 0x2F:  # '/'
            return self.read_literal_name(ras)
        if next_byte == -1:
            return None
        if 0x30 <= next_byte <= 0x39:  # digit
            return self.read_number(ras, next_byte)
        return self.read_operator(ras, next_byte)

    def parse_integer(self, ras: RandomAccessRead) -> int:
        """Read the next token and require it to be an integer.
        Mirrors upstream ``parseInteger``."""
        nxt = self.parse_next_token(ras)
        if nxt is None:
            raise OSError("expected integer value is missing")
        if isinstance(nxt, int) and not isinstance(nxt, bool):
            return nxt
        raise OSError("invalid type for next token")

    def parse_byte_array(self, ras: RandomAccessRead) -> bytes:
        """Read the next token and require it to be a byte array.
        Mirrors upstream ``parseByteArray``."""
        nxt = self.parse_next_token(ras)
        if nxt is None:
            raise OSError("expected byte[] value is missing")
        if isinstance(nxt, (bytes, bytearray)):
            return bytes(nxt)
        raise OSError("invalid type for next token")

    def read_array(self, ras: RandomAccessRead) -> list[object]:
        """Consume tokens until ``]`` and return them as a list.
        Mirrors upstream ``readArray``."""
        out: list[object] = []
        nxt = self.parse_next_token(ras)
        while nxt is not None and nxt != _MARK_END_OF_ARRAY:
            out.append(nxt)
            nxt = self.parse_next_token(ras)
        return out

    @staticmethod
    def read_string(ras: RandomAccessRead) -> str:
        """Read a PostScript ``( ... )`` string. Mirrors upstream
        ``readString``."""
        # PostScript-flavored string: bytes up to ')'. Upstream does *not*
        # decode escapes here — every byte becomes a char via (char) cast.
        out = bytearray()
        b = ras.read()
        while b != -1 and b != 0x29:  # ')'
            out.append(b)
            b = ras.read()
        # Match Java's `(char) byte` widening — latin-1 is the byte-identity codec.
        return out.decode("latin-1")

    @classmethod
    def read_line(cls, ras: RandomAccessRead, first_byte: int) -> str:
        """Read a comment / header line up to (and not including) the
        next CR/LF. Mirrors upstream ``readLine``."""
        # Comment / header line; read through EOL.
        out = bytearray([first_byte])
        cls.read_until_end_of_line(ras, out)
        return out.decode("latin-1")

    @staticmethod
    def read_until_end_of_line(ras: RandomAccessRead, buf: bytearray) -> None:
        """Read bytes from ``ras`` into ``buf`` up to (but not including)
        the next CR / LF / EOF. Mirrors upstream
        ``CMapParser#readUntilEndOfLine`` — separated from :meth:`read_line`
        so callers that already have a buffer (header-line collector,
        comment skipper) can share the EOL scan.
        """
        b = ras.read()
        while b != -1 and b != 0x0D and b != 0x0A:
            buf.append(b)
            b = ras.read()

    @staticmethod
    def read_literal_name(ras: RandomAccessRead) -> _LiteralName:
        """Read a ``/name`` token. Mirrors upstream
        ``readLiteralName``."""
        out = bytearray()
        b = ras.read()
        while not _is_whitespace_or_eof(b) and not _is_delimiter(b):
            out.append(b)
            b = ras.read()
        if _is_delimiter(b):
            ras.rewind(1)
        return _LiteralName(out.decode("latin-1"))

    @staticmethod
    def read_operator(ras: RandomAccessRead, first_byte: int) -> _Operator:
        """Read a PostScript operator name. Mirrors upstream
        ``readOperator`` — newline separator may be missing in malformed
        CMap files (PDFBOX-2035)."""
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
    def read_number(ras: RandomAccessRead, first_byte: int) -> int | float:
        """Read an integer or float literal. Mirrors upstream
        ``readNumber``."""
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

    def read_dictionary(self, ras: RandomAccessRead) -> object:
        """Read either a dictionary (``<< ... >>``) or a hex string
        (``< ... >``). Mirrors upstream ``readDictionary``."""
        the_next = ras.read()
        if the_next == 0x3C:  # '<'
            # Dictionary ``<< ... >>``.
            result: dict[str, object] = {}
            key = self.parse_next_token(ras)
            while isinstance(key, _LiteralName) and key.name != _MARK_END_OF_DICTIONARY:
                value = self.parse_next_token(ras)
                result[key.name] = value
                key = self.parse_next_token(ras)
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

    # ---------- shared static helpers (parity with Java statics) ----------

    @staticmethod
    def is_whitespace_or_eof(a_byte: int) -> bool:
        """Return ``True`` for ``-1`` (EOF), ``0x20`` (space), ``0x0D``
        (CR) or ``0x0A`` (LF). Mirrors upstream
        ``CMapParser#isWhitespaceOrEOF``."""
        return a_byte in (-1, 0x20, 0x0D, 0x0A)

    @staticmethod
    def is_delimiter(a_byte: int) -> bool:
        """Return ``True`` for the standard PDF delimiter characters
        ``( ) < > [ ] { } / %``. Mirrors upstream
        ``CMapParser#isDelimiter``."""
        return a_byte in (
            0x28,  # (
            0x29,  # )
            0x3C,  # <
            0x3E,  # >
            0x5B,  # [
            0x5D,  # ]
            0x7B,  # {
            0x7D,  # }
            0x2F,  # /
            0x25,  # %
        )

    @staticmethod
    def increment(data: bytearray, position: int, use_strict_mode: bool) -> bool:
        """In-place big-endian increment of ``data`` at ``position`` with
        carry. Returns ``False`` when overflow was detected and the
        increment was suppressed (PDFBOX-4661 / PDFBOX-5090 strict mode);
        otherwise ``True``. Mirrors upstream ``CMapParser#increment``."""
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

    @staticmethod
    def create_string_from_bytes(data: bytes) -> str:
        """Map a byte sequence to its CMap string value.

        Mirrors upstream ``CMapParser#createStringFromBytes``: a sequence
        of ``length <= 2`` routes through ``CMapStrings.getMapping`` —
        1 byte decodes through latin-1 (one char per byte), 2 bytes (and
        the *empty* ``<>`` token, whose ``CMap.toInt`` is ``0``) decode as
        UTF-16BE. Longer values decode as UTF-16BE directly. Malformed
        UTF-16BE input is decoded with replacement so corrupt ToUnicode
        CMaps do not abort parsing.

        The empty-token (``len == 0``) case is the lenient edge a
        ``beginbfchar <01> <>`` entry exercises: upstream's
        ``getMapping(new byte[0])`` indexes ``twoByteMappings.get(0)`` and
        so yields ``"\\u0000"`` rather than the empty string a naive
        UTF-16BE decode of zero bytes would produce.
        """
        if len(data) == 1:
            return data.decode("latin-1")
        if len(data) == 0:
            # Upstream getMapping([]) -> twoByteMappings.get(0) == "\x00".
            return "\x00"
        return data.decode("utf-16-be", errors="replace")

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


# ---------- module-level helpers (kept for back-compat with existing imports) ----------


def _is_whitespace_or_eof(b: int) -> bool:
    return b == -1 or _is_whitespace(b)


def _is_whitespace(b: int) -> bool:
    return b in (0x00, 0x09, 0x0A, 0x0C, 0x0D, 0x20)


def _is_delimiter(b: int) -> bool:
    return b in (0x28, 0x29, 0x3C, 0x3E, 0x5B, 0x5D, 0x7B, 0x7D, 0x2F, 0x25)


def _increment(data: bytearray, position: int, use_strict_mode: bool) -> bool:
    """Module-level alias for :meth:`CMapParser.increment` retained so
    existing callers (``tests/fontbox/cmap/test_cmap_tail_wave795.py``)
    keep working without reaching across the class boundary."""
    return CMapParser.increment(data, position, use_strict_mode)


def _create_string_from_bytes(data: bytes) -> str:
    """Module-level alias for :meth:`CMapParser.create_string_from_bytes`."""
    return CMapParser.create_string_from_bytes(data)


_PREDEFINED_CACHE: dict[str, CMap] = {}


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
    # CIDRange entry rather than 65536 dict entries.
    cmap.add_cid_range(b"\x00\x00", b"\xff\xff", 0)
    return cmap
