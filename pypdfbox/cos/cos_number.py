from __future__ import annotations

from .cos_base import COSBase

_LONG_MIN = -(2**63)
_LONG_MAX = 2**63 - 1


def _is_ascii_digits(text: str) -> bool:
    r"""``True`` when every char of ``text`` is an ASCII ``0``-``9`` digit.

    Mirrors Java's ``String.matches("\d*")`` (whose ``\d`` is ASCII-only by
    default): the empty string matches, and non-ASCII "digit" code points
    (which Python's ``str.isdigit`` would accept) do not.
    """
    return all("0" <= ch <= "9" for ch in text)


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
        r"""Parse a PDF number literal — mirrors ``COSNumber.get(String)``.

        Reproduces upstream ``COSNumber.get`` (PDFBox 3.0.7) branch-for-branch:

        1. A single-character literal dispatches specially: ``'0'..'9'`` ->
           ``COSInteger.get(digit)``; ``'-'`` or ``'.'`` -> ``COSInteger.ZERO``;
           anything else -> ``OSError`` (upstream ``IOException``).
        2. ``isFloat`` (a ``.`` or lowercase ``e`` anywhere — upstream does NOT
           treat ``E`` as float) -> ``COSFloat``.
        3. Otherwise parse as a ``Long``. Java's ``Long.parseLong`` accepts a
           single leading ``+``/``-`` sign. On failure the digits-only check
           ``matches("\d*")`` (after stripping one leading ``+``/``-``)
           decides: all-digits means the value merely overflowed ``Long`` and
           we return ``OUT_OF_RANGE_MIN`` / ``OUT_OF_RANGE_MAX`` (PDFBOX-5176,
           flagged invalid); a non-digit residue -> ``OSError``.

        Note the empty string ``""`` is NOT a single-char literal, is not a
        float, and ``"".matches("\d*")`` is ``True``, so upstream returns
        ``OUT_OF_RANGE_MAX`` — not ``ZERO``.
        """
        # Local imports avoid the circular dependency between cos_number,
        # cos_integer and cos_float at module-import time.
        from .cos_float import COSFloat
        from .cos_integer import COSInteger

        if value is None:
            raise TypeError("value is None")
        # Single-character fast path (upstream ``number.length() == 1``).
        if len(value) == 1:
            ch = value[0]
            if "0" <= ch <= "9":
                return COSInteger.get(ord(ch) - ord("0"))
            if ch in ("-", "."):
                return COSInteger.ZERO  # type: ignore[attr-defined,no-any-return]
            raise OSError(f"Not a number: {value}")
        # Anything with a fractional or lowercase-exponent component is a float.
        # Upstream ``isFloat`` deliberately checks only ``.`` and ``e`` — an
        # uppercase ``E`` does NOT route here (it falls through to the integer
        # branch and fails the digits-only check).
        if COSNumber.is_float(value):
            return COSFloat(value)
        # Integer path. Java ``Long.parseLong`` accepts one leading sign char.
        try:
            n = COSNumber._parse_long(value)
        except ValueError:
            # Strip a single leading '+'/'-' and verify the residue is all
            # digits (upstream ``matches("\d*")``); only then is it a genuine
            # Long overflow rather than malformed input.
            candidate = value[1:] if value[:1] in ("+", "-") else value
            if not _is_ascii_digits(candidate):
                raise OSError(f"Not a number: {value}") from None
            if value.startswith("-"):
                return COSInteger.OUT_OF_RANGE_MIN  # type: ignore[attr-defined,no-any-return]
            return COSInteger.OUT_OF_RANGE_MAX  # type: ignore[attr-defined,no-any-return]
        return COSInteger.get(n)

    @staticmethod
    def _parse_long(value: str) -> int:
        """Mirror Java ``Long.parseLong`` strictly: accept an optional single
        leading ``+``/``-`` followed by ASCII digits, reject everything else
        (including ``""``), and raise ``ValueError`` for any value outside the
        signed 64-bit ``Long`` range so the overflow branch in ``get`` engages.
        """
        body = value
        negative = False
        if body[:1] in ("+", "-"):
            negative = body[0] == "-"
            body = body[1:]
        if body == "" or not _is_ascii_digits(body):
            raise ValueError(f"For input string: {value!r}")
        n = -int(body) if negative else int(body)
        if not (_LONG_MIN <= n <= _LONG_MAX):
            raise ValueError(f"For input string: {value!r}")
        return n
