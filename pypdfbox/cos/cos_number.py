from __future__ import annotations

from .cos_base import COSBase

_LONG_MIN = -(2**63)
_LONG_MAX = 2**63 - 1


class COSNumber(COSBase):
    """
    Abstract numeric COS object — common base of ``COSInteger`` and
    ``COSFloat``. Mirrors PDFBox's ``COSNumber``; preserves the
    ``COSBase → COSNumber → {COSInteger, COSFloat}`` hierarchy.
    """

    def float_value(self) -> float:
        raise NotImplementedError

    def int_value(self) -> int:
        raise NotImplementedError

    def long_value(self) -> int:
        raise NotImplementedError

    @staticmethod
    def get(value: str) -> COSNumber:
        """Parse a PDF number literal — mirrors ``COSNumber.get(String)``.

        Returns a ``COSInteger`` for integral inputs and a ``COSFloat`` for
        anything containing a decimal point or exponent. The trivial inputs
        ``""``, ``"-"`` and ``"."`` map to ``COSInteger.ZERO`` per upstream.
        Values whose magnitude exceeds Java's ``Long`` range produce a
        ``COSInteger`` flagged invalid (matches PDFBOX-5176 behavior).
        """
        # Local imports avoid the circular dependency between cos_number,
        # cos_integer and cos_float at module-import time.
        from .cos_float import COSFloat
        from .cos_integer import COSInteger

        if value is None:
            raise TypeError("value is None")
        if value in ("", "-", "."):
            return COSInteger.ZERO  # type: ignore[attr-defined,no-any-return]
        # Anything with a fractional or exponent component is a float.
        if "." in value or "e" in value or "E" in value:
            try:
                return COSFloat(value)
            except (ValueError, OSError) as exc:
                raise OSError(f"not a number: {value!r}") from exc
        # Integer path; strip a leading '+' (Java's parseLong doesn't accept it).
        candidate = value.lstrip("+") if value.startswith("+") else value
        try:
            n = int(candidate)
        except ValueError as exc:
            raise OSError(f"not a number: {value!r}") from exc
        if _LONG_MIN <= n <= _LONG_MAX:
            return COSInteger.get(n)
        cosint = COSInteger(n)
        cosint.set_valid(False)
        return cosint
