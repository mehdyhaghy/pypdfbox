from __future__ import annotations

from typing import Any

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


class COSName(COSBase):
    """
    PDF name object (e.g. ``/Type``, ``/Pages``). Names are interned: any
    two ``COSName.get_pdf_name(s)`` calls with the same string return the
    same instance, so equality and ``is`` are interchangeable.

    PDF 1.2+ encodes the name as UTF-8 with ``#xx`` escapes for special
    bytes. The stored ``name`` here is the decoded logical string (without
    the leading ``/`` and without ``#xx`` escaping); encoding/decoding for
    the wire format is the writer/parser's responsibility.
    """

    _registry: dict[str, COSName] = {}

    __slots__ = ("_name", "_direct", "_needs_to_be_updated")

    def __new__(cls, name: str) -> COSName:
        existing = cls._registry.get(name)
        if existing is not None:
            return existing
        inst = super().__new__(cls)
        cls._registry[name] = inst
        return inst

    def __init__(self, name: str) -> None:
        # Re-init guard: __new__ may return an interned instance.
        if getattr(self, "_name", None) is not None:
            return
        super().__init__()
        self._name = name

    @classmethod
    def get_pdf_name(cls, name: str) -> COSName:
        """Canonical accessor — returns the interned instance."""
        return cls(name)

    @property
    def name(self) -> str:
        return self._name

    def get_name(self) -> str:
        return self._name

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_name(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSName):
            return self._name == other._name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)

    def __repr__(self) -> str:
        return f"COSName({self._name!r})"

    def __str__(self) -> str:
        return f"/{self._name}"


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
