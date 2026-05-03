from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition

from .pd_action import PDAction

_TRANS: COSName = COSName.get_pdf_name("Trans")


class PDActionTransition(PDAction):
    """Transition action. Mirrors PDFBox ``PDActionTransition`` lite surface.

    PDF 32000-1 §12.6.4.16 Table 213: ``/Trans`` references the transition
    dictionary controlling how the page transitions when this action is
    triggered.
    """

    SUB_TYPE = "Trans"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_trans(self) -> PDTransition | None:
        """Return ``/Trans`` as a typed :class:`PDTransition`, or ``None``
        when the entry is absent or not a dictionary."""
        value = self._action.get_dictionary_object(_TRANS)
        if isinstance(value, COSDictionary):
            return PDTransition(value)
        return None

    def set_trans(self, trans: PDTransition | COSDictionary | None) -> None:
        """Set ``/Trans``. Accepts ``None`` (removes the entry), a
        :class:`PDTransition`, or a raw :class:`COSDictionary`."""
        if trans is None:
            self._action.remove_item(_TRANS)
            return
        if isinstance(trans, PDTransition):
            self._action.set_item(_TRANS, trans.get_cos_object())
            return
        self._action.set_item(_TRANS, trans)

    # ---------- predicates / clear / is_empty ----------

    def has_trans(self) -> bool:
        """``True`` when ``/Trans`` is present on the underlying
        dictionary. Lets callers branch on transition-presence without
        paying the cost of constructing a :class:`PDTransition` wrapper.
        Parallels :class:`PDActionEmbeddedGoTo.has_target` /
        :class:`PDActionRemoteGoTo.has_file`."""
        return isinstance(self._action.get_dictionary_object(_TRANS), COSDictionary)

    def clear_trans(self) -> None:
        """Remove ``/Trans`` from the action dictionary."""
        self._action.remove_item(_TRANS)

    def is_empty(self) -> bool:
        """``True`` when ``/Trans`` is absent — i.e. the action carries no
        transition state. Parallels :class:`PDActionURI.is_empty` /
        :class:`PDActionResetForm.is_empty`."""
        return not self.has_trans()

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"Trans"``). Useful as a sanity check after
        round-tripping through :meth:`PDAction.create` or when constructing
        the wrapper around a hand-built :class:`COSDictionary`. Parallels
        :class:`PDActionEmbeddedGoTo.is_valid`."""
        return self.get_sub_type() == self.SUB_TYPE


__all__ = ["PDActionTransition"]
