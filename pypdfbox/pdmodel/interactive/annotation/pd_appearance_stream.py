from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]
_FORM_TYPE: COSName = COSName.get_pdf_name("FormType")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")
_STRUCT_PARENTS: COSName = COSName.get_pdf_name("StructParents")


class PDAppearanceStream:
    """
    An appearance stream is a Form XObject — a self-contained content
    stream rendered inside the annotation rectangle. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream``.

    Upstream extends ``PDFormXObject``. The cluster #6 lite port of
    PDAppearanceStream wraps a ``COSStream`` directly without going
    through ``PDFormXObject`` — the form XObject base brings in
    ``/Type /XObject``, ``/Subtype /Form``, ``/BBox``, ``/Matrix``,
    ``/Resources`` semantics that aren't yet exercised by the appearance
    surface we expose to callers. The full inheritance chain
    ``PDAppearanceStream -> PDFormXObject -> PDXObject`` lands with the
    rendering cluster (PRD §6.13). Documented in ``CHANGES.md``.

    The ``get_stream`` / ``get_resources`` / ``set_resources`` accessors
    cover the surface needed by :class:`PDAppearanceContentStream` to
    open a writer against the appearance.
    """

    def __init__(self, stream: COSStream) -> None:
        if not isinstance(stream, COSStream):
            raise TypeError(
                "PDAppearanceStream requires a COSStream; got "
                f"{type(stream).__name__}"
            )
        self._stream = stream

    def get_cos_object(self) -> COSStream:
        return self._stream

    def get_stream(self) -> COSStream:
        """Return the underlying ``COSStream`` body — mirrors upstream
        ``PDFormXObject.getStream()`` (which returns the ``PDStream``
        wrapper; the lite port exposes the raw ``COSStream`` directly
        because :class:`PDStream` isn't on the appearance surface yet)."""
        return self._stream

    # ---------- /Resources ----------

    def get_resources(self) -> PDResources | None:
        """``/Resources`` of this appearance stream, or ``None`` if absent.

        Mirrors upstream ``PDFormXObject.getResources()``. When the key
        is present but the value isn't a dictionary, returns an empty
        :class:`PDResources` (PDFBOX-4372 — guards against a
        self-reference where the form refers to itself)."""
        value = self._stream.get_dictionary_object(_RESOURCES)
        if isinstance(value, COSDictionary):
            return PDResources(value)
        if self._stream.contains_key(_RESOURCES):
            return PDResources()
        return None

    def set_resources(
        self, resources: PDResources | COSDictionary | None
    ) -> None:
        """Set the ``/Resources`` entry for this appearance stream."""
        if resources is None:
            self._stream.remove_item(_RESOURCES)
            return
        target = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        self._stream.set_item(_RESOURCES, target)

    # ---------- /FormType ----------

    def get_form_type(self) -> int:
        """Return the form type. Currently ``1`` is the only defined value;
        upstream ``PDFormXObject.getFormType()`` defaults to ``1`` when the
        entry is absent (PDF 32000-1:2008 §8.10.2)."""
        return self._stream.get_int(_FORM_TYPE, 1)

    def set_form_type(self, form_type: int) -> None:
        """Set the form type entry. Mirrors upstream
        ``PDFormXObject.setFormType(int)``."""
        self._stream.set_int(_FORM_TYPE, int(form_type))

    # ---------- /BBox ----------

    def get_bbox(self) -> PDRectangle | None:
        """Return the ``/BBox`` rectangle in form coordinates, or ``None``
        when absent. Mirrors upstream ``PDFormXObject.getBBox()``."""
        array = self._stream.get_cos_array(_BBOX)
        if array is None:
            return None
        return PDRectangle.from_cos_array(array)

    def set_bbox(self, bbox: PDRectangle | None) -> None:
        """Set the ``/BBox`` entry. ``None`` clears it. Mirrors upstream
        ``PDFormXObject.setBBox(PDRectangle)``."""
        if bbox is None:
            self._stream.remove_item(_BBOX)
            return
        if not isinstance(bbox, PDRectangle):
            raise TypeError(
                "set_bbox requires a PDRectangle or None; got "
                f"{type(bbox).__name__}"
            )
        self._stream.set_item(_BBOX, bbox.get_cos_array())

    # ---------- /Matrix ----------

    def get_matrix(self) -> list[float]:
        """``/Matrix`` as a 6-element list ``[a, b, c, d, e, f]``.

        Defaults to the identity matrix ``[1, 0, 0, 1, 0, 0]`` when the
        entry is absent or malformed (PDF 32000-1:2008 §8.10.2). Mirrors
        upstream ``PDFormXObject.getMatrix()`` semantics — pypdfbox returns
        a plain ``list[float]`` because the typed ``Matrix`` class lands
        with the rendering cluster.
        """
        value = self._stream.get_dictionary_object(_MATRIX)
        if isinstance(value, COSArray) and value.size() >= 6:
            out: list[float] = []
            for i in range(6):
                entry = value.get_object(i)
                if isinstance(entry, (COSInteger, COSFloat)):
                    out.append(float(entry.value))
                else:
                    # Malformed entry — fall back to identity, matching
                    # upstream Matrix.createMatrix() permissive behaviour.
                    return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
            return out
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def set_matrix(
        self, values: Sequence[float] | COSArray | None
    ) -> None:
        """Set the ``/Matrix`` entry.

        ``None`` clears the entry (callers fall back to identity).
        Sequences must have exactly 6 numeric elements.
        Mirrors upstream ``PDFormXObject.setMatrix(AffineTransform)``.
        """
        if values is None:
            self._stream.remove_item(_MATRIX)
            return
        if isinstance(values, COSArray):
            self._stream.set_item(_MATRIX, values)
            return
        if len(values) != 6:
            raise ValueError(
                f"/Matrix expects exactly 6 numbers (a b c d e f); got {len(values)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in values])
        self._stream.set_item(_MATRIX, arr)

    # ---------- /StructParents ----------

    def get_struct_parents(self) -> int:
        """Return the structural parent tree key, or ``-1`` when absent.
        Mirrors upstream ``PDFormXObject.getStructParents()`` whose
        underlying ``getInt`` defaults to ``-1``."""
        return self._stream.get_int(_STRUCT_PARENTS)

    def set_struct_parents(self, struct_parent: int) -> None:
        """Set the structural parent tree key. Mirrors upstream
        ``PDFormXObject.setStructParents(int)``."""
        self._stream.set_int(_STRUCT_PARENTS, int(struct_parent))


__all__ = ["PDAppearanceStream"]
