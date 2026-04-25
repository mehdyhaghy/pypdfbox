from __future__ import annotations

from typing import Any, ClassVar

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


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

    @property
    def value(self) -> bool:
        return self._value

    def get_value(self) -> bool:
        return self._value

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_boolean(self)

    def __bool__(self) -> bool:
        return self._value

    def __repr__(self) -> str:
        return "COSBoolean.TRUE" if self._value else "COSBoolean.FALSE"


COSBoolean.TRUE = COSBoolean(True)
COSBoolean.FALSE = COSBoolean(False)
COSBoolean._initialized = True
