from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_N: COSName = COSName.get_pdf_name("N")


class PDActionNamed(PDAction):
    """Named action. Mirrors PDFBox ``PDActionNamed``."""

    SUB_TYPE = "Named"

    # Standard named actions (PDF 32000-1 §12.6.4.11). PDF 1.5+ allows
    # extension names beyond these four; callers may pass arbitrary
    # strings to :meth:`set_n`.
    NAMED_ACTION_NEXT_PAGE = "NextPage"
    NAMED_ACTION_PREV_PAGE = "PrevPage"
    NAMED_ACTION_FIRST_PAGE = "FirstPage"
    NAMED_ACTION_LAST_PAGE = "LastPage"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_n(self) -> str | None:
        return self._action.get_name(_N)

    def set_n(self, name: str | None) -> None:
        if name is None:
            self._action.remove_item(_N)
            return
        self._action.set_name(_N, name)


__all__ = ["PDActionNamed"]
