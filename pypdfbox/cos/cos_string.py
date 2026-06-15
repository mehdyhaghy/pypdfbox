from __future__ import annotations

from typing import Any, ClassVar

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor

_REPLACEMENT_CHARACTER = "�"


def _decode_java_utf16(data: bytes, *, big_endian: bool) -> str:
    """Decode UTF-16 the way Java's ``StandardCharsets.UTF_16BE/LE`` decoder
    does with the default REPLACE action — the W3C / ICU "maximal subpart"
    substitution rather than Python's per-unit ``errors="replace"``.

    Rules (verified byte-for-byte against PDFBox 3.0.7's ``getString()`` over
    the surrogate / truncation battery in wave 1523's oracle test):

    * A valid high+low surrogate pair forms one supplementary code point.
    * A high surrogate followed by a full 16-bit unit that is **not** a low
      surrogate is one ill-formed two-unit sequence → a single U+FFFD that
      consumes both units (so the trailing unit is dropped, never re-decoded).
    * A high surrogate with fewer than two trailing bytes remaining → a single
      U+FFFD consuming the remainder.
    * A lone low surrogate → a single U+FFFD (one unit).
    * A trailing odd byte → a single U+FFFD.
    """
    out: list[str] = []
    n = len(data)
    i = 0
    while i < n:
        if i + 1 >= n:
            # trailing odd byte
            out.append(_REPLACEMENT_CHARACTER)
            break
        unit = (data[i] << 8) | data[i + 1] if big_endian else (data[i + 1] << 8) | data[i]
        i += 2
        if 0xD800 <= unit <= 0xDBFF:
            # High surrogate: require a following full low-surrogate unit.
            if i + 1 < n:
                nxt = (
                    (data[i] << 8) | data[i + 1]
                    if big_endian
                    else (data[i + 1] << 8) | data[i]
                )
                if 0xDC00 <= nxt <= 0xDFFF:
                    cp = 0x10000 + ((unit - 0xD800) << 10) + (nxt - 0xDC00)
                    out.append(chr(cp))
                    i += 2
                    continue
                # Next is a full non-low unit: consume it as part of the
                # single replacement (do NOT re-decode it).
                out.append(_REPLACEMENT_CHARACTER)
                i += 2
                continue
            # High surrogate with < 2 trailing bytes: one replacement, done.
            out.append(_REPLACEMENT_CHARACTER)
            break
        if 0xDC00 <= unit <= 0xDFFF:
            # Lone low surrogate.
            out.append(_REPLACEMENT_CHARACTER)
            continue
        out.append(chr(unit))
    return "".join(out)


class COSString(COSBase):
    """
    PDF string object. Stores the decoded byte sequence; the original
    syntactic form (literal ``(...)`` vs hex ``<...>``) is tracked by
    ``force_hex_form`` so the writer can preserve it for round-trip.

    Decoding to text requires knowledge of the document encoding
    (PDFDocEncoding, UTF-16BE BOM, UTF-8 BOM in PDF 2.0); helpers for
    that live alongside the parser. Here we keep raw bytes only.
    """

    # Mirrors upstream ``COSString.FORCE_PARSING`` — a JVM-level system
    # property in Java (``Boolean.getBoolean("org.apache.pdfbox.forceParsing")``).
    # When True, ``parse_hex`` substitutes ``?`` for malformed hex digits
    # instead of raising; default is False (strict). Exposed as a class
    # attribute so callers can flip it the same way upstream code does
    # (``COSString.FORCE_PARSING = True``).
    FORCE_PARSING: ClassVar[bool] = False

    def __init__(
        self,
        value: bytes | bytearray | memoryview | str,
        force_hex: bool = False,
    ) -> None:
        super().__init__()
        if isinstance(value, str):
            # Mirrors PDFBox's ``new COSString(String)`` constructor: if
            # every character can be represented in PDFDocEncoding, encode
            # there; otherwise upstream uses UTF-16BE with a BOM.
            from pypdfbox.pdmodel.common.pdfdoc_encoding import (
                contains_char,
                encode_bytes,
            )

            if all(contains_char(c) for c in value):
                value = encode_bytes(value)
            else:
                value = b"\xfe\xff" + value.encode("utf-16-be")
        self._bytes = bytes(value)
        self._force_hex_form = force_hex

    @property
    def bytes_(self) -> bytes:
        return self._bytes

    def get_bytes(self) -> bytes:
        return self._bytes

    def set_value(self, value: bytes | bytearray | memoryview) -> None:
        """Replace the raw byte payload.

        Mirrors upstream ``COSString.setValue(byte[])`` (deprecated in
        PDFBox 3.0 — kept for API parity; will be removed when upstream
        removes it). Copies the input so callers can mutate their own
        buffer without affecting this instance.
        """
        self._bytes = bytes(value)

    def get_string(self) -> str:
        """Decode using the same fallback PDFBox uses for text strings.

        Matches upstream ``COSString.getString()``:

        * UTF-16BE when the ``FE FF`` BOM is present;
        * UTF-16LE when the ``FF FE`` BOM is present;
        * PDFDocEncoding (PDF 32000-1 §D.3) otherwise.

        The UTF-16 branches mirror Java's ``new String(byte[], offset,
        length, StandardCharsets.UTF_16BE)`` — malformed / truncated input is
        substituted with U+FFFD rather than throwing. Java's substitution
        follows the W3C / ICU "maximal subpart" rule, which is **not** the
        same as Python's per-unit ``errors="replace"`` for surrogate
        sequences: a lone high surrogate followed by any other 16-bit unit (a
        non-low-surrogate, including a BMP character or another high
        surrogate) is treated as one ill-formed two-unit sequence and yields a
        **single** U+FFFD that consumes **both** units; a lone low surrogate,
        or a high surrogate followed by fewer than two trailing bytes, yields a
        single U+FFFD consuming just what remains. Python's codec would emit
        one U+FFFD per unit (e.g. ``D83D 0041`` → ``U+FFFD 'A'``), so we
        implement the Java rule directly in :func:`_decode_java_utf16`.

        We additionally strip a UTF-8 BOM (``EF BB BF``) and decode the rest
        as UTF-8. This is a deliberate forward-port of PDF 2.0 §7.9.2.2 /
        PDFBox 4.0 behaviour; the pinned upstream baseline (PDFBox 3.0.7) has
        no UTF-8-BOM branch and would decode those bytes as PDFDocEncoding.
        Recorded as an active divergence in CHANGES.md.
        """
        if self._bytes.startswith(b"\xfe\xff"):
            return _decode_java_utf16(self._bytes[2:], big_endian=True)
        if self._bytes.startswith(b"\xff\xfe"):
            return _decode_java_utf16(self._bytes[2:], big_endian=False)
        if self._bytes.startswith(b"\xef\xbb\xbf"):
            return self._bytes[3:].decode("utf-8", errors="replace")
        from pypdfbox.pdmodel.common.pdfdoc_encoding import decode_bytes

        return decode_bytes(self._bytes)

    def is_force_hex_form(self) -> bool:
        return self._force_hex_form

    def get_force_hex_form(self) -> bool:
        """Mirror PDFBox's ``getForceHexForm()`` accessor — same value as
        ``is_force_hex_form``; both spellings exist upstream."""
        return self._force_hex_form

    def get_ascii(self) -> str:
        """Decode the raw bytes as ASCII — mirrors PDFBox's ``getASCII()``.

        PDF byte strings sometimes hold ASCII content (e.g. signature
        fields, dates encoded as ``D:YYYYMMDD...``); this returns the
        bytes as a ``str`` without the BOM-aware logic of ``get_string``.
        Bytes outside 0x00..0x7F are replaced with ``?``, matching Java's
        ``new String(bytes, StandardCharsets.US_ASCII)`` substitution.
        """
        return self._bytes.decode("ascii", errors="replace").replace("�", "?")

    def set_force_hex_form(self, force_hex: bool) -> None:
        self._force_hex_form = force_hex

    def to_hex_string(self) -> str:
        """Hex-encoded raw bytes, uppercase — matches PDFBox ``toHexString``."""
        return self._bytes.hex().upper()

    @classmethod
    def parse_hex(cls, hex_text: str) -> COSString:
        """Construct from the body of a hex-string literal ``<...>``.

        Mirrors upstream ``COSString.parseHex(String)``:

        * Only **leading and trailing** whitespace is skipped — internal
          whitespace is treated as a malformed digit and raises
          ``OSError`` (PDFBox throws ``IOException``) unless
          :attr:`FORCE_PARSING` is True, in which case each malformed
          digit becomes ``?`` (0x3F).
        * An odd number of digits is implicitly padded with a trailing
          ``0`` per ISO 32000-1 §7.3.4.3.
        * The returned :class:`COSString` is **not** marked as hex-form;
          upstream returns ``new COSString(bytes)`` with the default
          (literal) form so the writer is free to choose.
        """
        # Trim leading and trailing whitespace only (Java
        # ``Character.isWhitespace`` is roughly Python ``str.isspace`` —
        # both cover the ASCII whitespace set used in PDF hex strings).
        end = len(hex_text)
        while end > 0 and hex_text[end - 1].isspace():
            end -= 1
        start = 0
        while start < end and hex_text[start].isspace():
            start += 1
        body = hex_text[start:end]

        # Pad odd-length input with a trailing "0" (ISO 32000-1 §7.3.4.3).
        if len(body) % 2 == 1:
            body += "0"

        # Walk in pairs so we can reject internal whitespace and other
        # non-hex characters strictly (``bytes.fromhex`` is lenient about
        # embedded whitespace, but upstream's ``Hex.getHexValue``
        # returns -1 for anything outside ``0-9a-fA-F`` and raises).
        # ``FORCE_PARSING`` substitutes ``?`` (0x3F) for malformed pairs
        # and logs a warning, mirroring the Java behaviour.
        _hex_digits = "0123456789abcdefABCDEF"
        buf = bytearray(len(body) // 2)
        for i in range(0, len(body), 2):
            pair = body[i : i + 2]
            if pair[0] in _hex_digits and pair[1] in _hex_digits:
                buf[i // 2] = int(pair, 16)
            elif cls.FORCE_PARSING:
                buf[i // 2] = 0x3F
            else:
                raise OSError(f"Invalid hex string: {hex_text}")
        return cls(bytes(buf))

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_string(self)

    def equals(self, other: object) -> bool:
        """Mirror upstream ``COSString.equals(Object)`` (line 301).

        Upstream compares the *decoded* string and the ``forceHexForm``
        flag — two COSStrings whose byte payloads decode to the same
        text are considered equal even if one is PDFDocEncoded and the
        other is UTF-16BE-with-BOM. We match that behaviour here.
        """
        if isinstance(other, COSString):
            return (
                self.get_string() == other.get_string()
                and self._force_hex_form == other._force_hex_form
            )
        return False

    def hash_code(self) -> int:
        """Mirror upstream ``COSString.hashCode()`` (line 313).

        Upstream uses ``Arrays.hashCode(bytes) + (forceHexForm ? 17 : 0)``
        — we use Python's ``hash`` on the raw byte tuple and add 17 when
        the hex flag is set so the contract ``equals → hash_code`` is
        preserved (note: Java's ``equals`` compares decoded strings while
        ``hashCode`` hashes raw bytes; we keep the upstream asymmetry).
        """
        return hash(self._bytes) + (17 if self._force_hex_form else 0)

    def to_string(self) -> str:
        """Mirror upstream ``COSString.toString()`` (line 320).

        Returns ``"COSString{<decoded text>}"``. Used by upstream for
        debug/logging; kept for parity so callers porting Java code
        relying on ``toString()`` continue to compile.
        """
        return f"COSString{{{self.get_string()}}}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSString):
            return self._bytes == other._bytes and self._force_hex_form == other._force_hex_form
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._bytes, self._force_hex_form))

    def __repr__(self) -> str:
        return f"COSString({self._bytes!r}, hex={self._force_hex_form})"
