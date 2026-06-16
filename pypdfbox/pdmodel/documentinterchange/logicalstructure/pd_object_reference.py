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

    # ---------- /Pg page (raw COSDictionary alias) ----

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

    def get_page(self) -> PDPage | None:
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

    def set_page(self, page: PDPage | COSDictionary | None) -> None:
        """Set ``/Pg`` to a typed :class:`PDPage` wrapper or remove it."""
        if page is None:
            self._dictionary.remove_item(_PG)
            return
        from pypdfbox.pdmodel.pd_page import PDPage

        if isinstance(page, PDPage):
            self._dictionary.set_item(_PG, page.get_cos_object())
            return
        if isinstance(page, COSDictionary):
            self._dictionary.set_item(_PG, page)
            return
        raise TypeError(
            "set_page expects a PDPage, COSDictionary, or None; "
            f"got {type(page).__name__}"
        )

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

    def get_referenced_object(self) -> PDAnnotation | PDXObject | None:
        """Resolve ``/Obj`` to a typed wrapper.

        Mirrors upstream ``getReferencedObject`` (PDF 32000-1 §14.7.4.3):

        Upstream resolves ``/Obj`` via ``getCOSDictionary(OBJ)``, so a
        ``/Obj`` that is not a dictionary (string, integer, array, absent)
        yields ``None`` immediately. A ``COSStream`` is a ``COSDictionary``
        subclass, so it satisfies that lookup too.

        1. If ``/Obj`` is a ``COSStream`` the resolver calls
           ``PDXObject.create_x_object``. ``/Form`` →
           :class:`PDFormXObject`, ``/Image`` → :class:`PDImageXObject`,
           ``/PS`` → :class:`PDPostScriptXObject`. Any returned XObject is
           handed back. A genuinely invalid or absent ``/Subtype`` raises
           ``OSError`` inside ``create_x_object``; upstream wraps the stream
           branch in a try/catch whose catch block returns ``null``
           *directly* (the ``IOException`` unwinds straight past the
           annotation dispatch), so such a stream resolves to ``None`` — it
           is never treated as an annotation.
        2. When ``/Obj`` is a non-stream dictionary the resolver dispatches
           to an annotation via
           :meth:`PDAnnotation.create`. The annotation is returned when it
           dispatched to a *known* subclass, or when ``/Type`` is ``/Annot``
           **or absent**: upstream's ``createAnnotation`` stamps ``/Type
           /Annot`` onto a dictionary that has no ``/Type``, so the
           subsequent ``COSName.ANNOT.equals(getCOSName(TYPE))`` filter
           passes and the unknown annotation is returned. A dictionary
           carrying a *different* explicit ``/Type`` (e.g. ``/Page``) is
           left untouched, fails the filter, and yields ``None``.
        3. Returns ``None`` when ``/Obj`` is absent, is not a dictionary,
           or fails both dispatch paths.
        """
        obj = self._dictionary.get_dictionary_object(_OBJ)
        if not isinstance(obj, COSDictionary):
            # Upstream getCOSDictionary(OBJ) returns null for any non-dict
            # /Obj (string / integer / array / absent). A COSStream is a
            # COSDictionary subclass, so it is *not* excluded here.
            return None

        # ---- Streams: XObject dispatch only (matches upstream). ----
        if isinstance(obj, COSStream):
            # Local import — cluster boundary, see module docstring.
            from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject

            try:
                return PDXObject.create_x_object(obj, None)
            except OSError as exc:
                # Upstream wraps the stream branch in a try/catch whose catch
                # block returns null directly — an invalid /Subtype does NOT
                # fall through to annotation dispatch (the IOException unwinds
                # straight past it). Mirror that: streams that fail XObject
                # creation resolve to None.
                _LOG.debug(
                    "PDObjectReference /Obj stream XObject dispatch failed: %s",
                    exc,
                )
                return None

        # ---- Dicts: annotation dispatch with upstream's filter rule. ----
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
        # Upstream returns the annotation when it's a *known* subclass, or
        # when it is a PDAnnotationUnknown whose /Type is /Annot. Upstream's
        # createAnnotation stamps /Type /Annot onto a dictionary with no
        # /Type, so an unknown annotation with absent /Type also passes.
        if not isinstance(annotation, PDAnnotationUnknown):
            return annotation
        if type_name == _ANNOT or type_name is None:
            return annotation
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
        self, obj: PDAnnotation | PDXObject | None
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
        from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
            PDAnnotation,
        )

        if not isinstance(obj, (PDAnnotation, PDXObject)):
            raise TypeError(
                "set_referenced_object expects a PDAnnotation or PDXObject; "
                f"got {type(obj).__name__}. Use set_obj for raw COSBase "
                "values."
            )
        self._dictionary.set_item(_OBJ, obj.get_cos_object())


__all__ = ["PDObjectReference"]
