"""Lite parser for the cleartext header of a Type 1 PostScript font.

Mirrors the responsibilities of ``org.apache.fontbox.type1.Type1Parser``
in upstream PDFBox at the *interface* level — we expose the same
``parse(segment1, segment2)`` entry point and emit a parsed font dict.
The heavy lifting (full PostScript-subset interpretation of the eexec
section) is delegated to :class:`fontTools.t1Lib.T1Font` because the
spec covers ~50 operators and re-implementing them in Python would
duplicate a battle-tested library; see
``pypdfbox/fontbox/type1/type1_font.py`` for the same pattern.

What we actually do here:

1. Tokenise segment 1 (the cleartext PostScript header) into a stream of
   ``(kind, value)`` tuples — names (``/FontName``), numbers, strings,
   operators (``def``, ``put``), array delimiters (``[`` ``]`` ``{``
   ``}``), and dict-marker tokens (``dict``, ``begin``, ``end``).
2. Walk the token stream, picking out the well-known top-level keys
   (``/FontName``, ``/FontMatrix``, ``/FontBBox``, ``/PaintType``,
   ``/FontType``, ``/Encoding``, ``/UniqueID``) plus the contents of the
   ``/FontInfo`` dict (the textual metadata exposed by ``Type1Font``
   getters).
3. Forward segment 2 (the binary eexec block) to
   :func:`Type1FontUtil.eexec_decrypt` — the recovered plaintext is what
   the upstream ``Type1Parser.parseBinary`` would feed to its private-dict
   parser. We surface it on the parser as ``decrypted_binary`` so
   callers can hand it to a downstream interpreter (or just confirm
   round-trip integrity in tests).

The parser does NOT execute PostScript; it only reads. That covers
everything ``Type1Font``'s metadata accessors need without forking a
PostScript interpreter.
"""

from __future__ import annotations

import re
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


class Type1Lexer:
    """Tokenises the cleartext segment of a PFA / PFB.

    Mirrors upstream ``org.apache.fontbox.type1.Type1Lexer`` in spirit;
    the upstream class is a stateful byte-buffer iterator whose
    ``nextToken()`` returns one ``Token`` at a time. We expose the same
    pull-style protocol via :meth:`next_token`.
    """

    def __init__(self, data: bytes | bytearray | str) -> None:
        if isinstance(data, str):
            self._buf = data
        else:
            # Cleartext PostScript is ASCII / Latin-1 by spec; decode
            # with latin-1 so any odd byte round-trips losslessly.
            self._buf = bytes(data).decode("latin-1")
        self._pos = 0

    # ---------- public ----------

    def peek_token(self) -> tuple[str, Any] | None:
        """Return the next token without consuming it. ``None`` at EOF."""
        saved = self._pos
        tok = self.next_token()
        self._pos = saved
        return tok

    def next_token(self) -> tuple[str, Any] | None:
        """Consume and return one ``(kind, value)`` token. ``None`` at EOF."""
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
                    while len(digits) < 3 and self._pos < len(self._buf) and self._buf[self._pos].isdigit():
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

    def __init__(self) -> None:
        # Public outputs — populated by parse().
        self.font_dict: dict[str, Any] = {}
        self.decrypted_binary: bytes = b""

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
        bytes are kept on :attr:`decrypted_binary`.
        """
        # _len_iv is currently informational; eexec uses a fixed 4-byte
        # warm-up. We accept the parameter to mirror upstream's signature.
        del len_iv
        self._parse_ascii(bytes(segment1))
        self.decrypted_binary = Type1FontUtil.eexec_decrypt(bytes(segment2))
        return self.font_dict

    # ---------- ascii section ----------

    def _parse_ascii(self, segment1: bytes) -> None:
        lex = Type1Lexer(segment1)
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


__all__ = ["Type1Parser", "Type1Lexer"]
