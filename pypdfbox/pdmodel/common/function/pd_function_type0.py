from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase

from .pd_function import PDFunction

_SIZE = "Size"
_BITS_PER_SAMPLE = "BitsPerSample"
_ORDER = "Order"
_ENCODE = "Encode"
_DECODE = "Decode"


class PDFunctionType0(PDFunction):
    """
    Type 0 (sampled) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType0``.

    Backed by a ``COSStream`` whose binary body holds the sample table.
    Sample-table decoding and ``eval`` are deferred — this lite port exposes
    the structural keys (``/Size``, ``/BitsPerSample``, ``/Order``,
    ``/Encode``, ``/Decode``) needed by writers and introspection.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)

    def get_function_type(self) -> int:
        return 0

    def get_size(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_SIZE)
        if isinstance(item, COSArray):
            return item
        return None

    def get_bits_per_sample(self) -> int:
        return self.get_cos_object().get_int(_BITS_PER_SAMPLE, 0)

    def get_order(self) -> int:
        """PDF default is 1 (linear) when ``/Order`` is absent."""
        return self.get_cos_object().get_int(_ORDER, 1)

    def get_encode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_ENCODE)
        if isinstance(item, COSArray):
            return item
        return None

    def get_decode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_DECODE)
        if isinstance(item, COSArray):
            return item
        return None


__all__ = ["PDFunctionType0"]
