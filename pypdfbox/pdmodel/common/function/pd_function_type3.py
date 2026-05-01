from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSStream

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
    input mapping). ``eval`` selects the partition that ``input[0]`` falls
    into, linearly maps the input through the matching ``/Encode`` pair,
    and dispatches to the matching child function.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)

    def get_function_type(self) -> int:
        return 3

    def get_functions(self) -> list[PDFunction]:
        """Each ``/Functions`` entry is wrapped via ``PDFunction.create``.
        Entries that are not COSDictionary/COSStream are skipped.

        Upstream returns the raw ``COSArray`` here; this port returns a
        materialised list of typed wrappers because that is the typical
        consumer (eval dispatch, shading renderers). Use
        :meth:`get_functions_array` for the raw COSArray.
        """
        item = self.get_cos_object().get_dictionary_object(_FUNCTIONS)
        out: list[PDFunction] = []
        if not isinstance(item, COSArray):
            return out
        for i in range(item.size()):
            entry = item.get_object(i)
            if not isinstance(entry, (COSDictionary, COSStream)):
                continue
            sub = PDFunction.create(entry)
            if sub is not None:
                out.append(sub)
        return out

    def get_functions_array(self) -> COSArray | None:
        """Return the raw ``/Functions`` ``COSArray`` (or ``None`` when
        absent / malformed). Mirrors upstream ``PDFunctionType3.getFunctions()``
        which returns ``COSArray`` directly. Use :meth:`get_functions` for
        a materialised list of typed :class:`PDFunction` wrappers."""
        item = self.get_cos_object().get_dictionary_object(_FUNCTIONS)
        if isinstance(item, COSArray):
            return item
        return None

    def get_encode_for_parameter(self, n: int) -> tuple[float, float] | None:
        """Return the ``(encode_min, encode_max)`` ``/Encode`` pair for
        subfunction ``n``. Returns ``None`` when ``/Encode`` is absent or
        does not cover index ``n``. Mirrors upstream private helper
        ``getEncodeForParameter(int)``; exposed publicly here so callers
        building stitching dictionaries can introspect per-subfunction
        encode ranges without recomputing the offset arithmetic."""
        encode = self.get_encode()
        if encode is None:
            return None
        flat = encode.to_float_array()
        if 2 * n + 1 >= len(flat):
            return None
        return (flat[2 * n], flat[2 * n + 1])

    def set_functions(self, functions: COSArray | None) -> None:
        """Replace ``/Functions`` with the supplied COSArray, or remove the key
        when ``None``. Mirrors PDFBox ``setFunctions(COSArray)``."""
        if functions is None:
            self.get_cos_object().remove_item(_FUNCTIONS)
        else:
            self.get_cos_object().set_item(_FUNCTIONS, functions)

    def get_bounds(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_BOUNDS)
        if isinstance(item, COSArray):
            return item
        return None

    def set_bounds(self, bounds: COSArray | None) -> None:
        """Replace ``/Bounds`` with the supplied COSArray, or remove the key
        when ``None``. Mirrors PDFBox ``setBounds(COSArray)``."""
        if bounds is None:
            self.get_cos_object().remove_item(_BOUNDS)
        else:
            self.get_cos_object().set_item(_BOUNDS, bounds)

    def get_encode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_ENCODE)
        if isinstance(item, COSArray):
            return item
        return None

    def set_encode(self, encode: COSArray | None) -> None:
        """Replace ``/Encode`` with the supplied COSArray, or remove the key
        when ``None``. Mirrors PDFBox ``setEncode(COSArray)``."""
        if encode is None:
            self.get_cos_object().remove_item(_ENCODE)
        else:
            self.get_cos_object().set_item(_ENCODE, encode)

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
