from __future__ import annotations

from typing import Any

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

    def __init__(self, value: bytes | bytearray | memoryview | str) -> None:
        super().__init__()
        if isinstance(value, str):
            # Convenience for ASCII literals — mirrors PDFBox's
            # ``new COSString(String)`` constructor that encodes via
            # PDFDocEncoding. We approximate with latin-1 for ASCII-only
            # input; non-ASCII text should be encoded by the caller.
            value = value.encode("latin-1")
        self._bytes = bytes(value)
        self._force_hex_form = False

    @property
    def bytes_(self) -> bytes:
        return self._bytes

    def get_bytes(self) -> bytes:
        return self._bytes

    def get_string(self) -> str:
        """Decode using the same fallback PDFBox uses for text strings:
        UTF-16BE if the BOM is present, UTF-8 if the UTF-8 BOM is present
        (PDF 2.0 §7.9.2.2), else PDFDocEncoding (approximated as latin-1)."""
        if self._bytes.startswith(b"\xfe\xff"):
            return self._bytes[2:].decode("utf-16-be")
        if self._bytes.startswith(b"\xff\xfe"):
            return self._bytes[2:].decode("utf-16-le")
        if self._bytes.startswith(b"\xef\xbb\xbf"):
            return self._bytes[3:].decode("utf-8")
        return self._bytes.decode("latin-1")

    def is_force_hex_form(self) -> bool:
        return self._force_hex_form

    def set_force_hex_form(self, force_hex: bool) -> None:
        self._force_hex_form = force_hex

    @classmethod
    def parse_hex(cls, hex_text: str) -> COSString:
        """Construct from the body of a hex-string literal ``<...>``.

        Whitespace is ignored; an odd number of digits is implicitly
        padded with a trailing ``0`` per ISO 32000-1 §7.3.4.3.
        """
        cleaned = "".join(c for c in hex_text if not c.isspace())
        if len(cleaned) % 2 == 1:
            cleaned += "0"
        try:
            data = bytes.fromhex(cleaned)
        except ValueError as exc:
            raise ValueError(f"invalid hex string: {hex_text!r}") from exc
        s = cls(data)
        s.set_force_hex_form(True)
        return s

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_string(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSString):
            return self._bytes == other._bytes and self._force_hex_form == other._force_hex_form
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._bytes, self._force_hex_form))

    def __repr__(self) -> str:
        return f"COSString({self._bytes!r}, hex={self._force_hex_form})"
