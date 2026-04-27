from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_button import PDButton

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_OFF: COSName = COSName.get_pdf_name("Off")


class PDCheckBox(PDButton):
    """``/FT /Btn`` with neither ``FLAG_PUSHBUTTON`` nor ``FLAG_RADIO`` set.
    Mirrors PDFBox ``PDCheckBox``.

    ``get_on_value`` walks the widget normal appearance dictionary and returns
    the first non-Off entry; if none, returns the empty string.
    """

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        new_field = field is None
        if new_field:
            field = COSDictionary()
            field.set_name(_FT_KEY, self.FT)
        super().__init__(form, field, parent)
        # Constructor leaves push/radio bits cleared by default; nothing to do
        # for fresh fields. Explicit clear in case a caller wired flags first.
        if new_field:
            self.set_field_flags(0)

    # ---------- on/off helpers ----------

    def _widget_appearance_dict(self) -> COSDictionary | None:
        # Prefer first widget kid; fall back to the field dict (merged widget).
        kids = self._field.get_dictionary_object(_KIDS)
        candidate: COSDictionary | None = None
        if isinstance(kids, COSArray) and kids.size() > 0:
            entry = kids.get_object(0)
            if isinstance(entry, COSDictionary):
                candidate = entry
        if candidate is None:
            candidate = self._field
        ap = candidate.get_dictionary_object(_AP)
        if not isinstance(ap, COSDictionary):
            return None
        n = ap.get_dictionary_object(_N)
        if isinstance(n, COSDictionary):
            return n
        return None

    def get_on_value(self) -> str:
        n_dict = self._widget_appearance_dict()
        if n_dict is None:
            return ""
        for key in n_dict.key_set():
            if key != _OFF:
                return key.name
        return ""

    def _on_value_for_set(self) -> str:
        """Like ``get_on_value`` but falls back to ``"Yes"`` when no widget
        appearance dictionary is present — used by :meth:`check` so a freshly
        constructed (no-AP) checkbox still toggles a sensible /V.
        """
        value = self.get_on_value()
        return value if value else "Yes"

    def is_checked(self) -> bool:
        on_value = self.get_on_value()
        current = self.get_value()
        if on_value:
            return current == on_value
        # No appearance dictionary: treat anything other than empty / "Off" as
        # checked (matches the spirit of upstream's value comparison while
        # remaining usable in scaffold tests without widget appearances).
        return bool(current) and current != "Off"

    def check(self) -> None:
        self.set_value(self._on_value_for_set())

    def un_check(self) -> None:
        self.set_value("Off")

    # ---------- /V + appearance ----------

    def set_value(
        self, value: str | None, regenerate_appearance: bool = False
    ) -> None:
        """Set the field's ``/V`` value.

        When ``regenerate_appearance=True``, also rebuilds each widget's
        ``/AP /N`` two-state on/off appearance subdictionary via
        :class:`PDAppearanceGenerator` and syncs ``/AS`` to either the
        on-state name or ``/Off``. The default (``False``) preserves the
        historical lite-port behaviour of writing the value alone.
        """
        super().set_value(value)
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)


__all__ = ["PDCheckBox"]
