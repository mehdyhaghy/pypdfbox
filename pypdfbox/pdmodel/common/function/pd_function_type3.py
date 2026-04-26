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

    # ---------- evaluation ----------

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Stitching evaluation per PDF 32000-1 §7.10.4.

        Selects subfunction ``k`` based on which subdomain (built from
        ``/Domain`` and ``/Bounds``) the clipped input falls into, maps the
        input into that subfunction's encoded interval, then delegates.
        """
        clipped = self.clip_input(input)
        if not clipped:
            raise ValueError("PDFunctionType3.eval requires at least one input")
        x = clipped[0]

        functions = self.get_functions()
        if not functions:
            raise ValueError("PDFunctionType3 has no /Functions entries to dispatch to")

        domain_ranges = self.get_ranges_for_inputs()
        if not domain_ranges:
            raise ValueError("PDFunctionType3.eval requires /Domain to be defined")
        domain_lo, domain_hi = domain_ranges[0]

        bounds_arr = self.get_bounds()
        bounds: list[float] = bounds_arr.to_float_array() if bounds_arr is not None else []

        encode_arr = self.get_encode()
        encode: list[float] = encode_arr.to_float_array() if encode_arr is not None else []

        # Find subfunction index k. Per spec: x in [domain_lo, bounds[0]) -> 0,
        # [bounds[i-1], bounds[i]) -> i, [bounds[-1], domain_hi] -> last.
        k = len(functions) - 1
        for i, b in enumerate(bounds):
            if x < b:
                k = i
                break

        # Subdomain boundaries for interval k.
        sub_lo = domain_lo if k == 0 else bounds[k - 1]
        sub_hi = domain_hi if k >= len(bounds) else bounds[k]

        # Encoded target interval; default to [0, 1] per spec when /Encode short.
        enc_lo = encode[2 * k] if 2 * k < len(encode) else 0.0
        enc_hi = encode[2 * k + 1] if 2 * k + 1 < len(encode) else 1.0

        if sub_hi == sub_lo:
            mapped_x = enc_lo
        else:
            mapped_x = enc_lo + (x - sub_lo) * (enc_hi - enc_lo) / (sub_hi - sub_lo)

        result = functions[k].eval([mapped_x])
        return self.clip_output(result)


__all__ = ["PDFunctionType3"]
