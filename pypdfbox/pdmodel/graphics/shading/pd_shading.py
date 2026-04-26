from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSStream

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SHADING: COSName = COSName.get_pdf_name("Shading")
_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_BACKGROUND: COSName = COSName.get_pdf_name("Background")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_ANTI_ALIAS: COSName = COSName.get_pdf_name("AntiAlias")


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


__all__ = ["PDShading"]
