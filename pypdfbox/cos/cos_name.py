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

    _registry: dict[bytes, COSName] = {}

    __slots__ = ("_bytes", "_direct", "_needs_to_be_updated")

    def __new__(cls, name: str | bytes | bytearray | memoryview) -> COSName:
        data = cls._coerce_name_bytes(name)
        existing = cls._registry.get(data)
        if existing is not None:
            return existing
        inst = super().__new__(cls)
        cls._registry[data] = inst
        return inst

    def __init__(self, name: str | bytes | bytearray | memoryview) -> None:
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
        try:
            return self._bytes.decode("utf-8")
        except UnicodeDecodeError:
            return self._bytes.decode("latin-1")

    def get_bytes(self) -> bytes:
        return bytes(self._bytes)

    def getBytes(self) -> bytes:  # noqa: N802
        return self.get_bytes()

    def write_pdf(self, output: BinaryIO) -> None:
        output.write(b"/")
        for b in self._bytes:
            if _is_printable_name_byte(b):
                output.write(bytes((b,)))
            else:
                output.write(b"#")
                output.write(f"{b:02X}".encode("ascii"))

    def writePDF(self, output: BinaryIO) -> None:  # noqa: N802
        self.write_pdf(output)

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_name(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSName):
            return self._bytes == other._bytes
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._bytes)

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


# A small starter set of predefined names. The full PDFBox catalog has
# hundreds; we'll grow this organically as each consuming module needs
# them. Anything not predefined can be obtained via
# ``COSName.get_pdf_name(...)`` — it is interned the first time it is seen.
COSName.TYPE = COSName.get_pdf_name("Type")  # type: ignore[attr-defined]
COSName.SUBTYPE = COSName.get_pdf_name("Subtype")  # type: ignore[attr-defined]
COSName.LENGTH = COSName.get_pdf_name("Length")  # type: ignore[attr-defined]
COSName.FILTER = COSName.get_pdf_name("Filter")  # type: ignore[attr-defined]
COSName.ROOT = COSName.get_pdf_name("Root")  # type: ignore[attr-defined]
COSName.INFO = COSName.get_pdf_name("Info")  # type: ignore[attr-defined]
COSName.ENCRYPT = COSName.get_pdf_name("Encrypt")  # type: ignore[attr-defined]
COSName.ID = COSName.get_pdf_name("ID")  # type: ignore[attr-defined]
COSName.LINEARIZED = COSName.get_pdf_name("Linearized")  # type: ignore[attr-defined]
COSName.SIZE = COSName.get_pdf_name("Size")  # type: ignore[attr-defined]
COSName.PREV = COSName.get_pdf_name("Prev")  # type: ignore[attr-defined]
COSName.PAGES = COSName.get_pdf_name("Pages")  # type: ignore[attr-defined]
COSName.PAGE = COSName.get_pdf_name("Page")  # type: ignore[attr-defined]
COSName.KIDS = COSName.get_pdf_name("Kids")  # type: ignore[attr-defined]
COSName.COUNT = COSName.get_pdf_name("Count")  # type: ignore[attr-defined]
COSName.PARENT = COSName.get_pdf_name("Parent")  # type: ignore[attr-defined]
COSName.RESOURCES = COSName.get_pdf_name("Resources")  # type: ignore[attr-defined]
COSName.MEDIA_BOX = COSName.get_pdf_name("MediaBox")  # type: ignore[attr-defined]
COSName.CONTENTS = COSName.get_pdf_name("Contents")  # type: ignore[attr-defined]
COSName.CATALOG = COSName.get_pdf_name("Catalog")  # type: ignore[attr-defined]
COSName.STRUCT_TREE_ROOT = COSName.get_pdf_name("StructTreeRoot")  # type: ignore[attr-defined]
COSName.METADATA = COSName.get_pdf_name("Metadata")  # type: ignore[attr-defined]
# Single-letter / short names referenced by upstream tests and a handful of
# PDF spec-defined keys. Keep this list minimal — grow on demand.
COSName.A = COSName.get_pdf_name("A")  # type: ignore[attr-defined]
COSName.B = COSName.get_pdf_name("B")  # type: ignore[attr-defined]
COSName.C = COSName.get_pdf_name("C")  # type: ignore[attr-defined]
COSName.D = COSName.get_pdf_name("D")  # type: ignore[attr-defined]
COSName.T = COSName.get_pdf_name("T")  # type: ignore[attr-defined]
COSName.BE = COSName.get_pdf_name("BE")  # type: ignore[attr-defined]
COSName.PARAMS = COSName.get_pdf_name("Params")  # type: ignore[attr-defined]
COSName.FLATE_DECODE = COSName.get_pdf_name("FlateDecode")  # type: ignore[attr-defined]
COSName.ASCII85_DECODE = COSName.get_pdf_name("ASCII85Decode")  # type: ignore[attr-defined]
COSName.STANDARD_ENCODING = COSName.get_pdf_name("StandardEncoding")  # type: ignore[attr-defined]
COSName.MAC_EXPERT_ENCODING = COSName.get_pdf_name("MacExpertEncoding")  # type: ignore[attr-defined]
COSName.MAC_ROMAN_ENCODING = COSName.get_pdf_name("MacRomanEncoding")  # type: ignore[attr-defined]
COSName.WIN_ANSI_ENCODING = COSName.get_pdf_name("WinAnsiEncoding")  # type: ignore[attr-defined]
COSName.FIRST_CHAR = COSName.get_pdf_name("FirstChar")  # type: ignore[attr-defined]
COSName.LAST_CHAR = COSName.get_pdf_name("LastChar")  # type: ignore[attr-defined]
COSName.WIDTHS = COSName.get_pdf_name("Widths")  # type: ignore[attr-defined]
