from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName, COSNumber, COSString

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_U: COSName = COSName.get_pdf_name("U")
_C: COSName = COSName.get_pdf_name("C")
_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.get_pdf_name("D")
_FD: COSName = COSName.get_pdf_name("FD")
_RT: COSName = COSName.get_pdf_name("RT")
_RD: COSName = COSName.get_pdf_name("RD")
_PS: COSName = COSName.get_pdf_name("PS")
_SS: COSName = COSName.get_pdf_name("SS")
_O: COSName = COSName.get_pdf_name("O")


class PDNumberFormatDictionary:
    """Number format dictionary used inside a measurement dictionary.

    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.interactive.measurement.PDNumberFormatDictionary``.
    Wraps a :class:`COSDictionary` whose ``/Type`` is ``NumberFormat``.
    """

    #: The ``/Type`` value of the dictionary.
    TYPE: str = "NumberFormat"

    #: Constant indicating that the label specified by ``U`` is a suffix to the value.
    LABEL_SUFFIX_TO_VALUE: str = "S"
    #: Constant indicating that the label specified by ``U`` is a prefix to the value.
    LABEL_PREFIX_TO_VALUE: str = "P"

    #: Constant for showing a fractional value as decimal to the precision specified by ``D``.
    FRACTIONAL_DISPLAY_DECIMAL: str = "D"
    #: Constant for showing a fractional value as a fraction with denominator specified by ``D``.
    FRACTIONAL_DISPLAY_FRACTION: str = "F"
    #: Constant for showing a fractional value rounded to the nearest whole unit.
    FRACTIONAL_DISPLAY_ROUND: str = "R"
    #: Constant for showing a fractional value truncated to whole units.
    FRACTIONAL_DISPLAY_TRUNCATE: str = "T"

    #: Tuple of all valid ``/F`` (fractional display) values, in spec order.
    FRACTIONAL_DISPLAYS: tuple[str, ...] = (
        FRACTIONAL_DISPLAY_DECIMAL,
        FRACTIONAL_DISPLAY_FRACTION,
        FRACTIONAL_DISPLAY_ROUND,
        FRACTIONAL_DISPLAY_TRUNCATE,
    )

    #: Tuple of all valid ``/O`` (label position) values, in spec order.
    LABEL_POSITIONS: tuple[str, ...] = (
        LABEL_SUFFIX_TO_VALUE,
        LABEL_PREFIX_TO_VALUE,
    )

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_name(_TYPE, self.TYPE)
        else:
            self._dict = dictionary

    # ------------------------------------------------------------------ COSObjectable
    def get_cos_object(self) -> COSDictionary:
        """Return the underlying ``COSDictionary``."""
        return self._dict

    @staticmethod
    def _is_string_entry(value: object) -> bool:
        return isinstance(value, (COSName, COSString))

    def _has_string_entry(self, key: COSName) -> bool:
        return self._is_string_entry(self._dict.get_dictionary_object(key))

    def _has_number_entry(self, key: COSName) -> bool:
        return isinstance(self._dict.get_dictionary_object(key), COSNumber)

    def _clear(self, key: COSName) -> None:
        self._dict.remove_item(key)

    # ------------------------------------------------------------------ /Type
    def get_type(self) -> str:
        """Return the type of the number format dictionary (always ``NumberFormat``)."""
        return self.TYPE

    # ------------------------------------------------------------------ /U
    def get_units(self) -> str | None:
        """Return the label for the units (``/U``)."""
        return self._dict.get_string(_U)

    def set_units(self, units: str | None) -> None:
        """Set the label for the units (``/U``)."""
        self._dict.set_string(_U, units)

    def has_units(self) -> bool:
        """Return ``True`` when ``/U`` is present as a string or name."""
        return self._has_string_entry(_U)

    def clear_units(self) -> None:
        """Clear the units label (``/U``)."""
        self._clear(_U)

    # ------------------------------------------------------------------ /C
    def get_conversion_factor(self) -> float:
        """Return the conversion factor (``/C``)."""
        return self._dict.get_float(_C)

    def set_conversion_factor(self, conversion_factor: float) -> None:
        """Set the conversion factor (``/C``)."""
        self._dict.set_float(_C, conversion_factor)

    def has_conversion_factor(self) -> bool:
        """Return ``True`` when ``/C`` is present as a number."""
        return self._has_number_entry(_C)

    def clear_conversion_factor(self) -> None:
        """Clear the conversion factor (``/C``)."""
        self._clear(_C)

    # ------------------------------------------------------------------ /F
    def get_fractional_display(self) -> str | None:
        """Return the manner to display a fractional value (``/F``).

        Defaults to :attr:`FRACTIONAL_DISPLAY_DECIMAL` if the entry is missing.
        """
        return self._dict.get_string(_F, self.FRACTIONAL_DISPLAY_DECIMAL)

    def set_fractional_display(self, fractional_display: str | None) -> None:
        """Set the manner to display a fractional value (``/F``).

        Allowed values are ``"D"``, ``"F"``, ``"R"``, ``"T"`` and ``None``.
        """
        if fractional_display is None or fractional_display in self.FRACTIONAL_DISPLAYS:
            self._dict.set_string(_F, fractional_display)
        else:
            raise ValueError('Value must be "D", "F", "R", or "T", (or None).')

    def has_fractional_display(self) -> bool:
        """Return ``True`` when ``/F`` is present as a string or name."""
        return self._has_string_entry(_F)

    def clear_fractional_display(self) -> None:
        """Clear the fractional display mode (``/F``)."""
        self._clear(_F)

    def is_fractional_display_decimal(self) -> bool:
        """Return ``True`` if the fractional display mode is ``"D"`` (decimal)."""
        return self.get_fractional_display() == self.FRACTIONAL_DISPLAY_DECIMAL

    def is_fractional_display_fraction(self) -> bool:
        """Return ``True`` if the fractional display mode is ``"F"`` (fraction)."""
        return self.get_fractional_display() == self.FRACTIONAL_DISPLAY_FRACTION

    def is_fractional_display_round(self) -> bool:
        """Return ``True`` if the fractional display mode is ``"R"`` (round)."""
        return self.get_fractional_display() == self.FRACTIONAL_DISPLAY_ROUND

    def is_fractional_display_truncate(self) -> bool:
        """Return ``True`` if the fractional display mode is ``"T"`` (truncate)."""
        return self.get_fractional_display() == self.FRACTIONAL_DISPLAY_TRUNCATE

    # ------------------------------------------------------------------ /D
    def get_denominator(self) -> int:
        """Return the precision or denominator of a fractional amount (``/D``)."""
        return self._dict.get_int(_D)

    def set_denominator(self, denominator: int) -> None:
        """Set the precision or denominator of a fractional amount (``/D``)."""
        self._dict.set_int(_D, denominator)

    def has_denominator(self) -> bool:
        """Return ``True`` when ``/D`` is present as a number."""
        return self._has_number_entry(_D)

    def clear_denominator(self) -> None:
        """Clear the precision or denominator (``/D``)."""
        self._clear(_D)

    # ------------------------------------------------------------------ /FD
    def is_fd(self) -> bool:
        """Return whether the denominator of the fractional value is reduced/truncated (``/FD``)."""
        return self._dict.get_boolean(_FD, False)

    def set_fd(self, fd: bool) -> None:
        """Set whether the denominator is reduced/truncated (``/FD``)."""
        self._dict.set_boolean(_FD, fd)

    def has_fd(self) -> bool:
        """Return ``True`` when ``/FD`` is present as a boolean."""
        return isinstance(self._dict.get_dictionary_object(_FD), COSBoolean)

    def clear_fd(self) -> None:
        """Clear the fractional denominator flag (``/FD``)."""
        self._clear(_FD)

    # ------------------------------------------------------------------ /RT
    def get_thousands_separator(self) -> str | None:
        """Return the text used between orders of thousands (``/RT``).

        Defaults to ``","`` if the entry is missing.
        """
        return self._dict.get_string(_RT, ",")

    def set_thousands_separator(self, thousands_separator: str | None) -> None:
        """Set the text used between orders of thousands (``/RT``)."""
        self._dict.set_string(_RT, thousands_separator)

    def has_thousands_separator(self) -> bool:
        """Return ``True`` when ``/RT`` is present as a string or name."""
        return self._has_string_entry(_RT)

    def clear_thousands_separator(self) -> None:
        """Clear the thousands separator (``/RT``)."""
        self._clear(_RT)

    # ------------------------------------------------------------------ /RD
    def get_decimal_separator(self) -> str | None:
        """Return the text used as the decimal point (``/RD``).

        Defaults to ``"."`` if the entry is missing.
        """
        return self._dict.get_string(_RD, ".")

    def set_decimal_separator(self, decimal_separator: str | None) -> None:
        """Set the text used as the decimal point (``/RD``)."""
        self._dict.set_string(_RD, decimal_separator)

    def has_decimal_separator(self) -> bool:
        """Return ``True`` when ``/RD`` is present as a string or name."""
        return self._has_string_entry(_RD)

    def clear_decimal_separator(self) -> None:
        """Clear the decimal separator (``/RD``)."""
        self._clear(_RD)

    # ------------------------------------------------------------------ /PS
    def get_label_prefix_string(self) -> str | None:
        """Return the text concatenated to the left of the label specified by ``/U`` (``/PS``).

        Defaults to ``" "`` if the entry is missing.
        """
        return self._dict.get_string(_PS, " ")

    def set_label_prefix_string(self, label_prefix_string: str | None) -> None:
        """Set the text concatenated to the left of the label specified by ``/U`` (``/PS``)."""
        self._dict.set_string(_PS, label_prefix_string)

    def has_label_prefix_string(self) -> bool:
        """Return ``True`` when ``/PS`` is present as a string or name."""
        return self._has_string_entry(_PS)

    def clear_label_prefix_string(self) -> None:
        """Clear the label prefix string (``/PS``)."""
        self._clear(_PS)

    # ------------------------------------------------------------------ /SS
    def get_label_suffix_string(self) -> str | None:
        """Return the text concatenated after the label specified by ``/U`` (``/SS``).

        Defaults to ``" "`` if the entry is missing.
        """
        return self._dict.get_string(_SS, " ")

    def set_label_suffix_string(self, label_suffix_string: str | None) -> None:
        """Set the text concatenated after the label specified by ``/U`` (``/SS``)."""
        self._dict.set_string(_SS, label_suffix_string)

    def has_label_suffix_string(self) -> bool:
        """Return ``True`` when ``/SS`` is present as a string or name."""
        return self._has_string_entry(_SS)

    def clear_label_suffix_string(self) -> None:
        """Clear the label suffix string (``/SS``)."""
        self._clear(_SS)

    # ------------------------------------------------------------------ /O
    def get_label_position_to_value(self) -> str | None:
        """Return the ordering of the ``/U`` label to the unit value (``/O``).

        Defaults to :attr:`LABEL_SUFFIX_TO_VALUE` if the entry is missing.
        """
        return self._dict.get_string(_O, self.LABEL_SUFFIX_TO_VALUE)

    def set_label_position_to_value(self, label_position_to_value: str | None) -> None:
        """Set the ordering of the label specified by ``/U`` to the calculated unit value (``/O``).

        Allowed values are ``"S"``, ``"P"`` and ``None``.
        """
        if label_position_to_value is None or label_position_to_value in self.LABEL_POSITIONS:
            self._dict.set_string(_O, label_position_to_value)
        else:
            raise ValueError('Value must be "S", or "P" (or None).')

    def has_label_position_to_value(self) -> bool:
        """Return ``True`` when ``/O`` is present as a string or name."""
        return self._has_string_entry(_O)

    def clear_label_position_to_value(self) -> None:
        """Clear the label position mode (``/O``)."""
        self._clear(_O)

    def is_label_prefix_to_value(self) -> bool:
        """Return ``True`` if the label position is ``"P"`` (prefix to value)."""
        return self.get_label_position_to_value() == self.LABEL_PREFIX_TO_VALUE

    def is_label_suffix_to_value(self) -> bool:
        """Return ``True`` if the label position is ``"S"`` (suffix to value)."""
        return self.get_label_position_to_value() == self.LABEL_SUFFIX_TO_VALUE


__all__ = ["PDNumberFormatDictionary"]
