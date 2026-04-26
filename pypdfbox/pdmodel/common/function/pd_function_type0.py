from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSStream

from .pd_function import PDFunction

_SIZE = "Size"
_BITS_PER_SAMPLE = "BitsPerSample"
_ORDER = "Order"
_ENCODE = "Encode"
_DECODE = "Decode"

# Supported /BitsPerSample values per PDF 32000-1 §7.10.2 Table 38.
# Cubic-spline interpolation (/Order = 3) is not implemented; we silently
# fall back to linear (/Order = 1) per PDFBox parity.
_SUPPORTED_BITS = frozenset({1, 2, 4, 8, 16, 24, 32})


class PDFunctionType0(PDFunction):
    """
    Type 0 (sampled) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType0``.

    Backed by a ``COSStream`` whose binary body holds the sample table.
    Evaluation reads the surrounding 2^n samples for an n-dimensional input
    and combines them with n-linear interpolation per PDF 32000-1 §7.10.2.
    Cubic-spline interpolation (``/Order = 3``) is deferred — we fall back
    to linear (``/Order = 1``) regardless of the dictionary value.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)
        # Decoded sample-table body; populated lazily on first eval to
        # amortise filter-chain decode across repeated evaluations.
        self._sample_bytes: bytes | None = None

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

    # ---------- evaluation ----------

    def _get_sample_bytes(self) -> bytes:
        """Decoded body bytes — cached after first read."""
        if self._sample_bytes is None:
            stream = self.get_pd_stream()
            if stream is None:
                # Dictionary-only construction (no body) — empty table.
                self._sample_bytes = b""
            else:
                cos = stream.get_cos_object()
                if isinstance(cos, COSStream):
                    self._sample_bytes = cos.to_byte_array()
                else:  # pragma: no cover - PDStream always wraps COSStream
                    self._sample_bytes = b""
        return self._sample_bytes

    def _get_size_list(self) -> list[int]:
        size = self.get_size()
        if size is None:
            return []
        out: list[int] = []
        for i in range(size.size()):
            item = size.get(i)
            try:
                out.append(int(item.float_value()))  # type: ignore[union-attr]
            except AttributeError:
                out.append(0)
        return out

    def _get_encode_pairs(self, num_in: int, sizes: list[int]) -> list[tuple[float, float]]:
        """``/Encode`` paired ``(min, max)``; default per dim = ``(0, Size[i]-1)``."""
        encode = self.get_encode()
        if encode is None:
            return [(0.0, max(0.0, sizes[i] - 1)) for i in range(num_in)]
        flat = encode.to_float_array()
        pairs: list[tuple[float, float]] = []
        for i in range(num_in):
            if 2 * i + 1 < len(flat):
                pairs.append((flat[2 * i], flat[2 * i + 1]))
            else:
                pairs.append((0.0, max(0.0, sizes[i] - 1)))
        return pairs

    def _get_decode_pairs(self, num_out: int) -> list[tuple[float, float]]:
        """``/Decode`` paired ``(min, max)``; default = ``/Range``."""
        decode = self.get_decode()
        if decode is None:
            return self.get_ranges_for_outputs()[:num_out] or [
                (0.0, 0.0) for _ in range(num_out)
            ]
        flat = decode.to_float_array()
        rng_pairs = self.get_ranges_for_outputs()
        pairs: list[tuple[float, float]] = []
        for j in range(num_out):
            if 2 * j + 1 < len(flat):
                pairs.append((flat[2 * j], flat[2 * j + 1]))
            elif j < len(rng_pairs):
                pairs.append(rng_pairs[j])
            else:
                pairs.append((0.0, 0.0))
        return pairs

    def _read_sample(
        self,
        coords: tuple[int, ...],
        output_index: int,
        sizes: list[int],
        num_outputs: int,
        bits: int,
        body: bytes,
    ) -> int:
        """Read one sample value at integer ``coords`` for output ``output_index``.

        Sample layout per §7.10.2: the table is row-major over input
        dimensions (first dim varies fastest), with ``num_outputs`` samples
        per cell, each ``bits`` wide and packed MSB-first big-endian.
        """
        # Linearise coords → cell index. PDF spec: first dim varies fastest.
        linear = 0
        stride = 1
        for i, c in enumerate(coords):
            linear += c * stride
            stride *= sizes[i]
        bit_offset = (linear * num_outputs + output_index) * bits

        if bits % 8 == 0:
            byte_offset = bit_offset // 8
            byte_count = bits // 8
            chunk = body[byte_offset : byte_offset + byte_count]
            if len(chunk) < byte_count:
                # Out-of-range read → treat as zero (lenient).
                return 0
            return int.from_bytes(chunk, "big")

        # Sub-byte bits: 1, 2, or 4. Read across at most two bytes (since
        # bits <= 4 ≤ 8) MSB-first.
        byte_offset = bit_offset // 8
        bit_in_byte = bit_offset % 8
        if byte_offset >= len(body):
            return 0
        first = body[byte_offset]
        if bit_in_byte + bits <= 8:
            shift = 8 - bit_in_byte - bits
            return (first >> shift) & ((1 << bits) - 1)
        # Crosses a byte boundary (only possible for bits=2 starting at
        # bit-7 or bits=4 starting at bit-5/6/7; defensive).
        if byte_offset + 1 >= len(body):
            return 0
        second = body[byte_offset + 1]
        combined = (first << 8) | second
        shift = 16 - bit_in_byte - bits
        return (combined >> shift) & ((1 << bits) - 1)

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """N-linear interpolation over the sample table per §7.10.2.

        Cubic-spline (/Order = 3) is not implemented — falls back to linear.
        """
        num_in = self.get_number_of_input_parameters()
        num_out = self.get_number_of_output_parameters()
        bits = self.get_bits_per_sample()
        if num_in == 0 or num_out == 0:
            raise ValueError("PDFunctionType0 requires /Domain and /Range")
        if bits not in _SUPPORTED_BITS:
            raise ValueError(
                f"unsupported /BitsPerSample={bits}; expected one of {sorted(_SUPPORTED_BITS)}"
            )

        sizes = self._get_size_list()
        if len(sizes) < num_in or any(s < 1 for s in sizes[:num_in]):
            raise ValueError("/Size missing or invalid for declared input dimensions")

        clipped = self.clip_input(input)
        domain = self.get_ranges_for_inputs()
        encode_pairs = self._get_encode_pairs(num_in, sizes)
        decode_pairs = self._get_decode_pairs(num_out)

        # Step 2 + 3: encode each clipped input then clamp to [0, Size[i]-1]
        # and split into floor + fractional part.
        floors: list[int] = []
        fracs: list[float] = []
        for i in range(num_in):
            d_lo, d_hi = domain[i]
            e_lo, e_hi = encode_pairs[i]
            if d_hi == d_lo:
                encoded = e_lo
            else:
                encoded = (clipped[i] - d_lo) * (e_hi - e_lo) / (d_hi - d_lo) + e_lo
            # Clamp encoded to [0, Size[i]-1] (§7.10.2 step "e' = min(max(...))")
            upper = sizes[i] - 1
            if encoded < 0.0:
                encoded = 0.0
            elif encoded > upper:
                encoded = float(upper)
            f = int(encoded)
            if f >= upper:
                # Sit at the right edge — no neighbour to the right; use frac=0.
                f = upper
                frac = 0.0
            else:
                frac = encoded - f
            floors.append(f)
            fracs.append(frac)

        body = self._get_sample_bytes()
        sample_max = (1 << bits) - 1

        # Step 4: read 2^n surrounding samples per output dim and n-linearly
        # interpolate. We fold one dim at a time: at iteration i we keep
        # 2^(n-i) interpolated values; final pass leaves a single value.
        output: list[float] = []
        n = num_in
        for j in range(num_out):
            # Gather all 2^n corner samples into a flat list. Index encodes
            # the binary corner offset: bit i = 0 → floor, bit i = 1 → ceil.
            corners: list[float] = []
            for mask in range(1 << n):
                coords = tuple(
                    floors[i] + ((mask >> i) & 1) for i in range(n)
                )
                corners.append(
                    float(
                        self._read_sample(
                            coords, j, sizes, num_out, bits, body
                        )
                    )
                )
            # Collapse one dimension at a time using the per-axis fraction.
            for i in range(n):
                t = fracs[i]
                next_corners: list[float] = []
                for k in range(0, len(corners), 2):
                    a, b = corners[k], corners[k + 1]
                    next_corners.append(a + t * (b - a))
                corners = next_corners
            sample = corners[0]
            # Step 5: map [0, 2^bits-1] → /Decode
            d_lo, d_hi = decode_pairs[j]
            if sample_max == 0:
                decoded = d_lo
            else:
                decoded = sample * (d_hi - d_lo) / sample_max + d_lo
            output.append(decoded)

        # Step 6: clip to /Range.
        return self.clip_output(output)


__all__ = ["PDFunctionType0"]
