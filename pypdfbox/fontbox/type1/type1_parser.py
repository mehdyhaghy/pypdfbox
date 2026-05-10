"""Parser for the two-segment Type 1 PostScript font format.

Mirrors :class:`org.apache.fontbox.type1.Type1Parser` in upstream PDFBox
at the *interface* level — we expose the same ``parse(segment1,
segment2)`` entry point and emit a parsed font dict.

What we extract:

1. Segment 1 (cleartext PostScript header):
   - Top-level keys: ``/FontName``, ``/FontType``, ``/PaintType``,
     ``/FontMatrix``, ``/FontBBox``, ``/Encoding``, ``/UniqueID``,
     ``/StrokeWidth``, ``/FID``.
   - ``/FontInfo`` sub-dict: ``version``, ``Notice``, ``Copyright``,
     ``FullName``, ``FamilyName``, ``Weight``, ``ItalicAngle``,
     ``isFixedPitch``, ``UnderlinePosition``, ``UnderlineThickness``.
2. Segment 2 (eexec-encrypted private + charstrings block):
   - eexec-decrypt via :func:`Type1FontUtil.eexec_decrypt`.
   - Walk the decrypted PostScript to extract:
     - ``/Private`` dict (``BlueValues``, ``OtherBlues``, ``FamilyBlues``,
       ``FamilyOtherBlues``, ``BlueScale``, ``BlueShift``, ``BlueFuzz``,
       ``StdHW``, ``StdVW``, ``StemSnapH``, ``StemSnapV``, ``ForceBold``,
       ``LanguageGroup``, ``lenIV``).
     - ``/Subrs`` array — each entry charstring-decrypted to raw bytes.
     - ``/CharStrings`` dict — ``name -> charstring-decrypted bytes``.

The parser does NOT execute the charstring bytecode (that lives in
:class:`pypdfbox.fontbox.cff.type1_char_string.Type1CharString` and
delegates to fontTools); it only recovers the raw byte payload so the
Type1Font accessors can hand it on.
"""

from __future__ import annotations

import re
import string
from typing import Any

from .type1_font_util import Type1FontUtil

# ---------- token kinds ----------

# We use a tiny enum-style namespace of plain strings so the token
# stream stays printable for debugging and tests can match on it
# without importing an Enum.
TOKEN_NAME = "name"
TOKEN_LITERAL = "literal"  # /FontName
TOKEN_NUMBER = "number"
TOKEN_STRING = "string"
TOKEN_INTEGER = "integer"
TOKEN_REAL = "real"
TOKEN_START_ARRAY = "startarray"
TOKEN_END_ARRAY = "endarray"
TOKEN_START_PROC = "startproc"
TOKEN_END_PROC = "endproc"
TOKEN_START_DICT = "startdict"
TOKEN_END_DICT = "enddict"
TOKEN_CHARSTRING = "charstring"


_NUMBER_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+\.?)(?:[eE][+-]?\d+)?$")
_INT_RE = re.compile(r"^[+-]?\d+$")
# Radix-form integers: ``base#digits`` (e.g. ``16#FF``). PostScript spec.
_RADIX_RE = re.compile(r"^(\d+)#([0-9A-Za-z]+)$")
_HEX_CHARS = frozenset(ord(ch) for ch in string.hexdigits)
_HEX_WHITESPACE = frozenset(b"\n\r \t")


class Type1Lexer:
    """Tokenises the cleartext segment of a PFA / PFB.

    Mirrors upstream ``org.apache.fontbox.type1.Type1Lexer`` in spirit;
    the upstream class is a stateful byte-buffer iterator whose
    ``nextToken()`` returns one ``Token`` at a time. We expose the same
    pull-style protocol via :meth:`next_token`.

    The lexer recognises the binary CHARSTRING token: when the bareword
    ``RD`` or ``-|`` appears immediately after an integer literal, the
    integer is consumed as the byte length of an encrypted charstring
    payload. The next byte after RD is a single delimiter (whitespace),
    then exactly ``length`` raw bytes follow as the charstring body. The
    payload is returned as a ``(TOKEN_CHARSTRING, bytes)`` token rather
    than a name.
    """

    def __init__(self, data: bytes | bytearray | str) -> None:
        if isinstance(data, str):
            # When given str input we still need a byte view for
            # CHARSTRING extraction (binary RD payloads are 0..255).
            # Latin-1 round-trips losslessly between str and bytes.
            self._buf = data
            self._raw = data.encode("latin-1")
        else:
            # Cleartext PostScript is ASCII / Latin-1 by spec; decode
            # with latin-1 so any odd byte round-trips losslessly.
            self._raw = bytes(data)
            self._buf = self._raw.decode("latin-1")
        self._pos = 0
        # Sliding window of last-emitted token — needed to recognise
        # ``<INT> RD`` (and ``<INT> -|``) sequences and capture the
        # following binary charstring payload.
        self._prev_token: tuple[str, Any] | None = None

    # ---------- public ----------

    def peek_token(self) -> tuple[str, Any] | None:
        """Return the next token without consuming it. ``None`` at EOF."""
        saved_pos = self._pos
        saved_prev = self._prev_token
        tok = self.next_token()
        self._pos = saved_pos
        self._prev_token = saved_prev
        return tok

    def next_token(self) -> tuple[str, Any] | None:
        """Consume and return one ``(kind, value)`` token. ``None`` at EOF."""
        tok = self._next_token_inner()
        self._prev_token = tok
        return tok

    def _next_token_inner(self) -> tuple[str, Any] | None:
        self._skip_whitespace_and_comments()
        if self._pos >= len(self._buf):
            return None
        ch = self._buf[self._pos]

        # Delimiters that need their own tokens.
        if ch == "[":
            self._pos += 1
            return (TOKEN_START_ARRAY, "[")
        if ch == "]":
            self._pos += 1
            return (TOKEN_END_ARRAY, "]")
        if ch == "{":
            self._pos += 1
            return (TOKEN_START_PROC, "{")
        if ch == "}":
            self._pos += 1
            return (TOKEN_END_PROC, "}")
        if ch == "<":
            # Either ``<<`` (dict mark) or hex string.
            if self._peek(1) == "<":
                self._pos += 2
                return (TOKEN_START_DICT, "<<")
            return self._read_hex_string()
        if ch == ">":
            if self._peek(1) == ">":
                self._pos += 2
                return (TOKEN_END_DICT, ">>")
            # Unbalanced ">": treat as literal name fragment for safety.
            self._pos += 1
            return (TOKEN_NAME, ">")
        if ch == "(":
            return self._read_paren_string()
        if ch == "/":
            return self._read_literal_name()

        # Default: bareword (name or number).
        return self._read_bareword()

    def remaining(self) -> str:
        """Slice of the buffer that has not yet been tokenised."""
        return self._buf[self._pos :]

    # ---------- internals ----------

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        if idx >= len(self._buf):
            return ""
        return self._buf[idx]

    def _skip_whitespace_and_comments(self) -> None:
        # PostScript whitespace: space, tab, CR, LF, FF, NUL.
        # Comment: ``%`` to end-of-line.
        while self._pos < len(self._buf):
            ch = self._buf[self._pos]
            if ch in " \t\r\n\f\x00":
                self._pos += 1
                continue
            if ch == "%":
                while self._pos < len(self._buf) and self._buf[self._pos] not in "\r\n":
                    self._pos += 1
                continue
            return

    def _read_literal_name(self) -> tuple[str, str]:
        # Already at "/" — consume it.
        self._pos += 1
        start = self._pos
        while self._pos < len(self._buf):
            ch = self._buf[self._pos]
            if ch in " \t\r\n\f\x00[]{}/<>()%":
                break
            self._pos += 1
        return (TOKEN_LITERAL, self._buf[start : self._pos])

    def _read_paren_string(self) -> tuple[str, str]:
        # Skip opening "(". PostScript ``( ... )`` strings allow nested
        # balanced parens and ``\`` escapes — handle the common forms.
        assert self._buf[self._pos] == "("  # noqa: S101
        self._pos += 1
        depth = 1
        out: list[str] = []
        while self._pos < len(self._buf) and depth > 0:
            ch = self._buf[self._pos]
            self._pos += 1
            if ch == "\\":
                # Escape: \\, \(, \), \n, \r, \t, \b, \f, \\ddd (octal).
                if self._pos >= len(self._buf):
                    break
                esc = self._buf[self._pos]
                self._pos += 1
                if esc in "\r\n":
                    if (
                        esc == "\r"
                        and self._pos < len(self._buf)
                        and self._buf[self._pos] == "\n"
                    ):
                        self._pos += 1
                    continue
                mapping = {
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    "b": "\b",
                    "f": "\f",
                    "\\": "\\",
                    "(": "(",
                    ")": ")",
                }
                if esc in mapping:
                    out.append(mapping[esc])
                elif esc.isdigit():
                    # Up to 3 octal digits.
                    digits = esc
                    while (
                        len(digits) < 3
                        and self._pos < len(self._buf)
                        and self._buf[self._pos].isdigit()
                    ):
                        digits += self._buf[self._pos]
                        self._pos += 1
                    out.append(chr(int(digits, 8) & 0xFF))
                else:
                    out.append(esc)
                continue
            if ch == "(":
                depth += 1
                out.append(ch)
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
                out.append(ch)
            else:
                out.append(ch)
        return (TOKEN_STRING, "".join(out))

    def _read_hex_string(self) -> tuple[str, bytes]:
        # Skip opening "<".
        assert self._buf[self._pos] == "<"  # noqa: S101
        self._pos += 1
        chars: list[str] = []
        while self._pos < len(self._buf) and self._buf[self._pos] != ">":
            ch = self._buf[self._pos]
            self._pos += 1
            if not ch.isspace():
                chars.append(ch)
        if self._pos < len(self._buf):
            self._pos += 1  # consume closing ">"
        # PostScript hex strings allow odd length — pad with 0.
        text = "".join(chars)
        if len(text) % 2:
            text += "0"
        return (TOKEN_STRING, bytes.fromhex(text))

    def _read_bareword(self) -> tuple[str, Any]:
        start = self._pos
        while self._pos < len(self._buf):
            ch = self._buf[self._pos]
            if ch in " \t\r\n\f\x00[]{}/<>()%":
                break
            self._pos += 1
        word = self._buf[start : self._pos]
        # Classify the word.
        if _INT_RE.match(word):
            return (TOKEN_INTEGER, int(word))
        if _NUMBER_RE.match(word):
            return (TOKEN_REAL, float(word))
        m = _RADIX_RE.match(word)
        if m:
            base = int(m.group(1))
            if 2 <= base <= 36:
                try:
                    return (TOKEN_INTEGER, int(m.group(2), base))
                except ValueError:
                    pass
        # CHARSTRING capture: ``<INT> RD <space> <N raw bytes>`` or the
        # equivalent ``<INT> -| <space> <N raw bytes>``. Upstream
        # ``Type1Lexer.readCharString(length)`` does the same.
        if word in ("RD", "-|") and self._prev_token is not None:
            kind, value = self._prev_token
            if kind == TOKEN_INTEGER:
                length = int(value)
                # Consume one delimiter byte (typically space).
                if self._pos < len(self._buf):
                    self._pos += 1
                if length < 0:
                    return (TOKEN_CHARSTRING, b"")
                # Read ``length`` raw bytes from the underlying byte
                # buffer (bypass the latin-1 view so high bytes survive).
                end = self._pos + length
                if end > len(self._raw):
                    end = len(self._raw)
                payload = self._raw[self._pos:end]
                self._pos = end
                return (TOKEN_CHARSTRING, bytes(payload))
        return (TOKEN_NAME, word)


# ---------- top-level keys we know how to harvest ----------

# Top-level font-dict keys we surface as-is. Anything not in this set
# is still tokenised but does not get hoisted into the parsed dict —
# we keep the surface narrow because ``Type1Font``'s accessors are the
# only consumers and they consult exactly these keys.
_TOP_LEVEL_KEYS = frozenset(
    {
        "FontName",
        "FontType",
        "PaintType",
        "FontMatrix",
        "FontBBox",
        "Encoding",
        "UniqueID",
        "StrokeWidth",
        "WMode",
        "FID",
    }
)

# Keys we expect inside the FontInfo sub-dict.
_FONT_INFO_KEYS = frozenset(
    {
        "version",
        "Notice",
        "Copyright",
        "FullName",
        "FamilyName",
        "Weight",
        "ItalicAngle",
        "isFixedPitch",
        "UnderlinePosition",
        "UnderlineThickness",
        "FontName",
    }
)


class Type1Parser:
    """Parse the cleartext + binary segments of a Type 1 PostScript font.

    Pythonic mirror of upstream ``Type1Parser``. The upstream class
    walks tokens through a state machine; we use the same token stream
    but extract only the keys ``Type1Font`` actually exposes (we do NOT
    re-implement the PostScript-subset interpreter). The binary segment
    is decrypted via :class:`Type1FontUtil` and stored verbatim on the
    parser as :attr:`decrypted_binary` so downstream callers (or tests)
    can pass it to a real interpreter.
    """

    # Upstream constants for encryption (parity with Type1Parser.java
    # ``EEXEC_KEY`` / ``CHARSTRING_KEY``).
    EEXEC_KEY = 55665
    CHARSTRING_KEY = 4330

    def __init__(self) -> None:
        # Public outputs — populated by parse().
        self.font_dict: dict[str, Any] = {}
        self.decrypted_binary: bytes = b""
        # Mirror of upstream's ``private Type1Lexer lexer`` field — the
        # parity helper methods below (``read``, ``read_maybe``,
        # ``read_value``, ...) operate against this. ``parse()`` keeps it
        # populated so callers can also drive the parser one token at a
        # time after handing in segments.
        self._lexer: Type1Lexer | None = None

    # ---------- entry point ----------

    def parse(
        self,
        segment1: bytes | bytearray,
        segment2: bytes | bytearray,
        len_iv: int = 4,
    ) -> dict[str, Any]:
        """Parse a (cleartext, eexec-binary) PFB segment pair.

        ``len_iv`` is forwarded to :func:`Type1FontUtil.eexec_decrypt`'s
        warm-up trim; the eexec spec fixes it at 4 (the function will
        drop the first 4 bytes regardless), but passing it through keeps
        the signature consistent with the charstring path.

        Returns the parsed top-level font dict and stores it on
        :attr:`font_dict` for inspection. The decrypted private-dict
        bytes are kept on :attr:`decrypted_binary`. After eexec decrypt,
        the parser walks the recovered PostScript to populate the
        ``Private`` sub-dict (Blue values, lenIV, ForceBold, etc.), the
        ``Subrs`` array (charstring-decrypted bytes), and the
        ``CharStrings`` map (glyph name → charstring-decrypted bytes).
        """
        # _len_iv is currently informational; eexec uses a fixed 4-byte
        # warm-up. We accept the parameter to mirror upstream's signature.
        del len_iv
        self._parse_ascii(bytes(segment1))
        self.decrypted_binary = Type1FontUtil.eexec_decrypt(
            self._normalise_eexec_segment(bytes(segment2))
        )
        # Best-effort second-stage parse over the decrypted block. Any
        # parse failure leaves Private / Subrs / CharStrings empty and is
        # logged at debug — matches our overall "tolerant defaults"
        # posture (upstream raises IOException; we diverge for ergonomics
        # and let the accessor-side defaults handle the missing data).
        try:
            self._parse_binary(self.decrypted_binary)
        except Exception as exc:  # noqa: BLE001
            import logging  # noqa: PLC0415

            logging.getLogger(__name__).debug(
                "Type1Parser: binary segment parse failed: %s", exc
            )
        return self.font_dict

    @staticmethod
    def _normalise_eexec_segment(segment: bytes) -> bytes:
        """Return binary eexec bytes, decoding ASCII-hex PFA data when used.

        Mirrors PDFBox's ``Type1Parser.isBinary`` heuristic: if all of the
        first four ciphertext bytes are hex digits or whitespace, treat the
        whole segment as ASCII hex and ignore non-hex separators.
        """
        if len(segment) < 4:
            return segment
        for by in segment[:4]:
            if by not in _HEX_WHITESPACE and by not in _HEX_CHARS:
                return segment

        nibbles = [by for by in segment if by in _HEX_CHARS]
        # PDFBox truncates an unmatched trailing nibble when normalising
        # ASCII-hex eexec data.
        if len(nibbles) % 2:
            nibbles.pop()
        return bytes.fromhex(bytes(nibbles).decode("ascii"))

    # ---------- ascii section ----------

    def _parse_ascii(self, segment1: bytes) -> None:
        lex = Type1Lexer(segment1)
        self._lexer = lex
        # Sliding window of last consumed tokens — enough to recognise
        # "/key value def" without building a full AST.
        pending_key: str | None = None
        # Non-None when we are inside FontInfo's dict body.
        in_font_info = False
        font_info: dict[str, Any] = {}

        while True:
            tok = lex.next_token()
            if tok is None:
                break
            kind, value = tok

            # ----- always-on container transitions (must run regardless
            # of pending_key state, otherwise we never see ``end``).
            if (
                in_font_info
                and pending_key is None
                and kind == TOKEN_NAME
                and value == "end"
            ):
                in_font_info = False
                self.font_dict["FontInfo"] = font_info
                continue

            if kind == TOKEN_LITERAL:
                # A literal name is either the START of a definition
                # (``/FontName ...``) or the VALUE of an existing
                # definition (``/FontName /TestFont def``). Decide based
                # on whether we already have a pending top-level key
                # whose definition is still open. If we do, treat this
                # literal as the value for that key.
                if pending_key is not None and (
                    pending_key in _TOP_LEVEL_KEYS or in_font_info
                ):
                    if in_font_info and pending_key in _FONT_INFO_KEYS:
                        font_info[pending_key] = value
                    elif pending_key in _TOP_LEVEL_KEYS:
                        self.font_dict[pending_key] = value
                    pending_key = None
                    continue
                # Otherwise this is a fresh key definition.
                pending_key = value
                continue

            if pending_key is None:
                # Free-floating token outside a definition (likely an
                # operator like ``currentdict`` or version preamble) —
                # ignore.
                continue

            # Recognise the FontInfo container open: the upstream
            # idiom is ``/FontInfo <N> dict dup begin``. Once we see
            # ``begin`` after ``/FontInfo`` we switch into FontInfo
            # collection mode; ``end`` switches us back out.
            if pending_key == "FontInfo" and kind == TOKEN_NAME and value == "begin":
                in_font_info = True
                pending_key = None
                continue

            if in_font_info:
                if kind == TOKEN_NAME and value == "end":
                    in_font_info = False
                    self.font_dict["FontInfo"] = font_info
                    pending_key = None
                    continue
                # Inside FontInfo we still see ``/Key value def`` triples.
                # The lexer fed us the literal name as ``pending_key``;
                # the next non-def token is the value. Booleans
                # (``true`` / ``false``) come through as TOKEN_NAME, so
                # accept those for boolean-typed keys; ignore other
                # bareword operators (``readonly``, ``def``, ``noaccess``).
                if pending_key in _FONT_INFO_KEYS:
                    if kind != TOKEN_NAME:
                        font_info[pending_key] = self._coerce_value(kind, value, lex)
                        pending_key = None
                        continue
                    if value in ("true", "false"):
                        font_info[pending_key] = (value == "true")
                        pending_key = None
                        continue
                if kind == TOKEN_NAME and value == "def":
                    pending_key = None
                continue

            # Top-level key collection.
            if pending_key in _TOP_LEVEL_KEYS:
                if pending_key == "Encoding" and kind == TOKEN_INTEGER:
                    self.font_dict[pending_key] = self._read_encoding_array(
                        lex,
                        int(value),
                    )
                    pending_key = None
                    continue
                if kind == TOKEN_START_ARRAY:
                    self.font_dict[pending_key] = self._read_array(lex)
                    pending_key = None
                    continue
                if kind == TOKEN_START_PROC:
                    # ``{ ... }`` is a procedure literal in PostScript;
                    # for value-bearing keys like ``/FontBBox`` it is
                    # used interchangeably with ``[ ... ]``. Read it the
                    # same way and stop at the matching ``}``.
                    self.font_dict[pending_key] = self._read_proc(lex)
                    pending_key = None
                    continue
                if kind == TOKEN_NAME and value in ("StandardEncoding", "ISOLatin1Encoding"):
                    # Predefined encoding by name.
                    self.font_dict[pending_key] = value
                    pending_key = None
                    continue
                if kind in (TOKEN_INTEGER, TOKEN_REAL, TOKEN_STRING, TOKEN_LITERAL):
                    self.font_dict[pending_key] = value
                    pending_key = None
                    continue
                if kind == TOKEN_NAME and value == "def":
                    pending_key = None
                    continue
            else:
                # Reset the pending key on the next ``def`` so we don't
                # accidentally pair it with a downstream value.
                if kind == TOKEN_NAME and value == "def":
                    pending_key = None

    def _read_proc(self, lex: Type1Lexer) -> list[Any]:
        out: list[Any] = []
        while True:
            tok = lex.next_token()
            if tok is None:
                break
            kind, value = tok
            if kind == TOKEN_END_PROC:
                break
            if kind == TOKEN_START_PROC:
                out.append(self._read_proc(lex))
                continue
            if kind in (TOKEN_INTEGER, TOKEN_REAL, TOKEN_STRING, TOKEN_LITERAL, TOKEN_NAME):
                out.append(value)
        return out

    def _read_array(self, lex: Type1Lexer) -> list[Any]:
        out: list[Any] = []
        while True:
            tok = lex.next_token()
            if tok is None:
                break
            kind, value = tok
            if kind == TOKEN_END_ARRAY:
                break
            if kind == TOKEN_START_ARRAY:
                out.append(self._read_array(lex))
                continue
            if kind in (TOKEN_INTEGER, TOKEN_REAL, TOKEN_STRING):
                out.append(value)
            elif kind == TOKEN_LITERAL:
                # Stored as the bare name (matches fontTools convention).
                out.append(value)
            elif kind == TOKEN_NAME:
                out.append(value)
        return out

    def _read_encoding_array(self, lex: Type1Lexer, length: int) -> list[str]:
        """Read a PostScript-built Encoding vector.

        Real Type 1 programs commonly spell custom encodings as::

            /Encoding 256 array
              0 1 255 {1 index exch /.notdef put} for
              dup 65 /A put
            readonly def

        The generic top-level parser would otherwise capture only the
        leading integer. Track ``dup <code> /<glyph> put`` assignments
        until the surrounding definition closes.
        """
        encoding = [".notdef"] * max(length, 0)

        while True:
            tok = lex.next_token()
            if tok is None:
                break
            kind, value = tok
            if kind == TOKEN_START_PROC:
                self._read_proc(lex)
                continue
            if kind == TOKEN_NAME and value == "def":
                break
            if kind != TOKEN_NAME or value != "dup":
                continue

            code_tok = lex.next_token()
            name_tok = lex.next_token()
            if (
                code_tok is None
                or name_tok is None
                or code_tok[0] != TOKEN_INTEGER
                or name_tok[0] != TOKEN_LITERAL
            ):
                continue

            code = int(code_tok[1])
            if 0 <= code < len(encoding):
                encoding[code] = str(name_tok[1])

            while True:
                peek = lex.peek_token()
                if peek is None:
                    return encoding
                if peek[0] == TOKEN_NAME and peek[1] in ("put", "readonly", "noaccess"):
                    lex.next_token()
                    if peek[1] == "put":
                        break
                    continue
                break

        return encoding

    # ---------- binary section (eexec-decrypted) ----------

    # Keys we hoist into ``font_dict["Private"]``. Values are typed by
    # the caller-side accessors; the parser stores the decoded shape:
    # numeric arrays as ``list[int|float]``, scalars as int/float/bool.
    _PRIVATE_NUMERIC_ARRAY_KEYS = frozenset(
        {
            "BlueValues",
            "OtherBlues",
            "FamilyBlues",
            "FamilyOtherBlues",
            "StdHW",
            "StdVW",
            "StemSnapH",
            "StemSnapV",
        }
    )
    _PRIVATE_SCALAR_KEYS = frozenset(
        {
            "BlueScale",
            "BlueShift",
            "BlueFuzz",
            "ForceBold",
            "LanguageGroup",
            "lenIV",
            "MinFeature",
            "password",
            "RndStemUp",
            "ExpansionFactor",
            "UniqueID",
        }
    )

    def _parse_binary(self, decrypted: bytes) -> None:
        """Walk the eexec-decrypted PostScript and harvest Private +
        Subrs + CharStrings into ``font_dict``.

        The decrypted block looks like::

            dup /Private 16 dict dup begin
              /Subrs 5 array
                dup 0 23 RD <23 raw bytes> NP
                ...
                def
              /CharStrings 4 dict dup begin
                /A 12 RD <12 raw bytes> ND
                ...
              end
              /BlueValues [-20 0 800 820] def
              /lenIV 4 def
              ...
              end
            end
            ...

        We are tolerant of missing keys / out-of-order layouts because
        real-world fonts deviate (PDFBOX-2134, PDFBOX-5942). On any
        unrecognised structure we simply continue scanning until we hit
        the next literal key.
        """
        if not decrypted:
            return
        lex = Type1Lexer(decrypted)
        self._lexer = lex
        private: dict[str, Any] = {}
        subrs: list[bytes] = []
        charstrings: dict[str, bytes] = {}
        len_iv = 4

        # Locate ``/Private`` to anchor the body. Real fonts wrap the
        # block in ``dup /Private N dict dup begin``; we just skip until
        # we see the literal ``Private``.
        found = False
        while True:
            tok = lex.next_token()
            if tok is None:
                break
            if tok[0] == TOKEN_LITERAL and tok[1] == "Private":
                found = True
                break
        if not found:
            return

        # Now walk the Private dict body until we hit the
        # ``/CharStrings`` literal that marks the second sub-dict.
        # Inside this loop we also pick up ``/Subrs`` (which is itself
        # a procedure-style array of dup-N-RD-payload triples).
        while True:
            tok = lex.next_token()
            if tok is None:
                return
            kind, value = tok
            if kind == TOKEN_LITERAL:
                if value == "Subrs":
                    self._read_subrs(lex, subrs, len_iv)
                    continue
                if value == "CharStrings":
                    self._read_charstrings(lex, charstrings, len_iv)
                    break
                if value == "lenIV":
                    val = self._read_scalar_value(lex)
                    if isinstance(val, int):
                        len_iv = val
                    private["lenIV"] = val
                    continue
                if value in self._PRIVATE_NUMERIC_ARRAY_KEYS:
                    arr = self._read_numeric_array_value(lex)
                    if arr is not None:
                        private[value] = arr
                    continue
                if value in self._PRIVATE_SCALAR_KEYS:
                    val = self._read_scalar_value(lex)
                    if val is not None:
                        private[value] = val
                    continue
                # Unknown literal — drain its value and continue.
                self._drain_value(lex)
                continue
            # Hitting ``end`` at top level closes the Private dict.
            if kind == TOKEN_NAME and value == "end":
                break

        if private:
            self.font_dict["Private"] = private
        if subrs:
            # Store under Private/Subrs to match upstream's
            # `font.subrs` / `Type1Font.getSubrsArray()` shape.
            self.font_dict.setdefault("Private", private)["Subrs"] = subrs
        if charstrings:
            self.font_dict["CharStrings"] = charstrings

    @staticmethod
    def _read_scalar_value(lex: Type1Lexer) -> Any:
        """Read a simple scalar from a ``/Key value def`` triple.

        Drains tokens up to and including the closing ``def`` (or the
        next ``ND`` / ``|-`` postscript synonym). Returns the first
        meaningful value seen — int, float, bool, or string.
        """
        out: Any = None
        depth = 0
        while True:
            tok = lex.next_token()
            if tok is None:
                return out
            kind, value = tok
            if kind == TOKEN_START_ARRAY:
                depth += 1
                continue
            if kind == TOKEN_END_ARRAY:
                if depth > 0:
                    depth -= 1
                continue
            if depth > 0:
                continue
            if kind == TOKEN_NAME and value in ("def", "ND", "|-", "readonly", "noaccess"):
                if value in ("def", "ND", "|-"):
                    return out
                continue
            if kind == TOKEN_INTEGER and out is None:
                out = int(value)
                continue
            if kind == TOKEN_REAL and out is None:
                out = float(value)
                continue
            if kind == TOKEN_NAME and value in ("true", "false") and out is None:
                out = (value == "true")
                continue
            if kind == TOKEN_STRING and out is None:
                out = value
                continue

    @staticmethod
    def _read_numeric_array_value(lex: Type1Lexer) -> list[Any] | None:
        """Read a ``[ n n n ] def`` style numeric array."""
        # Skip until we see the array opener.
        while True:
            tok = lex.next_token()
            if tok is None:
                return None
            kind, value = tok
            if kind in (TOKEN_START_ARRAY, TOKEN_START_PROC):
                break
            if kind == TOKEN_NAME and value == "def":
                return None
        out: list[Any] = []
        while True:
            tok = lex.next_token()
            if tok is None:
                break
            kind, value = tok
            if kind in (TOKEN_END_ARRAY, TOKEN_END_PROC):
                break
            if kind in (TOKEN_INTEGER, TOKEN_REAL):
                out.append(value)
        # Drain to def.
        while True:
            tok = lex.next_token()
            if tok is None:
                break
            if tok[0] == TOKEN_NAME and tok[1] in ("def", "ND", "|-"):
                break
        return out

    @staticmethod
    def _drain_value(lex: Type1Lexer) -> None:
        """Skip tokens until the next ``def`` / ``ND`` / ``|-``.

        Used to ignore Private-dict keys we don't model (``OtherSubrs``,
        ``MinFeature``, ``UniqueID`` overrides at this scope, etc.).
        """
        depth = 0
        while True:
            tok = lex.next_token()
            if tok is None:
                return
            kind, value = tok
            if kind in (TOKEN_START_ARRAY, TOKEN_START_PROC):
                depth += 1
                continue
            if kind in (TOKEN_END_ARRAY, TOKEN_END_PROC):
                if depth > 0:
                    depth -= 1
                continue
            if depth == 0 and kind == TOKEN_NAME and value in ("def", "ND", "|-"):
                return

    def _read_subrs(self, lex: Type1Lexer, out: list[bytes], len_iv: int) -> None:
        """Walk the ``/Subrs N array dup K M RD <bytes> NP …`` block.

        Each entry is a charstring; we decrypt it with the supplied
        ``len_iv`` (from the Private dict's ``lenIV`` key, default 4)
        and store the plaintext at index ``K``. Indexes need not be
        in-order — upstream pre-sizes the list with ``None`` and slots
        each entry into its declared position.
        """
        # Read array length.
        length_tok = lex.next_token()
        if length_tok is None or length_tok[0] != TOKEN_INTEGER:
            return
        length = int(length_tok[1])
        # Pre-fill so out-of-order indexes are positional.
        out.extend(b"" for _ in range(length))
        # Optional ``array`` operator.
        peek = lex.peek_token()
        if peek and peek[0] == TOKEN_NAME and peek[1] == "array":
            lex.next_token()

        while True:
            peek = lex.peek_token()
            if peek is None:
                return
            if peek[0] != TOKEN_NAME or peek[1] != "dup":
                # No more entries — drain trailing operators (def, etc.)
                # until we exit. Upstream just falls through.
                return
            lex.next_token()  # consume ``dup``
            idx_tok = lex.next_token()
            if idx_tok is None or idx_tok[0] != TOKEN_INTEGER:
                return
            length_tok = lex.next_token()
            if length_tok is None or length_tok[0] != TOKEN_INTEGER:
                return
            cs_tok = lex.next_token()
            if cs_tok is None or cs_tok[0] != TOKEN_CHARSTRING:
                return
            idx = int(idx_tok[1])
            try:
                plain = Type1FontUtil.charstring_decrypt(cs_tok[1], len_iv)
            except Exception:  # noqa: BLE001
                plain = b""
            if 0 <= idx < len(out):
                out[idx] = plain
            # Drain trailing put / NP / | / def per upstream readPut.
            while True:
                t = lex.peek_token()
                if t is None:
                    return
                if t[0] == TOKEN_NAME and t[1] == "dup":
                    break
                lex.next_token()
                if t[0] == TOKEN_NAME and t[1] in ("NP", "|", "put"):
                    break

    def _read_charstrings(
        self, lex: Type1Lexer, out: dict[str, bytes], len_iv: int
    ) -> None:
        """Walk the ``/CharStrings N dict dup begin /name M RD <bytes> ND …``
        block. Each ``name -> charstring`` entry is decrypted with
        ``len_iv`` and stored under the literal glyph name."""
        # Length / dict / dup / begin preamble — tolerant of variants.
        length_tok = lex.next_token()
        if length_tok is None:
            return
        # Drain through ``dict`` / ``dup`` / ``begin``.
        for _ in range(4):
            peek = lex.peek_token()
            if peek is None:
                return
            if peek[0] == TOKEN_NAME and peek[1] in ("dict", "dup", "begin"):
                lex.next_token()
            else:
                break

        while True:
            peek = lex.peek_token()
            if peek is None:
                return
            if peek[0] == TOKEN_NAME and peek[1] == "end":
                lex.next_token()
                return
            if peek[0] != TOKEN_LITERAL:
                lex.next_token()
                continue
            name_tok = lex.next_token()
            if name_tok is None:
                return
            length_tok = lex.next_token()
            if length_tok is None or length_tok[0] != TOKEN_INTEGER:
                continue
            cs_tok = lex.next_token()
            if cs_tok is None or cs_tok[0] != TOKEN_CHARSTRING:
                continue
            try:
                plain = Type1FontUtil.charstring_decrypt(cs_tok[1], len_iv)
            except Exception:  # noqa: BLE001
                plain = b""
            out[str(name_tok[1])] = plain
            # Drain trailing readonly / noaccess / def / ND.
            while True:
                t = lex.peek_token()
                if t is None:
                    return
                if t[0] != TOKEN_NAME:
                    break
                lex.next_token()
                if t[1] in ("def", "ND", "|-"):
                    break

    @staticmethod
    def _coerce_value(kind: str, value: Any, lex: Type1Lexer) -> Any:
        del lex  # accepted for symmetry with array reader
        if kind in (TOKEN_INTEGER, TOKEN_REAL, TOKEN_STRING, TOKEN_LITERAL):
            return value
        if kind == TOKEN_NAME:
            # PostScript booleans appear as bareword names.
            if value == "true":
                return True
            if value == "false":
                return False
            return value
        return value

    # ---------- upstream-parity helpers ----------
    #
    # The block below mirrors ``Type1Parser.java`` method-for-method.
    # Our top-level ``parse()`` takes the streaming/extractor path
    # because real-world Type 1 fonts deviate from the spec in many
    # documented ways (PDFBOX-2134, PDFBOX-5942, ...). These helpers
    # round out the upstream API surface so callers can drive the
    # parser at a finer granularity (handy for fuzz-style fixtures and
    # for direct port-tests). They all operate on ``self._lexer`` —
    # the same field upstream uses.

    @staticmethod
    def is_binary(data: bytes | bytearray) -> bool:
        """Return ``True`` when ``data`` looks like raw eexec ciphertext.

        Mirrors ``Type1Parser.isBinary`` (Type1Parser.java line 958). Per
        Adobe Type 1 7.2: at least one of the first 4 ciphertext bytes
        must not be ASCII hex / whitespace.
        """
        if len(data) < 4:
            return True
        for by in data[:4]:
            if by in _HEX_WHITESPACE:
                continue
            if by in _HEX_CHARS:
                continue
            return True
        return False

    @staticmethod
    def hex_to_binary(data: bytes | bytearray) -> bytes:
        """Decode an ASCII-hex eexec segment to raw bytes.

        Mirrors ``Type1Parser.hexToBinary`` (Type1Parser.java line 978).
        Whitespace and other non-hex bytes are discarded; an unmatched
        trailing nibble is dropped (upstream truncates the same way via
        the integer division in ``new byte[len / 2]``).
        """
        nibbles = bytes(by for by in data if by in _HEX_CHARS)
        if len(nibbles) % 2:
            nibbles = nibbles[:-1]
        return bytes.fromhex(nibbles.decode("ascii"))

    @staticmethod
    def decrypt(cipher: bytes | bytearray, r: int, n: int) -> bytes:
        """Type 1 eexec / charstring decryption.

        Mirrors ``Type1Parser.decrypt`` (Type1Parser.java line 927). The
        ``r`` seed selects between eexec (``EEXEC_KEY``) and charstring
        (``CHARSTRING_KEY``) flows; ``n`` is the number of warm-up bytes
        to drop (``lenIV``). ``n == -1`` means "no encryption" (an
        undocumented tolerance found in PDFBox).
        """
        if n == -1:
            return bytes(cipher)
        if len(cipher) == 0 or n > len(cipher):
            return b""
        c1 = 52845
        c2 = 22719
        plain = bytearray(len(cipher) - n)
        for i, by in enumerate(cipher):
            cipher_byte = by & 0xFF
            plain_byte = cipher_byte ^ (r >> 8)
            if i >= n:
                plain[i - n] = plain_byte & 0xFF
            r = ((cipher_byte + r) * c1 + c2) & 0xFFFF
        return bytes(plain)

    def read(self, kind: str, name: str | None = None) -> tuple[str, Any]:
        """Read the next token, raising if it does not match.

        Mirrors the two ``read`` overloads (Type1Parser.java lines 881
        and 895). ``kind`` selects the expected token kind; pass
        ``name`` to additionally require a specific text value (used by
        upstream when matching named operators like ``begin`` / ``def``).
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        token = self._lexer.next_token()
        if token is None or token[0] != kind:
            raise OSError(f"Found {token!r} but expected {kind}")
        if name is not None and token[1] != name:
            raise OSError(f"Found {token!r} but expected {name}")
        return token

    def read_maybe(self, kind: str, name: str) -> tuple[str, Any] | None:
        """Consume the next token only if it matches ``kind`` + ``name``.

        Mirrors ``Type1Parser.readMaybe`` (Type1Parser.java line 910).
        Returns the consumed token, or ``None`` if the next token does
        not match (in which case the lexer position is unchanged).
        """
        if self._lexer is None:
            return None
        peek = self._lexer.peek_token()
        if peek is None or peek[0] != kind or peek[1] != name:
            return None
        return self._lexer.next_token()

    def read_value(self) -> list[tuple[str, Any]]:
        """Read a simple value (number, name, literal, array, proc, ...).

        Mirrors ``Type1Parser.readValue`` (Type1Parser.java line 385).
        Returns the list of raw tokens that make up the value, with
        nested arrays and procedures preserved verbatim.
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        value: list[tuple[str, Any]] = []
        token = self._lexer.next_token()
        if token is None or self._lexer.peek_token() is None:
            return value
        value.append(token)

        kind = token[0]
        if kind == TOKEN_START_ARRAY:
            open_array = 1
            while True:
                peek = self._lexer.peek_token()
                if peek is None:
                    return value
                if peek[0] == TOKEN_START_ARRAY:
                    open_array += 1
                tok = self._lexer.next_token()
                if tok is None:
                    return value
                value.append(tok)
                if tok[0] == TOKEN_END_ARRAY:
                    open_array -= 1
                    if open_array == 0:
                        break
        elif kind == TOKEN_START_PROC:
            value.extend(self.read_proc())
        elif kind == TOKEN_START_DICT:
            # skip "/GlyphNames2HostCode << >> def"
            self.read(TOKEN_END_DICT)
            return value

        self.read_post_script_wrapper(value)
        return value

    def read_dict_value(self) -> list[tuple[str, Any]]:
        """Read a value followed by ``def`` / ``ND`` / ``|-``.

        Mirrors ``Type1Parser.readDictValue`` (Type1Parser.java line 373).
        """
        value = self.read_value()
        self.read_def()
        return value

    def read_proc(self) -> list[tuple[str, Any]]:
        """Read a balanced ``{ ... }`` procedure.

        Mirrors ``Type1Parser.readProc`` (Type1Parser.java line 472).
        Returns the procedure body tokens including the trailing
        ``executeonly`` bareword if present.
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        value: list[tuple[str, Any]] = []
        open_proc = 1
        while True:
            peek = self._lexer.peek_token()
            if peek is None:
                raise OSError("Malformed procedure: missing token")
            if peek[0] == TOKEN_START_PROC:
                open_proc += 1
            tok = self._lexer.next_token()
            if tok is None:
                raise OSError("Malformed procedure: missing token")
            value.append(tok)
            if tok[0] == TOKEN_END_PROC:
                open_proc -= 1
                if open_proc == 0:
                    break
        executeonly = self.read_maybe(TOKEN_NAME, "executeonly")
        if executeonly is not None:
            value.append(executeonly)
        return value

    def read_proc_void(self) -> None:
        """Read and discard a balanced ``{ ... }`` procedure.

        Mirrors ``Type1Parser.readProcVoid`` (Type1Parser.java line 513).
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        open_proc = 1
        while True:
            peek = self._lexer.peek_token()
            if peek is None:
                raise OSError("Malformed procedure: missing token")
            if peek[0] == TOKEN_START_PROC:
                open_proc += 1
            tok = self._lexer.next_token()
            if tok is None:
                raise OSError("Malformed procedure: missing token")
            if tok[0] == TOKEN_END_PROC:
                open_proc -= 1
                if open_proc == 0:
                    break
        self.read_maybe(TOKEN_NAME, "executeonly")

    def read_post_script_wrapper(self, value: list[tuple[str, Any]]) -> None:
        """Strip the optional ``systemdict / internaldict known`` wrapper.

        Mirrors ``Type1Parser.readPostScriptWrapper`` (Type1Parser.java
        line 437). Used when the cleartext segment wraps a value in a
        runtime guard procedure; the inner value replaces the outer.
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        peek = self._lexer.peek_token()
        if peek is None:
            raise OSError("Missing start token for the system dictionary")
        if peek[1] == "systemdict":
            self.read(TOKEN_NAME, "systemdict")
            self.read(TOKEN_LITERAL, "internaldict")
            self.read(TOKEN_NAME, "known")

            self.read(TOKEN_START_PROC)
            self.read_proc_void()

            self.read(TOKEN_START_PROC)
            self.read_proc_void()

            self.read(TOKEN_NAME, "ifelse")

            # replace value
            self.read(TOKEN_START_PROC)
            self.read(TOKEN_NAME, "pop")
            value.clear()
            value.extend(self.read_value())
            self.read(TOKEN_END_PROC)

            self.read(TOKEN_NAME, "if")

    def read_def(self) -> None:
        """Consume an optional ``readonly``/``noaccess`` then ``def``/``ND``.

        Mirrors ``Type1Parser.readDef`` (Type1Parser.java line 824).
        """
        self.read_maybe(TOKEN_NAME, "readonly")
        self.read_maybe(TOKEN_NAME, "noaccess")
        token = self.read(TOKEN_NAME)
        text = token[1]
        if text in ("ND", "|-"):
            return
        if text == "noaccess":
            token = self.read(TOKEN_NAME)
            text = token[1]
        if text == "def":
            return
        raise OSError(f"Found {token!r} but expected ND")

    def read_put(self) -> None:
        """Consume an optional ``readonly`` then ``put``/``NP``/``|``.

        Mirrors ``Type1Parser.readPut`` (Type1Parser.java line 852).
        """
        self.read_maybe(TOKEN_NAME, "readonly")
        token = self.read(TOKEN_NAME)
        text = token[1]
        if text in ("NP", "|"):
            return
        if text == "noaccess":
            token = self.read(TOKEN_NAME)
            text = token[1]
        if text == "put":
            return
        raise OSError(f"Found {token!r} but expected NP")

    def read_simple_dict(self) -> dict[str, list[tuple[str, Any]]]:
        """Read a ``<N> dict dup begin ... end def`` flat sub-dict.

        Mirrors ``Type1Parser.readSimpleDict`` (Type1Parser.java line 319).
        Values are returned as raw token lists; FontInfo / Metrics are
        the only consumers and they normalise from there.
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        out: dict[str, list[tuple[str, Any]]] = {}
        length = self.read(TOKEN_INTEGER)[1]
        self.read(TOKEN_NAME, "dict")
        self.read_maybe(TOKEN_NAME, "dup")
        if self.read_maybe(TOKEN_NAME, "def") is not None:
            # PDFBOX-5942 empty dict.
            return out
        self.read(TOKEN_NAME, "begin")
        for _ in range(int(length)):
            peek = self._lexer.peek_token()
            if peek is None:
                break
            if peek[0] == TOKEN_NAME and peek[1] != "end":
                self.read(TOKEN_NAME)
            peek = self._lexer.peek_token()
            if peek is None:
                break
            if peek[0] == TOKEN_NAME and peek[1] == "end":
                break
            key_tok = self.read(TOKEN_LITERAL)
            value = self.read_dict_value()
            out[str(key_tok[1])] = value
        self.read(TOKEN_NAME, "end")
        self.read_maybe(TOKEN_NAME, "readonly")
        self.read(TOKEN_NAME, "def")
        return out

    @staticmethod
    def array_to_numbers(value: list[tuple[str, Any]]) -> list[Any]:
        """Extract integer / real values from a tokenised array.

        Mirrors ``Type1Parser.arrayToNumbers`` (Type1Parser.java line 247).
        Strips the leading ``[`` and trailing ``]`` tokens upstream
        leaves in place when handing over a value list.
        """
        numbers: list[Any] = []
        for i in range(1, len(value) - 1):
            tok = value[i]
            kind, val = tok
            if kind == TOKEN_REAL:
                numbers.append(float(val))
            elif kind == TOKEN_INTEGER:
                numbers.append(int(val))
            else:
                raise OSError(
                    f"Expected INTEGER or REAL but got {tok!r} at array position {i}"
                )
        return numbers

    def read_simple_value(self, key: str) -> None:
        """Harvest one ``/Key value def`` triple into ``font_dict``.

        Mirrors ``Type1Parser.readSimpleValue`` (Type1Parser.java line 157).
        Recognised top-level keys are coerced to their canonical type;
        unknowns are silently dropped (matching upstream's ``default``).
        """
        value = self.read_dict_value()
        if not value:
            return
        first = value[0]
        if key == "FontName":
            self.font_dict["FontName"] = first[1]
        elif key == "PaintType":
            self.font_dict["PaintType"] = int(first[1])
        elif key == "FontType":
            self.font_dict["FontType"] = int(first[1])
        elif key == "FontMatrix":
            self.font_dict["FontMatrix"] = self.array_to_numbers(value)
        elif key == "FontBBox":
            self.font_dict["FontBBox"] = self.array_to_numbers(value)
        elif key == "UniqueID":
            self.font_dict["UniqueID"] = int(first[1])
        elif key == "StrokeWidth":
            self.font_dict["StrokeWidth"] = float(first[1])
        elif key == "FID":
            self.font_dict["FID"] = first[1]

    def read_font_info(self, font_info: dict[str, list[tuple[str, Any]]]) -> None:
        """Lift recognised entries from a tokenised FontInfo sub-dict.

        Mirrors ``Type1Parser.readFontInfo`` (Type1Parser.java line 273).
        """
        info: dict[str, Any] = {}
        for key, value in font_info.items():
            if not value:
                continue
            first = value[0]
            kind, val = first
            if key == "version":
                info["version"] = val
            elif key == "Notice":
                info["Notice"] = val
            elif key == "FullName":
                info["FullName"] = val
            elif key == "FamilyName":
                info["FamilyName"] = val
            elif key == "Weight":
                info["Weight"] = val
            elif key == "ItalicAngle":
                info["ItalicAngle"] = float(val) if kind in (TOKEN_REAL, TOKEN_INTEGER) else val
            elif key == "isFixedPitch":
                if kind == TOKEN_NAME:
                    info["isFixedPitch"] = (val == "true")
                else:
                    info["isFixedPitch"] = bool(val)
            elif key == "UnderlinePosition":
                info["UnderlinePosition"] = (
                    float(val) if kind in (TOKEN_REAL, TOKEN_INTEGER) else val
                )
            elif key == "UnderlineThickness":
                info["UnderlineThickness"] = (
                    float(val) if kind in (TOKEN_REAL, TOKEN_INTEGER) else val
                )
        if info:
            existing = self.font_dict.get("FontInfo", {})
            existing.update(info)
            self.font_dict["FontInfo"] = existing

    def read_encoding(self) -> None:
        """Read either ``StandardEncoding def`` or a built-in ``dup`` table.

        Mirrors ``Type1Parser.readEncoding`` (Type1Parser.java line 192).
        Stores ``"StandardEncoding"`` (string) for the predefined case;
        otherwise stores the ``code -> name`` map under the ``Encoding``
        key (note: differs from the streaming parser, which stores a
        positional list — this helper preserves upstream's dict shape).
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        peek = self._lexer.peek_token()
        if peek is not None and peek[0] == TOKEN_NAME:
            name_tok = self._lexer.next_token()
            if name_tok is None:
                raise OSError("Unexpected EOF in encoding")
            name = name_tok[1]
            if name == "StandardEncoding":
                self.font_dict["Encoding"] = "StandardEncoding"
            else:
                raise OSError(f"Unknown encoding: {name}")
            self.read_maybe(TOKEN_NAME, "readonly")
            self.read(TOKEN_NAME, "def")
            return
        self.read(TOKEN_INTEGER)
        self.read_maybe(TOKEN_NAME, "array")

        # Drain operators ahead of dup/readonly/def (PDFBOX-2134).
        while True:
            peek = self._lexer.peek_token()
            if peek is None:
                raise OSError("Incomplete data while reading encoding of type 1 font")
            if peek[0] == TOKEN_NAME and peek[1] in ("dup", "readonly", "def"):
                break
            if self._lexer.next_token() is None:
                raise OSError("Incomplete data while reading encoding of type 1 font")

        code_to_name: dict[int, str] = {}
        while True:
            peek = self._lexer.peek_token()
            if peek is None or peek[0] != TOKEN_NAME or peek[1] != "dup":
                break
            self.read(TOKEN_NAME, "dup")
            code = int(self.read(TOKEN_INTEGER)[1])
            glyph = self.read(TOKEN_LITERAL)[1]
            self.read(TOKEN_NAME, "put")
            code_to_name[code] = str(glyph)
        self.font_dict["Encoding"] = code_to_name
        self.read_maybe(TOKEN_NAME, "readonly")
        self.read(TOKEN_NAME, "def")

    def read_private(self, key: str, value: list[tuple[str, Any]]) -> None:
        """Harvest one ``/Key value`` entry from the Private dict.

        Mirrors ``Type1Parser.readPrivate`` (Type1Parser.java line 660).
        Stores recognised keys under ``font_dict["Private"]``.
        """
        if not value:
            return
        first = value[0]
        kind, val = first
        private = self.font_dict.setdefault("Private", {})
        if key in ("BlueValues", "OtherBlues", "FamilyBlues", "FamilyOtherBlues",
                   "StdHW", "StdVW", "StemSnapH", "StemSnapV"):
            private[key] = self.array_to_numbers(value)
        elif key == "BlueScale":
            private[key] = float(val)
        elif key in ("BlueShift", "BlueFuzz", "LanguageGroup"):
            private[key] = int(val)
        elif key == "ForceBold":
            if kind == TOKEN_NAME:
                private[key] = (val == "true")
            else:
                private[key] = bool(val)

    def read_other_subrs(self) -> None:
        """Drain the ``/OtherSubrs`` array — values are not modelled.

        Mirrors ``Type1Parser.readOtherSubrs`` (Type1Parser.java line 752).
        OtherSubrs are PostScript procedures the spec lets us skip; we
        consume tokens up to the matching ``def`` so the parser cursor
        ends in the right place.
        """
        if self._lexer is None:
            raise OSError("Type1Parser has no active lexer")
        peek = self._lexer.peek_token()
        if peek is None:
            raise OSError("Missing start token of OtherSubrs procedure")
        if peek[0] == TOKEN_START_ARRAY:
            self.read_value()
            self.read_def()
            return
        length = int(self.read(TOKEN_INTEGER)[1])
        self.read(TOKEN_NAME, "array")
        for _ in range(length):
            self.read(TOKEN_NAME, "dup")
            self.read(TOKEN_INTEGER)
            self.read_value()
            self.read_put()
        self.read_def()


__all__ = ["Type1Parser", "Type1Lexer"]
