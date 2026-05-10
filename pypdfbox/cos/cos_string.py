from __future__ import annotations

from typing import Any, ClassVar

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


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

    def getBytes(self) -> bytes:  # noqa: N802 - upstream Java name
        return self.get_bytes()

    def set_value(self, value: bytes | bytearray | memoryview) -> None:
        """Replace the raw byte payload.

        Mirrors upstream ``COSString.setValue(byte[])`` (deprecated in
        PDFBox 3.0 — kept for API parity; will be removed when upstream
        removes it). Copies the input so callers can mutate their own
        buffer without affecting this instance.
        """
        self._bytes = bytes(value)

    def get_string(self) -> str:
        """Decode using the same fallback PDFBox uses for text strings:
        UTF-16BE if the BOM is present, UTF-8 if the UTF-8 BOM is present
        (PDF 2.0 §7.9.2.2), else PDFDocEncoding (PDF 32000-1 §D.3)."""
        if self._bytes.startswith(b"\xfe\xff"):
            return self._bytes[2:].decode("utf-16-be")
        if self._bytes.startswith(b"\xff\xfe"):
            return self._bytes[2:].decode("utf-16-le")
        if self._bytes.startswith(b"\xef\xbb\xbf"):
            return self._bytes[3:].decode("utf-8")
        from pypdfbox.pdmodel.common.pdfdoc_encoding import decode_bytes

        return decode_bytes(self._bytes)

    def getString(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_string()

    def is_force_hex_form(self) -> bool:
        return self._force_hex_form

    def get_force_hex_form(self) -> bool:
        """Mirror PDFBox's ``getForceHexForm()`` accessor — same value as
        ``is_force_hex_form``; both spellings exist upstream."""
        return self._force_hex_form

    def isForceHexForm(self) -> bool:  # noqa: N802 - upstream Java name
        return self.is_force_hex_form()

    def get_ascii(self) -> str:
        """Decode the raw bytes as ASCII — mirrors PDFBox's ``getASCII()``.

        PDF byte strings sometimes hold ASCII content (e.g. signature
        fields, dates encoded as ``D:YYYYMMDD...``); this returns the
        bytes as a ``str`` without the BOM-aware logic of ``get_string``.
        Bytes outside 0x00..0x7F are replaced with ``?``, matching Java's
        ``new String(bytes, StandardCharsets.US_ASCII)`` substitution.
        """
        return self._bytes.decode("ascii", errors="replace").replace("�", "?")

    def getASCII(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_ascii()

    def set_force_hex_form(self, force_hex: bool) -> None:
        self._force_hex_form = force_hex

    def setForceHexForm(self, force_hex: bool) -> None:  # noqa: N802
        self.set_force_hex_form(force_hex)

    def to_hex_string(self) -> str:
        """Hex-encoded raw bytes, uppercase — matches PDFBox ``toHexString``."""
        return self._bytes.hex().upper()

    def toHexString(self) -> str:  # noqa: N802 - upstream Java name
        return self.to_hex_string()

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
