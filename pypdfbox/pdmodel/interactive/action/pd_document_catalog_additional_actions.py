from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_WC: COSName = COSName.get_pdf_name("WC")
_WS: COSName = COSName.get_pdf_name("WS")
_DS: COSName = COSName.get_pdf_name("DS")
_WP: COSName = COSName.get_pdf_name("WP")
_DP: COSName = COSName.get_pdf_name("DP")


class PDDocumentCatalogAdditionalActions:
    """
    Document-catalog additional-actions dictionary. Mirrors PDFBox
    ``PDDocumentCatalogAdditionalActions`` for the will-close (``/WC``),
    will-save (``/WS``), did-save (``/DS``), will-print (``/WP``) and
    did-print (``/DP``) triggers (PDF 32000-1:2008 §12.6.3, Table 195).
    """

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_wc(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_WC)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_wc(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_WC)
            return
        self._actions.set_item(_WC, action.get_cos_object())

    def get_ws(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_WS)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_ws(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_WS)
            return
        self._actions.set_item(_WS, action.get_cos_object())

    def get_ds(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_DS)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_ds(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_DS)
            return
        self._actions.set_item(_DS, action.get_cos_object())

    def get_wp(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_WP)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_wp(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_WP)
            return
        self._actions.set_item(_WP, action.get_cos_object())

    def get_dp(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_DP)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_dp(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_DP)
            return
        self._actions.set_item(_DP, action.get_cos_object())

    # ------------------------------------------------------------------
    # Upstream-named aliases. PDFBox exposes longer descriptive accessors
    # alongside the two-letter ones; mirror those for source-level
    # familiarity.
    # ------------------------------------------------------------------

    def get_will_close(self) -> PDAction | None:
        return self.get_wc()

    def set_will_close(self, action: PDAction | None) -> None:
        self.set_wc(action)

    def get_will_save(self) -> PDAction | None:
        return self.get_ws()

    def set_will_save(self, action: PDAction | None) -> None:
        self.set_ws(action)

    def get_did_save(self) -> PDAction | None:
        return self.get_ds()

    def set_did_save(self, action: PDAction | None) -> None:
        self.set_ds(action)

    def get_will_print(self) -> PDAction | None:
        return self.get_wp()

    def set_will_print(self, action: PDAction | None) -> None:
        self.set_wp(action)

    def get_did_print(self) -> PDAction | None:
        return self.get_dp()

    def set_did_print(self, action: PDAction | None) -> None:
        self.set_dp(action)


__all__ = ["PDDocumentCatalogAdditionalActions"]
