from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .operator import Operator
    from .operator_name import OperatorName
    from .operator_processor import (
        MissingOperandException,
        OperatorProcessor,
    )
    from .pd_content_stream import PDContentStream
    from .pdf_graphics_stream_engine import (
        WIND_EVEN_ODD,
        WIND_NON_ZERO,
        PDFGraphicsStreamEngine,
    )
    from .pdf_stream_engine import PDFStreamEngine

__getattr__, __dir__ = _attach(
    __name__,
    {
        "Operator": ".operator",
        "OperatorName": ".operator_name",
        "MissingOperandException": ".operator_processor",
        "OperatorProcessor": ".operator_processor",
        "PDContentStream": ".pd_content_stream",
        "WIND_EVEN_ODD": ".pdf_graphics_stream_engine",
        "WIND_NON_ZERO": ".pdf_graphics_stream_engine",
        "PDFGraphicsStreamEngine": ".pdf_graphics_stream_engine",
        "PDFStreamEngine": ".pdf_stream_engine",
    },
)

__all__ = [
    "MissingOperandException",
    "Operator",
    "OperatorName",
    "OperatorProcessor",
    "PDContentStream",
    "PDFGraphicsStreamEngine",
    "PDFStreamEngine",
    "WIND_EVEN_ODD",
    "WIND_NON_ZERO",
]
