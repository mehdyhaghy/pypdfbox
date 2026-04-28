from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pypdfbox.cos import COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

from .open_mode import OpenMode
from .pd_action import PDAction
from .pd_target_directory import PDTargetDirectory

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
        PDPageDestination,
    )

_LOG = logging.getLogger(__name__)


@dataclass
class TargetStep:
    """A single hop in the chained ``/T`` walk for an embedded GoTo action.

    Mirrors the entries of ``PDTargetDirectory`` (PDF 32000-1 Table 202)
    flattened into a snapshot for one level of the chain."""

    relationship: str  # 'P' (parent) or 'C' (child)
    target_filename: str | None  # /N — embedded file name
    page_number: int | None  # /P int form
    named_destination: str | None  # /P string form
    annotation_number: int | None  # /A index

_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_NEW_WINDOW: COSName = COSName.get_pdf_name("NewWindow")
_T: COSName = COSName.get_pdf_name("T")


class PDActionEmbeddedGoTo(PDAction):
    """Embedded GoTo action. Mirrors PDFBox ``PDActionEmbeddedGoTo`` lite
    surface."""

    SUB_TYPE = "GoToE"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_file(self) -> PDFileSpecification | None:
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(self, fs: PDFileSpecification | None) -> None:
        if fs is None:
            self._action.remove_item(_F)
            return
        self._action.set_item(_F, fs.get_cos_object())

    def get_d(self) -> PDDestination | None:
        return PDDestination.create(self._action.get_dictionary_object(_D))

    def set_d(self, destination: PDDestination | None) -> None:
        if destination is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, destination.get_cos_object())

    # PDFBox spec-named accessors for /D — alias of get_d / set_d.
    def get_destination(self) -> PDDestination | None:
        """Spec-named accessor for the ``/D`` destination entry. Mirrors
        upstream PDFBox ``getDestination()``."""
        return self.get_d()

    def set_destination(self, destination: PDDestination | None) -> None:
        """Spec-named setter for the ``/D`` destination entry. Mirrors
        upstream PDFBox ``setDestination(PDDestination)``."""
        self.set_d(destination)

    def is_new_window(self) -> bool:
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_new_window(self, new_window: bool) -> None:
        self._action.set_boolean(_NEW_WINDOW, new_window)

    # PDFBox spec-named accessors for /NewWindow — alias of is_new_window /
    # set_new_window. Default per PDF 32000-1 §12.6.4.4 is ``False``.
    def get_open_in_new_window(self) -> bool:
        """Spec-named accessor for the ``/NewWindow`` boolean. Defaults to
        ``False`` when the entry is absent. For the upstream tri-state
        :class:`OpenMode` surface use :meth:`get_open_in_new_window_mode`."""
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_open_in_new_window(self, value: bool | OpenMode) -> None:
        """Spec-named setter for ``/NewWindow``. Accepts a plain ``bool``
        or an :class:`OpenMode`. :attr:`OpenMode.USER_PREFERENCE` removes
        the entry."""
        if isinstance(value, OpenMode):
            if value is OpenMode.USER_PREFERENCE:
                self._action.remove_item(_NEW_WINDOW)
                return
            self._action.set_boolean(_NEW_WINDOW, value is OpenMode.NEW_WINDOW)
            return
        self._action.set_boolean(_NEW_WINDOW, bool(value))

    def get_open_in_new_window_mode(self) -> OpenMode:
        """Return ``/NewWindow`` as an :class:`OpenMode` tri-state. Mirrors
        upstream ``PDActionEmbeddedGoTo.getOpenInNewWindow()`` which
        returns ``OpenMode`` rather than a plain boolean."""
        entry = self._action.get_dictionary_object(_NEW_WINDOW)
        if isinstance(entry, COSBoolean):
            return OpenMode.NEW_WINDOW if entry.get_value() else OpenMode.SAME_WINDOW
        return OpenMode.USER_PREFERENCE

    def get_target(self) -> PDTargetDirectory | None:
        d = self._action.get_dictionary_object(_T)
        if isinstance(d, COSDictionary):
            return PDTargetDirectory(d)
        return None

    def set_target(
        self, target: PDTargetDirectory | COSDictionary | None
    ) -> None:
        if target is None:
            self._action.remove_item(_T)
            return
        self._action.set_item(
            _T,
            target.get_cos_object() if hasattr(target, "get_cos_object") else target,
        )

    # PDFBox spec-named accessors for /T — alias of get_target / set_target.
    def get_target_directory(self) -> PDTargetDirectory | None:
        """Spec-named accessor for the ``/T`` target directory. Mirrors
        upstream PDFBox ``getTargetDirectory()``."""
        return self.get_target()

    def set_target_directory(
        self, value: PDTargetDirectory | COSDictionary | None
    ) -> None:
        """Spec-named setter for the ``/T`` target directory. Mirrors
        upstream PDFBox ``setTargetDirectory(PDTargetDirectory)``."""
        self.set_target(value)

    def resolve_target(
        self,
        source_document: PDDocument,
        target_document: PDDocument | None = None,
    ) -> tuple[PDDocument, PDPageDestination | PDPage] | None:
        """Walk the ``/T`` chain to the embedded file the action targets and
        resolve the final destination inside it.

        Per PDF 32000-1 §12.6.4.4 / Table 202, ``/T`` is a chain of
        ``PDTargetDirectory`` dictionaries. For each step:

        * ``/R = "C"`` (child) — the new scope is the document obtained by
          loading the embedded file named in ``/N`` from the current
          scope's ``/Names /EmbeddedFiles`` name tree.
        * ``/R = "P"`` (parent) — the new scope pops back to
          ``target_document`` (the document containing this action's
          owning attachment, supplied by the caller). When
          ``target_document`` is ``None`` the walk gracefully returns
          ``None``.

        After the last hop (no nested ``/T``), the action's ``/D`` entry is
        resolved against the final scope's catalog (``/Dests`` name tree
        for named destinations) and returned.

        Returns ``(final_document, destination_or_page)`` on success, or
        ``None`` when any step fails to resolve (missing ``/N``, missing
        embedded file bytes, unreadable embedded PDF, missing destination)."""
        from pypdfbox.pdmodel.pd_document import PDDocument as _PDDocument

        current_scope: PDDocument = source_document
        current_target = self.get_target()

        # Track docs we opened so we don't leak them on a graceful failure.
        opened_docs: list[PDDocument] = []

        try:
            while current_target is not None:
                relationship = current_target.get_relationship() or "C"
                next_filename = current_target.get_target_filename()
                if next_filename is None:
                    # /N missing — chain broken.
                    return None

                if relationship == "P":
                    # Pop to the supplied parent scope.
                    if target_document is None:
                        return None
                    next_scope: PDDocument | None = target_document
                else:
                    # Descend into the embedded file referenced by /N inside
                    # the current scope's /Names /EmbeddedFiles tree.
                    next_scope = _open_embedded_pdf(
                        current_scope, next_filename, _PDDocument
                    )
                    if next_scope is None:
                        return None
                    if next_scope is not source_document and next_scope is not target_document:
                        opened_docs.append(next_scope)

                current_scope = next_scope
                nested = current_target.get_target()
                if nested is None:
                    break
                current_target = nested

            # Resolve the action's /D against the final scope.
            final = self._resolve_final_destination(current_scope)
            if final is None:
                return None
            # Hand ownership of opened docs back so caller closes the chain
            # by closing the final doc only — we drop our list once the
            # walk succeeds (caller may close them via documents we return).
            opened_docs.clear()
            return current_scope, final
        finally:
            # Close any docs we opened that we won't return to the caller.
            for d in opened_docs:
                try:
                    d.close()
                except Exception:  # noqa: BLE001 — best-effort cleanup
                    _LOG.debug("Failed to close embedded PDDocument", exc_info=True)

    def _resolve_final_destination(
        self, scope: PDDocument
    ) -> PDPageDestination | PDPage | None:
        """Resolve this action's ``/D`` against ``scope``'s name dictionaries.

        ``/D`` can be:
        * an explicit page destination array → :class:`PDPageDestination`
          (returned as-is — the page reference inside is opaque to us
          unless it's a numeric index, which the caller can resolve).
        * a name / byte string → looked up in ``scope``'s
          ``/Names /Dests`` name tree.
        """
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
            PDNamedDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
            PDPageDestination,
        )

        dest = self.get_d()
        if dest is None:
            return None
        if isinstance(dest, PDPageDestination):
            return dest
        if isinstance(dest, PDNamedDestination):
            name = dest.get_named_destination()
            if name is None:
                return None
            resolved = _resolve_named_destination(scope, name)
            if isinstance(resolved, PDPageDestination):
                return resolved
            return None
        return None

    def walk_to_target(self) -> list[TargetStep]:
        """Walk the ``/T`` → ``/T`` → ... chain and return each hop as a
        :class:`TargetStep`.

        Returns the chain as a list (root first). Returns an empty list
        when ``/T`` is absent on this action.

        Cycle handling (soft-stop): a malformed ``/T`` chain that loops
        back to an already-visited ``COSDictionary`` (compared by Python
        object identity) terminates the walk after recording the current
        step. The partial chain accumulated up to that point is returned
        rather than raising — callers receive what we have so far instead
        of an exception or an infinite loop."""
        steps: list[TargetStep] = []
        visited: set[int] = set()
        current = self.get_target()
        while current is not None:
            target_dict = current.get_cos_object()
            target_id = id(target_dict)
            if target_id in visited:
                break
            visited.add(target_id)
            relationship = current.get_relationship() or "C"
            steps.append(
                TargetStep(
                    relationship=relationship,
                    target_filename=current.get_target_filename(),
                    page_number=current.get_page_number(),
                    named_destination=current.get_named_destination(),
                    annotation_number=current.get_annotation_number(),
                )
            )
            current = current.get_target()
        return steps


def _open_embedded_pdf(
    scope: PDDocument,
    name: str,
    pddocument_cls: type[PDDocument],
) -> PDDocument | None:
    """Look up ``name`` in ``scope``'s ``/Names /EmbeddedFiles`` name tree
    and load the referenced embedded file as a fresh :class:`PDDocument`.

    Returns ``None`` when the name is missing, the file specification has
    no embedded stream, the bytes are empty, or the bytes don't parse as
    a PDF (graceful degradation per spec — callers get a soft ``None``
    rather than an exception, mirroring upstream's tolerant behaviour
    for malformed embedded GoTo targets)."""
    catalog = scope.get_document_catalog()
    names = catalog.get_names()
    if names is None:
        return None
    embedded_files = names.get_embedded_files()
    if embedded_files is None:
        return None
    file_spec = embedded_files.get_value(name)
    if file_spec is None:
        return None
    if not isinstance(file_spec, PDComplexFileSpecification):
        # Lookup may return raw COSDictionary — wrap.
        cos = getattr(file_spec, "get_cos_object", lambda: None)()
        if isinstance(cos, COSDictionary):
            file_spec = PDComplexFileSpecification(cos)
        else:
            return None
    embedded = file_spec.get_embedded_file()
    if embedded is None:
        # Fall back to /UF / /DOS / /Mac / /Unix in that order.
        embedded = (
            file_spec.get_embedded_file_unicode()
            or file_spec.get_embedded_file_dos()
            or file_spec.get_embedded_file_mac()
            or file_spec.get_embedded_file_unix()
        )
        if embedded is None:
            return None
    try:
        data = embedded.to_byte_array()
    except Exception:  # noqa: BLE001 — malformed stream is a soft failure
        _LOG.debug(
            "Embedded file %r — failed to read bytes", name, exc_info=True
        )
        return None
    if not data:
        return None
    try:
        return pddocument_cls.load(data)
    except Exception:  # noqa: BLE001 — non-PDF payload is a soft failure
        _LOG.debug(
            "Embedded file %r — bytes do not parse as a PDF",
            name,
            exc_info=True,
        )
        return None


def _resolve_named_destination(
    scope: PDDocument, name: str
) -> PDDestination | None:
    """Resolve a named destination ``name`` against ``scope``'s
    ``/Names /Dests`` name tree (PDF 1.2+), falling back to the legacy
    catalog ``/Dests`` flat dictionary (PDF 1.1)."""
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination_name_tree_node import (
        PDDestinationNameTreeNode,
    )

    catalog = scope.get_document_catalog()

    # PDF 1.2+ /Names /Dests path (proper name tree).
    names = catalog.get_names()
    if names is not None:
        names_cos = names.get_cos_object()
        dests_dict = names_cos.get_dictionary_object(
            COSName.get_pdf_name("Dests")
        )
        if isinstance(dests_dict, COSDictionary):
            tree = PDDestinationNameTreeNode(dests_dict)
            value = tree.get_value(name)
            if value is not None:
                return value
        flat = names.get_dests()
        if flat is not None:
            value = flat.get_destination(name)
            if value is not None:
                return value

    # Legacy catalog /Dests — wrapped here as PDDestinationNameTreeNode in
    # this codebase (its get_value walks the flat /Names array form).
    legacy = catalog.get_dests()
    if legacy is not None:
        value = legacy.get_value(name)
        if value is not None:
            return value
    return None


__all__ = ["PDActionEmbeddedGoTo", "TargetStep"]
