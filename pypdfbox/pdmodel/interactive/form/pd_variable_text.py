from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSNumber, COSStream, COSString

from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_DA: COSName = COSName.get_pdf_name("DA")
_DS: COSName = COSName.get_pdf_name("DS")
_Q: COSName = COSName.get_pdf_name("Q")
_RV: COSName = COSName.get_pdf_name("RV")
_KIDS: COSName = COSName.get_pdf_name("Kids")


class PDVariableText(PDTerminalField):
    """Abstract intermediate for fields with variable text. Mirrors PDFBox
    ``PDVariableText`` lite surface (``/DA``, ``/Q``, ``/DS``, ``/RV``).

    Deferred upstream surface: ``getDefaultAppearanceString`` returns a typed
    ``PDDefaultAppearanceString`` (not yet ported) — ``get_default_appearance``
    returns the raw string instead.
    """

    QUADDING_LEFT = 0
    QUADDING_CENTERED = 1
    QUADDING_RIGHT = 2

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        super().__init__(form, field, parent)

    # ---------- /DA ----------

    def get_default_appearance(self) -> str | None:
        item = self.get_inheritable_attribute(_DA)
        if isinstance(item, COSString):
            return item.get_string()
        return None

    def set_default_appearance(self, da_value: str | None) -> None:
        self._field.set_string(_DA, da_value)
        if self._field.contains_key(_KIDS):
            for widget in self.get_widgets():
                widget_cos = widget.get_cos_object()
                if widget_cos.contains_key(_DA):
                    widget_cos.set_string(_DA, da_value)

    def has_default_appearance(self) -> bool:
        """Predicate — return ``True`` when ``/DA`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: does **not** walk the inheritable chain.
        Use :meth:`get_default_appearance` (which falls back through the
        parent + AcroForm chain) to read the effective value.
        """
        return isinstance(self._field.get_dictionary_object(_DA), COSString)

    def clear_default_appearance(self) -> None:
        """Remove this field's local ``/DA`` entry."""
        self._field.remove_item(_DA)

    # ---------- /DS ----------

    def get_default_style_string(self) -> str | None:
        return self._field.get_string(_DS)

    def set_default_style_string(self, value: str | None) -> None:
        self._field.set_string(_DS, value)

    def has_default_style_string(self) -> bool:
        """Predicate — return ``True`` when ``/DS`` is set on this field's own
        dictionary. ``/DS`` is **not** inheritable per the PDF spec, so this
        is equivalent to "the entry is present".
        """
        return isinstance(self._field.get_dictionary_object(_DS), COSString)

    def clear_default_style_string(self) -> None:
        """Remove this field's local ``/DS`` entry."""
        self._field.remove_item(_DS)

    # ---------- /Q ----------

    def get_q(self) -> int:
        """Return the effective ``/Q`` (text quadding/justification).

        Mirrors upstream ``PDVariableText.getQ`` — ``/Q`` is inheritable per
        the PDF spec, so this walks ``self -> parent -> AcroForm``. Defaults
        to :attr:`QUADDING_LEFT` (0) when no ancestor sets it.
        """
        item = self.get_inheritable_attribute(_Q)
        if isinstance(item, COSNumber):
            return item.int_value()
        return 0

    def set_q(self, q: int) -> None:
        self._field.set_int(_Q, q)

    def has_q(self) -> bool:
        """Predicate — return ``True`` when ``/Q`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: does **not** walk the inheritable chain
        (``/Q`` is inheritable per the PDF spec). Use :meth:`get_q` to read
        the effective value (which falls back to ``QUADDING_LEFT``/``0``).
        Useful for callers that need to distinguish "field has its own /Q"
        from "field inherits /Q (or defaults to left-aligned)".
        """
        return isinstance(self._field.get_dictionary_object(_Q), COSNumber)

    def clear_q(self) -> None:
        """Remove this field's local ``/Q`` entry."""
        self._field.remove_item(_Q)

    # ---------- /RV ----------

    def get_rich_text_value(self) -> str | None:
        return self._get_string_or_stream(self.get_inheritable_attribute(_RV))

    def set_rich_text_value(self, value: str | None) -> None:
        self._field.set_string(_RV, value)

    def has_rich_text_value(self) -> bool:
        """Predicate — return ``True`` when ``/RV`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: does **not** walk the inheritable chain.
        """
        return isinstance(self._field.get_dictionary_object(_RV), (COSString, COSStream))

    def clear_rich_text_value(self) -> None:
        """Remove this field's local ``/RV`` rich-text value."""
        self._field.remove_item(_RV)

    # ---------- /DA + /DS + /RV helper ----------

    def _get_string_or_stream(self, base: COSBase | None) -> str | None:
        """Return a text-or-stream payload as a Python ``str``.

        Mirrors upstream ``PDVariableText.getStringOrStream``: some
        dictionary entries (``/V``, ``/DV``, ``/RV``) admit either a
        ``COSString`` or a ``COSStream`` body. ``COSString`` returns its
        decoded text, ``COSStream`` decodes through ``to_text_string``
        (matching upstream ``COSStream.toTextString``). Returns ``None``
        when the entry is missing or any other COS type — pypdfbox keeps
        the explicit ``None`` for callers that want to distinguish "no
        entry" from "empty payload" (upstream returns ``""`` in both
        cases; see CHANGES.md).
        """
        if isinstance(base, COSString):
            return base.get_string()
        if isinstance(base, COSStream):
            return base.to_text_string()
        return None


__all__ = ["PDVariableText"]
