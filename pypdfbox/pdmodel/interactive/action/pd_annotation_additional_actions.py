from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_E: COSName = COSName.get_pdf_name("E")
_X: COSName = COSName.get_pdf_name("X")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_U: COSName = COSName.get_pdf_name("U")
_FO: COSName = COSName.get_pdf_name("Fo")
_BL: COSName = COSName.get_pdf_name("Bl")
_PO: COSName = COSName.get_pdf_name("PO")
_PC: COSName = COSName.get_pdf_name("PC")
_PV: COSName = COSName.get_pdf_name("PV")
_PI: COSName = COSName.get_pdf_name("PI")


class PDAnnotationAdditionalActions:
    """
    Annotation additional-actions dictionary. Mirrors PDFBox
    ``PDAnnotationAdditionalActions`` for the cursor enter (``/E``), exit
    (``/X``), mouse down (``/D``), mouse up (``/U``), focus (``/Fo``), blur
    (``/Bl``), page open (``/PO``), page close (``/PC``), page visible
    (``/PV``) and page invisible (``/PI``) triggers (PDF 32000-1:2008
    §12.6.3, Table 197).
    """

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_e(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_E)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_e(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_E)
            return
        self._actions.set_item(_E, action.get_cos_object())

    def get_x(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_X)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_x(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_X)
            return
        self._actions.set_item(_X, action.get_cos_object())

    def get_d(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_D)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_d(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_D)
            return
        self._actions.set_item(_D, action.get_cos_object())

    def get_u(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_U)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_u(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_U)
            return
        self._actions.set_item(_U, action.get_cos_object())

    def get_fo(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_FO)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_fo(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_FO)
            return
        self._actions.set_item(_FO, action.get_cos_object())

    def get_bl(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_BL)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_bl(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_BL)
            return
        self._actions.set_item(_BL, action.get_cos_object())

    def get_po(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_PO)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_po(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_PO)
            return
        self._actions.set_item(_PO, action.get_cos_object())

    def get_pc(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_PC)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_pc(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_PC)
            return
        self._actions.set_item(_PC, action.get_cos_object())

    def get_pv(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_PV)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_pv(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_PV)
            return
        self._actions.set_item(_PV, action.get_cos_object())

    def get_pi(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_PI)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_pi(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_PI)
            return
        self._actions.set_item(_PI, action.get_cos_object())


__all__ = ["PDAnnotationAdditionalActions"]
