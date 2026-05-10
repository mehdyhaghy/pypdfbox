from __future__ import annotations

from typing import IO, Any, ClassVar

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor

# Literal byte tokens emitted by ``write_pdf`` — mirrors PDFBox's
# ``TRUE_BYTES`` / ``FALSE_BYTES`` ISO-8859-1 byte arrays.
_TRUE_BYTES: bytes = b"true"
_FALSE_BYTES: bytes = b"false"


class COSBoolean(COSBase):
    """
    PDF boolean object. Two canonical instances exist — ``COSBoolean.TRUE``
    and ``COSBoolean.FALSE``; constructors are private-by-convention.
    """

    TRUE: ClassVar[COSBoolean]
    FALSE: ClassVar[COSBoolean]
    _initialized: ClassVar[bool] = False

    def __init__(self, value: bool) -> None:
        if COSBoolean._initialized:
            raise RuntimeError("Use COSBoolean.TRUE / COSBoolean.FALSE")
        super().__init__()
        self._value = value

    @classmethod
    def get(cls, value: bool) -> COSBoolean:
        return cls.TRUE if value else cls.FALSE

    @classmethod
    def get_boolean(cls, value: bool) -> COSBoolean:
        """Upstream-named factory mirroring ``COSBoolean.getBoolean(boolean)``."""
        return cls.TRUE if value else cls.FALSE

    @property
    def value(self) -> bool:
        return self._value

    def get_value(self) -> bool:
        return self._value

    def get_value_as_object(self) -> bool:
        """Mirror PDFBox's ``getValueAsObject()``.

        Java distinguishes ``boolean`` from boxed ``Boolean``; in Python the
        two are the same type, so this is a thin alias of ``get_value`` kept
        for API parity.
        """
        return self._value

    def is_true(self) -> bool:
        return self._value is True

    def is_false(self) -> bool:
        return self._value is False

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_boolean(self)

    def write_pdf(self, output: IO[bytes]) -> None:
        """Write the literal ``true`` / ``false`` token to *output*.

        Mirrors PDFBox's ``COSBoolean.writePDF(OutputStream)``.
        """
        output.write(_TRUE_BYTES if self._value else _FALSE_BYTES)

    def equals(self, other: object) -> bool:
        """Java-style equality predicate. Mirrors ``COSBoolean.equals(Object)``.

        Upstream uses ``this == obj`` (reference equality) since only the two
        canonical singletons ever exist; we do the same with ``is``.
        """
        return self is other

    def hash_code(self) -> int:
        """Mirror Java's ``COSBoolean.hashCode()``.

        PDFBox copies the ``java.lang.Boolean`` recipe verbatim — ``1231`` for
        ``true`` and ``1237`` for ``false``.
        """
        return 1231 if self._value else 1237

    def to_string(self) -> str:
        """Mirror Java's ``COSBoolean.toString()`` — ``String.valueOf(value)``,
        i.e. the lowercase ``"true"`` / ``"false"`` literal.
        """
        return "true" if self._value else "false"

    def __bool__(self) -> bool:
        return self._value

    def __repr__(self) -> str:
        return "COSBoolean.TRUE" if self._value else "COSBoolean.FALSE"


COSBoolean.TRUE = COSBoolean(True)
COSBoolean.FALSE = COSBoolean(False)
COSBoolean._initialized = True
