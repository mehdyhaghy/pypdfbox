from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_field import PDField


class PDFieldTree(Sequence["PDField"]):
    """Iterable view over an AcroForm's field tree.

    Mirrors PDFBox ``PDFieldTree`` as a read-side wrapper: iteration walks
    root fields first, then each non-terminal field's descendants in ``/Kids``
    order. ``Sequence`` methods are provided for Python callers that used the
    previous list-returning ``PDAcroForm.get_field_tree`` surface.
    """

    def __init__(self, acro_form: PDAcroForm) -> None:
        self._acro_form = acro_form

    def __iter__(self) -> Iterator[PDField]:
        for field in self._acro_form.get_fields():
            yield from self._walk(field)

    def __len__(self) -> int:
        return len(self._as_list())

    def __getitem__(self, index: int | slice) -> PDField | list[PDField]:
        return self._as_list()[index]

    def _as_list(self) -> list[PDField]:
        return list(iter(self))

    def _walk(self, field: PDField) -> Iterator[PDField]:
        yield field
        if field.is_terminal():
            return

        from .pd_non_terminal_field import PDNonTerminalField

        if not isinstance(field, PDNonTerminalField):
            return
        for child in field.get_children():
            yield from self._walk(child)


__all__ = ["PDFieldTree"]
