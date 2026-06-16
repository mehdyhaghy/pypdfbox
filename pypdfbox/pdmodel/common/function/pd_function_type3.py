from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSNumber,
    COSStream,
)

from .pd_function import PDFunction

_FUNCTIONS = "Functions"
_BOUNDS = "Bounds"
_ENCODE = "Encode"


def _float_compare(a: float, b: float) -> int:
    """Port of Java ``Float.compare(float, float)`` for the single comparison
    Type 3 eval needs — the last-interval boundary test ``x == partition[last]``.

    Returns ``-1`` / ``0`` / ``+1``. NaN sorts greater than everything (so a NaN
    input never equality-matches the closing bound), matching upstream."""
    if a < b:
        return -1
    if a > b:
        return 1
    a_nan = a != a
    b_nan = b != b
    if a_nan and b_nan:
        return 0
    if a_nan:
        return 1
    if b_nan:
        return -1
    return 0


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
            # ``create`` only returns None for a None / unresolved-COSObject
            # argument; an entry that already passed the dict/stream check
            # above always yields a function or raises, so the None arm is
            # defensive and never taken here.
            sub = PDFunction.create(entry)
            if sub is not None:  # pragma: no branch
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
        if n < 0:
            return None
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

    def get_bounds_values(self) -> list[float]:
        """Return ``/Bounds`` as a flat ``list[float]`` (empty when absent /
        malformed). Mirrors upstream ``PDFunctionType3.boundsValues`` — a
        cached float array materialised on first ``eval`` from
        ``getBounds().toFloatArray()``. Exposed as a public accessor here so
        callers building stitching dictionaries can introspect partition
        boundaries without depending on eval side-effects."""
        bounds = self.get_bounds()
        if bounds is None:
            return []
        return bounds.to_float_array()

    def get_encode_values(self) -> list[float]:
        """Return ``/Encode`` as a flat ``list[float]`` (empty when absent /
        malformed).

        This mirrors :meth:`get_bounds_values` for callers that need to
        inspect or validate the stitching dictionary without reaching into
        the raw COS array or recomputing per-subfunction offsets.
        """
        encode = self.get_encode()
        if encode is None:
            return []
        return encode.to_float_array()

    def get_number_of_functions(self) -> int:
        """Return the count of subfunctions in ``/Functions`` — i.e. the
        number of partitions the stitching function dispatches across.
        Returns ``0`` when ``/Functions`` is absent or not a ``COSArray``.

        No exact upstream equivalent (PDFBox callers read
        ``getFunctions().size()``); added for symmetry with
        :meth:`PDFunction.get_number_of_input_parameters` /
        :meth:`PDFunction.get_number_of_output_parameters`."""
        arr = self.get_functions_array()
        if arr is None:
            return 0
        return arr.size()

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

    @staticmethod
    def _clip_to_range_scalar(x: float, range_min: float, range_max: float) -> float:
        """Non-normalising scalar clamp — direct port of upstream
        ``PDFunction.clipToRange(float, float, float)`` (PDFunction.java).

        Unlike :meth:`PDFunction.clip_value_to_range`, this does **not** swap a
        reversed ``(min, max)`` pair: ``if x < range_min -> range_min``;
        ``if x > range_max -> range_max``; else ``x``. Type 3 eval relies on
        this exact (un-normalised) behaviour so a reversed ``/Domain`` produces
        the same "partition not found" failure as upstream rather than silently
        evaluating against a normalised interval."""
        if x < range_min:
            return range_min
        if x > range_max:
            return range_max
        return x

    def _encode_pair(self, n: int) -> tuple[float, float]:
        """Return the ``(min, max)`` ``/Encode`` pair for subfunction ``n``.

        Mirrors upstream ``getEncodeForParameter(int)`` =
        ``new PDRange(getEncode(), n).getMin()/getMax()``, which reads
        ``encode[2n]`` / ``encode[2n+1]`` and casts each to ``COSNumber``.
        Raises ``ValueError`` when ``/Encode`` is absent, too short, or carries
        a non-numeric entry at either index — upstream raises ``NPE`` /
        ``ClassCastException`` (surfaced as eval failure) on the same inputs.
        Defensive ``[0, 1]`` defaults are *not* used: that would make pypdfbox
        accept malformed ``/Encode`` arrays upstream rejects."""
        encode = self.get_encode()
        if encode is None:
            raise ValueError("PDFunctionType3 /Encode is absent")
        lo = encode.get_object(2 * n) if 2 * n < encode.size() else None
        hi = encode.get_object(2 * n + 1) if 2 * n + 1 < encode.size() else None
        if not isinstance(lo, COSNumber) or not isinstance(hi, COSNumber):
            raise ValueError(
                f"PDFunctionType3 /Encode missing numeric pair for subfunction {n}"
            )
        return (float(lo.float_value()), float(hi.float_value()))

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Stitching evaluation per PDF 32000-1 §7.10.4.

        Faithful port of upstream ``PDFunctionType3.eval(float[])``:

        * Clip ``input[0]`` to ``/Domain`` (non-normalising —
          :meth:`_clip_to_range_scalar`).
        * Materialise every ``/Functions`` entry via ``PDFunction.create``.
        * **Single subfunction:** dispatch to it directly, interpolating the
          input across the *whole* ``/Domain`` into ``/Encode`` pair 0;
          ``/Bounds`` is ignored entirely (no length validation).
        * **Multiple subfunctions:** build a partition array
          ``[domain_min, *bounds, domain_max]`` and select interval ``i`` where
          ``x >= partition[i]`` and (``x < partition[i+1]`` or ``i`` is the last
          interval and ``x == partition[i+1]``); interpolate over
          ``[partition[i], partition[i+1]]`` into ``/Encode`` pair ``i``.
        * If no interval matches, raise ``ValueError`` ("partition not found").
        """
        if not input:
            raise IndexError("PDFunctionType3.eval requires at least one input")
        x = input[0]

        domain_ranges = self.get_ranges_for_inputs()
        if not domain_ranges:
            # Upstream getDomainForInput(0) dereferences a null /Domain -> NPE.
            raise ValueError("PDFunctionType3.eval requires /Domain to be defined")
        domain_lo, domain_hi = domain_ranges[0]
        x = self._clip_to_range_scalar(x, domain_lo, domain_hi)

        # Build the typed subfunction array exactly as upstream does — every
        # /Functions entry passes through PDFunction.create (a malformed child
        # raises here, surfacing as an eval failure). A null /Functions array
        # mirrors upstream's NPE on getFunctions().size().
        functions_array = self.get_functions_array()
        if functions_array is None:
            raise ValueError("PDFunctionType3 /Functions is absent or not an array")
        functions: list[PDFunction | None] = []
        for i in range(functions_array.size()):
            functions.append(PDFunction.create(functions_array.get_object(i)))

        selected: PDFunction | None = None

        if len(functions) == 1:
            # Single subfunction: ignore /Bounds, encode over the whole domain.
            selected = functions[0]
            enc_lo, enc_hi = self._encode_pair(0)
            x = self.interpolate(x, domain_lo, domain_hi, enc_lo, enc_hi)
        else:
            bounds_arr = self.get_bounds()
            bounds: list[float] = (
                bounds_arr.to_float_array() if bounds_arr is not None else []
            )
            # partition = [domain_lo, *bounds, domain_hi]
            partition = [domain_lo, *bounds, domain_hi]
            n_intervals = len(partition) - 1
            for i in range(n_intervals):
                # Upstream uses ``x >= partition[i]`` as the entry test, which
                # is NaN-correct: ``NaN >= anything`` is false, so a NaN input or
                # a NaN partition bound makes every interval miss and the function
                # raises "partition not found" (oracle-confirmed wave 1544:
                # ``t3_nan_bound`` => eval ERR). The earlier ``if x < partition[i]:
                # continue`` form inverted this incorrectly — ``NaN < bound`` is
                # also false, so it fell through and evaluated against a NaN
                # interval instead of skipping.
                if not (x >= partition[i]):
                    continue
                is_last = i == n_intervals - 1
                if x < partition[i + 1] or (
                    is_last and _float_compare(x, partition[i + 1]) == 0
                ):
                    selected = functions[i]
                    enc_lo, enc_hi = self._encode_pair(i)
                    x = self.interpolate(
                        x, partition[i], partition[i + 1], enc_lo, enc_hi
                    )
                    break

        if selected is None:
            raise ValueError("partition not found in type 3 function")

        result = selected.eval([x])
        return self.clip_output(result)


__all__ = ["PDFunctionType3"]
