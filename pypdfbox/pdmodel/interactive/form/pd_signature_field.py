from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from ..digitalsignature import PDSeedValue, PDSignature, PDSignatureLock
from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_SV: COSName = COSName.get_pdf_name("SV")
_LOCK: COSName = COSName.get_pdf_name("Lock")


class PDSignatureField(PDTerminalField):
    """``/FT /Sig`` signature field. Mirrors PDFBox ``PDSignatureField`` lite
    surface.

    Deferred upstream behavior: none on the core field dictionary surface;
    actual signing remains in the digital-signature module.
    """

    FT = "Sig"

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        new_field = field is None
        if field is None:
            field = COSDictionary()
            field.set_name(_FT_KEY, self.FT)
        super().__init__(form, field, parent)
        if new_field:
            self.set_partial_name(self._generate_partial_name())
            widget = self.get_widgets()[0]
            widget.set_printed(True)
            widget.set_locked(True)

    def _generate_partial_name(self) -> str:
        field_name = "Signature"
        sig_names = {
            field.get_partial_name()
            for field in self.get_acro_form().get_field_tree()
            if isinstance(field, PDSignatureField)
        }
        index = 1
        while f"{field_name}{index}" in sig_names:
            index += 1
        return f"{field_name}{index}"

    # ---------- /V ----------

    def get_signature(self) -> PDSignature | None:
        item = self._field.get_dictionary_object(_V)
        if isinstance(item, COSDictionary):
            return PDSignature(item)
        return None

    def get_value(self) -> PDSignature | None:
        return self.get_signature()

    def set_value(
        self,
        value: PDSignature | COSDictionary | str | None,
        regenerate_appearance: bool = False,
    ) -> None:
        """Set the field's ``/V`` value.

        Mirrors upstream's overloads:
        - ``setValue(PDSignature)`` — typed signature dictionary.
        - ``setValue(String)`` — explicitly unsupported upstream
          (``UnsupportedOperationException``); we raise ``NotImplementedError``
          to preserve the upstream contract.

        ``None`` removes ``/V`` (extension over upstream — symmetric with the
        rest of the form-field API in this port).
        """
        if isinstance(value, str):
            raise NotImplementedError(
                "Signature fields cannot be set with a string value — "
                "use a PDSignature instance"
            )
        if value is None:
            self._field.remove_item(_V)
        else:
            self._field.set_item(
                _V,
                value.get_cos_object() if hasattr(value, "get_cos_object") else value,
            )
        # Mirror upstream PDSignatureField.setValue(PDSignature): notify the
        # field tree that the value changed so any visibility-driven cache
        # (appearance regeneration etc.) gets a chance to react.
        self.apply_change()
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)

    # ---------- /DV ----------

    def get_default_value(self) -> PDSignature | None:
        item = self._field.get_dictionary_object(_DV)
        if isinstance(item, COSDictionary):
            return PDSignature(item)
        return None

    def set_default_value(
        self, value: PDSignature | COSDictionary | None
    ) -> None:
        """Mirrors upstream ``PDSignatureField.setDefaultValue(PDSignature)``."""
        if value is None:
            self._field.remove_item(_DV)
        else:
            self._field.set_item(
                _DV,
                value.get_cos_object() if hasattr(value, "get_cos_object") else value,
            )

    # ---------- appearance regeneration ----------

    def regenerate_appearance(self) -> None:
        """Rebuild each widget's ``/AP /N`` from the field's signature
        ``/V``. Convenience wrapper around the appearance generator —
        callers that mutate the underlying ``PDSignature`` after
        :meth:`set_value` can invoke this to refresh the widget visual
        without rewriting ``/V``.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)

    def construct_appearances(self) -> None:
        """No-op for visible signature appearance generation.

        Mirrors upstream ``PDSignatureField.constructAppearances``: PDFBox
        intentionally does not synthesize visible signature appearances here
        (PDFBOX-3524); callers must provide/update those manually.
        """
        return None

    def get_value_as_string(self) -> str:
        """Return ``str(self.get_signature())`` when ``/V`` is present, else ``""``.

        Mirrors upstream ``PDSignatureField.getValueAsString()`` which returns
        ``signature.toString()`` when a signature is present, otherwise the
        empty string. The ``__str__`` form on :class:`PDSignature` is a compact
        summary of the populated identity fields.
        """
        signature = self.get_signature()
        return str(signature) if signature is not None else ""

    # ---------- /SV ----------

    def get_seed_value(self) -> PDSeedValue | None:
        item = self._field.get_dictionary_object(_SV)
        if isinstance(item, COSDictionary):
            return PDSeedValue(item)
        return None

    def set_seed_value(self, seed: PDSeedValue | COSDictionary | None) -> None:
        if seed is None:
            self._field.remove_item(_SV)
        else:
            self._field.set_item(
                _SV,
                seed.get_cos_object() if hasattr(seed, "get_cos_object") else seed,
            )

    # ---------- /Lock ----------

    def get_lock(self) -> PDSignatureLock | None:
        item = self._field.get_dictionary_object(_LOCK)
        if isinstance(item, COSDictionary):
            return PDSignatureLock(item)
        return None

    def set_lock(self, lock: PDSignatureLock | COSDictionary | None) -> None:
        if lock is None:
            self._field.remove_item(_LOCK)
        else:
            self._field.set_item(
                _LOCK,
                lock.get_cos_object() if hasattr(lock, "get_cos_object") else lock,
            )


__all__ = ["PDSignatureField"]
