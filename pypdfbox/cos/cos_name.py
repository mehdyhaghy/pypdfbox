from __future__ import annotations

from typing import Any, BinaryIO

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


class COSName(COSBase):
    """
    PDF name object (e.g. ``/Type``, ``/Pages``). Names are interned: any
    two ``COSName.get_pdf_name(s)`` calls with the same string return the
    same instance, so equality and ``is`` are interchangeable.

    PDF names are byte strings. ``get_pdf_name(str)`` uses UTF-8 bytes,
    while ``get_pdf_name(bytes)`` preserves parser-supplied raw bytes.
    ``get_name()`` decodes those bytes as UTF-8 and falls back to Latin-1,
    matching PDFBox's ``COSName.getName()`` behavior.
    """

    # Two-tier registry mirroring upstream PDFBox: ``_common_name_map`` holds
    # the predefined static constants and survives ``clear_resources()``;
    # ``_name_map`` holds dynamically-encountered names and is the only map
    # cleared by ``clear_resources()``. See ``COSName.java``.
    _common_name_map: dict[bytes, COSName] = {}
    _name_map: dict[bytes, COSName] = {}

    __slots__ = ("_bytes", "_direct", "_needs_to_be_updated")

    def __new__(
        cls,
        name: str | bytes | bytearray | memoryview,
        *,
        _static: bool = False,
    ) -> COSName:
        data = cls._coerce_name_bytes(name)
        existing = cls._common_name_map.get(data)
        if existing is not None:
            return existing
        existing = cls._name_map.get(data)
        if existing is not None:
            return existing
        inst = super().__new__(cls)
        if _static:
            cls._common_name_map[data] = inst
        else:
            cls._name_map[data] = inst
        return inst

    def __init__(
        self,
        name: str | bytes | bytearray | memoryview,
        *,
        _static: bool = False,
    ) -> None:
        # Re-init guard: __new__ may return an interned instance.
        if getattr(self, "_bytes", None) is not None:
            return
        super().__init__()
        self._bytes = self._coerce_name_bytes(name)

    @staticmethod
    def _coerce_name_bytes(name: str | bytes | bytearray | memoryview) -> bytes:
        if isinstance(name, str):
            return name.encode("utf-8")
        return bytes(name)

    @classmethod
    def get_pdf_name(cls, name: str | bytes | bytearray | memoryview) -> COSName:
        """Canonical accessor — returns the interned instance."""
        return cls(name)

    @property
    def name(self) -> str:
        return self.get_name()

    def get_name(self) -> str:
        # Match Java's ``new String(bytes, UTF_8)`` substitute behavior:
        # invalid UTF-8 bytes are replaced with U+FFFD, then if any U+FFFD
        # appears we fall back to ISO-8859-1 (Latin-1), which can decode any
        # byte sequence without loss. This mirrors COSName.getName() exactly.
        utf8_string = self._bytes.decode("utf-8", errors="replace")
        if "�" in utf8_string:
            return self._bytes.decode("latin-1")
        return utf8_string

    def get_bytes(self) -> bytes:
        return bytes(self._bytes)

    def is_empty(self) -> bool:
        """``True`` if this name is the empty string. Mirrors
        ``COSName.isEmpty()``."""
        return len(self._bytes) == 0

    def write_pdf(self, output: BinaryIO) -> None:
        output.write(b"/")
        for b in self._bytes:
            if _is_printable_name_byte(b):
                output.write(bytes((b,)))
            else:
                output.write(b"#")
                output.write(f"{b:02X}".encode("ascii"))

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_name(self)

    def compare_to(self, other: COSName | None) -> int:
        """Lexicographic ordering over unsigned byte values.

        Mirrors ``COSName.compareTo(COSName)``. Unsigned comparison is used so
        that bytes with the high bit set sort after all ASCII bytes, which
        matches the natural PDF byte ordering.
        """
        if other is None:
            return 1
        if self._bytes is other._bytes:
            return 0
        a = self._bytes
        b = other._bytes
        n = min(len(a), len(b))
        for i in range(n):
            diff = a[i] - b[i]
            if diff != 0:
                return diff
        return len(a) - len(b)

    @classmethod
    def clear_resources(cls) -> None:
        """Clear the dynamic interned-name registry. Mirrors the deprecated
        ``COSName.clearResources()``; only the document-specific name map is
        cleared — predefined static constants survive."""
        cls._name_map.clear()

    def equals(self, other: object) -> bool:
        """Mirror Java's ``COSName.equals(Object)`` — byte-array equality
        (PDFBox COSName.java:824-827).

        Two ``COSName`` instances are equal iff their underlying byte
        sequences match. Provided alongside ``__eq__`` so PDFBox-style
        Java callers can keep using the explicit predicate when porting.
        """
        if not isinstance(other, COSName):
            return False
        return self._bytes == other._bytes

    def hash_code(self) -> int:
        """Mirror Java's ``COSName.hashCode()`` — ``Arrays.hashCode(byte[])``
        (PDFBox COSName.java:830-833).

        The Java contract: ``int h = 1; for (byte b : nameBytes) h = 31 * h + b;``
        with ``b`` widened as a *signed* 8-bit value, and the running total
        kept as a signed 32-bit ``int`` (overflow wraps).
        """
        h = 1
        for b in self._bytes:
            # Java widens byte → int as signed (-128..127), so re-sign here.
            signed = b - 256 if b >= 128 else b
            h = (31 * h + signed) & 0xFFFFFFFF
        # Re-sign the 32-bit result, matching Java's signed int return.
        if h >= 0x80000000:
            h -= 0x1_0000_0000
        return h

    def to_string(self) -> str:
        """Mirror Java's ``COSName.toString()`` —
        ``"COSName{" + getName() + "}"`` (PDFBox COSName.java:817-821)."""
        return f"COSName{{{self.get_name()}}}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSName):
            return self._bytes == other._bytes
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._bytes)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, COSName):
            return NotImplemented
        return self.compare_to(other) < 0

    def __le__(self, other: object) -> bool:
        if not isinstance(other, COSName):
            return NotImplemented
        return self.compare_to(other) <= 0

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, COSName):
            return NotImplemented
        return self.compare_to(other) > 0

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, COSName):
            return NotImplemented
        return self.compare_to(other) >= 0

    def __repr__(self) -> str:
        return f"COSName({self.get_name()!r})"

    def __str__(self) -> str:
        return f"/{self.get_name()}"


def _is_printable_name_byte(b: int) -> bool:
    return (
        (0x41 <= b <= 0x5A)
        or (0x61 <= b <= 0x7A)
        or (0x30 <= b <= 0x39)
        or b in (0x2B, 0x2D, 0x5F, 0x40, 0x2A, 0x24, 0x3B, 0x2E)
    )


def _static_name(value: str) -> COSName:
    """Build and intern a predefined static-constant ``COSName`` whose
    interned slot lives in ``_common_name_map`` so it survives
    ``clear_resources()``. Mirrors upstream's ``new COSName(String)``
    private constructor with ``staticValue=true``."""
    return COSName(value, _static=True)


# A small starter set of predefined names. The full PDFBox catalog has
# hundreds; we'll grow this organically as each consuming module needs
# them. Anything not predefined can be obtained via
# ``COSName.get_pdf_name(...)`` — it is interned the first time it is seen.
COSName.TYPE = _static_name("Type")  # type: ignore[attr-defined]
COSName.SUBTYPE = _static_name("Subtype")  # type: ignore[attr-defined]
COSName.LENGTH = _static_name("Length")  # type: ignore[attr-defined]
COSName.FILTER = _static_name("Filter")  # type: ignore[attr-defined]
COSName.ROOT = _static_name("Root")  # type: ignore[attr-defined]
COSName.INFO = _static_name("Info")  # type: ignore[attr-defined]
COSName.ENCRYPT = _static_name("Encrypt")  # type: ignore[attr-defined]
COSName.ID = _static_name("ID")  # type: ignore[attr-defined]
COSName.LINEARIZED = _static_name("Linearized")  # type: ignore[attr-defined]
COSName.SIZE = _static_name("Size")  # type: ignore[attr-defined]
COSName.PREV = _static_name("Prev")  # type: ignore[attr-defined]
COSName.PAGES = _static_name("Pages")  # type: ignore[attr-defined]
COSName.PAGE = _static_name("Page")  # type: ignore[attr-defined]
COSName.KIDS = _static_name("Kids")  # type: ignore[attr-defined]
COSName.COUNT = _static_name("Count")  # type: ignore[attr-defined]
COSName.PARENT = _static_name("Parent")  # type: ignore[attr-defined]
COSName.RESOURCES = _static_name("Resources")  # type: ignore[attr-defined]
COSName.MEDIA_BOX = _static_name("MediaBox")  # type: ignore[attr-defined]
COSName.CONTENTS = _static_name("Contents")  # type: ignore[attr-defined]
COSName.CATALOG = _static_name("Catalog")  # type: ignore[attr-defined]
COSName.STRUCT_TREE_ROOT = _static_name("StructTreeRoot")  # type: ignore[attr-defined]
COSName.METADATA = _static_name("Metadata")  # type: ignore[attr-defined]
# Single-letter / short names referenced by upstream tests and a handful of
# PDF spec-defined keys. Keep this list minimal — grow on demand.
COSName.A = _static_name("A")  # type: ignore[attr-defined]
COSName.B = _static_name("B")  # type: ignore[attr-defined]
COSName.C = _static_name("C")  # type: ignore[attr-defined]
COSName.D = _static_name("D")  # type: ignore[attr-defined]
COSName.T = _static_name("T")  # type: ignore[attr-defined]
COSName.BE = _static_name("BE")  # type: ignore[attr-defined]
COSName.PARAMS = _static_name("Params")  # type: ignore[attr-defined]
COSName.FLATE_DECODE = _static_name("FlateDecode")  # type: ignore[attr-defined]
COSName.ASCII85_DECODE = _static_name("ASCII85Decode")  # type: ignore[attr-defined]
COSName.STANDARD_ENCODING = _static_name("StandardEncoding")  # type: ignore[attr-defined]
COSName.MAC_EXPERT_ENCODING = _static_name("MacExpertEncoding")  # type: ignore[attr-defined]
COSName.MAC_ROMAN_ENCODING = _static_name("MacRomanEncoding")  # type: ignore[attr-defined]
COSName.WIN_ANSI_ENCODING = _static_name("WinAnsiEncoding")  # type: ignore[attr-defined]
COSName.FIRST_CHAR = _static_name("FirstChar")  # type: ignore[attr-defined]
COSName.LAST_CHAR = _static_name("LastChar")  # type: ignore[attr-defined]
COSName.WIDTHS = _static_name("Widths")  # type: ignore[attr-defined]
