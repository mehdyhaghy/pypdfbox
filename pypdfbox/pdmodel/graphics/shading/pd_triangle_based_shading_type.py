"""Abstract base for triangle-based shading PD types (Types 4-7).

Mirrors PDFBox
``org.apache.pdfbox.pdmodel.graphics.shading.PDTriangleBasedShadingType``.

In upstream Java this is an ``abstract`` class extending ``PDShading`` that
groups the bits-per-coordinate / bits-per-component / number-of-color
components accessors plus the bit-stream vertex reader shared by Types 4,
5, 6 and 7. The pypdfbox concrete shading subclasses
(``PDShadingType4`` etc.) historically inherited from ``PDShading``
directly. This module exposes the same surface for parity tooling and
delegates the COSObject-backed accessors to ``PDShading``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos.cos_dictionary import COSDictionary

from .pd_shading import PDShading

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


class PDTriangleBasedShadingType(PDShading):
    """Mix-in for triangle-based shadings (PDF Types 4-7)."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        self._decode: Any = None
        self._bits_per_coordinate: int = -1
        self._bits_per_color_component: int = -1
        self._number_of_color_components: int = -1

    @staticmethod
    def interpolate(src: float, src_max: int, dst_min: float, dst_max: float) -> float:
        """Interpolate ``src`` from ``[0, src_max]`` into ``[dst_min, dst_max]``."""
        if src_max == 0:
            return dst_min
        return dst_min + (src * (dst_max - dst_min) / src_max)

    # ------------------------------------------------------------------
    # Bits-per-coordinate / -component / number-of-colour-components
    # ------------------------------------------------------------------
    def get_bits_per_coordinate(self) -> int:
        """Return the value of the ``/BitsPerCoordinate`` entry (-1 if unset)."""
        if self._bits_per_coordinate == -1:
            self._bits_per_coordinate = self._dict.get_int("BitsPerCoordinate", -1)
        return self._bits_per_coordinate

    def set_bits_per_coordinate(self, bits: int) -> None:
        """Set the ``/BitsPerCoordinate`` entry."""
        self._dict.set_int("BitsPerCoordinate", bits)
        self._bits_per_coordinate = bits

    def get_bits_per_component(self) -> int:
        """Return the value of the ``/BitsPerComponent`` entry (-1 if unset)."""
        if self._bits_per_color_component == -1:
            self._bits_per_color_component = self._dict.get_int(
                "BitsPerComponent", -1
            )
        return self._bits_per_color_component

    def set_bits_per_component(self, bits: int) -> None:
        """Set the ``/BitsPerComponent`` entry."""
        self._dict.set_int("BitsPerComponent", bits)
        self._bits_per_color_component = bits

    def get_number_of_color_components(self) -> int:
        """Number of colour components used by this shading.

        Equals 1 when a ``Function`` is attached, otherwise comes from the
        colour space.
        """
        if self._number_of_color_components == -1:
            if self.get_function() is not None:
                self._number_of_color_components = 1
            else:
                cs = self.get_color_space_object()
                self._number_of_color_components = (
                    cs.get_number_of_components() if cs is not None else 0
                )
        return self._number_of_color_components

    def get_decode_for_parameter(self, param_num: int) -> Any:
        """Return the decode range for parameter ``param_num`` or ``None``."""
        decode_values = self.get_decode_values()
        if decode_values is None:
            return None
        if hasattr(decode_values, "size"):
            if decode_values.size() < param_num * 2 + 2:
                return None
        else:
            if len(decode_values) < param_num * 2 + 2:
                return None
        # Return the (min, max) pair for the parameter.
        base = param_num * 2
        try:
            lo = float(decode_values.get_object(base).get_value())
            hi = float(decode_values.get_object(base + 1).get_value())
        except AttributeError:
            lo = float(decode_values[base])
            hi = float(decode_values[base + 1])
        return (lo, hi)

    def get_decode_values(self) -> Any:
        """Return the raw ``COSArray`` for the ``/Decode`` entry, if any."""
        if self._decode is None:
            self._decode = self._dict.get_cos_array("Decode") if hasattr(
                self._dict, "get_cos_array"
            ) else self._dict.get_item("Decode")
        return self._decode

    def set_decode_values(self, decode_values: Any) -> None:
        """Replace the ``/Decode`` array."""
        self._decode = decode_values
        self._dict.set_item("Decode", decode_values)

    def read_vertex(
        self,
        input_stream: Any,
        max_src_coord: int,
        max_src_color: int,
        range_x: Any,
        range_y: Any,
        col_range_tab: Any,
        matrix: Any,
        xform: Any,
    ) -> Any:
        """Read a single vertex from a bit-aligned PDF mesh data stream.

        Concrete subclasses wire this up against the real bit reader; the
        abstract surface exists for parity with upstream's protected helper.
        """
        _ = (
            input_stream,
            max_src_coord,
            max_src_color,
            range_x,
            range_y,
            col_range_tab,
            matrix,
            xform,
        )
        raise NotImplementedError(
            "PDTriangleBasedShadingType.read_vertex is abstract"
        )

    def collect_triangles(self, xform: Any = None, matrix: Any = None) -> list[Any]:
        """Concrete subclasses produce a list of ``ShadedTriangle`` instances."""
        _ = (xform, matrix)
        raise NotImplementedError(
            "PDTriangleBasedShadingType.collect_triangles is abstract"
        )

    def get_bounds(self, xform: Any = None, matrix: Any = None) -> Any:
        """Bounding rectangle of the union of all triangles.

        Mirrors upstream by iterating over ``collect_triangles`` and
        returning ``None`` if the triangle list is empty.
        """
        try:
            triangles = self.collect_triangles(xform, matrix)
        except NotImplementedError:
            return None
        if not triangles:
            return None
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for tri in triangles:
            for corner in tri.corner:
                cx, cy = float(corner[0]), float(corner[1])
                min_x = min(min_x, cx)
                min_y = min(min_y, cy)
                max_x = max(max_x, cx)
                max_y = max(max_y, cy)
        return (min_x, min_y, max_x - min_x, max_y - min_y)
