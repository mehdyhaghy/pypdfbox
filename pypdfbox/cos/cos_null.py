from __future__ import annotations

from typing import IO, Any, ClassVar

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor

# The five literal bytes the writer emits for ``null``. Held as a module-level
# constant to mirror PDFBox's ``COSNull.NULL_BYTES`` byte array.
_NULL_BYTES: bytes = b"null"


class COSNull(COSBase):
    """PDF null object. Single canonical instance ``COSNull.NULL``."""

    NULL: ClassVar[COSNull]
    _initialized: ClassVar[bool] = False

    def __init__(self) -> None:
        if COSNull._initialized:
            raise RuntimeError("Use COSNull.NULL")
        super().__init__()

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_null(self)

    def write_pdf(self, output: IO[bytes]) -> None:
        """Write the literal ``null`` token to *output*.

        Mirrors PDFBox's ``COSNull.writePDF(OutputStream)``. Placeholder until
        the dedicated ``COSWriter`` path takes over — the writer does not call
        this directly today, but providing the method keeps API parity for
        callers that bypass the visitor.
        """
        output.write(_NULL_BYTES)

    def get_value(self) -> None:
        """Return Python ``None`` — mirrors ``COSNull.getValue()``."""
        return None

    @staticmethod
    def is_null(value: Any) -> bool:
        """Return ``True`` iff *value* is the canonical ``COSNull.NULL`` instance.

        Mirrors PDFBox's ``COSNull.isNull(Object)`` static helper. Python
        ``None`` deliberately returns ``False``: the COS layer treats
        ``COSNull`` as a real PDF object distinct from "missing".
        """
        return value is COSNull.NULL

    def __bool__(self) -> bool:
        # PDF null is falsy in boolean contexts (matches Python None).
        return False

    def __eq__(self, other: object) -> bool:
        # Singleton: every COSNull instance is the same instance, but we still
        # implement value equality so subclassing or accidental duplicate
        # construction in tests doesn't bite. Python ``None`` is intentionally
        # NOT equal — see ``is_null`` for the rationale.
        if isinstance(other, COSNull):
            return True
        return NotImplemented

    def __hash__(self) -> int:
        # All COSNull instances hash the same — singleton-friendly.
        return hash("COSNull")

    def __repr__(self) -> str:
        return "COSNull.NULL"

    def to_string(self) -> str:
        """Mirror upstream ``COSNull.toString()`` — returns the literal
        ``"COSNull{}"`` string. Distinct from Python's :meth:`__str__`
        (which inherits the default ``repr``-style format from
        :class:`COSBase`); kept as an explicit method so callers porting
        Java code that calls ``cosNull.toString()`` get byte-identical
        output."""
        return "COSNull{}"


COSNull.NULL = COSNull()
COSNull._initialized = True
