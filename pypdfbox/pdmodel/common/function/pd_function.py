from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

_FUNCTION_TYPE = "FunctionType"
_DOMAIN = "Domain"
_RANGE = "Range"


class PDFunction:
    """
    Base PDF function wrapper. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunction``.

    A PDFunction wraps either a ``COSDictionary`` (Type 2, 3) or a
    ``COSStream`` (Type 0, 4). The dictionary/stream provides ``/FunctionType``,
    ``/Domain``, and (for sampled / output-clipped functions) ``/Range``.

    Function evaluation (``eval(input)``) and PostScript-calculator parsing
    are deferred — see ``CHANGES.md``. This lite port covers the structural
    accessors needed by callers that introspect or build function dictionaries
    (e.g. shading dictionaries, tint transforms).
    """

    def __init__(self, function: COSBase | None = None) -> None:
        if function is None:
            self._function_dictionary: COSDictionary = COSDictionary()
            self._function_stream: PDStream | None = None
        elif isinstance(function, COSStream):
            self._function_stream = PDStream(function)
            self._function_dictionary = function
        elif isinstance(function, COSDictionary):
            self._function_dictionary = function
            self._function_stream = None
        else:
            raise TypeError(
                "PDFunction expects COSDictionary or COSStream, "
                f"got {type(function).__name__}"
            )

    # ---------- factory ----------

    @staticmethod
    def create(function: COSBase | None) -> PDFunction | None:
        """Dispatch on ``/FunctionType`` to the concrete subclass.

        Returns ``None`` if ``function`` is ``None``. Raises ``ValueError``
        for an unsupported function type so callers can distinguish a missing
        function from an invalid one (mirrors upstream ``IOException``).
        """
        # Local imports to avoid circular references.
        from .pd_function_type0 import PDFunctionType0
        from .pd_function_type2 import PDFunctionType2
        from .pd_function_type3 import PDFunctionType3
        from .pd_function_type4 import PDFunctionType4

        if function is None:
            return None
        if not isinstance(function, (COSDictionary, COSStream)):
            raise TypeError(
                "PDFunction.create expects COSDictionary or COSStream, "
                f"got {type(function).__name__}"
            )
        function_type = function.get_int(_FUNCTION_TYPE, -1)
        if function_type == 0:
            return PDFunctionType0(function)
        if function_type == 2:
            return PDFunctionType2(function)
        if function_type == 3:
            return PDFunctionType3(function)
        if function_type == 4:
            return PDFunctionType4(function)
        raise ValueError(f"Unsupported /FunctionType value: {function_type}")

    # ---------- core ----------

    def get_cos_object(self) -> COSDictionary:
        return self._function_dictionary

    def get_pd_stream(self) -> PDStream | None:
        """Returns the underlying ``PDStream`` for stream-backed functions
        (Type 0 and Type 4); ``None`` for dictionary-backed functions."""
        return self._function_stream

    def get_function_type(self) -> int:
        """Subclasses override with their concrete type number (0, 2, 3, 4)."""
        raise NotImplementedError("PDFunction subclasses must implement get_function_type")

    # ---------- /Domain ----------

    def get_domain(self) -> COSArray | None:
        item = self._function_dictionary.get_dictionary_object(_DOMAIN)
        if isinstance(item, COSArray):
            return item
        return None

    def set_domain(self, domain: COSArray | None) -> None:
        if domain is None:
            self._function_dictionary.remove_item(_DOMAIN)
        else:
            self._function_dictionary.set_item(_DOMAIN, domain)

    def get_number_of_input_parameters(self) -> int:
        """Pairs in ``/Domain`` — one (min, max) per input dimension."""
        domain = self.get_domain()
        if domain is None:
            return 0
        return domain.size() // 2

    # ---------- /Range ----------

    def get_range(self) -> COSArray | None:
        item = self._function_dictionary.get_dictionary_object(_RANGE)
        if isinstance(item, COSArray):
            return item
        return None

    def set_range(self, value: COSArray | None) -> None:
        if value is None:
            self._function_dictionary.remove_item(_RANGE)
        else:
            self._function_dictionary.set_item(_RANGE, value)

    def get_number_of_output_parameters(self) -> int:
        """Pairs in ``/Range`` — one (min, max) per output dimension. Returns
        ``0`` when ``/Range`` is absent (legal for Type 2 / 3 per PDF 32000-1
        §7.10.3)."""
        rng = self.get_range()
        if rng is None:
            return 0
        return rng.size() // 2


__all__ = ["PDFunction"]
