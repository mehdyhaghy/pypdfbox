from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_INK_LIST: COSName = COSName.get_pdf_name("InkList")


class PDAnnotationInk(PDAnnotationMarkup):
    """``/Subtype /Ink`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk``.

    ``/InkList`` is an array of arrays — each inner array is a stroked
    path of alternating x/y float coordinates (PDF 32000-1:2008 §12.5.6.13).
    """

    SUB_TYPE: str = "Ink"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /InkList ----------

    def get_ink_list(self) -> "PDInkList | None":
        from .pd_ink_list import PDInkList

        value = self._dict.get_dictionary_object(_INK_LIST)
        if isinstance(value, COSArray):
            return PDInkList(value)
        return None

    def set_ink_list(self, ink: "PDInkList | COSArray | None") -> None:
        from .pd_ink_list import PDInkList

        if ink is None:
            self._dict.remove_item(_INK_LIST)
            return
        arr = ink.get_cos_array() if isinstance(ink, PDInkList) else ink
        self._dict.set_item(_INK_LIST, arr)

    # ---------- raw float[][] accessors (upstream parity) ----------

    def get_ink_paths(self) -> list[list[float]]:
        """Return ``/InkList`` as a raw list of float lists — one inner
        list per stroked path, each a series of alternating x/y
        coordinates.

        Mirrors upstream ``getInkList() -> float[][]``: returns an empty
        list when ``/InkList`` is absent (not ``None``), and substitutes
        an empty inner list for any non-array entry.
        """
        value = self._dict.get_dictionary_object(_INK_LIST)
        if not isinstance(value, COSArray):
            return []
        result: list[list[float]] = []
        for i in range(value.size()):
            item = value.get(i)
            if isinstance(item, COSArray):
                result.append(item.to_float_array())
            else:
                result.append([])
        return result

    def set_ink_paths(
        self,
        paths: list[list[float]] | list[tuple[float, ...]] | tuple | None,
    ) -> None:
        """Replace ``/InkList`` from a raw list of float lists. ``None``
        removes the entry.

        Mirrors upstream ``setInkList(float[][])``.
        """
        if paths is None:
            self._dict.remove_item(_INK_LIST)
            return
        outer = COSArray()
        for path in paths:
            inner = COSArray([COSFloat(float(c)) for c in path])
            outer.add(inner)
        self._dict.set_item(_INK_LIST, outer)

    def path_count(self) -> int:
        """Return the number of disjoint stroked paths in ``/InkList``.

        Returns ``0`` when ``/InkList`` is absent or not a ``COSArray``.
        Convenience helper — upstream callers iterate ``getInkList().length``;
        this avoids materialising the float array just to count paths.
        """
        value = self._dict.get_dictionary_object(_INK_LIST)
        if isinstance(value, COSArray):
            return value.size()
        return 0


__all__ = ["PDAnnotationInk"]
