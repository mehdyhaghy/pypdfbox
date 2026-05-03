from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation

from .pd_action import PDAction

_H: COSName = COSName.get_pdf_name("H")
_T: COSName = COSName.T  # type: ignore[attr-defined]


class PDActionHide(PDAction):
    """Hide action. Mirrors PDFBox ``PDActionHide``.

    PDF 32000-1 §12.6.4.10 Table 200: ``/T`` is the annotation (or
    annotations) to be hidden or shown — encoded as a fully-qualified
    field-name text string, an annotation dictionary, or an array of
    either; ``/H`` is the hide flag (defaults to ``True``)."""

    SUB_TYPE = "Hide"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /T (raw, back-compat) ----------

    def get_target(self) -> COSBase | None:
        """Return the raw ``/T`` entry. Per PDF 32000-1 Table 200 the value
        can be a text string (fully-qualified field name), an annotation
        dictionary, or an array mixing the two. Use
        :meth:`get_target_names`, :meth:`get_annotation`, or
        :meth:`get_annotations` for typed views."""
        return self._action.get_dictionary_object(_T)

    def set_target(self, target: COSBase | None) -> None:
        if target is None:
            self._action.remove_item(_T)
            return
        self._action.set_item(_T, target)

    # Back-compat aliases mirroring the historical ``get_t``/``set_t`` surface.
    def get_t(self) -> COSBase | None:
        return self.get_target()

    def set_t(self, target: COSBase | None) -> None:
        self.set_target(target)

    # ---------- /T (typed: field names) ----------

    def get_target_names(self) -> list[str] | None:
        """Return ``/T`` as a list of fully-qualified field-name strings.

        Handles both shapes from Table 200:

        * single ``COSString`` → one-element list;
        * ``COSArray`` of ``COSString`` → string entries collected in
          document order (annotation-dict entries are skipped — use
          :meth:`get_annotations` for those).

        Returns ``None`` when ``/T`` is absent. Returns an empty list when
        ``/T`` is present but contains no string entries (e.g. an array of
        annotation dicts only)."""
        entry = self._action.get_dictionary_object(_T)
        if entry is None:
            return None
        if isinstance(entry, COSString):
            return [entry.get_string()]
        if isinstance(entry, COSArray):
            names: list[str] = []
            for i in range(entry.size()):
                item = entry.get_object(i)
                if isinstance(item, COSString):
                    names.append(item.get_string())
            return names
        return []

    def set_target_names(self, names: list[str] | None) -> None:
        """Replace ``/T`` with a list of fully-qualified field-name strings.

        When ``names`` is ``None`` the entry is removed. A single-element
        list is stored as a bare ``COSString`` (the simple-form upstream
        readers expect when only one annotation is targeted); two or more
        names are stored as a ``COSArray`` of ``COSString``."""
        if names is None:
            self._action.remove_item(_T)
            return
        if len(names) == 1:
            self._action.set_string(_T, names[0])
            return
        array = COSArray()
        for name in names:
            array.add(COSString(name))
        self._action.set_item(_T, array)

    # ---------- /T (typed: annotation) ----------

    def get_annotation(self) -> PDAnnotation | None:
        """Return ``/T`` as a typed :class:`PDAnnotation` subclass when the
        entry is a single annotation dictionary. Returns ``None`` when
        ``/T`` is absent, a string, or an array form (use
        :meth:`get_annotations` for the array case)."""
        entry = self._action.get_dictionary_object(_T)
        if isinstance(entry, COSDictionary):
            return PDAnnotation.create(entry)
        return None

    def set_annotation(
        self, annotation: PDAnnotation | COSDictionary | None
    ) -> None:
        """Replace ``/T`` with a single annotation. Accepts ``None``
        (removes the entry), a :class:`PDAnnotation` (stores its
        underlying ``COSDictionary``), or a raw ``COSDictionary``."""
        if annotation is None:
            self._action.remove_item(_T)
            return
        if isinstance(annotation, PDAnnotation):
            self._action.set_item(_T, annotation.get_cos_object())
            return
        self._action.set_item(_T, annotation)

    # ---------- /T (typed: annotations array) ----------

    def get_annotations(self) -> list[PDAnnotation] | None:
        """Return ``/T`` as a list of typed :class:`PDAnnotation` wrappers
        for the array form (PDF 32000-1 Table 200 — array entries can be
        annotation dictionaries).

        Returns ``None`` when ``/T`` is absent. When ``/T`` is a single
        annotation dictionary the result is a one-element list (matches
        the spec's "annotation or array of annotations" symmetry).
        Field-name strings are skipped — use :meth:`get_target_names`
        for those. An array of strings only therefore returns ``[]``."""
        entry = self._action.get_dictionary_object(_T)
        if entry is None:
            return None
        if isinstance(entry, COSDictionary):
            return [PDAnnotation.create(entry)]
        if isinstance(entry, COSArray):
            annotations: list[PDAnnotation] = []
            for i in range(entry.size()):
                item = entry.get_object(i)
                if isinstance(item, COSDictionary):
                    annotations.append(PDAnnotation.create(item))
            return annotations
        return []

    def set_annotations(
        self, annotations: list[PDAnnotation | COSDictionary] | None
    ) -> None:
        """Replace ``/T`` with a list of annotations. ``None`` removes the
        entry; a single-element list collapses to a bare annotation
        dictionary (matches the simple form upstream emits when only one
        annotation is targeted); two or more entries become a
        ``COSArray`` of annotation dictionaries."""
        if annotations is None:
            self._action.remove_item(_T)
            return
        if len(annotations) == 1:
            entry = annotations[0]
            if isinstance(entry, PDAnnotation):
                self._action.set_item(_T, entry.get_cos_object())
            else:
                self._action.set_item(_T, entry)
            return
        array = COSArray()
        for entry in annotations:
            if isinstance(entry, PDAnnotation):
                array.add(entry.get_cos_object())
            else:
                array.add(entry)
        self._action.set_item(_T, array)

    # ---------- /H ----------

    def get_h(self) -> bool:
        """Return ``/H`` (default ``True`` per PDF 32000-1 Table 200)."""
        return self._action.get_boolean(_H, True)

    def set_h(self, hide: bool) -> None:
        self._action.set_boolean(_H, hide)

    # Predicate aliases — ``is_hide`` matches pypdfbox's ``is_*`` boolean
    # convention; ``should_hide`` reads naturally at call sites that act
    # on the flag (parallel to upstream's ``shouldOpenInNewWindow`` style
    # on PDActionLaunch / PDActionRemoteGoTo).
    def is_hide(self) -> bool:
        """Return ``/H`` (default ``True``). Predicate alias of
        :meth:`get_h`."""
        return self.get_h()

    def should_hide(self) -> bool:
        """Return ``/H`` (default ``True``). Predicate alias of
        :meth:`get_h` matching upstream PDFBox's ``shouldXxx`` naming
        convention used on other action wrappers."""
        return self.get_h()

    def set_hide(self, hide: bool) -> None:
        """Set ``/H``. Alias of :meth:`set_h` for symmetry with
        :meth:`is_hide` / :meth:`should_hide`."""
        self.set_h(hide)

    # ---------- predicates / clear / validation ----------

    def has_target(self) -> bool:
        """``True`` when ``/T`` is present on the underlying dictionary,
        regardless of whether it is a string, an annotation dictionary, or
        an array of either. Lets callers branch on target presence without
        paying the cost of dispatching through :meth:`get_target_names` /
        :meth:`get_annotation` / :meth:`get_annotations`."""
        return self._action.get_dictionary_object(_T) is not None

    def has_hide_flag(self) -> bool:
        """``True`` when ``/H`` is explicitly present on the dictionary
        (independent of its boolean value). Distinct from :meth:`is_hide`
        which always returns the effective value (defaulting to ``True``
        when absent) — useful for round-tripping callers that want to
        preserve the upstream "no /H written" shape vs. "/H true written"
        shape."""
        return self._action.get_dictionary_object(_H) is not None

    def clear_target(self) -> None:
        """Remove the ``/T`` entry. Equivalent to ``set_target(None)``;
        provided as a verb-named convenience that mirrors the ``clear_*``
        helpers on other action wrappers."""
        self._action.remove_item(_T)

    def clear_hide_flag(self) -> None:
        """Remove the ``/H`` entry so :meth:`is_hide` falls back to its
        Table 200 default of ``True``. Equivalent to ``set_hide(True)``
        in effective-value terms but distinct on the wire — leaves the
        dictionary in the canonical "default omitted" shape that upstream
        readers/writers prefer for new actions."""
        self._action.remove_item(_H)

    def is_empty(self) -> bool:
        """``True`` when neither ``/T`` nor ``/H`` is present. A freshly
        constructed :class:`PDActionHide` is "empty" in this sense — it
        carries only the ``/Type /Action`` and ``/S /Hide`` boilerplate
        and has no payload yet. Useful for callers building actions
        incrementally and validating before serialisation."""
        return not self.has_target() and not self.has_hide_flag()

    def is_valid(self) -> bool:
        """``True`` when ``/S`` equals :attr:`SUB_TYPE` (``"Hide"``).
        Sanity check after round-tripping through :meth:`PDAction.create`
        or when wrapping a hand-built :class:`COSDictionary`. Mirrors the
        ``is_valid`` predicate exposed on other action wrappers (e.g.
        :class:`PDActionEmbeddedGoTo`)."""
        return self.get_sub_type() == self.SUB_TYPE


__all__ = ["PDActionHide"]
