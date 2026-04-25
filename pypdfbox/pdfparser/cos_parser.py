from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSString,
)
from pypdfbox.io import RandomAccessRead

from .base_parser import BaseParser
from .parse_error import PDFParseError


class COSParser(BaseParser):
    """
    Builds ``COSBase`` objects from the token stream produced by
    ``BaseParser``. Mirrors `org.apache.pdfbox.pdfparser.COSParser` for
    the direct-object / array / dictionary / indirect-reference subset.

    Stream bodies (the ``stream ... endstream`` payload following a
    stream dictionary) are NOT handled here — that requires resolved
    ``/Length`` and lives in ``PDFParser`` (cluster #3).

    Usage:
        parser = COSParser(source, document=doc)  # document is optional
        obj = parser.parse_direct_object()
    """

    def __init__(
        self, source: RandomAccessRead, document: COSDocument | None = None
    ) -> None:
        super().__init__(source)
        self._document = document

    @property
    def document(self) -> COSDocument | None:
        return self._document

    # ---------- top-level dispatch ----------

    def parse_direct_object(self) -> COSBase:
        """Parse one direct object (or an indirect reference, returned as
        an unresolved ``COSObject``). Whitespace is consumed first."""
        self.skip_whitespace()
        b = self.peek_byte()
        if b == RandomAccessRead.EOF:
            raise PDFParseError("unexpected EOF in object stream", position=self.position)
        # Dispatch by the first byte of the object.
        if b == 0x3C:  # '<' — could be '<<' (dict) or '<' (hex string)
            second = self._peek_two_bytes()[1]
            if second == 0x3C:
                return self.parse_cos_dictionary()
            return self._read_cos_hex_string()
        if b == 0x28:  # '('
            return self._read_cos_literal_string()
        if b == 0x2F:  # '/'
            return COSName.get_pdf_name(self.read_name())
        if b == 0x5B:  # '['
            return self.parse_cos_array()
        if b in (0x2B, 0x2D, 0x2E) or self.is_digit(b):
            return self._parse_number_or_indirect_reference()
        if b in (0x74, 0x66, 0x6E):  # 't', 'f', 'n' — true / false / null
            return self._parse_keyword_value()
        raise PDFParseError(
            f"unexpected byte {b:#04x} ({chr(b)!r}) at start of object",
            position=self.position,
        )

    # ---------- arrays ----------

    def parse_cos_array(self) -> COSArray:
        """Parse a ``[ ... ]`` array."""
        start = self.position
        b = self.read_byte()
        if b != 0x5B:
            raise PDFParseError("expected array '['", position=start)
        items: list[COSBase] = []
        while True:
            self.skip_whitespace()
            nxt = self.peek_byte()
            if nxt == RandomAccessRead.EOF:
                raise PDFParseError("unterminated array", position=start)
            if nxt == 0x5D:  # ']'
                self.read_byte()
                return COSArray(items)
            items.append(self.parse_direct_object())

    # ---------- dictionaries ----------

    def parse_cos_dictionary(self) -> COSDictionary:
        """Parse a ``<< ... >>`` dictionary."""
        start = self.position
        self.read_expected(b"<<")
        d = COSDictionary()
        while True:
            self.skip_whitespace()
            nxt = self.peek_byte()
            if nxt == RandomAccessRead.EOF:
                raise PDFParseError("unterminated dictionary", position=start)
            if nxt == 0x3E:  # '>'
                self.read_expected(b">>")
                return d
            if nxt != 0x2F:  # '/'
                raise PDFParseError(
                    f"expected name in dictionary at byte {self.position}",
                    position=self.position,
                )
            key = self.read_name()
            value = self.parse_direct_object()
            d.set_item(key, value)

    # ---------- numbers and indirect references ----------

    def _parse_number_or_indirect_reference(self) -> COSBase:
        """Parse a number; if followed by a second number and the keyword
        ``R``, return an indirect-reference ``COSObject`` instead."""
        start = self.position
        first = self.read_number()
        # An indirect reference looks like ``<int> <int> R`` and the first
        # token must be a non-negative integer. Anything else is just a
        # number.
        if not isinstance(first, int) or first < 0:
            return self._wrap_number(first, start)
        # Save position to potentially rewind if this isn't an indirect ref.
        post_first = self.position
        # Lookahead: next token might be the second integer.
        self.skip_whitespace()
        if not self._next_byte_starts_unsigned_int():
            self.seek(post_first)
            return self._wrap_number(first, start)
        try:
            second = self.read_number()
        except PDFParseError:
            self.seek(post_first)
            return self._wrap_number(first, start)
        if not isinstance(second, int) or second < 0:
            self.seek(post_first)
            return self._wrap_number(first, start)
        # Lookahead: keyword ``R``?
        self.skip_whitespace()
        if self.peek_byte() != 0x52:  # 'R'
            self.seek(post_first)
            return self._wrap_number(first, start)
        try:
            kw = self.read_keyword()
        except PDFParseError:
            self.seek(post_first)
            return self._wrap_number(first, start)
        if kw != b"R":
            self.seek(post_first)
            return self._wrap_number(first, start)
        return self._make_indirect_reference(first, second)

    def _next_byte_starts_unsigned_int(self) -> bool:
        b = self.peek_byte()
        return b != RandomAccessRead.EOF and self.is_digit(b)

    def _wrap_number(self, value: int | float, start: int) -> COSBase:
        if isinstance(value, int):
            cos_int = COSInteger.get(value)
            return cos_int
        # Re-read original textual representation so COSFloat preserves it.
        end = self.position
        cur = self.position
        self.seek(start)
        text_bytes = bytearray()
        while self.position < end:
            text_bytes.append(self.read_byte())
        self.seek(cur)
        return COSFloat(text_bytes.decode("ascii"))

    def _make_indirect_reference(self, object_number: int, generation_number: int) -> COSObject:
        """Build (or fetch from the document pool) the ``COSObject``
        referenced by ``<n> <m> R``. Without a bound document the reference
        is fresh — the caller is responsible for resolving it later."""
        if self._document is None:
            return COSObject(object_number, generation_number)
        return self._document.get_object_from_pool(
            COSObjectKey(object_number, generation_number)
        )

    # ---------- keyword-valued primitives ----------

    def _parse_keyword_value(self) -> COSBase:
        """Parse ``true``, ``false``, or ``null``."""
        start = self.position
        kw = self.read_keyword()
        if kw == b"true":
            return COSBoolean.TRUE
        if kw == b"false":
            return COSBoolean.FALSE
        if kw == b"null":
            return COSNull.NULL
        raise PDFParseError(f"unexpected keyword {kw!r}", position=start)

    # ---------- string helpers (return COSString) ----------

    def _read_cos_literal_string(self) -> COSString:
        return COSString(self.read_literal_string())

    def _read_cos_hex_string(self) -> COSString:
        s = COSString(self.read_hex_string())
        s.set_force_hex_form(True)
        return s

    # ---------- indirect object definitions ----------

    def parse_indirect_object_definition(self) -> COSObject:
        """Parse ``n m obj <direct-object> endobj``. Returns a resolved
        ``COSObject`` whose target is the parsed direct object.

        Stream bodies (``... <<dict>> stream ... endstream endobj``) are
        NOT supported here — they require ``/Length`` resolution and live
        in ``PDFParser`` (cluster #3). If the next keyword after the
        object is ``stream`` rather than ``endobj``, this raises
        ``NotImplementedError``."""
        start = self.position
        self.skip_whitespace()
        object_number = self.read_int()
        self.skip_whitespace()
        generation_number = self.read_int()
        self.skip_whitespace()
        kw = self.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' after object header, got {kw!r}", position=start
            )
        body = self.parse_direct_object()
        self.skip_whitespace()
        # Distinguish ``endobj`` from ``stream`` keyword.
        peeked = self.peek_byte()
        if peeked == 0x73:  # 's' — possibly 'stream'
            kw2 = self.read_keyword()
            if kw2 == b"stream":
                raise NotImplementedError(
                    "stream-body parsing requires /Length resolution; "
                    "lives in PDFParser (parser cluster #3)"
                )
            raise PDFParseError(
                f"expected 'endobj' after object body, got {kw2!r}",
                position=self.position,
            )
        kw_end = self.read_keyword()
        if kw_end != b"endobj":
            raise PDFParseError(
                f"expected 'endobj' after object body, got {kw_end!r}",
                position=self.position,
            )
        if self._document is not None:
            cos_obj = self._document.get_object_from_pool(
                COSObjectKey(object_number, generation_number)
            )
            cos_obj.set_object(body)
            return cos_obj
        cos_obj = COSObject(object_number, generation_number, resolved=body)
        return cos_obj

    # ---------- internal byte-pair lookahead ----------

    def _peek_two_bytes(self) -> tuple[int, int]:
        """Return the next two bytes without consuming them. Returns
        ``(-1, -1)`` if both are at EOF; ``(b, -1)`` if only one byte
        remains."""
        first = self._src.read()
        if first == RandomAccessRead.EOF:
            return (-1, -1)
        second = self._src.read()
        if second == RandomAccessRead.EOF:
            self._src.rewind(1)
            return (first, -1)
        self._src.rewind(2)
        return (first, second)
