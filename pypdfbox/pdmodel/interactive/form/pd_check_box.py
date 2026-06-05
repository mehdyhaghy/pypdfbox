from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_button import PDButton

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
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
        widgets = self.get_widgets()
        candidate = widgets[0].get_cos_object() if widgets else self._field
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

    def is_checked(self) -> bool:
        """Whether the box is in its On state.

        Mirrors upstream ``PDCheckBox.isChecked``:
        ``getValue().compareTo(getOnValue()) == 0``. For an AP-less box both
        :meth:`get_value` (``"Off"``) and :meth:`get_on_value` (``""``) differ,
        so it reports unchecked until :meth:`check` sets the value.
        """
        return self.get_value() == self.get_on_value()

    def check(self) -> None:
        # Upstream PDCheckBox.check calls setValue(getOnValue()). For a fresh
        # AP-less box getOnValue() is "" — which getOnValues() now reports as a
        # valid on-state, so the strict check_value accepts it (no "Yes"
        # fallback, which would now raise).
        self.set_value(self.get_on_value())

    def un_check(self) -> None:
        self.set_value("Off")

    # ---------- /V + appearance ----------

    def set_value(
        self, value: str | None, regenerate_appearance: bool = False
    ) -> None:
        """Set the field's ``/V`` value.

        The base :meth:`PDButton.set_value` already performs the
        value-visible appearance step for buttons — it syncs each widget's
        ``/AS`` to the matching existing ``/AP /N`` on-state (or ``/Off``),
        which is exactly what upstream ``PDCheckBox.setValue`` does (real
        check-box widgets ship their on/off appearance streams; setting the
        value only flips ``/AS``). ``regenerate_appearance`` therefore
        defaults to ``False``: pass ``True`` only to additionally *redraw*
        the on/off appearance streams (ZapfDingbats glyph / empty) via
        :class:`PDAppearanceGenerator`. Redrawing is opt-in because it
        rebuilds the ``/AP /N`` subdictionary from scratch and would discard
        producer-chosen state keys (e.g. the numeric ``/Opt``-indexed keys
        in PDFBOX-3656).

        Ordering note (wave 1487): when ``regenerate_appearance`` is set, the
        on/off appearance streams are rebuilt *before* the base
        :meth:`PDButton.set_value` runs its strict :meth:`PDButton.check_value`.
        A freshly built box has no ``/AP``, so its on-values would be ``{""}``
        and a non-empty ``value`` would fail the strict check; generating the
        ``/AP /N`` on-state first (default state name ``"Yes"``, or the
        producer-chosen name preserved from an existing ``/AP``) makes that
        name a recognised on-value. This is the explicit purpose of the
        pypdfbox-only ``regenerate_appearance`` extension, which upstream
        lacks; with it unset, ``set_value`` matches upstream exactly and
        raises for an unknown name on an AP-less box.
        """
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)
        super().set_value(value)

    def construct_appearances(self) -> None:
        """Rebuild widget appearances for this check box.

        Wave 1305 extends the lite-port behaviour beyond upstream's
        ``PDCheckBox.constructAppearances`` (which only syncs ``/AS``):
        the appearance generator is invoked first so every widget gets a
        fresh on/off ``/AP /N`` subdictionary drawn from the field's
        current value, then the super call syncs ``/AS`` against the
        rebuilt appearance dictionary. This mirrors the user-visible
        contract of upstream's ``AppearanceGeneratorHelper`` flow while
        keeping ``PDButton.constructAppearances``'s state-sync semantics
        intact.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)
        super().construct_appearances()


__all__ = ["PDCheckBox"]
