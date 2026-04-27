from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_PG: COSName = COSName.get_pdf_name("Pg")
_OBJ: COSName = COSName.get_pdf_name("Obj")
_ANNOT: str = "Annot"
_XOBJECT: str = "XObject"
_FORM: str = "Form"
_IMAGE: str = "Image"


class PDObjectReference:
    """
    An object reference (``/Type /OBJR`` dictionary). Mirrors PDFBox
    ``PDObjectReference``.

    Exposes typed resolution of the referenced object via
    :meth:`get_referenced_object`. Per PDF 32000-1 §14.7.4 ``/Obj``
    references either a ``PDAnnotation`` (an OBJR pointing at an
    annotation in a page's ``/Annots`` array) or a ``PDXObject`` (rare —
    a Form XObject acting as a tagged unit). Raw ``/Pg`` and ``/Obj``
    accessors remain for callers that need the underlying COS objects.
    """

    TYPE: str = "OBJR"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dictionary: COSDictionary = COSDictionary()
            self._dictionary.set_name(_TYPE, self.TYPE)
        else:
            self._dictionary = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /Pg page (raw COSDictionary; typed PDPage deferred) ----

    def get_pg(self) -> COSDictionary | None:
        pg = self._dictionary.get_dictionary_object(_PG)
        return pg if isinstance(pg, COSDictionary) else None

    def set_pg(self, page: COSDictionary | None) -> None:
        if page is None:
            self._dictionary.remove_item(_PG)
            return
        cos = page.get_cos_object() if hasattr(page, "get_cos_object") else page
        self._dictionary.set_item(_PG, cos)

    # ---------- /Obj referenced object (raw COSBase) ----

    def get_obj(self) -> COSBase | None:
        return self._dictionary.get_dictionary_object(_OBJ)

    def set_obj(self, obj: COSBase | None) -> None:
        if obj is None:
            self._dictionary.remove_item(_OBJ)
            return
        cos = obj.get_cos_object() if hasattr(obj, "get_cos_object") else obj
        self._dictionary.set_item(_OBJ, cos)

    # ---------- /Obj typed resolution ----

    def get_referenced_object(self) -> "PDAnnotation | PDXObject | None":
        """Resolve ``/Obj`` to a typed wrapper.

        Returns a :class:`PDAnnotation` subclass when ``/Obj`` points at
        an annotation dict (``/Type /Annot``), a :class:`PDFormXObject`
        or :class:`PDImageXObject` when it points at a Form / Image
        XObject (either ``/Type /XObject`` on a dict or a stream whose
        ``/Subtype`` identifies the form/image), or ``None`` when
        ``/Obj`` is absent or unresolvable.
        """
        obj = self._dictionary.get_dictionary_object(_OBJ)
        if obj is None:
            return None

        # Local imports break the cos→pdmodel→annotation/XObject cycle.
        if isinstance(obj, COSStream):
            subtype = obj.get_name(_SUBTYPE)
            if subtype == _FORM:
                from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (
                    PDFormXObject,
                )

                return PDFormXObject(obj)
            if subtype == _IMAGE:
                from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
                    PDImageXObject,
                )

                return PDImageXObject(obj)
            return None

        if isinstance(obj, COSDictionary):
            type_name = obj.get_name(_TYPE)
            subtype = obj.get_name(_SUBTYPE)
            if type_name == _ANNOT:
                from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
                    PDAnnotation,
                )

                return PDAnnotation.create(obj)
            if type_name == _XOBJECT or subtype in (_FORM, _IMAGE):
                # Some producers stamp /Type /XObject on a dict (rare —
                # XObjects are usually streams). Fall through if /Subtype
                # is missing; we cannot dispatch without it.
                if subtype == _FORM:
                    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (
                        PDFormXObject,
                    )

                    # PDFormXObject requires a stream; a bare dict cannot
                    # be wrapped. Return None rather than raising — round-
                    # tripping a malformed reference shouldn't crash.
                    return None
                if subtype == _IMAGE:
                    return None
        return None

    def set_referenced_object(
        self, obj: "PDAnnotation | PDXObject | None"
    ) -> None:
        """Set ``/Obj`` to a typed wrapper or remove it.

        Accepts a typed :class:`PDAnnotation` / :class:`PDXObject`
        wrapper (calls ``get_cos_object()``) or ``None`` to remove
        ``/Obj``. Raw ``COSBase`` values should go through :meth:`set_obj`
        instead — keeping the typed surface narrow makes intent obvious.
        """
        if obj is None:
            self._dictionary.remove_item(_OBJ)
            return
        if not hasattr(obj, "get_cos_object"):
            raise TypeError(
                "set_referenced_object expects a typed wrapper exposing "
                f"get_cos_object(); got {type(obj).__name__}. Use set_obj "
                "for raw COSBase values."
            )
        self._dictionary.set_item(_OBJ, obj.get_cos_object())


__all__ = ["PDObjectReference"]
