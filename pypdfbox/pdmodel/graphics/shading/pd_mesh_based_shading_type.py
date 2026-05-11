"""Abstract base for mesh-based shading PD types (Types 6 and 7).

Mirrors PDFBox
``org.apache.pdfbox.pdmodel.graphics.shading.PDMeshBasedShadingType``.

Concrete bit-stream parsing of patch flags / control points lives on the
``PDShadingType6`` / ``PDShadingType7`` classes in pypdfbox; this module
exposes the abstract surface (``collect_patches`` / ``read_patch`` /
``get_bounds``) for parity counters and as a hand-off seam.
"""

from __future__ import annotations

from typing import Any

from .pd_triangle_based_shading_type import PDTriangleBasedShadingType


class PDMeshBasedShadingType(PDTriangleBasedShadingType):
    """Mix-in for Coons (Type 6) / tensor (Type 7) mesh-based shadings."""

    def generate_patch(
        self, points: list[tuple[float, float]], color: list[list[float]]
    ) -> Any:
        """Subclasses produce a CoonsPatch / TensorPatch from raw decoded data."""
        raise NotImplementedError

    def collect_patches(
        self,
        xform: Any = None,
        matrix: Any = None,
        control_points: int = 12,
    ) -> list[Any]:
        """Decode the patch list from this mesh shading's bit stream.

        Concrete subclasses override this with the full bit-stream reader;
        the abstract base raises ``NotImplementedError`` so parity tooling
        sees the symbol while the production path stays on the concrete
        subclass.
        """
        raise NotImplementedError

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
        raise NotImplementedError

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
