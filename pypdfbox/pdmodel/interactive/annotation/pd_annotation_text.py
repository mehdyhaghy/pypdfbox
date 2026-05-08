from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_OPEN: COSName = COSName.get_pdf_name("Open")
_NAME: COSName = COSName.get_pdf_name("Name")
_STATE: COSName = COSName.get_pdf_name("State")
_STATE_MODEL: COSName = COSName.get_pdf_name("StateModel")


class PDAnnotationText(PDAnnotationMarkup):
    """
    Text (sticky note) annotation — ``/Subtype /Text``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText``.

    A text annotation is a "sticky note" attached to a point in the
    document. The icon (``/Name``) and open state (``/Open``) drive the
    viewer's rendering; ``/State`` and ``/StateModel`` form a per-reviewer
    workflow (PDF 32000-1:2008 §12.5.6.4 + Table 171).

    Extends :class:`PDAnnotationMarkup` so review-workflow fields
    (``/CreationDate``, ``/Subj``, ``/IRT``, ``/IT``, ``/CA``, ``/RT``)
    come for free — matching upstream's class hierarchy.
    """

    SUB_TYPE: str = "Text"

    # Icon name constants (PDF 32000-1:2008 §12.5.6.4 Table 171 + adobe addenda).
    NAME_COMMENT: str = "Comment"
    NAME_KEY: str = "Key"
    NAME_NOTE: str = "Note"  # spec default
    NAME_HELP: str = "Help"
    NAME_NEW_PARAGRAPH: str = "NewParagraph"
    NAME_PARAGRAPH: str = "Paragraph"
    NAME_INSERT: str = "Insert"
    NAME_CIRCLE: str = "Circle"
    NAME_CROSS: str = "Cross"
    NAME_STAR: str = "Star"
    NAME_CHECK: str = "Check"
    NAME_RIGHT_ARROW: str = "RightArrow"
    NAME_RIGHT_POINTER: str = "RightPointer"
    NAME_UP_ARROW: str = "UpArrow"
    NAME_UP_LEFT_ARROW: str = "UpLeftArrow"
    NAME_CROSS_HAIRS: str = "CrossHairs"

    # State-model values (PDF 32000-1:2008 §12.5.6.3 Table 172).
    STATE_MODEL_MARKED: str = "Marked"
    STATE_MODEL_REVIEW: str = "Review"

    # State values for the ``Marked`` model.
    STATE_MARKED: str = "Marked"
    STATE_UNMARKED: str = "Unmarked"

    # State values for the ``Review`` model.
    STATE_ACCEPTED: str = "Accepted"
    STATE_REJECTED: str = "Rejected"
    STATE_CANCELLED: str = "Cancelled"
    STATE_COMPLETED: str = "Completed"
    STATE_NONE: str = "None"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /Open ----------

    def get_open(self) -> bool:
        """Default is ``False`` per spec ("default closed")."""
        return self._dict.get_boolean(_OPEN, False)

    def is_open(self) -> bool:
        """Predicate alias for :meth:`get_open`."""
        return self.get_open()

    def set_open(self, value: bool) -> None:
        self._dict.set_item(_OPEN, COSBoolean.get(value))

    def getOpen(self) -> bool:  # noqa: N802 - upstream Java name
        return self.get_open()

    def setOpen(self, value: bool) -> None:  # noqa: N802 - upstream Java name
        self.set_open(value)

    # ---------- /Name (icon) ----------

    def get_name(self) -> str:
        """Default per spec is ``Note``."""
        value = self._dict.get_name(_NAME)
        return value if value is not None else self.NAME_NOTE

    def set_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)

    def getName(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_name()

    def setName(self, name: str | None) -> None:  # noqa: N802 - upstream Java name
        self.set_name(name)

    # ---------- icon predicates ----------

    def is_note(self) -> bool:
        """Predicate matching the spec default icon (``Note``)."""
        return self.get_name() == self.NAME_NOTE

    def is_comment(self) -> bool:
        return self.get_name() == self.NAME_COMMENT

    # ---------- /State ----------

    def get_state(self) -> str | None:
        return self._dict.get_string(_STATE)

    def set_state(self, state: str | None) -> None:
        self._dict.set_string(_STATE, state)

    def getState(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_state()

    def setState(self, state: str | None) -> None:  # noqa: N802 - upstream Java name
        self.set_state(state)

    # ---------- /StateModel ----------

    def get_state_model(self) -> str | None:
        return self._dict.get_string(_STATE_MODEL)

    def set_state_model(self, model: str | None) -> None:
        self._dict.set_string(_STATE_MODEL, model)

    def getStateModel(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_state_model()

    def setStateModel(self, model: str | None) -> None:  # noqa: N802 - upstream Java name
        self.set_state_model(model)


__all__ = ["PDAnnotationText"]
