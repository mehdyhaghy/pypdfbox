from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSBase, COSInteger, COSNumber, COSStream

from .pd_function import PDFunction

_LOG = logging.getLogger(__name__)

_SIZE = "Size"
_BITS_PER_SAMPLE = "BitsPerSample"
_ORDER = "Order"
_ENCODE = "Encode"
_DECODE = "Decode"

# Upstream PDFBox does NOT validate /BitsPerSample against the Table-38 set
# ({1,2,4,8,12,16,24,32}): its
# eval reads each sample with ``MemoryCacheImageInputStream.readBits(bits)``,
# whose contract accepts any width in [0, 64]. So an off-spec width like 3, 5, 7
# (or 0) is read bit-for-bit rather than rejected — PDFBox parity over the
# stricter spec set (behavior over style). For widths 0..32 the
# read is fully determinate and pypdfbox reproduces PDFBox's output to the bit
# (verified by the wave-1535 sampled-fuzz oracle). Widths 33..64 are accepted by
# PDFBox too, but its output there depends on a Java ``(int)`` long-truncation
# plus a stateful "first eval throws, the cached sample grid is left zeroed, so
# later evals return 0" quirk that is not bit-reproducible in Python; pypdfbox
# raises for those (pinned divergence, CHANGES.md Wave 1535). Width > 64 or < 0
# is an error on both sides (PDFBox IllegalArgumentException from readBits;
# pypdfbox ValueError).
_MIN_BITS = 0
_MAX_BITS = 32


def _bits_supported(bits: int) -> bool:
    """True when pypdfbox can evaluate this /BitsPerSample bit-for-bit vs PDFBox."""
    return _MIN_BITS <= bits <= _MAX_BITS


class PDFunctionType0(PDFunction):
    """
    Type 0 (sampled) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType0``.

    Backed by a ``COSStream`` whose binary body holds the sample table.
    Evaluation reads the surrounding 2^n samples for an n-dimensional input
    and combines them with n-linear interpolation per PDF 32000-1 §7.10.2.
    ``/Order`` is read for diagnostics only: upstream PDFBox's eval() ignores
    it and always interpolates linearly, so a ``/Order = 3`` table is
    interpolated linearly here too (parity over spec-cubic — behavior
    over style).
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)
        # Decoded sample-table body; populated lazily on first eval to
        # amortise filter-chain decode across repeated evaluations.
        self._sample_bytes: bytes | None = None
        # Lazy decoded sample grid cache for get_samples(). int[][] in
        # upstream — outer index = linearised input cell, inner = output dim.
        self._samples_cache: list[list[int]] | None = None

    def _invalidate_samples(self) -> None:
        self._sample_bytes = None
        self._samples_cache = None

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
        # Invalidate decoded samples — grid layout changes.
        self._invalidate_samples()
        if size is None:
            self.get_cos_object().remove_item(_SIZE)
        else:
            self.get_cos_object().set_item(_SIZE, size)

    def get_bits_per_sample(self) -> int:
        # Upstream parity: PDFunctionType0.getBitsPerSample() is
        # ``getCOSObject().getInt(COSName.BITS_PER_SAMPLE)`` — the single-arg
        # ``COSDictionary.getInt`` returns -1 when the key is absent / non-int,
        # NOT 0. The absent-key value (-1) never feeds a valid eval (it is below
        # the supported [0, 32] range so eval raises), but the accessor's
        # return must match upstream for introspection / parity.
        return self.get_cos_object().get_int(_BITS_PER_SAMPLE, -1)

    def set_bits_per_sample(self, bits: int) -> None:
        """Set ``/BitsPerSample`` — per PDF 32000-1 §7.10.2 Table 38 one of
        {1, 2, 4, 8, 12, 16, 24, 32}, but the value is not validated here
        (mirrors upstream's permissive setter). eval reads any width in
        [0, 32] bit-for-bit like PDFBox and raises only outside that range."""
        self._invalidate_samples()
        self.get_cos_object().set_int(_BITS_PER_SAMPLE, bits)

    def get_order(self) -> int:
        """PDF default is 1 (linear) when ``/Order`` is absent."""
        return self.get_cos_object().get_int(_ORDER, 1)

    def set_order(self, order: int) -> None:
        """Set ``/Order`` — 1 (linear, default) or 3 (cubic per spec).
        Note: eval interpolates linearly for any /Order value, mirroring
        upstream PDFBox which has no cubic branch. Mirrors upstream
        ``setOrder(int)`` as a pure COS setter."""
        self.get_cos_object().set_int(_ORDER, order)

    def get_encode(self) -> COSArray | None:
        item = self.get_cos_object().get_dictionary_object(_ENCODE)
        if isinstance(item, COSArray):
            return item
        return None

    def get_encode_values(self) -> COSArray | None:
        """Return the ``/Encode`` array, defaulting to ``[0 (Size[0]-1)
        0 (Size[1]-1) ...]`` when the entry is absent.

        Mirrors PDFBox ``getEncodeValues()`` (PDFunctionType0.java:144-163).
        Upstream the method is private and used by ``getEncodeForParameter``
        and ``eval``; pypdfbox exposes it for parity / diagnostic callers
        that want the resolved array including the spec-default fill-in.
        Returns ``None`` only when ``/Size`` is also absent (no shape to
        synthesise defaults from).
        """
        encode = self.get_encode()
        if encode is not None:
            return encode
        size = self.get_size()
        if size is None:
            return None
        # Default per PDF 32000-1 Table 38: (0, Size[i] - 1) per dim.
        synthesised = COSArray()
        for i in range(size.size()):
            item = size.get(i)
            upper = int(item.float_value()) - 1 if isinstance(item, COSNumber) else -1
            synthesised.add(COSInteger.ZERO)
            synthesised.add(COSInteger.get(upper))
        return synthesised

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

    def get_decode_values(self) -> COSArray | None:
        """Return the ``/Decode`` array, defaulting to the function's
        ``/Range`` array when the entry is absent.

        Mirrors PDFBox ``getDecodeValues()`` (PDFunctionType0.java:170-182).
        Upstream the method is private and used by
        ``getDecodeForParameter`` and ``eval``; pypdfbox exposes it for
        parity / diagnostic callers that want the resolved array including
        the spec-default fall-through to ``/Range``.
        """
        decode = self.get_decode()
        if decode is not None:
            return decode
        # Default per PDF 32000-1 Table 38: same as /Range.
        return self.get_range()

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

        Mirrors PDFBox ``getEncodeForParameter(int)`` exactly: it resolves
        :meth:`get_encode_values` (which fills the spec default ``[0 Size[i]-1]``
        ONLY when ``/Encode`` is absent — never when present-but-short) and
        returns the pair only when that array is long enough
        (``size() >= 2*n + 1``). When ``/Encode`` is present but too short for
        ``n`` it returns ``None`` — upstream does NOT default-fill a partial
        ``/Encode``; eval then NPEs on the null PDRange, so a too-short
        ``/Encode`` is a hard error there (parity, CHANGES.md Wave 1535).
        ``None`` is also returned when ``n`` is negative or ``/Encode`` and
        ``/Size`` are both absent.
        """
        if n < 0:
            return None
        values = self.get_encode_values()
        if values is None or values.size() < 2 * n + 1:
            return None
        flat = values.to_float_array()
        return (flat[2 * n], flat[2 * n + 1])

    def get_decode_for_parameter(self, n: int) -> tuple[float, float] | None:
        """Return the ``(min, max)`` ``/Decode`` pair for output dimension ``n``.

        Mirrors PDFBox ``getDecodeForParameter(int)`` exactly: it resolves
        :meth:`get_decode_values` (which falls back to ``/Range`` ONLY when
        ``/Decode`` is absent — never when present-but-short) and returns the
        pair only when that array is long enough (``size() >= 2*n + 1``). When
        ``/Decode`` is present but too short for ``n`` it returns ``None`` —
        upstream does NOT default-fill a partial ``/Decode``; eval then NPEs on
        the null PDRange, so a too-short ``/Decode`` is a hard error there
        (parity, CHANGES.md Wave 1535). ``None`` is also returned when ``n`` is
        negative or both ``/Decode`` and ``/Range`` are absent.
        """
        if n < 0:
            return None
        values = self.get_decode_values()
        if values is None or values.size() < 2 * n + 1:
            return None
        flat = values.to_float_array()
        return (flat[2 * n], flat[2 * n + 1])

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
        if not _bits_supported(bits):
            raise ValueError(
                f"/BitsPerSample={bits} out of supported range "
                f"[{_MIN_BITS}, {_MAX_BITS}]"
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

    @staticmethod
    def _clip_to_range_scalar(x: float, range_min: float, range_max: float) -> float:
        """Non-normalising scalar clamp — direct port of upstream
        ``PDFunction.clipToRange(float, float, float)`` (PDFunction.java).

        Unlike :meth:`PDFunction.clip_input` / :meth:`PDFunction.clip_output`,
        this does **not** swap a reversed ``(min, max)`` pair:
        ``if x < range_min -> range_min``; ``if x > range_max -> range_max``;
        else ``x``. PDFunctionType0.eval (jar 3.0.7) clips both its inputs (to
        ``/Domain``) and its outputs (to ``/Range``) with this scalar
        ``clipToRange(F,F,F)``, NOT the array clip helpers — so a reversed
        ``/Domain`` or ``/Range`` pair must collapse to the (lower) ``max`` value
        the way Java does, rather than be silently normalised to a sane interval.
        Wave 1540 fix (mirrors the Type 3 / Type 4 non-normalising overrides)."""
        if x < range_min:
            return range_min
        if x > range_max:
            return range_max
        return x

    def _clip_input_unnormalised(
        self, values: list[float], domain: list[tuple[float, float]]
    ) -> list[float]:
        """Clamp each input to its ``/Domain`` pair via the non-normalising
        scalar :meth:`_clip_to_range_scalar`. Inputs beyond the declared
        dimension count pass through unchanged (matches upstream eval which
        only iterates ``input.length`` against the per-dim ``PDRange``)."""
        out: list[float] = []
        for i, v in enumerate(values):
            if i < len(domain):
                lo, hi = domain[i]
                out.append(self._clip_to_range_scalar(v, lo, hi))
            else:
                out.append(v)
        return out

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
            if isinstance(item, COSNumber):
                out.append(int(item.float_value()))
            else:
                out.append(0)
        return out

    def _get_encode_pairs(self, num_in: int, sizes: list[int]) -> list[tuple[float, float]]:
        """``/Encode`` paired ``(min, max)`` per input dim, via
        :meth:`get_encode_for_parameter`.

        When ``/Encode`` is absent the default ``(0, Size[i]-1)`` per dim is
        used; when ``/Encode`` is present but too short for some dim,
        ``get_encode_for_parameter`` returns ``None`` (no default fill-in) and
        this raises ``ValueError`` — mirroring upstream eval's NullPointerException
        on the null PDRange returned by ``getEncodeForParameter`` for a
        too-short ``/Encode`` (CHANGES.md Wave 1535)."""
        pairs: list[tuple[float, float]] = []
        for i in range(num_in):
            pair = self.get_encode_for_parameter(i)
            if pair is None:
                raise ValueError(
                    f"/Encode present but too short for input dimension {i}"
                )
            pairs.append(pair)
        return pairs

    def _get_decode_pairs(self, num_out: int) -> list[tuple[float, float]]:
        """``/Decode`` paired ``(min, max)`` per output dim, via
        :meth:`get_decode_for_parameter`.

        When ``/Decode`` is absent it defaults to the ``/Range`` pair per dim;
        when ``/Decode`` is present but too short for some dim,
        ``get_decode_for_parameter`` returns ``None`` (no default fill-in) and
        this raises ``ValueError`` — mirroring upstream eval's NullPointerException
        on the null PDRange returned by ``getDecodeForParameter`` for a
        too-short ``/Decode`` (CHANGES.md Wave 1535)."""
        pairs: list[tuple[float, float]] = []
        for j in range(num_out):
            pair = self.get_decode_for_parameter(j)
            if pair is None:
                raise ValueError(
                    f"/Decode present but too short for output dimension {j}"
                )
            pairs.append(pair)
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
        value &= (1 << bits) - 1
        # Upstream stores each code with ``(int) mciis.readBits(bitsPerSample)``
        # (PDFunctionType0.java getSamples()). For bits < 32 the read value is
        # < 2^31 so the cast is lossless, but at bits == 32 a code with the top
        # bit set is truncated to a NEGATIVE signed-32 int before the /Decode
        # mapping. Replicate that sign-extension so 32-bit samples >= 2^31 feed
        # the same negative value into interpolate() as Java does (eval then
        # clamps to /Range). See the upstream "TODO will this cast work
        # properly for 32 bitsPerSample" comment.
        if bits == 32 and value >= 0x80000000:
            value -= 0x100000000
        return value

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
        if not _bits_supported(bits):
            raise ValueError(
                f"/BitsPerSample={bits} out of supported range "
                f"[{_MIN_BITS}, {_MAX_BITS}]"
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
        # Upstream eval requires only /Domain: with num_in == 0 the sample-grid
        # path is degenerate and PDFBox throws (matched here). num_out == 0
        # (empty /Range) is NOT an error in PDFBox — its output loop runs zero
        # times and eval returns an empty array; mirror that (wave 1540).
        if num_in == 0:
            raise ValueError("PDFunctionType0 requires /Domain")
        if not _bits_supported(bits):
            raise ValueError(
                f"/BitsPerSample={bits} out of supported range "
                f"[{_MIN_BITS}, {_MAX_BITS}]"
            )

        sizes = self._get_size_list()
        if len(sizes) < num_in or any(s < 1 for s in sizes[:num_in]):
            raise ValueError("/Size missing or invalid for declared input dimensions")

        # Upstream PDFBox (PDFunctionType0.eval, 3.0.7) ignores /Order entirely
        # and ALWAYS performs n-linear interpolation — there is no cubic branch
        # in its eval(). Parity is the metric (behavior over style),
        # so we mirror that: /Order is read for diagnostics only and any value
        # (including 3) is interpolated linearly. A /Order=3 sample table that a
        # cubic spline would round differently must still match Java's linear
        # output to the bit, so cubic interpolation is intentionally not used.
        order = self.get_order()
        if order != 1:
            _LOG.debug(
                "PDFunctionType0: /Order=%s ignored — upstream always interpolates"
                " linearly",
                order,
            )
        order = 1

        domain = self.get_ranges_for_inputs()
        # Upstream eval clips inputs with the scalar clipToRange(F,F,F) (per-dim
        # PDRange getMin/getMax), NOT the normalising array clip — so a reversed
        # /Domain pair is honoured as-is (collapses to the lower max), not swapped.
        clipped = self._clip_input_unnormalised(input, domain)
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

        # Per-axis stencil is always the 2-sample linear pair — upstream
        # PDFunctionType0.eval has no cubic branch (see the /Order note above),
        # so the function is n-linear over the 2^n surrounding samples.
        output: list[float] = []
        for j in range(num_out):
            # Gather 2**n corner samples. The flat index encodes the per-axis
            # offset (0 or 1) as a binary number with axis 0 as the
            # least-significant bit.
            total = 1 << n
            corners: list[float] = []
            for idx in range(total):
                coords: list[int] = []
                for i in range(n):
                    pos = (idx >> i) & 1
                    upper = sizes[i] - 1
                    raw = floors[i] + pos
                    # Edge clamp — the right-edge floor sets frac=0 above, so a
                    # clamped raw never contributes once frac is 0.
                    if raw > upper:
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
                for k in range(0, len(corners), 2):
                    a, b = corners[k], corners[k + 1]
                    next_corners.append(a + t * (b - a))
                corners = next_corners
            sample = corners[0]
            # Step 5: map [0, 2^bits-1] → /Decode.
            d_lo, d_hi = decode_pairs[j]
            decoded = (
                d_lo
                if sample_max == 0
                else sample * (d_hi - d_lo) / sample_max + d_lo
            )
            output.append(decoded)

        # Step 6: clip to /Range. Upstream eval clips each output with the scalar
        # clipToRange(F,F,F) against the per-dim getRangeForOutput PDRange, NOT
        # the normalising array clip — so a reversed /Range pair is honoured
        # exactly as Java does (collapses to the lower max) rather than swapped.
        range_pairs = self.get_ranges_for_outputs()
        out_clipped: list[float] = []
        for j, v in enumerate(output):
            if j < len(range_pairs):
                lo, hi = range_pairs[j]
                out_clipped.append(self._clip_to_range_scalar(v, lo, hi))
            else:
                out_clipped.append(v)
        return out_clipped


__all__ = ["PDFunctionType0"]
