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
    def is_float(number: str) -> bool:
        """Return ``True`` when ``number`` looks like a PDF real literal.

        Mirrors ``org.apache.pdfbox.cos.COSNumber#isFloat`` (a ``private
        static`` upstream helper). Detection is intentionally narrow:
        the literal contains either ``.`` or ``e``. Upstream does not
        check for ``E``; this port preserves that surface area so a
        round-trip through ``COSNumber.get`` yields the same dispatch
        decision as upstream when fed the same input.
        """
        if number is None:
            raise TypeError("number is None")
        return any(ch in (".", "e") for ch in number)

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
        # Out-of-range — return the canonical OUT_OF_RANGE_* sentinel so
        # callers see object identity (``is``) parity with PDFBox.
        if n > _LONG_MAX:
            return COSInteger.OUT_OF_RANGE_MAX  # type: ignore[attr-defined,no-any-return]
        return COSInteger.OUT_OF_RANGE_MIN  # type: ignore[attr-defined,no-any-return]
