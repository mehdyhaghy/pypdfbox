from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_field_tree import _FieldIterator

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_field import PDField


class FieldIterator(_FieldIterator):
    """Breadth-first iterator over an AcroForm's field tree. Mirrors
    the upstream package-private
    ``org.apache.pdfbox.pdmodel.interactive.form.PDFieldTree.FieldIterator``
    (upstream Java inner class; pypdfbox already implements it as
    ``_FieldIterator`` inside :mod:`pd_field_tree` to satisfy the
    public iterator protocol).

    This subclass-of-alias makes the upstream identifier available at
    its expected location
    (``pypdfbox.pdmodel.interactive.form.FieldIterator``) so code
    ported from PDFBox can keep its original imports without forcing
    a rename of the existing implementation.
    """

    def __init__(self, form: PDAcroForm) -> None:
        super().__init__(form)

    def enqueue_kids(self, node: PDField) -> None:
        """Push ``node`` plus any non-cyclic descendants onto the
        iteration queue. Mirrors upstream's package-private
        ``PDFieldTree.FieldIterator.enqueueKids`` (Java line 108).

        Public alias of the underlying ``_enqueue_kids`` worker so the
        upstream method name is reachable from ported call sites.
        """
        self._enqueue_kids(node)


__all__ = ["FieldIterator"]
