from __future__ import annotations

from pypdfbox.cos import COSBase

from .pd_function import PDFunction


class PDFunctionType4(PDFunction):
    """
    Type 4 (PostScript calculator) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType4``.

    The function body is a PostScript-calculator expression stored in the
    underlying ``COSStream``. Parsing into an instruction sequence and
    evaluation are deferred — see ``CHANGES.md``. This lite port only
    identifies the function type and exposes the underlying stream via
    ``get_pd_stream()``.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)

    def get_function_type(self) -> int:
        return 4


__all__ = ["PDFunctionType4"]
