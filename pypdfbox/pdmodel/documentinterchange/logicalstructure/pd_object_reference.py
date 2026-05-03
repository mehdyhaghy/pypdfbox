from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
    from pypdfbox.pdmodel.pd_page import PDPage

_LOG = logging.getLogger(__name__)

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

    #: ``/Type`` value identifying an annotation dictionary that ``/Obj``
    #: references. Mirrors PDFBox's ``COSName.ANNOT`` string. Exposed as a
    #: class constant so callers can predicate against it without reaching
    #: into the COS namespace directly.
    SUBTYPE_ANNOT: str = "Annot"
    #: ``/Subtype`` value on a Form XObject stream that ``/Obj`` references.
    SUBTYPE_XOBJECT_FORM: str = "Form"
    #: ``/Subtype`` value on an Image XObject stream that ``/Obj`` references.
    SUBTYPE_XOBJECT_IMAGE: str = "Image"

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

    # ---------- /Pg page (typed PDPage — mirrors upstream getPage) ----

    def get_page(self) -> "PDPage | None":
        """Resolve ``/Pg`` to a typed :class:`PDPage`.

        Mirrors upstream ``PDObjectReference.getPage()``. Returns ``None``
        when ``/Pg`` is absent or not a dictionary. ``/Pg`` is optional —
        when present on the OBJR it overrides the enclosing structure
        element's ``/Pg`` for this referenced object only (PDF 32000-1
        §14.7.4.3).
        """
        page_dict = self._dictionary.get_dictionary_object(_PG)
        if not isinstance(page_dict, COSDictionary):
            return None
        # Local import avoids the pdmodel→logicalstructure→pdmodel cycle.
        from pypdfbox.pdmodel.pd_page import PDPage

        return PDPage(page_dict)

    def set_page(self, page: "PDPage | COSDictionary | None") -> None:
        """Set ``/Pg`` to a typed :class:`PDPage` wrapper or remove it."""
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

        Mirrors upstream ``getReferencedObject`` (PDF 32000-1 §14.7.4.3):

        1. If ``/Obj`` is a ``COSStream`` with ``/Subtype /Form`` or
           ``/Image`` it is wrapped as :class:`PDFormXObject` /
           :class:`PDImageXObject`.
        2. Otherwise — including streams whose ``/Subtype`` is unknown —
           the resolver falls through to annotation dispatch via
           :meth:`PDAnnotation.create`. The annotation is returned only
           when it dispatched to a *known* subclass, or when
           ``/Type /Annot`` is present (matching upstream's
           ``!instanceof PDAnnotationUnknown || /Type == /Annot``).
        3. Returns ``None`` when ``/Obj`` is absent, points at
           something that isn't a dictionary, or fails both dispatch
           paths.

        Streams that aren't Form/Image XObjects (e.g. ``/Subtype /PS``)
        return ``None`` — upstream's ``PDXObject.createXObject`` raises
        ``IOException`` for unknown subtypes which the upstream catch
        block swallows and logs.
        """
        obj = self._dictionary.get_dictionary_object(_OBJ)
        if obj is None:
            return None

        # ---- Streams: try XObject dispatch first (matches upstream). ----
        if isinstance(obj, COSStream):
            subtype = obj.get_name(_SUBTYPE)
            if subtype == _FORM:
                # Local import — cluster boundary, see module docstring.
                from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (
                    PDFormXObject,
                )

                return PDFormXObject(obj)
            if subtype == _IMAGE:
                from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
                    PDImageXObject,
                )

                return PDImageXObject(obj)
            # Unknown stream subtype (e.g. /PS PostScript XObject).
            # Upstream catches the IOException and returns null after
            # falling through to annotation dispatch — but a stream is
            # never a valid annotation, so short-circuit here.
            _LOG.debug(
                "PDObjectReference /Obj stream has unrecognised /Subtype %r — "
                "returning None",
                subtype,
            )
            return None

        # ---- Dicts: annotation dispatch with upstream's filter rule. ----
        if isinstance(obj, COSDictionary):
            from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
                PDAnnotation,
            )
            from pypdfbox.pdmodel.interactive.annotation.pd_annotation_unknown import (
                PDAnnotationUnknown,
            )

            type_name = obj.get_name(_TYPE)
            try:
                annotation = PDAnnotation.create(obj)
            except (TypeError, ValueError) as exc:
                _LOG.debug(
                    "PDObjectReference /Obj annotation dispatch failed: %s", exc
                )
                return None
            # Upstream returns the annotation when it's a *known* subclass,
            # or when /Type is /Annot (allowing /Subtype-less typed dicts).
            if not isinstance(annotation, PDAnnotationUnknown):
                return annotation
            if type_name == _ANNOT:
                return annotation
            return None

        # COSBase that's neither a dict nor a stream — not resolvable.
        return None

    # ---------- /Obj presence + subtype predicates (pypdfbox additions) ----

    def has_obj(self) -> bool:
        """Return ``True`` when ``/Obj`` is present.

        pypdfbox addition: lets callers gate :meth:`get_referenced_object`
        without paying the dispatch cost just to check for absence.
        """
        return self._dictionary.get_dictionary_object(_OBJ) is not None

    def has_pg(self) -> bool:
        """Return ``True`` when ``/Pg`` is present and a dictionary.

        pypdfbox addition: ``/Pg`` on an OBJR is optional (PDF 32000-1
        §14.7.4.3); this predicate distinguishes "no override" from
        "override is malformed" without materialising a :class:`PDPage`.
        """
        return isinstance(
            self._dictionary.get_dictionary_object(_PG), COSDictionary
        )

    def is_referenced_form_xobject(self) -> bool:
        """Return ``True`` when ``/Obj`` is a Form XObject stream.

        pypdfbox addition: probes ``/Obj``'s ``/Subtype`` directly without
        running the full annotation/XObject dispatch. Returns ``False``
        when ``/Obj`` is absent, not a stream, or has any other subtype.
        """
        obj = self._dictionary.get_dictionary_object(_OBJ)
        if not isinstance(obj, COSStream):
            return False
        return obj.get_name(_SUBTYPE) == self.SUBTYPE_XOBJECT_FORM

    def is_referenced_image_xobject(self) -> bool:
        """Return ``True`` when ``/Obj`` is an Image XObject stream.

        pypdfbox addition: companion to :meth:`is_referenced_form_xobject`.
        """
        obj = self._dictionary.get_dictionary_object(_OBJ)
        if not isinstance(obj, COSStream):
            return False
        return obj.get_name(_SUBTYPE) == self.SUBTYPE_XOBJECT_IMAGE

    def is_referenced_annotation(self) -> bool:
        """Return ``True`` when ``/Obj`` is a dictionary with ``/Type /Annot``.

        pypdfbox addition: probes the dictionary's ``/Type`` rather than
        running annotation dispatch. Note that an annotation dictionary
        without ``/Type /Annot`` is still a valid annotation per PDF
        32000-1 §12.5.2 (``/Type`` is optional); this predicate is the
        narrow positive answer — callers wanting the upstream-aligned
        "is this anything dispatchable as an annotation?" still need to
        call :meth:`get_referenced_object`.
        """
        obj = self._dictionary.get_dictionary_object(_OBJ)
        if not isinstance(obj, COSDictionary) or isinstance(obj, COSStream):
            return False
        return obj.get_name(_TYPE) == self.SUBTYPE_ANNOT

    def set_referenced_object(
        self, obj: "PDAnnotation | PDXObject | None"
    ) -> None:
        """Set ``/Obj`` to a typed wrapper or remove it.

        Accepts a typed :class:`PDAnnotation` / :class:`PDXObject`
        wrapper (calls ``get_cos_object()``) or ``None`` to remove
        ``/Obj``. Raw ``COSBase`` values should go through :meth:`set_obj`
        instead — keeping the typed surface narrow makes intent obvious.

        Upstream PDFBox splits this into two overloads —
        ``setReferencedObject(PDAnnotation)`` and
        ``setReferencedObject(PDXObject)``. Python doesn't have method
        overloading; one entry-point dispatches on ``get_cos_object()``
        which both wrappers implement.
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
