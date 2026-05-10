from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSNumber, COSStream, COSString

from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources

    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_DA: COSName = COSName.get_pdf_name("DA")
_DS: COSName = COSName.get_pdf_name("DS")
_Q: COSName = COSName.get_pdf_name("Q")
_RV: COSName = COSName.get_pdf_name("RV")
_KIDS: COSName = COSName.get_pdf_name("Kids")


class PDDefaultAppearanceString:
    """Lite data-only port of upstream ``PDDefaultAppearanceString``.

    Mirrors the *constructor surface* of upstream
    ``org.apache.pdfbox.pdmodel.interactive.form.PDDefaultAppearanceString``
    (package-private upstream — surfaced here for parity with
    :meth:`PDVariableText.get_default_appearance_string`). The upstream
    class parses the ``/DA`` content-stream operators to recover the
    selected font / size / colour; pypdfbox keeps the parser deferred and
    just retains the raw ``/DA`` ``COSString`` and the ``PDResources``
    reference for callers that want to perform the parsing themselves
    (e.g. tests asserting round-trip identity).

    Both ``/DA`` and ``/DR`` are required by upstream (which raises
    ``IllegalArgumentException`` when either is ``None``); pypdfbox keeps
    that contract via ``ValueError`` (Python's closest analogue).
    """

    def __init__(
        self,
        default_appearance: COSString | None,
        default_resources: PDResources | None,
    ) -> None:
        if default_appearance is None:
            raise ValueError(
                "/DA is a required entry. Please set a default appearance first."
            )
        if default_resources is None:
            raise ValueError("/DR is a required entry")
        self._default_appearance: COSString = default_appearance
        self._default_resources: PDResources = default_resources

    def get_default_appearance(self) -> COSString:
        """Return the raw ``/DA`` ``COSString`` operand."""
        return self._default_appearance

    def get_default_resources(self) -> PDResources:
        """Return the ``/DR`` resources used to resolve fonts / colour spaces."""
        return self._default_resources


def _require_text_or_none(value: object, method: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise TypeError(f"{method} expected str or None; got {type(value).__name__}")


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
        da_value = _require_text_or_none(da_value, "set_default_appearance")
        self._field.set_string(_DA, da_value)
        if self._field.contains_key(_KIDS):
            for widget in self.get_widgets():
                widget_cos = widget.get_cos_object()
                if widget_cos.contains_key(_DA):
                    widget_cos.set_string(_DA, da_value)

    def get_default_appearance_string(self) -> PDDefaultAppearanceString | None:
        """Return ``/DA`` as a typed :class:`PDDefaultAppearanceString`.

        Mirrors upstream ``PDVariableText.getDefaultAppearanceString`` (lines
        96-106 in PDVariableText.java). The upstream method walks
        ``getInheritableAttribute(COSName.DA)`` to find the ``COSString``
        operand, then constructs a ``PDDefaultAppearanceString(da, dr)``
        using the AcroForm's default resources (``/DR``).

        Returns ``None`` when ``/DA`` is absent across the inheritance
        chain — upstream lets the ``ValueError`` ("required entry")
        bubble out, but pypdfbox prefers an early ``None`` so callers can
        distinguish "no DA configured" from "malformed DA" without
        catching exceptions. Callers that want upstream parity can do
        ``self.get_default_appearance_string()`` and treat ``None`` as
        the upstream error case themselves.
        """
        base = self.get_inheritable_attribute(_DA)
        da: COSString | None = base if isinstance(base, COSString) else None
        if da is None:
            return None
        dr = self.get_acro_form().get_default_resources()
        if dr is None:
            return None
        return PDDefaultAppearanceString(da, dr)

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
        value = _require_text_or_none(value, "set_default_style_string")
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
        return self.get_string_or_stream(self.get_inheritable_attribute(_RV))

    def set_rich_text_value(self, value: str | None) -> None:
        value = _require_text_or_none(value, "set_rich_text_value")
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

    def get_string_or_stream(self, base: COSBase | None) -> str | None:
        """Return a text-or-stream payload as a Python ``str``.

        Mirrors upstream ``PDVariableText.getStringOrStream`` (declared
        ``protected final`` in Java; surfaced as a regular method in
        pypdfbox following the project convention for ``protected``
        members — see ``apply_change`` etc.). Some dictionary entries
        (``/V``, ``/DV``, ``/RV``) admit either a ``COSString`` or a
        ``COSStream`` body. ``COSString`` returns its decoded text,
        ``COSStream`` decodes through ``to_text_string`` (matching
        upstream ``COSStream.toTextString``). Returns ``None`` when the
        entry is missing or any other COS type — pypdfbox keeps the
        explicit ``None`` for callers that want to distinguish "no entry"
        from "empty payload" (upstream returns ``""`` in both cases; see
        CHANGES.md).
        """
        if isinstance(base, COSString):
            return base.get_string()
        if isinstance(base, COSStream):
            return base.to_text_string()
        return None

    # Backwards-compatible alias for callers that used the underscore-
    # prefixed name before ``get_string_or_stream`` was promoted to the
    # public surface (Java ``protected final`` parity).
    _get_string_or_stream = get_string_or_stream


__all__ = ["PDDefaultAppearanceString", "PDVariableText"]
