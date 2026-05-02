from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSBase, COSStream

from .pd_function import PDFunction

_LOG = logging.getLogger(__name__)

_SIZE = "Size"
_BITS_PER_SAMPLE = "BitsPerSample"
_ORDER = "Order"
_ENCODE = "Encode"
_DECODE = "Decode"

# Supported /BitsPerSample values per PDF 32000-1 §7.10.2 Table 38.
_SUPPORTED_BITS = frozenset({1, 2, 4, 8, 12, 16, 24, 32})


class PDFunctionType0(PDFunction):
    """
    Type 0 (sampled) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType0``.

    Backed by a ``COSStream`` whose binary body holds the sample table.
    Evaluation reads the surrounding 2^n samples for an n-dimensional input
    and combines them with n-linear interpolation per PDF 32000-1 §7.10.2.
    Cubic-spline interpolation (``/Order = 3``) is implemented as a Catmull-
    Rom Hermite spline (4 surrounding samples per axis, edge-clamped). Any
    other ``/Order`` value falls back to linear with a debug log.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)
        # Decoded sample-table body; populated lazily on first eval to
        # amortise filter-chain decode across repeated evaluations.
        self._sample_bytes: bytes | None = None
        # Lazy decoded sample grid cache for get_samples(). int[][] in
        # upstream — outer index = linearised input cell, inner = output dim.
        self._samples_cache: list[list[int]] | None = None

    def get_function_type(self) -> int:
        return 0

    def get_size(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_SIZE)
        if isinstance(item, COSArray):
            return item
        return None

    def set_size(self, size: COSArray | None) -> None:
        """Set ``/Size`` — one entry per input dimension (sample count
        along that axis). ``None`` removes the entry."""
        # Invalidate any cached decoded samples — grid layout changes.
        self._samples_cache = None
        if size is None:
            self.get_cos_object().remove_item(_SIZE)
        else:
            self.get_cos_object().set_item(_SIZE, size)

    def get_bits_per_sample(self) -> int:
        return self.get_cos_object().get_int(_BITS_PER_SAMPLE, 0)

    def set_bits_per_sample(self, bits: int) -> None:
        """Set ``/BitsPerSample`` — must be one of {1, 2, 4, 8, 12, 16,
        24, 32} per PDF 32000-1 §7.10.2 Table 38, but the value is not
        validated here (mirrors upstream's permissive setter — eval
        rejects unsupported widths)."""
        self._samples_cache = None
        self.get_cos_object().set_int(_BITS_PER_SAMPLE, bits)

    def get_order(self) -> int:
        """PDF default is 1 (linear) when ``/Order`` is absent."""
        return self.get_cos_object().get_int(_ORDER, 1)

    def set_order(self, order: int) -> None:
        """Set ``/Order`` — 1 (linear, default) or 3 (cubic). pypdfbox
        falls back to linear with a debug log for any other value at
        eval time. Mirrors upstream ``setOrder(int)``."""
        self.get_cos_object().set_int(_ORDER, order)

    def get_encode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_ENCODE)
        if isinstance(item, COSArray):
            return item
        return None

    def set_encode(self, encode: COSArray | None) -> None:
        """Set ``/Encode`` — paired ``(min, max)`` per input dimension.
        ``None`` removes the entry; eval then defaults each dimension to
        ``(0, Size[i] - 1)``."""
        if encode is None:
            self.get_cos_object().remove_item(_ENCODE)
        else:
            self.get_cos_object().set_item(_ENCODE, encode)

    def get_decode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_DECODE)
        if isinstance(item, COSArray):
            return item
        return None

    def set_decode(self, decode: COSArray | None) -> None:
        """Set ``/Decode`` — paired ``(min, max)`` per output dimension.
        ``None`` removes the entry; eval then defaults to the function's
        ``/Range`` pairs."""
        if decode is None:
            self.get_cos_object().remove_item(_DECODE)
        else:
            self.get_cos_object().set_item(_DECODE, decode)

    # ---------- upstream-named aliases ----------

    def set_encode_values(self, encode_values: COSArray | None) -> None:
        """Upstream-named alias for :meth:`set_encode` (PDFBox
        ``setEncodeValues(COSArray)``)."""
        self.set_encode(encode_values)

    def set_decode_values(self, decode_values: COSArray | None) -> None:
        """Upstream-named alias for :meth:`set_decode` (PDFBox
        ``setDecodeValues(COSArray)``)."""
        self.set_decode(decode_values)

    def get_encode_for_parameter(self, n: int) -> tuple[float, float] | None:
        """Return the ``(min, max)`` ``/Encode`` pair for input dimension ``n``.

        Mirrors PDFBox ``getEncodeForParameter(int)``. When ``/Encode`` is
        absent or too short for ``n``, the default ``(0, Size[n] - 1)`` pair
        is returned per PDF 32000-1 §7.10.2 Table 38. Returns ``None`` when
        ``n`` is negative or exceeds the declared input dimension count
        (mirrors upstream's "null when out of range" contract — upstream
        returns null for ``encodeValues.size() < paramNum * 2 + 1`` after
        defaults are filled in).
        """
        if n < 0:
            return None
        sizes = self._get_size_list()
        num_in = self.get_number_of_input_parameters()
        if n >= max(num_in, len(sizes)):
            return None
        encode = self.get_encode()
        if encode is not None:
            flat = encode.to_float_array()
            if 2 * n + 1 < len(flat):
                return (flat[2 * n], flat[2 * n + 1])
        # Default: (0, Size[n] - 1)
        if n < len(sizes):
            upper = sizes[n] - 1
            return (0.0, float(max(0, upper)))
        return None

    def get_decode_for_parameter(self, n: int) -> tuple[float, float] | None:
        """Return the ``(min, max)`` ``/Decode`` pair for output dimension ``n``.

        Mirrors PDFBox ``getDecodeForParameter(int)``. When ``/Decode`` is
        absent or too short for ``n``, the default falls back to the
        function's ``/Range`` pair for output dimension ``n`` per PDF 32000-1
        §7.10.2 Table 38. Returns ``None`` when ``n`` is negative or exceeds
        the declared output dimension count.
        """
        if n < 0:
            return None
        num_out = self.get_number_of_output_parameters()
        if n >= num_out:
            return None
        decode = self.get_decode()
        if decode is not None:
            flat = decode.to_float_array()
            if 2 * n + 1 < len(flat):
                return (flat[2 * n], flat[2 * n + 1])
        # Default: /Range pair for output n.
        rng_pairs = self.get_ranges_for_outputs()
        if n < len(rng_pairs):
            return rng_pairs[n]
        return None

    # ---------- sample table ----------

    def get_samples(self) -> list[list[int]]:
        """Lazy-decode the bit-packed sample table into ``int[][]``.

        Outer index = linearised input cell (first input dim varies
        fastest, mirroring upstream's ``calcSampleIndex`` layout).
        Inner index = output dimension (length =
        ``getNumberOfOutputParameters``). Cached on first call;
        invalidated when any of ``/Size``, ``/BitsPerSample`` is reset
        via the setters above. Mirrors PDFBox ``getSamples()`` which
        also caches its decoded ``int[][]``.
        """
        if self._samples_cache is not None:
            return self._samples_cache
        num_in = self.get_number_of_input_parameters()
        num_out = self.get_number_of_output_parameters()
        bits = self.get_bits_per_sample()
        if bits not in _SUPPORTED_BITS:
            raise ValueError(
                f"unsupported /BitsPerSample={bits}; expected one of {sorted(_SUPPORTED_BITS)}"
            )
        sizes = self._get_size_list()
        if len(sizes) < num_in or any(s < 1 for s in sizes[:num_in]):
            raise ValueError("/Size missing or invalid for declared input dimensions")
        body = self._get_sample_bytes()

        total_cells = 1
        for i in range(num_in):
            total_cells *= sizes[i]
        out: list[list[int]] = []
        for cell in range(total_cells):
            coords: list[int] = []
            tmp = cell
            for i in range(num_in):
                coords.append(tmp % sizes[i])
                tmp //= sizes[i]
            row: list[int] = []
            for j in range(num_out):
                row.append(
                    self._read_sample(tuple(coords), j, sizes, num_out, bits, body)
                )
            out.append(row)
        self._samples_cache = out
        return out

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
        per cell, each ``bits`` wide. Successive sample values are adjacent
        in the bit stream with no padding at byte boundaries; bits are
        packed MSB-first (PDF spec p.171). Mirrors upstream
        ``MemoryCacheImageInputStream.readBits(bitsPerSample)``.
        """
        # Linearise coords → cell index. PDF spec: first dim varies fastest.
        linear = 0
        stride = 1
        for i, c in enumerate(coords):
            linear += c * stride
            stride *= sizes[i]
        bit_offset = (linear * num_outputs + output_index) * bits

        # Generic MSB-first bit-stream read — handles 1, 2, 4, 8, 12, 16,
        # 24, 32 (and any other width) uniformly. Out-of-range bytes are
        # treated as zero so a truncated body yields zero-padded samples
        # rather than crashing — matches PDFBox's lenient-on-IOException
        # behaviour (it logs and returns the partially-built ``samples``
        # array which is zero-initialised by ``new int[][]``).
        body_len = len(body)
        byte_offset = bit_offset // 8
        bit_in_byte = bit_offset % 8
        # Number of bytes we may need to span: 1 + ceil((bit_in_byte + bits) / 8) - 1
        span = (bit_in_byte + bits + 7) // 8
        value = 0
        for k in range(span):
            value <<= 8
            idx = byte_offset + k
            if 0 <= idx < body_len:
                value |= body[idx]
        # Strip trailing bits past the value we care about, then mask off
        # the leading bits that belonged to the previous sample.
        trailing = span * 8 - bit_in_byte - bits
        value >>= trailing
        return value & ((1 << bits) - 1)

    def decode_sample_grid(self) -> list[list[float]]:
        """Decode the bit-packed sample stream into a flat list of cells.

        Each entry is a list of ``num_outputs`` floats. The outer index is
        the linearised input coordinate (first input dimension varies
        fastest, mirroring upstream's ``calcSampleIndex`` layout). Sample
        codes are returned as raw integers cast to ``float`` — the
        ``/Decode`` mapping into the function's output range happens later
        during :meth:`eval`. Provided as a public diagnostic / parity
        helper; eval reads samples on demand via :meth:`_read_sample`
        without materialising the full grid.
        """
        num_in = self.get_number_of_input_parameters()
        num_out = self.get_number_of_output_parameters()
        bits = self.get_bits_per_sample()
        if bits not in _SUPPORTED_BITS:
            raise ValueError(
                f"unsupported /BitsPerSample={bits}; expected one of {sorted(_SUPPORTED_BITS)}"
            )
        sizes = self._get_size_list()
        if len(sizes) < num_in or any(s < 1 for s in sizes[:num_in]):
            raise ValueError("/Size missing or invalid for declared input dimensions")
        body = self._get_sample_bytes()

        total_cells = 1
        for i in range(num_in):
            total_cells *= sizes[i]
        grid: list[list[float]] = []
        for cell in range(total_cells):
            # Reconstruct per-axis coords for this linear index.
            coords: list[int] = []
            tmp = cell
            for i in range(num_in):
                coords.append(tmp % sizes[i])
                tmp //= sizes[i]
            row: list[float] = []
            for j in range(num_out):
                row.append(
                    float(
                        self._read_sample(
                            tuple(coords), j, sizes, num_out, bits, body
                        )
                    )
                )
            grid.append(row)
        return grid

    def _interpolate_linear(
        self,
        coords: list[float],
        sizes: list[int],
        num_out: int,
        bits: int,
        body: bytes,
    ) -> list[float]:
        """Multi-linear (n-linear) interpolation at fractional ``coords``.

        ``coords[i]`` is an already-encoded, sample-grid coordinate in
        ``[0, sizes[i]-1]``. Returns one float per output dimension —
        each is the n-linear blend of the 2^n surrounding integer-coord
        samples (raw sample codes, not yet ``/Decode``-mapped). Mirrors
        the upstream ``Rinterpol.rinterpolate()`` recursive collapse, but
        unrolled into a flat-index gather + per-axis fold.
        """
        n = len(coords)
        floors: list[int] = []
        fracs: list[float] = []
        for i in range(n):
            c = coords[i]
            upper = sizes[i] - 1
            if c < 0.0:
                c = 0.0
            elif c > upper:
                c = float(upper)
            f = int(c)
            if f >= upper:
                # Right-edge sample: no neighbour to the right.
                f = upper
                frac = 0.0
            else:
                frac = c - f
            floors.append(f)
            fracs.append(frac)

        result: list[float] = []
        for j in range(num_out):
            total = 1 << n  # 2^n corners
            corners: list[float] = []
            for idx in range(total):
                pt: list[int] = []
                for i in range(n):
                    pos = (idx >> i) & 1
                    raw = floors[i] + pos
                    upper = sizes[i] - 1
                    if raw > upper:
                        raw = upper
                    pt.append(raw)
                corners.append(
                    float(
                        self._read_sample(
                            tuple(pt), j, sizes, num_out, bits, body
                        )
                    )
                )
            # Fold one axis at a time using the per-axis fraction.
            for i in range(n):
                t = fracs[i]
                next_corners: list[float] = []
                for k in range(0, len(corners), 2):
                    a, b = corners[k], corners[k + 1]
                    next_corners.append(a + t * (b - a))
                corners = next_corners
            result.append(corners[0])
        return result

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """N-dimensional interpolation over the sample table per §7.10.2.

        ``/Order = 1`` (linear, default) folds 2^n surrounding samples per
        output dim. ``/Order = 3`` (cubic Catmull-Rom Hermite) folds 4^n
        samples per output dim with edge-clamped neighbour lookups. Any
        other order value falls back to linear with a debug log.
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

        order = self.get_order()
        if order not in (1, 3):
            _LOG.debug(
                "PDFunctionType0: unsupported /Order=%s — falling back to linear", order
            )
            order = 1

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
        n = num_in

        # Per-axis stencil: 2 samples (linear) or 4 samples (cubic).
        if order == 3:
            # Cubic Catmull-Rom: per axis we need samples at floor-1, floor,
            # floor+1, floor+2 — clamped to [0, size-1].
            stencil_offsets = (-1, 0, 1, 2)
        else:
            stencil_offsets = (0, 1)
        stencil_w = len(stencil_offsets)

        output: list[float] = []
        for j in range(num_out):
            # Gather stencil_w**n corner samples. The flat index encodes the
            # per-axis offset position (0..stencil_w-1) as a base-stencil_w
            # number with axis 0 as the least-significant digit.
            total = stencil_w**n
            corners: list[float] = []
            for idx in range(total):
                coords: list[int] = []
                tmp = idx
                for i in range(n):
                    pos = tmp % stencil_w
                    tmp //= stencil_w
                    upper = sizes[i] - 1
                    raw = floors[i] + stencil_offsets[pos]
                    # Edge clamp — mirrors PDFBox cubic neighbour handling.
                    if raw < 0:
                        raw = 0
                    elif raw > upper:
                        raw = upper
                    coords.append(raw)
                corners.append(
                    float(
                        self._read_sample(
                            tuple(coords), j, sizes, num_out, bits, body
                        )
                    )
                )

            # Collapse one dimension at a time using the per-axis fraction.
            for i in range(n):
                t = fracs[i]
                next_corners: list[float] = []
                if order == 3:
                    for k in range(0, len(corners), 4):
                        s0, s1, s2, s3 = corners[k : k + 4]
                        next_corners.append(_catmull_rom(s0, s1, s2, s3, t))
                else:
                    for k in range(0, len(corners), 2):
                        a, b = corners[k], corners[k + 1]
                        next_corners.append(a + t * (b - a))
                corners = next_corners
            sample = corners[0]
            # Step 5: map [0, 2^bits-1] → /Decode (and clamp to it — cubic
            # Catmull-Rom can overshoot the sample envelope).
            d_lo, d_hi = decode_pairs[j]
            if sample_max == 0:
                decoded = d_lo
            else:
                decoded = sample * (d_hi - d_lo) / sample_max + d_lo
            output.append(decoded)

        # Step 6: clip to /Range.
        return self.clip_output(output)


def _catmull_rom(s0: float, s1: float, s2: float, s3: float, t: float) -> float:
    """Cubic Hermite (Catmull-Rom flavour) at fraction ``t`` ∈ [0, 1].

    Tangents at the bracketing samples are central differences:
    ``m1 = (s2 - s0) / 2`` at ``s1`` and ``m2 = (s3 - s1) / 2`` at ``s2``.
    Standard Hermite basis gives the closed form below — equivalent to
    PDFBox's `PDFunctionType0` cubic interpolation step.
    """
    t2 = t * t
    t3 = t2 * t
    h00 = 2.0 * t3 - 3.0 * t2 + 1.0
    h10 = t3 - 2.0 * t2 + t
    h01 = -2.0 * t3 + 3.0 * t2
    h11 = t3 - t2
    m1 = 0.5 * (s2 - s0)
    m2 = 0.5 * (s3 - s1)
    return h00 * s1 + h10 * m1 + h01 * s2 + h11 * m2


__all__ = ["PDFunctionType0"]
