from __future__ import annotations

from dataclasses import dataclass

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

from .pd_action import PDAction
from .pd_target_directory import PDTargetDirectory


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

    def is_new_window(self) -> bool:
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_new_window(self, new_window: bool) -> None:
        self._action.set_boolean(_NEW_WINDOW, new_window)

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

    def walk_to_target(self) -> list[TargetStep]:
        """Walk the ``/T`` → ``/T`` → ... chain and return each hop as a
        :class:`TargetStep`.

        Returns the chain as a list (root first). Returns an empty list
        when ``/T`` is absent on this action.

        Note: this walker does not detect cycles in malformed chains (a
        target that ``/T``s back to an ancestor will loop forever). Cycle
        detection and document-tree resolution are deferred."""
        steps: list[TargetStep] = []
        current = self.get_target()
        while current is not None:
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


__all__ = ["PDActionEmbeddedGoTo", "TargetStep"]
