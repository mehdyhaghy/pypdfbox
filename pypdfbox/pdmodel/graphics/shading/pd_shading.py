from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSName,
    COSNumber,
    COSStream,
)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SHADING: COSName = COSName.get_pdf_name("Shading")
_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_CS: COSName = COSName.get_pdf_name("CS")
_BACKGROUND: COSName = COSName.get_pdf_name("Background")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_ANTI_ALIAS: COSName = COSName.get_pdf_name("AntiAlias")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


def _is_number_array(value: COSBase | None, *, min_size: int = 0) -> bool:
    if not isinstance(value, COSArray) or value.size() < min_size:
        return False
    return all(isinstance(value.get_object(i), COSNumber) for i in range(value.size()))


class PDShading:
    """A Shading resource. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.shading.PDShading`` lite surface.

    The class is abstract: ``get_shading_type`` must be overridden by each
    concrete subclass. Function evaluation, paint conversion, mesh-data
    decoding, and bounds calculations are deferred until the rendering
    cluster lands.
    """

    SHADING_TYPE1: int = 1
    SHADING_TYPE2: int = 2
    SHADING_TYPE3: int = 3
    SHADING_TYPE4: int = 4
    SHADING_TYPE5: int = 5
    SHADING_TYPE6: int = 6
    SHADING_TYPE7: int = 7

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        if dictionary_or_stream is None:
            self._dict: COSDictionary = COSDictionary()
        else:
            if not isinstance(dictionary_or_stream, COSDictionary):
                raise TypeError(
                    "PDShading expects COSDictionary or COSStream, got "
                    f"{type(dictionary_or_stream).__name__}"
                )
            self._dict = dictionary_or_stream

    # ---------- factory ----------

    @staticmethod
    def create(base: COSDictionary | None) -> PDShading | None:
        # Local imports avoid an import cycle: each subclass imports
        # PDShading.
        from .pd_shading_type1 import PDShadingType1
        from .pd_shading_type2 import PDShadingType2
        from .pd_shading_type3 import PDShadingType3
        from .pd_shading_type4 import PDShadingType4
        from .pd_shading_type5 import PDShadingType5
        from .pd_shading_type6 import PDShadingType6
        from .pd_shading_type7 import PDShadingType7

        if base is None:
            return None
        if not isinstance(base, COSDictionary):
            raise TypeError(
                f"PDShading.create expects COSDictionary, got {type(base).__name__}"
            )
        # Upstream: getInt(SHADING_TYPE, 0) — missing/non-int defaults to 0,
        # which then falls through the switch to the "Unknown shading type 0"
        # error. Mirror the 0 default (not the COSDictionary -1 sentinel).
        shading_type = base.get_int(_SHADING_TYPE, 0)
        if shading_type == PDShading.SHADING_TYPE1:
            return PDShadingType1(base)
        if shading_type == PDShading.SHADING_TYPE2:
            return PDShadingType2(base)
        if shading_type == PDShading.SHADING_TYPE3:
            return PDShadingType3(base)
        if shading_type == PDShading.SHADING_TYPE4:
            # Upstream PDShading.create constructs PDShadingType4..7 directly
            # from the COSDictionary — the mesh constructors take a plain
            # COSDictionary (PDShadingType4(COSDictionary)), not a stream.
            # An earlier stream-required guard here diverged from upstream by
            # raising on a plain mesh dictionary; removed for parity.
            return PDShadingType4(base)
        if shading_type == PDShading.SHADING_TYPE5:
            return PDShadingType5(base)
        if shading_type == PDShading.SHADING_TYPE6:
            return PDShadingType6(base)
        if shading_type == PDShading.SHADING_TYPE7:
            return PDShadingType7(base)
        raise OSError(f"Error: Unknown shading type {shading_type}")

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_type(self) -> str:
        return "Shading"

    def get_shading_type(self) -> int:
        """Return the ``/ShadingType`` value for this shading. Abstract on
        :class:`PDShading`: each concrete subclass returns its fixed code
        (1 for function-based, 2 axial, 3 radial, 4-7 mesh-based).

        Falls back to reading the ``/ShadingType`` entry off the underlying
        dictionary when called on a bare ``PDShading`` instance — matches
        the upstream behavior where the value is stored in COS and the
        getter is only declared ``abstract`` for compile-time enforcement.
        """
        value = self._dict.get_int(_SHADING_TYPE, 0)
        if value:
            return int(value)
        raise NotImplementedError("PDShading is abstract; override get_shading_type")

    def set_shading_type(self, shading_type: int) -> None:
        self._dict.set_int(_SHADING_TYPE, shading_type)

    @staticmethod
    def is_valid_shading_type(value: int) -> bool:
        """``True`` iff ``value`` is a defined shading-type identifier
        (``1`` through ``7``). Useful for validating ``/ShadingType``
        entries before dispatch — matches the range upstream's
        ``PDShading.create`` recognises in its switch."""
        return isinstance(value, int) and 1 <= value <= 7

    # ---------- shading-type predicates ----------

    def is_function_based(self) -> bool:
        """``True`` for Type 1 (function-based) shadings."""
        return self.get_shading_type() == PDShading.SHADING_TYPE1

    def is_axial(self) -> bool:
        """``True`` for Type 2 (axial / linear-gradient) shadings."""
        return self.get_shading_type() == PDShading.SHADING_TYPE2

    def is_radial(self) -> bool:
        """``True`` for Type 3 (radial-gradient) shadings."""
        return self.get_shading_type() == PDShading.SHADING_TYPE3

    def is_mesh_based(self) -> bool:
        """``True`` for the mesh-based shading types (4–7): Free-Form
        Gouraud, Lattice-Form Gouraud, Coons Patch, and Tensor-Product
        Patch meshes. Mirrors the dispatch families upstream's
        ``PDShading.create`` switch groups together with
        ``PDMeshBasedShadingType`` parentage."""
        return self.get_shading_type() in (
            PDShading.SHADING_TYPE4,
            PDShading.SHADING_TYPE5,
            PDShading.SHADING_TYPE6,
            PDShading.SHADING_TYPE7,
        )

    # ---------- /ColorSpace ----------

    def get_color_space(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_COLOR_SPACE, _CS)

    def set_color_space(self, color_space: COSBase | None) -> None:
        if color_space is None:
            self.clear_color_space()
            return
        self._dict.set_item(_COLOR_SPACE, color_space)

    def has_color_space(self) -> bool:
        """``True`` when ``/ColorSpace`` or fallback ``/CS`` is present."""
        return self._dict.get_dictionary_object(_COLOR_SPACE, _CS) is not None

    def clear_color_space(self) -> None:
        """Remove both long and abbreviated color-space entries."""
        self._dict.remove_item(_COLOR_SPACE)
        self._dict.remove_item(_CS)

    def get_color_space_object(self, resources: Any = None) -> Any:
        """Return the ``/ColorSpace`` (or ``/CS`` short-form) entry wrapped
        as a typed ``PDColorSpace``, or ``None`` when absent. Mirrors
        upstream ``PDShading.getColorSpace()`` which dispatches via
        ``PDColorSpace.create(...)`` and accepts the abbreviated ``/CS``
        key as a fallback (see ``COSDictionary.getDictionaryObject(CS,
        COLORSPACE)`` in upstream).

        ``resources`` is forwarded to ``PDColorSpace.create`` so named
        color-space references (e.g. ``/CS0`` looked up via the page's
        ``/Resources/ColorSpace`` table) can be resolved.
        """
        from pypdfbox.pdmodel.graphics.color.pd_color_space import (  # noqa: PLC0415
            PDColorSpace,
        )

        # Match upstream's two-key lookup: prefer /ColorSpace, fall back
        # to the abbreviated /CS form (used in inline-image-style shading
        # dictionaries).
        cs_obj = self._dict.get_dictionary_object(_COLOR_SPACE, _CS)
        if cs_obj is None:
            return None
        return PDColorSpace.create(cs_obj, resources)

    def set_color_space_object(self, color_space: Any) -> None:
        """Set ``/ColorSpace`` from a typed ``PDColorSpace`` (its backing
        COS object is stored), a raw ``COSBase``, or ``None`` (clears the
        entry). Mirrors upstream
        ``PDShading.setColorSpace(PDColorSpace)``."""
        from pypdfbox.pdmodel.graphics.color.pd_color_space import (  # noqa: PLC0415
            PDColorSpace,
        )

        if color_space is None:
            self.clear_color_space()
            return
        if isinstance(color_space, PDColorSpace):
            cs_cos = color_space.get_cos_object()
            if cs_cos is None:
                self.clear_color_space()
                return
            self._dict.set_item(_COLOR_SPACE, cs_cos)
            return
        if isinstance(color_space, COSBase):
            self._dict.set_item(_COLOR_SPACE, color_space)
            return
        raise TypeError(
            "set_color_space_object expects PDColorSpace, COSBase, or "
            f"None; got {type(color_space).__name__}"
        )

    # ---------- /Background ----------

    def get_background(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_BACKGROUND)
        return v if isinstance(v, COSArray) else None

    def set_background(self, background: COSArray | None) -> None:
        if background is None:
            self.clear_background()
            return
        self._dict.set_item(_BACKGROUND, background)

    def has_background(self) -> bool:
        """``True`` when ``/Background`` is a non-empty numeric array."""
        return _is_number_array(
            self._dict.get_dictionary_object(_BACKGROUND), min_size=1
        )

    def clear_background(self) -> None:
        """Remove ``/Background``. No-op if absent."""
        self._dict.remove_item(_BACKGROUND)

    # ---------- /BBox ----------

    def get_b_box(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_BBOX)
        return v if isinstance(v, COSArray) else None

    def set_b_box(self, bbox: COSArray | None) -> None:
        if bbox is None:
            self.clear_b_box()
            return
        self._dict.set_item(_BBOX, bbox)

    def has_b_box(self) -> bool:
        """``True`` when ``/BBox`` is present as a valid numeric 4-array."""
        return _is_number_array(self._dict.get_dictionary_object(_BBOX), min_size=4)

    def clear_b_box(self) -> None:
        """Remove ``/BBox``. No-op if absent."""
        self._dict.remove_item(_BBOX)

    def get_b_box_rect(self) -> Any:
        """Return ``/BBox`` as a typed ``PDRectangle``, or ``None`` when the
        entry is absent or not a valid 4-entry numeric array. Mirrors
        upstream ``PDShading.getBBox()`` which returns ``PDRectangle``."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle  # noqa: PLC0415

        value = self._dict.get_dictionary_object(_BBOX)
        if isinstance(value, COSArray) and value.size() >= 4:
            try:
                return PDRectangle.from_cos_array(value)
            except (TypeError, ValueError):
                return None
        return None

    def set_b_box_rect(self, bbox: Any) -> None:
        """Set ``/BBox`` from a typed ``PDRectangle``, raw ``COSArray``, or
        ``None`` (clears the entry). Mirrors upstream
        ``PDShading.setBBox(PDRectangle)``."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle  # noqa: PLC0415

        if bbox is None:
            self.clear_b_box()
            return
        if isinstance(bbox, PDRectangle):
            self._dict.set_item(_BBOX, bbox.to_cos_array())
            return
        if isinstance(bbox, COSArray):
            self._dict.set_item(_BBOX, bbox)
            return
        raise TypeError(
            "set_b_box_rect expects PDRectangle, COSArray, or None; got "
            f"{type(bbox).__name__}"
        )

    # ---------- /AntiAlias ----------

    def get_anti_alias(self) -> bool:
        return self._dict.get_boolean(_ANTI_ALIAS, False)

    def set_anti_alias(self, anti_alias: bool) -> None:
        self._dict.set_boolean(_ANTI_ALIAS, anti_alias)

    def has_anti_alias(self) -> bool:
        """``True`` when ``/AntiAlias`` is present as a COS boolean."""
        return isinstance(self._dict.get_dictionary_object(_ANTI_ALIAS), COSBoolean)

    def clear_anti_alias(self) -> None:
        """Remove ``/AntiAlias``. No-op if absent."""
        self._dict.remove_item(_ANTI_ALIAS)

    def is_anti_alias(self) -> bool:
        """Predicate alias for :meth:`get_anti_alias`. Returns ``True``
        when ``/AntiAlias`` is present and truthy. Convenience companion
        to upstream's ``getAntiAlias()`` for callers that read the entry
        as a boolean test."""
        return self.get_anti_alias()

    # ---------- /Function (base-level fallback) ----------

    def get_function(self) -> Any:
        """Return the ``/Function`` entry wrapped as a ``PDFunction``
        (dispatched on ``/FunctionType``), or ``None`` when absent.

        Mirrors upstream ``PDShading.getFunction``. When ``/Function`` is
        an array of single-output functions (one per color component),
        returns the raw ``COSArray`` — callers should use
        :meth:`get_functions_array` to enumerate per-component functions.

        Subclasses (Types 1–3) override with a typed wrapper; this base
        implementation provides the same behavior for direct base-class
        users and for shading types where the subclass does not override.
        """
        from pypdfbox.pdmodel.common.function import PDFunction  # noqa: PLC0415

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return None
        if isinstance(item, COSArray):
            return item
        return PDFunction.create(item)

    def has_function(self) -> bool:
        """``True`` when ``/Function`` is a function dictionary/stream or array."""
        return isinstance(
            self._dict.get_dictionary_object(_FUNCTION),
            (COSArray, COSDictionary, COSStream),
        )

    def get_functions_array(self) -> list[Any]:
        """Return the per-component ``/Function`` entries wrapped as
        ``PDFunction`` instances. When ``/Function`` is a single function,
        returns a one-element list. Returns an empty list when absent.

        Mirrors upstream ``PDShading.getFunctionsArray`` (which is private
        in upstream but exposed here for callers that need explicit
        per-component access)."""
        from pypdfbox.pdmodel.common.function import PDFunction  # noqa: PLC0415

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return []
        if isinstance(item, COSArray):
            out: list[Any] = []
            for i in range(item.size()):
                entry = item.get_object(i)
                if entry is not None:
                    out.append(PDFunction.create(entry))
            return out
        return [PDFunction.create(item)]

    def set_function(self, value: Any) -> None:
        """Set ``/Function``. Accepts a ``PDFunction`` (its backing COS
        object is stored), a raw ``COSDictionary`` / ``COSStream``, a
        ``COSArray`` of per-component functions, an iterable of
        ``PDFunction`` instances (wrapped into a fresh ``COSArray``), or
        ``None`` to remove. Mirrors upstream's overloaded
        ``setFunction(PDFunction)`` and ``setFunction(COSArray)``."""
        from pypdfbox.pdmodel.common.function import PDFunction  # noqa: PLC0415

        if value is None:
            self.clear_function()
            return
        if isinstance(value, PDFunction):
            self._dict.set_item(_FUNCTION, value.get_cos_object())
            return
        if isinstance(value, COSBase):
            self._dict.set_item(_FUNCTION, value)
            return
        try:
            iterator = iter(value)
        except TypeError as exc:
            raise TypeError(
                "set_function expects PDFunction, COSDictionary, COSStream, "
                f"COSArray, iterable of PDFunction, or None; got "
                f"{type(value).__name__}"
            ) from exc
        array = COSArray()
        for entry in iterator:
            if isinstance(entry, PDFunction):
                array.add(entry.get_cos_object())
            elif isinstance(entry, COSBase):
                array.add(entry)
            else:
                raise TypeError(
                    "set_function iterable entries must be PDFunction or "
                    f"COSBase; got {type(entry).__name__}"
                )
        self._dict.set_item(_FUNCTION, array)

    def clear_function(self) -> None:
        """Remove ``/Function``. No-op if absent."""
        self._dict.remove_item(_FUNCTION)

    # ---------- function evaluation ----------

    def eval_function(
        self, input_value: float | Sequence[float] | Iterable[float]
    ) -> list[float]:
        """Convert input value(s) using the function(s) of the shading
        dictionary. Mirrors upstream ``PDShading.evalFunction(float)``
        and ``evalFunction(float[])``.

        Accepts a single ``float`` or a sequence of floats. Out-of-range
        outputs are clamped to ``[0, 1]`` per PDF §7.10.2 ("If the value
        returned by the function for a given colour component is out of
        range, it shall be adjusted to the nearest valid value.")"""
        if isinstance(input_value, (int, float)):
            input_list: list[float] = [float(input_value)]
        else:
            input_list = [float(v) for v in input_value]

        functions = self.get_functions_array()
        if not functions:
            raise OSError(
                "mandatory /Function element must be a dictionary or an array"
            )
        if len(functions) == 1:
            output = list(functions[0].eval(input_list))
        else:
            output = []
            for fn in functions:
                values = fn.eval(input_list)
                output.append(float(values[0]) if values else 0.0)

        # Clamp to [0, 1] per PDF spec.
        clamped: list[float] = []
        for v in output:
            f = float(v)
            if f < 0.0:
                f = 0.0
            elif f > 1.0:
                f = 1.0
            clamped.append(f)
        return clamped

    # ---------- paint (rendering hook) ----------

    def to_paint(self, matrix: Any = None) -> Any:
        """Return a renderer-side ``Paint`` for this shading.

        Mirrors upstream abstract ``PDShading.toPaint(Matrix)`` (line
        445 of ``PDShading.java``). Concrete subclasses (Types 1–7) wrap
        themselves in a type-specific ``ShadingPaint`` instance — see
        ``Type1ShadingPaint``, ``Type2ShadingPaint``, etc.

        Dispatches to the type-specific paint class based on
        ``get_shading_type()``. Subclasses that return ``None`` from this
        method (Types 4-7 currently) match the lite-surface convention
        used for the mesh shading types.
        """
        shading_type = self._dict.get_int(_SHADING_TYPE, 0)
        if shading_type == PDShading.SHADING_TYPE1:
            from .type1_shading_paint import Type1ShadingPaint  # noqa: PLC0415
            return Type1ShadingPaint(self, matrix)
        if shading_type == PDShading.SHADING_TYPE2:
            from .axial_shading_paint import AxialShadingPaint  # noqa: PLC0415
            return AxialShadingPaint(self, matrix)
        if shading_type == PDShading.SHADING_TYPE3:
            from .radial_shading_paint import RadialShadingPaint  # noqa: PLC0415
            return RadialShadingPaint(self, matrix)
        if shading_type == PDShading.SHADING_TYPE4:
            from .type4_shading_paint import Type4ShadingPaint  # noqa: PLC0415
            return Type4ShadingPaint(self, matrix)
        if shading_type == PDShading.SHADING_TYPE5:
            from .type5_shading_paint import Type5ShadingPaint  # noqa: PLC0415
            return Type5ShadingPaint(self, matrix)
        if shading_type == PDShading.SHADING_TYPE6:
            from .type6_shading_paint import Type6ShadingPaint  # noqa: PLC0415
            return Type6ShadingPaint(self, matrix)
        if shading_type == PDShading.SHADING_TYPE7:
            from .type7_shading_paint import Type7ShadingPaint  # noqa: PLC0415
            return Type7ShadingPaint(self, matrix)
        return None

    # ---------- bounds (rendering hook) ----------

    def get_bounds(self, xform=None, matrix=None):  # type: ignore[no-untyped-def]
        """Calculate a bounding rectangle around the areas of this shading
        context. Mirrors upstream ``PDShading.getBounds(AffineTransform,
        Matrix)`` whose default implementation returns ``null``.

        Subclasses that can compute a bounding rectangle (the mesh-based
        Triangle/Coons types in upstream) override this; the default
        return is ``None``. Both arguments are accepted to preserve the
        upstream signature, even though the default ignores them."""
        return None


__all__ = ["PDShading"]
