from __future__ import annotations

from typing import Any, ClassVar

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


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

    def __repr__(self) -> str:
        return "COSNull.NULL"


COSNull.NULL = COSNull()
COSNull._initialized = True
