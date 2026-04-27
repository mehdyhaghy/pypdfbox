from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.measurement.pd_rendition import PDRendition

from .pd_action import PDAction

_AN: COSName = COSName.get_pdf_name("AN")
_OP: COSName = COSName.get_pdf_name("OP")
_JS: COSName = COSName.get_pdf_name("JS")
_R: COSName = COSName.get_pdf_name("R")


class PDActionRendition(PDAction):
    """Rendition action. Mirrors PDFBox ``PDActionRendition``.

    ``/AN`` (Screen annotation reference) and ``/R`` (rendition dictionary)
    are exposed as typed wrappers via :meth:`get_annotation` /
    :meth:`set_annotation` and :meth:`get_rendition` / :meth:`set_rendition`.
    The raw COS accessors :meth:`get_an` / :meth:`set_an` and
    :meth:`get_r` / :meth:`set_r` remain for back-compat."""

    SUB_TYPE = "Rendition"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /AN (raw, back-compat) ----------

    def get_an(self) -> COSBase | None:
        return self._action.get_dictionary_object(_AN)

    def set_an(self, an: COSBase | None) -> None:
        if an is None:
            self._action.remove_item(_AN)
            return
        self._action.set_item(_AN, an)

    # ---------- /AN (typed) ----------

    def get_annotation(self) -> PDAnnotation | None:
        """Return ``/AN`` as a typed :class:`PDAnnotation` subclass.

        Dispatches through :meth:`PDAnnotation.create`; a `/Subtype /Screen`
        dictionary therefore returns whatever the factory produces (currently
        :class:`PDAnnotationUnknown`, until a typed `PDAnnotationScreen`
        lands). Returns ``None`` when ``/AN`` is absent or not a dictionary."""
        entry = self._action.get_dictionary_object(_AN)
        if isinstance(entry, COSDictionary):
            return PDAnnotation.create(entry)
        return None

    def set_annotation(
        self, annotation: PDAnnotation | COSBase | None
    ) -> None:
        """Replace ``/AN``. Accepts ``None`` (removes the entry),
        a :class:`PDAnnotation` (stores its underlying COSDictionary),
        or a raw ``COSBase`` (stored as-is for back-compat)."""
        if annotation is None:
            self._action.remove_item(_AN)
            return
        if isinstance(annotation, PDAnnotation):
            self._action.set_item(_AN, annotation.get_cos_object())
            return
        self._action.set_item(_AN, annotation)

    # ---------- /OP, /JS ----------

    def get_op(self) -> int:
        return self._action.get_int(_OP)

    def set_op(self, op: int) -> None:
        self._action.set_int(_OP, op)

    def get_js(self) -> str | None:
        return self._action.get_string(_JS)

    def set_js(self, js: str | None) -> None:
        self._action.set_string(_JS, js)

    # ---------- /R (raw, back-compat) ----------

    def get_r(self) -> COSBase | None:
        return self._action.get_dictionary_object(_R)

    def set_r(self, r: COSBase | None) -> None:
        if r is None:
            self._action.remove_item(_R)
            return
        self._action.set_item(_R, r)

    # ---------- /R (typed) ----------

    def get_rendition(self) -> PDRendition | None:
        """Return ``/R`` as a typed :class:`PDRendition` subclass.

        Dispatches through :meth:`PDRendition.create`; ``/S /MR`` yields a
        :class:`PDMediaRendition`, ``/S /SR`` a :class:`PDSelectorRendition`.
        Returns ``None`` when ``/R`` is absent or not a dictionary, or when
        the factory does not recognise the ``/S`` subtype."""
        entry = self._action.get_dictionary_object(_R)
        if isinstance(entry, COSDictionary):
            return PDRendition.create(entry)
        return None

    def set_rendition(
        self, rendition: PDRendition | COSBase | None
    ) -> None:
        """Replace ``/R``. Accepts ``None`` (removes the entry),
        a :class:`PDRendition` (stores its underlying COSDictionary),
        or a raw ``COSBase`` (stored as-is for back-compat)."""
        if rendition is None:
            self._action.remove_item(_R)
            return
        if isinstance(rendition, PDRendition):
            self._action.set_item(_R, rendition.get_cos_object())
            return
        self._action.set_item(_R, rendition)


__all__ = ["PDActionRendition"]
