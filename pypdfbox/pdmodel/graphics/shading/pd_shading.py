from __future__ import annotations

from collections.abc import Iterable, Sequence

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSStream

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SHADING: COSName = COSName.get_pdf_name("Shading")
_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_BACKGROUND: COSName = COSName.get_pdf_name("Background")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_ANTI_ALIAS: COSName = COSName.get_pdf_name("AntiAlias")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


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
        shading_type = base.get_int(_SHADING_TYPE)
        if shading_type == PDShading.SHADING_TYPE1:
            return PDShadingType1(base)
        if shading_type == PDShading.SHADING_TYPE2:
            return PDShadingType2(base)
        if shading_type == PDShading.SHADING_TYPE3:
            return PDShadingType3(base)
        if shading_type == PDShading.SHADING_TYPE4:
            if not isinstance(base, COSStream):
                raise OSError(
                    "Shading type 4 requires a stream, got plain dictionary"
                )
            return PDShadingType4(base)
        if shading_type == PDShading.SHADING_TYPE5:
            if not isinstance(base, COSStream):
                raise OSError(
                    "Shading type 5 requires a stream, got plain dictionary"
                )
            return PDShadingType5(base)
        if shading_type == PDShading.SHADING_TYPE6:
            if not isinstance(base, COSStream):
                raise OSError(
                    "Shading type 6 requires a stream, got plain dictionary"
                )
            return PDShadingType6(base)
        if shading_type == PDShading.SHADING_TYPE7:
            if not isinstance(base, COSStream):
                raise OSError(
                    "Shading type 7 requires a stream, got plain dictionary"
                )
            return PDShadingType7(base)
        raise OSError(f"Invalid ShadingType {shading_type}")

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_type(self) -> str:
        return "Shading"

    def get_shading_type(self) -> int:
        raise NotImplementedError("PDShading is abstract; override get_shading_type")

    def set_shading_type(self, shading_type: int) -> None:
        self._dict.set_int(_SHADING_TYPE, shading_type)

    # ---------- /ColorSpace ----------

    def get_color_space(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_COLOR_SPACE)

    def set_color_space(self, color_space: COSBase | None) -> None:
        if color_space is None:
            self._dict.remove_item(_COLOR_SPACE)
            return
        self._dict.set_item(_COLOR_SPACE, color_space)

    # ---------- /Background ----------

    def get_background(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_BACKGROUND)
        return v if isinstance(v, COSArray) else None

    def set_background(self, background: COSArray | None) -> None:
        if background is None:
            self._dict.remove_item(_BACKGROUND)
            return
        self._dict.set_item(_BACKGROUND, background)

    # ---------- /BBox ----------

    def get_b_box(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_BBOX)
        return v if isinstance(v, COSArray) else None

    def set_b_box(self, bbox: COSArray | None) -> None:
        if bbox is None:
            self._dict.remove_item(_BBOX)
            return
        self._dict.set_item(_BBOX, bbox)

    # ---------- /AntiAlias ----------

    def get_anti_alias(self) -> bool:
        return self._dict.get_boolean(_ANTI_ALIAS, False)

    def set_anti_alias(self, anti_alias: bool) -> None:
        self._dict.set_boolean(_ANTI_ALIAS, anti_alias)

    # ---------- /Function (base-level fallback) ----------

    def get_function(self):
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

    def get_functions_array(self) -> list:
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
            out: list = []
            for i in range(item.size()):
                entry = item.get_object(i)
                if entry is not None:
                    out.append(PDFunction.create(entry))
            return out
        return [PDFunction.create(item)]

    def set_function(self, value) -> None:  # type: ignore[no-untyped-def]
        """Set ``/Function``. Accepts a ``PDFunction`` (its backing COS
        object is stored), a raw ``COSDictionary`` / ``COSStream``, a
        ``COSArray`` of per-component functions, an iterable of
        ``PDFunction`` instances (wrapped into a fresh ``COSArray``), or
        ``None`` to remove. Mirrors upstream's overloaded
        ``setFunction(PDFunction)`` and ``setFunction(COSArray)``."""
        from pypdfbox.pdmodel.common.function import PDFunction  # noqa: PLC0415

        if value is None:
            self._dict.remove_item(_FUNCTION)
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
