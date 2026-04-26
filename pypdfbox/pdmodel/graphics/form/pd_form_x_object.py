from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

_FORM: COSName = COSName.get_pdf_name("Form")
_FORMTYPE: COSName = COSName.get_pdf_name("FormType")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")
_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]


class PDFormXObject(PDXObject):
    """
    Form XObject — reusable graphics container. Mirrors
    ``org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject``.

    Has ``/Subtype /Form`` and the form-specific entries:

    - ``/FormType``  — int (currently always 1).
    - ``/BBox``      — bounding box rectangle (required).
    - ``/Matrix``    — transformation matrix [a b c d e f] (optional;
      defaults to identity per PDF §8.10).
    - ``/Resources`` — local resource dict (optional; falls back to the
      page's resources at use-time).
    """

    def __init__(self, stream: PDStream | COSStream) -> None:
        super().__init__(stream, _FORM)

    # ---------- /FormType ----------

    def get_form_type(self) -> int:
        """``/FormType`` (default 1 — the only defined value)."""
        return self.get_cos_object().get_int(_FORMTYPE, 1)

    def set_form_type(self, form_type: int) -> None:
        self.get_cos_object().set_int(_FORMTYPE, int(form_type))

    # ---------- /BBox ----------

    def get_b_box(self) -> PDRectangle | None:
        """``/BBox``. Returns ``None`` when absent (matches upstream)."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_BBOX)
        if isinstance(value, COSArray):
            return PDRectangle.from_cos_array(value)
        return None

    # PDFBox spells it ``getBBox`` — keep both forms for camelCase fidelity
    # (PDFBox developers will type ``get_b_box`` after the case-conversion
    # rule, but the two-word form ``get_bbox`` is what most port tests use).
    def get_bbox(self) -> PDRectangle | None:
        return self.get_b_box()

    def set_b_box(self, bbox: PDRectangle | None) -> None:
        cos = self.get_cos_object()
        if bbox is None:
            cos.remove_item(_BBOX)
        else:
            cos.set_item(_BBOX, bbox.to_cos_array())

    def set_bbox(self, bbox: PDRectangle | None) -> None:
        self.set_b_box(bbox)

    # ---------- /Matrix ----------

    def get_matrix(self) -> list[float]:
        """``/Matrix`` as a 6-tuple ``[a, b, c, d, e, f]``. Defaults to the
        identity matrix ``[1, 0, 0, 1, 0, 0]`` per PDF §8.10. Mirrors
        upstream's ``Matrix.createMatrix(...)`` semantics on the array form
        (a typed ``Matrix`` class lands with the rendering cluster)."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_MATRIX)
        if isinstance(value, COSArray) and value.size() >= 6:
            out: list[float] = []
            for i in range(6):
                entry = value.get_object(i)
                if isinstance(entry, (COSInteger, COSFloat)):
                    out.append(float(entry.value))
                else:
                    raise TypeError(
                        f"/Matrix entry {i} is not numeric: {type(entry).__name__}"
                    )
            return out
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def set_matrix(self, values: Sequence[float] | COSArray | None) -> None:
        cos = self.get_cos_object()
        if values is None:
            cos.remove_item(_MATRIX)
            return
        if isinstance(values, COSArray):
            cos.set_item(_MATRIX, values)
            return
        if len(values) != 6:
            raise ValueError(
                f"/Matrix expects exactly 6 numbers (a b c d e f); got {len(values)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in values])
        cos.set_item(_MATRIX, arr)

    # ---------- /Resources ----------

    def get_resources(self) -> PDResources | None:
        """``/Resources`` if present, else ``None``. Note: when the key is
        present but the value isn't a dictionary, upstream returns an empty
        ``PDResources`` (PDFBOX-4372 — guards against a self-reference where
        the form refers to itself). We mirror that."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_RESOURCES)
        if isinstance(value, COSDictionary):
            return PDResources(value)
        if cos.contains_key(_RESOURCES):
            return PDResources()
        return None

    def set_resources(self, resources: PDResources | COSDictionary | None) -> None:
        cos = self.get_cos_object()
        if resources is None:
            cos.remove_item(_RESOURCES)
            return
        target = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        cos.set_item(_RESOURCES, target)
