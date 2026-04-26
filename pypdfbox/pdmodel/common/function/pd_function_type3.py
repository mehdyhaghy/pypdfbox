from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase

from .pd_function import PDFunction

_FUNCTIONS = "Functions"
_BOUNDS = "Bounds"
_ENCODE = "Encode"


class PDFunctionType3(PDFunction):
    """
    Type 3 (stitching) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType3``.

    Combines a sequence of 1-input subfunctions over partitioned subdomains
    of ``/Domain``. Defining keys: ``/Functions`` (the subfunction array),
    ``/Bounds`` (subdomain boundaries), and ``/Encode`` (per-subfunction
    input mapping). Subfunction selection / eval is deferred.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)

    def get_function_type(self) -> int:
        return 3

    def get_functions(self) -> list[PDFunction]:
        """Each ``/Functions`` entry is wrapped via ``PDFunction.create``.
        Entries that are not COSDictionary/COSStream are skipped."""
        item = self.get_cos_object().get_dictionary_object(_FUNCTIONS)
        out: list[PDFunction] = []
        if not isinstance(item, COSArray):
            return out
        for i in range(item.size()):
            entry = item.get_object(i)
            if entry is None:
                continue
            sub = PDFunction.create(entry)
            if sub is not None:
                out.append(sub)
        return out

    def get_bounds(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_BOUNDS)
        if isinstance(item, COSArray):
            return item
        return None

    def get_encode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_ENCODE)
        if isinstance(item, COSArray):
            return item
        return None


__all__ = ["PDFunctionType3"]
