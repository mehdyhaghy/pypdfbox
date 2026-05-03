from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
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

    # PDF 32000-1 §12.6.4.13 Table 215 — /OP operation values.
    #: Play (only if rendition is currently stopped, otherwise no-op).
    OP_PLAY_IF_STOPPED: int = 0
    #: Stop the rendition.
    OP_STOP: int = 1
    #: Pause the rendition.
    OP_PAUSE: int = 2
    #: Resume the rendition.
    OP_RESUME: int = 3
    #: Play the rendition (resuming if paused; restarting if stopped).
    OP_PLAY: int = 4

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

    def get_screen_annotation(self) -> PDAnnotationScreen | None:
        """Return ``/AN`` as a typed :class:`PDAnnotationScreen`.

        PDF 32000-1 §12.6.4.13 Table 214 specifies ``/AN`` as a Screen
        annotation reference. Returns ``None`` when ``/AN`` is absent,
        not a dictionary, or not a Screen-subtype annotation. Distinct
        from :meth:`get_annotation` which dispatches through
        :meth:`PDAnnotation.create` and may yield any annotation
        subclass for malformed inputs."""
        entry = self._action.get_dictionary_object(_AN)
        if isinstance(entry, COSDictionary):
            wrapped = PDAnnotation.create(entry)
            if isinstance(wrapped, PDAnnotationScreen):
                return wrapped
        return None

    def has_annotation(self) -> bool:
        """``True`` when ``/AN`` is present and is a dictionary.

        Lets callers branch on annotation-presence without paying the
        cost of constructing a typed wrapper. Parallels
        :class:`PDActionMovie.has_annotation`."""
        return isinstance(self._action.get_dictionary_object(_AN), COSDictionary)

    def clear_annotation(self) -> None:
        """Remove ``/AN`` from the action dictionary.

        Convenience for ``set_annotation(None)`` that mirrors the
        ``clear_*`` helpers on sibling action wrappers."""
        self._action.remove_item(_AN)

    # ---------- /OP, /JS ----------

    def get_op(self) -> int:
        """Return ``/OP`` (Table 215 operation code), or ``-1`` when absent
        (matches the ``COSDictionary.get_int`` sentinel default). Use
        :meth:`get_operation` for an ``int | None`` flavour, or one of the
        ``is_*`` predicates for a single-operation check."""
        return self._action.get_int(_OP)

    def set_op(self, op: int) -> None:
        self._action.set_int(_OP, op)

    def get_operation(self) -> int | None:
        """Return ``/OP`` as an ``int`` when present, ``None`` otherwise.

        PDF 32000-1 §12.6.4.13 Table 214 makes ``/OP`` optional — it is
        required only when ``/JS`` is absent. Distinguishing "absent" from
        "explicitly 0 (Play if stopped)" matters to validators, hence this
        explicit ``None``-on-absent variant alongside :meth:`get_op`."""
        if self._action.get_dictionary_object(_OP) is None:
            return None
        return self._action.get_int(_OP)

    def has_op(self) -> bool:
        """Return ``True`` when the ``/OP`` entry is present."""
        return self._action.get_dictionary_object(_OP) is not None

    def clear_op(self) -> None:
        """Remove ``/OP`` from the action dictionary.

        PDF 32000-1 §12.6.4.13 Table 214 makes ``/OP`` optional —
        clearing it leaves the action in the ``/JS``-only form (which is
        legal *only* when ``/JS`` is present)."""
        self._action.remove_item(_OP)

    def is_play_if_stopped(self) -> bool:
        """Return ``True`` when ``/OP`` equals :attr:`OP_PLAY_IF_STOPPED`."""
        return self.get_operation() == self.OP_PLAY_IF_STOPPED

    def is_stop(self) -> bool:
        """Return ``True`` when ``/OP`` equals :attr:`OP_STOP`."""
        return self.get_operation() == self.OP_STOP

    def is_pause(self) -> bool:
        """Return ``True`` when ``/OP`` equals :attr:`OP_PAUSE`."""
        return self.get_operation() == self.OP_PAUSE

    def is_resume(self) -> bool:
        """Return ``True`` when ``/OP`` equals :attr:`OP_RESUME`."""
        return self.get_operation() == self.OP_RESUME

    def is_play(self) -> bool:
        """Return ``True`` when ``/OP`` equals :attr:`OP_PLAY`."""
        return self.get_operation() == self.OP_PLAY

    def get_js(self) -> str | None:
        """Return ``/JS`` as a Python string.

        Per PDF 32000-1 §12.6.4.13 Table 214 / §12.6.4.16, ``/JS`` may be
        either a text string (``COSString``) or a stream (``COSStream``).
        Mirrors :class:`PDActionJavaScript.get_action`. Returns ``None``
        when ``/JS`` is absent or not a recognised JS payload type."""
        base = self._action.get_dictionary_object(_JS)
        if isinstance(base, COSString):
            return base.get_string()
        if isinstance(base, COSStream):
            return base.to_text_string()
        return None

    def set_js(self, js: str | None) -> None:
        self._action.set_string(_JS, js)

    def has_js(self) -> bool:
        """Return ``True`` when the ``/JS`` entry is present (in either
        ``COSString`` or ``COSStream`` form)."""
        return self._action.get_dictionary_object(_JS) is not None

    def clear_js(self) -> None:
        """Remove ``/JS`` from the action dictionary.

        Convenience for ``set_js(None)`` — symmetrical with the other
        ``clear_*`` helpers on this wrapper."""
        self._action.remove_item(_JS)

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

    def has_rendition(self) -> bool:
        """``True`` when ``/R`` is present and is a dictionary.

        Lets callers branch on rendition-presence without constructing a
        typed wrapper. Parallels :meth:`has_annotation` /
        :meth:`PDActionMovie.has_annotation`."""
        return isinstance(self._action.get_dictionary_object(_R), COSDictionary)

    def clear_rendition(self) -> None:
        """Remove ``/R`` from the action dictionary.

        Convenience for ``set_rendition(None)`` that mirrors the other
        ``clear_*`` helpers on this wrapper."""
        self._action.remove_item(_R)

    # ---------- sanity predicates ----------

    def is_empty(self) -> bool:
        """``True`` when neither ``/R`` nor ``/AN`` is present.

        PDF 32000-1 §12.6.4.13 Table 214 says either a Rendition (``/R``)
        or a Screen annotation (``/AN``) should be present for the action
        to identify what to render. Without either, the action has no
        target to act on. Parallels :class:`PDActionMovie.is_empty`."""
        return not self.has_rendition() and not self.has_annotation()

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"Rendition"``).

        Useful as a sanity check after round-tripping through
        :meth:`PDAction.create` or when constructing the wrapper around a
        hand-built :class:`COSDictionary`. Parallels
        :class:`PDActionSound.is_valid`."""
        return self.get_sub_type() == self.SUB_TYPE


__all__ = ["PDActionRendition"]
