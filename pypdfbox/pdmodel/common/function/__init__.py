from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_function import (
        PDFunction,
        PDFunctionTypeIdentity,
    )
    from .pd_function_type0 import PDFunctionType0
    from .pd_function_type2 import PDFunctionType2
    from .pd_function_type3 import PDFunctionType3
    from .pd_function_type4 import PDFunctionType4
    from .rinterpol import Rinterpol

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDFunction": ".pd_function",
        "PDFunctionTypeIdentity": ".pd_function",
        "PDFunctionType0": ".pd_function_type0",
        "PDFunctionType2": ".pd_function_type2",
        "PDFunctionType3": ".pd_function_type3",
        "PDFunctionType4": ".pd_function_type4",
        "Rinterpol": ".rinterpol",
    },
)

__all__ = [
    "PDFunction",
    "PDFunctionType0",
    "PDFunctionType2",
    "PDFunctionType3",
    "PDFunctionType4",
    "PDFunctionTypeIdentity",
    "Rinterpol",
]
