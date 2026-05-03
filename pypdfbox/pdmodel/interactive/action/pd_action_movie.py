from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
    PDAnnotationMovie,
)

from .pd_action import PDAction

_ANNOTATION: COSName = COSName.get_pdf_name("Annotation")
_T: COSName = COSName.get_pdf_name("T")
_OPERATION: COSName = COSName.get_pdf_name("Operation")


class PDActionMovie(PDAction):
    """Movie action. Mirrors PDFBox ``PDActionMovie``.

    The ``/Annotation`` entry is exposed both as a raw ``COSBase`` via
    :meth:`get_annotation_dictionary` (legacy back-compat) and as a
    typed :class:`PDAnnotationMovie` via :meth:`get_annotation`.

    PDF 32000-1 §12.6.4.10 Table 209 — Movie action."""

    SUB_TYPE = "Movie"

    # /Operation values per PDF 32000-1 §12.6.4.10 Table 209.
    # ``Play`` is the spec default when ``/Operation`` is absent.
    OPERATION_PLAY: str = "Play"
    OPERATION_STOP: str = "Stop"
    OPERATION_PAUSE: str = "Pause"
    OPERATION_RESUME: str = "Resume"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_annotation_dictionary(self) -> COSBase | None:
        """Return the raw ``/Annotation`` entry. Back-compat surface — new
        code should prefer :meth:`get_annotation` for the typed wrapper."""
        return self._action.get_dictionary_object(_ANNOTATION)

    def get_annotation(self) -> PDAnnotationMovie | None:
        """Return ``/Annotation`` as a typed :class:`PDAnnotationMovie`, or
        ``None`` when the entry is absent or not a dictionary."""
        entry = self._action.get_dictionary_object(_ANNOTATION)
        if isinstance(entry, COSDictionary):
            return PDAnnotationMovie(entry)
        return None

    def set_annotation(
        self, annotation: PDAnnotationMovie | COSBase | None
    ) -> None:
        """Replace ``/Annotation``. Accepts ``None`` (removes the entry),
        a :class:`PDAnnotationMovie` (stores its underlying COSDictionary),
        or a raw ``COSBase`` (stored as-is for back-compat)."""
        if annotation is None:
            self._action.remove_item(_ANNOTATION)
            return
        if isinstance(annotation, PDAnnotationMovie):
            self._action.set_item(_ANNOTATION, annotation.get_cos_object())
            return
        self._action.set_item(_ANNOTATION, annotation)

    def get_t(self) -> str | None:
        return self._action.get_string(_T)

    def set_t(self, title: str | None) -> None:
        self._action.set_string(_T, title)

    def get_operation(self) -> str | None:
        """Return the raw ``/Operation`` entry, or ``None`` when absent.

        Per PDF 32000-1 §12.6.4.10 Table 209 the spec default when absent
        is ``"Play"``; use :meth:`get_effective_operation` to apply the
        default."""
        return self._action.get_name(_OPERATION)

    def set_operation(self, operation: str | None) -> None:
        if operation is None:
            self._action.remove_item(_OPERATION)
            return
        self._action.set_name(_OPERATION, operation)

    def get_effective_operation(self) -> str:
        """Return ``/Operation`` with the spec default applied.

        When ``/Operation`` is absent the value defaults to
        :attr:`OPERATION_PLAY` per PDF 32000-1 §12.6.4.10 Table 209."""
        op = self._action.get_name(_OPERATION)
        return op if op is not None else self.OPERATION_PLAY

    # ---------- /Operation predicates ----------

    def is_play(self) -> bool:
        """``True`` when ``/Operation`` resolves to ``"Play"`` (also true
        when the entry is absent — the spec default)."""
        return self.get_effective_operation() == self.OPERATION_PLAY

    def is_stop(self) -> bool:
        return self._action.get_name(_OPERATION) == self.OPERATION_STOP

    def is_pause(self) -> bool:
        return self._action.get_name(_OPERATION) == self.OPERATION_PAUSE

    def is_resume(self) -> bool:
        return self._action.get_name(_OPERATION) == self.OPERATION_RESUME

    # ---------- /Annotation vs /T mutual exclusivity ----------

    def has_annotation(self) -> bool:
        """``True`` when ``/Annotation`` is present and is a dictionary.

        Per PDF 32000-1 §12.6.4.10 Table 209 a Movie action targets the
        movie either by direct ``/Annotation`` reference or by ``/T``
        title; this helper lets callers branch without re-parsing the
        underlying COS."""
        return isinstance(self._action.get_dictionary_object(_ANNOTATION), COSDictionary)

    def has_title(self) -> bool:
        """``True`` when ``/T`` is present (a non-``None`` title string).

        Counterpart to :meth:`has_annotation`; helps callers detect the
        title-based addressing form."""
        return self._action.get_string(_T) is not None

    def has_operation(self) -> bool:
        """``True`` when ``/Operation`` is present in the action dictionary.

        Distinct from :meth:`is_play` — :meth:`is_play` is also ``True``
        when ``/Operation`` is *absent* (the spec default). This predicate
        purely reports presence, letting callers tell "explicit Play" from
        "implicit Play" when round-tripping malformed PDFs."""
        return self._action.get_dictionary_object(_OPERATION) is not None

    # ---------- clear_* helpers ----------

    def clear_annotation(self) -> None:
        """Remove ``/Annotation`` from the action dictionary.

        Convenience for ``set_annotation(None)`` that mirrors the
        ``clear_*`` helpers on other action wrappers
        (:class:`PDActionSound.clear_sound` etc.)."""
        self._action.remove_item(_ANNOTATION)

    def clear_title(self) -> None:
        """Remove ``/T`` from the action dictionary.

        Convenience for ``set_t(None)`` that aligns the title-clear path
        with the typed annotation-clear helper."""
        self._action.remove_item(_T)

    def clear_operation(self) -> None:
        """Remove ``/Operation``, re-engaging the spec default ``"Play"``.

        Convenience for ``set_operation(None)``; useful when normalising
        an action back to the implicit-Play form."""
        self._action.remove_item(_OPERATION)

    # ---------- sanity predicates ----------

    def is_empty(self) -> bool:
        """``True`` when neither ``/Annotation`` nor ``/T`` is present.

        Per PDF 32000-1 §12.6.4.10 Table 209 a Movie action must target
        a movie via one of those two entries; without either it has no
        movie to act on. Parallels :class:`PDActionSound.is_empty`."""
        return not self.has_annotation() and not self.has_title()

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"Movie"``).

        Useful as a sanity check after round-tripping through
        :meth:`PDAction.create` or when constructing the wrapper around a
        hand-built :class:`COSDictionary`. Parallels
        :class:`PDActionSound.is_valid`."""
        return self.get_sub_type() == self.SUB_TYPE


__all__ = ["PDActionMovie"]
