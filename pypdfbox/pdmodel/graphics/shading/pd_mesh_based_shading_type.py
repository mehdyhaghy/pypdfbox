"""Abstract base for mesh-based shading PD types (Types 6 and 7).

Mirrors PDFBox
``org.apache.pdfbox.pdmodel.graphics.shading.PDMeshBasedShadingType``.

In addition to the abstract surface (``collect_patches`` / ``read_patch`` /
``get_bounds``) used by parity counters, this module exposes the
geometry-only patch-stream decoder used by ``PDShadingType6`` /
``PDShadingType7``: :class:`ParsedPatch` (lightweight raw-points + raw-
colour record) and :func:`parse_patch_stream` (the shared flag-driven
bit-stream reader that handles full / shared-edge patches per PDF
32000-1 §8.7.4.5.7-8). Rendering-side `CoonsPatch` / `TensorPatch`
triangulation runs on top of this output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .pd_triangle_based_shading_type import PDTriangleBasedShadingType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence


# ----------------------------------------------------------------------
# Geometry-only patch record + bit reader
# ----------------------------------------------------------------------


@dataclass
class ParsedPatch:
    """Geometry-only result of decoding a single patch from a Type 6 / 7
    stream. ``points`` is a list of ``(x, y)`` control points in upstream
    order (12 entries for Coons, 16 for tensor); ``colors`` is a list of
    4 corner-colour vectors (each with ``n`` components). ``flag`` is the
    raw 2-bit edge-share flag that *introduced* this patch (0 = free, 1 /
    2 / 3 = shared with previous patch).
    """

    flag: int
    points: list[tuple[float, float]]
    colors: list[list[float]] = field(default_factory=list)


class _PatchBitReader:
    """MSB-first bit reader over a bytes-like buffer.

    Mirrors ``javax.imageio.stream.MemoryCacheImageInputStream.readBits``
    for the limited shape Type 6 / 7 patch streams need: read ``n`` bits
    MSB-first, advancing the cursor; raise ``EOFError`` when the buffer
    is exhausted. Upstream wraps ``EOFException`` to terminate the patch
    loop, so the caller must catch ``EOFError`` to do the same.
    """

    __slots__ = ("_data", "_byte_idx", "_bit_idx")

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._data = bytes(data)
        self._byte_idx = 0
        self._bit_idx = 0  # 0..7, MSB-first inside each byte

    def read_bits(self, n: int) -> int:
        if n <= 0:
            return 0
        value = 0
        for _ in range(n):
            if self._byte_idx >= len(self._data):
                raise EOFError("patch stream exhausted")
            bit = (self._data[self._byte_idx] >> (7 - self._bit_idx)) & 1
            value = (value << 1) | bit
            self._bit_idx += 1
            if self._bit_idx == 8:
                self._bit_idx = 0
                self._byte_idx += 1
        return value

    def get_bit_offset(self) -> int:
        """Current bit position within the active byte (0..7), matching
        ``javax.imageio.stream.ImageInputStream.getBitOffset``."""
        return self._bit_idx

    def align_to_byte(self) -> None:
        """Skip any partial bits so the next read starts on a byte boundary.

        Mirrors the per-vertex padding upstream applies in
        ``PDTriangleBasedShadingType.readVertex`` (PDF 32000-1 §8.7.4.5.5:
        "Each set of vertex data shall occupy a whole number of bytes. If
        the total number of bits required is not divisible by 8, the last
        data byte for each vertex is padded at the end with extra bits,
        which shall be ignored."). Triangle vertices (Types 4/5) are
        byte-aligned; patch control points (Types 6/7) are **not**, so this
        is only invoked by the Gouraud readers."""
        if self._bit_idx != 0:
            self._bit_idx = 0
            self._byte_idx += 1


def _interpolate(src: int, src_max: int, dst_min: float, dst_max: float) -> float:
    """Map ``src`` from ``[0, src_max]`` into ``[dst_min, dst_max]``.

    Mirrors upstream ``PDTriangleBasedShadingType.interpolate``. When
    ``src_max == 0`` (degenerate BitsPerCoordinate / BitsPerComponent = 0,
    or theoretical 1-bit case where 2**1 - 1 = 1), the implementation
    falls back to ``dst_min`` to avoid div-by-zero.
    """
    if src_max == 0:
        return dst_min
    return dst_min + (src * (dst_max - dst_min) / src_max)


def _patch_flag1_edge(
    pts: Sequence[tuple[float, float]], control_points: int
) -> list[tuple[float, float]]:
    """Implicit edge when flag == 1 (share trailing edge of previous patch).

    Mirrors upstream ``CoonsPatch.getFlag1Edge`` (returns p[3], p[4], p[5],
    p[6]) and ``TensorPatch.getFlag1Edge`` (returns p[3], p[4], p[5],
    p[6]) — both produce the previous patch's first interior boundary
    that becomes the new patch's leading 4 control points.
    """
    _ = control_points  # both variants share the same 4-point slice
    return [pts[3], pts[4], pts[5], pts[6]]


def _patch_flag2_edge(
    pts: Sequence[tuple[float, float]], control_points: int
) -> list[tuple[float, float]]:
    """Implicit edge when flag == 2."""
    if control_points == 12:
        return [pts[6], pts[7], pts[8], pts[9]]
    # Tensor: same 4-element slice index per upstream TensorPatch.getFlag2Edge.
    return [pts[6], pts[7], pts[8], pts[9]]


def _patch_flag3_edge(
    pts: Sequence[tuple[float, float]], control_points: int
) -> list[tuple[float, float]]:
    """Implicit edge when flag == 3."""
    if control_points == 12:
        return [pts[9], pts[10], pts[11], pts[0]]
    return [pts[9], pts[10], pts[11], pts[0]]


def _patch_flag_color(
    color: Sequence[Sequence[float]], flag: int
) -> list[list[float]]:
    """Implicit corner colours for flag 1/2/3. Mirrors ``Patch.getFlagNColor``."""
    if flag == 1:
        return [list(color[1]), list(color[2])]
    if flag == 2:
        return [list(color[2]), list(color[3])]
    if flag == 3:
        return [list(color[3]), list(color[0])]
    raise ValueError(f"invalid flag for implicit-color lookup: {flag}")


def parse_patch_stream(
    stream_bytes: bytes | bytearray | memoryview,
    *,
    bits_per_coordinate: int,
    bits_per_component: int,
    bits_per_flag: int,
    decode: Sequence[float],
    num_color_components: int,
    control_points: int,
) -> list[ParsedPatch]:
    """Decode a Type 6 (control_points == 12) or Type 7 (control_points
    == 16) patch mesh stream into a list of :class:`ParsedPatch`.

    Mirrors PDFBox ``PDMeshBasedShadingType.collectPatches`` +
    ``readPatch`` (PDMeshBasedShadingType.java:62-234) minus the
    rendering-side ``Patch`` triangulation. Coordinates and colours are
    interpolated through ``/Decode`` (xy + per-component ranges); the
    caller (renderer) is responsible for any user-space → device
    transform.

    Layout of ``decode``: ``[xmin, xmax, ymin, ymax, c0min, c0max, ...]``
    — exactly ``2 * (2 + num_color_components)`` floats. Raises
    ``ValueError`` on a too-short ``decode`` array; returns an empty
    list when the input stream is empty or the initial flag byte cannot
    be read (matches upstream's defensive EOF return).
    """
    if control_points not in (12, 16):
        raise ValueError(
            f"control_points must be 12 (Coons) or 16 (tensor); got {control_points}"
        )
    if bits_per_coordinate <= 0:
        raise ValueError(f"bits_per_coordinate must be > 0; got {bits_per_coordinate}")
    if bits_per_component <= 0:
        raise ValueError(f"bits_per_component must be > 0; got {bits_per_component}")
    if bits_per_flag <= 0:
        raise ValueError(f"bits_per_flag must be > 0; got {bits_per_flag}")
    if num_color_components <= 0:
        raise ValueError(
            f"num_color_components must be > 0; got {num_color_components}"
        )
    needed = 2 * (2 + num_color_components)
    if len(decode) < needed:
        raise ValueError(
            f"/Decode requires {needed} entries for {num_color_components} "
            f"colour component(s); got {len(decode)}"
        )

    range_x = (float(decode[0]), float(decode[1]))
    range_y = (float(decode[2]), float(decode[3]))
    col_range = [
        (float(decode[4 + 2 * i]), float(decode[4 + 2 * i + 1]))
        for i in range(num_color_components)
    ]

    max_src_coord = (1 << bits_per_coordinate) - 1
    max_src_color = (1 << bits_per_component) - 1

    reader = _PatchBitReader(stream_bytes)
    patches: list[ParsedPatch] = []

    # Implicit-edge / implicit-corner-colour carry-overs (only used for
    # flag != 0). Initialised to defaults so the first patch — which is
    # always flag == 0 per spec — never reads them.
    implicit_edge: list[tuple[float, float]] = [(0.0, 0.0)] * 4
    implicit_corner_color: list[list[float]] = [[0.0] * num_color_components] * 2

    try:
        flag = reader.read_bits(bits_per_flag) & 3
    except EOFError:
        return patches

    while True:
        is_free = flag == 0
        points: list[tuple[float, float] | None] = [None] * control_points
        colors: list[list[float] | None] = [None] * 4

        if is_free:
            p_start = 0
            c_start = 0
        else:
            p_start = 4
            c_start = 2
            points[0] = implicit_edge[0]
            points[1] = implicit_edge[1]
            points[2] = implicit_edge[2]
            points[3] = implicit_edge[3]
            colors[0] = list(implicit_corner_color[0])
            colors[1] = list(implicit_corner_color[1])

        try:
            for i in range(p_start, control_points):
                x = reader.read_bits(bits_per_coordinate)
                y = reader.read_bits(bits_per_coordinate)
                px = _interpolate(x, max_src_coord, range_x[0], range_x[1])
                py = _interpolate(y, max_src_coord, range_y[0], range_y[1])
                points[i] = (px, py)
            for i in range(c_start, 4):
                comps: list[float] = []
                for j in range(num_color_components):
                    c = reader.read_bits(bits_per_component)
                    comps.append(
                        _interpolate(
                            c, max_src_color, col_range[j][0], col_range[j][1]
                        ),
                    )
                colors[i] = comps
        except EOFError:
            break

        finalized_points = [p if p is not None else (0.0, 0.0) for p in points]
        finalized_colors = [c if c is not None else [0.0] * num_color_components for c in colors]
        patches.append(
            ParsedPatch(flag=flag, points=finalized_points, colors=finalized_colors),
        )

        try:
            next_flag = reader.read_bits(bits_per_flag) & 3
        except EOFError:
            break

        if next_flag == 0:
            pass
        elif next_flag == 1:
            implicit_edge = _patch_flag1_edge(finalized_points, control_points)
            implicit_corner_color = _patch_flag_color(finalized_colors, 1)
        elif next_flag == 2:
            implicit_edge = _patch_flag2_edge(finalized_points, control_points)
            implicit_corner_color = _patch_flag_color(finalized_colors, 2)
        elif next_flag == 3:  # pragma: no branch  # next_flag &3 -> 0/1/2/3 exhaustive
            implicit_edge = _patch_flag3_edge(finalized_points, control_points)
            implicit_corner_color = _patch_flag_color(finalized_colors, 3)
        flag = next_flag

    return patches


class PDMeshBasedShadingType(PDTriangleBasedShadingType):
    """Mix-in for Coons (Type 6) / tensor (Type 7) mesh-based shadings."""

    def generate_patch(
        self, points: list[tuple[float, float]], color: list[list[float]]
    ) -> Any:
        """Subclasses produce a CoonsPatch / TensorPatch from raw decoded data."""
        _ = (points, color)
        raise NotImplementedError(
            "PDMeshBasedShadingType.generate_patch is abstract"
        )

    def collect_patches(
        self,
        xform: Any = None,
        matrix: Any = None,
        control_points: int = 12,
    ) -> list[Any]:
        """Decode the patch list from this mesh shading's bit stream into
        ready-to-triangulate :class:`CoonsPatch` / :class:`TensorPatch`
        instances.

        Mirrors upstream ``PDMeshBasedShadingType.collectPatches`` (Java):
        it reads the same flag-driven control-point / corner-colour stream
        as :meth:`parse_patches` (via the shared :func:`parse_patch_stream`
        reader, which the live-oracle ``PatchMeshDecodeProbe`` already pins
        bit-for-bit), applies the user-space -> device-space transform
        (``matrix`` concatenated then ``xform``) to every control point, and
        wraps each patch in the rendering-side ``Patch`` subclass selected by
        ``control_points`` (12 -> Coons, 16 -> tensor). The returned objects
        carry the triangulated ``list_of_triangles`` that
        :class:`PatchMeshesShadingContext` walks when building its pixel
        table.

        ``parse_patches`` is preserved as the geometry-only (untransformed,
        un-triangulated) lite-renderer entry point used by the decode oracle;
        ``collect_patches`` is the full render path. Returns an empty list
        when the backing object is not a ``COSStream`` or the ``/Decode``
        array is missing/degenerate, matching upstream's fallback.
        """
        from pypdfbox.cos.cos_stream import COSStream  # noqa: PLC0415

        from .coons_patch import CoonsPatch  # noqa: PLC0415
        from .tensor_patch import TensorPatch  # noqa: PLC0415

        if control_points not in (12, 16):
            control_points = 16 if self.get_shading_type() == 7 else 12

        # Backing object must be a stream (upstream returns emptyList()
        # otherwise — collectPatches line ~70).
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return []
        range_x = self.get_decode_for_parameter(0)
        range_y = self.get_decode_for_parameter(1)
        if range_x is None or range_y is None:
            return []
        if range_x[0] == range_x[1] or range_y[0] == range_y[1]:
            return []
        ncc = self.get_number_of_color_components()
        if ncc <= 0:
            return []
        # Flatten the /Decode array into the [xmin,xmax,ymin,ymax,c..] shape
        # parse_patch_stream expects, via the same per-parameter accessor
        # upstream uses (getDecodeForParameter).
        decode: list[float] = [range_x[0], range_x[1], range_y[0], range_y[1]]
        for i in range(ncc):
            rng = self.get_decode_for_parameter(2 + i)
            if rng is None:
                # Mirrors upstream's IOException("Range missing in shading
                # /Decode entry") -> OSError per project convention.
                raise OSError("Range missing in shading /Decode entry")
            decode.extend((rng[0], rng[1]))

        bits_per_coordinate = self.get_bits_per_coordinate()
        bits_per_component = self.get_bits_per_component()
        bits_per_flag = self.get_bits_per_flag()
        if bits_per_coordinate <= 0 or bits_per_component <= 0 or bits_per_flag <= 0:
            return []

        with cos.create_input_stream() as src:
            stream_bytes = src.read()
        parsed = parse_patch_stream(
            stream_bytes,
            bits_per_coordinate=bits_per_coordinate,
            bits_per_component=bits_per_component,
            bits_per_flag=bits_per_flag,
            decode=decode,
            num_color_components=ncc,
            control_points=control_points,
        )
        if not parsed:
            return []

        def _apply(transform: Any, x: float, y: float) -> tuple[float, float]:
            # Accept either pypdfbox's ``Matrix`` (transform_point) or any
            # AffineTransform-shaped object exposing ``transform_point``; fall
            # back to identity for anything else (the lite-renderer convention
            # defers transforms, so a bare/None transform is a no-op).
            fn = getattr(transform, "transform_point", None)
            if callable(fn):
                tx, ty = fn(x, y)
                return float(tx), float(ty)
            return x, y

        def _xf(point: tuple[float, float]) -> tuple[float, float]:
            x, y = float(point[0]), float(point[1])
            if matrix is not None:
                x, y = _apply(matrix, x, y)
            if xform is not None:
                x, y = _apply(xform, x, y)
            return (x, y)

        patch_cls = TensorPatch if control_points == 16 else CoonsPatch
        patches: list[Any] = []
        for record in parsed:
            transformed = [_xf(p) for p in record.points]
            patches.append(patch_cls(transformed, record.colors))
        return patches

    def read_patch(
        self,
        input_stream: Any,
        is_free: bool,
        implicit_edge: Any,
        implicit_corner_color: Any,
        max_src_coord: int,
        max_src_color: int,
        range_x: Any,
        range_y: Any,
        col_range: Any,
        matrix: Any,
        xform: Any,
        control_points: int,
    ) -> Any:
        """Read a single patch (coordinates + corner colours) from the stream."""
        _ = (
            input_stream,
            is_free,
            implicit_edge,
            implicit_corner_color,
            max_src_coord,
            max_src_color,
            range_x,
            range_y,
            col_range,
            matrix,
            xform,
            control_points,
        )
        raise NotImplementedError(
            "PDMeshBasedShadingType.read_patch is abstract"
        )

    def get_bounds(
        self,
        xform: Any = None,
        matrix: Any = None,
        control_points: int = 12,
    ) -> Any:
        """Bounding rectangle covering every ``ShadedTriangle`` of every patch."""
        try:
            patches = self.collect_patches(xform, matrix, control_points)
        except NotImplementedError:
            return None
        if not patches:
            return None
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for patch in patches:
            for tri in getattr(patch, "list_of_triangles", []):
                for corner in tri.corner:
                    cx, cy = float(corner[0]), float(corner[1])
                    min_x = min(min_x, cx)
                    min_y = min(min_y, cy)
                    max_x = max(max_x, cx)
                    max_y = max(max_y, cy)
        if min_x == float("inf"):
            return None
        return (min_x, min_y, max_x - min_x, max_y - min_y)
