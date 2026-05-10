from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CFFOperator:
    """CFF Top/Private DICT operator metadata.

    Mirrors upstream ``org.apache.fontbox.cff.CFFOperator``
    (``CFFOperator.java`` lines 26-131).

    Upstream this class is a static utility — the constructor is
    private and the public surface is just ``getOperator(b0)`` /
    ``getOperator(b0, b1)``. We mirror that with module-level
    :func:`get_operator`, but additionally expose ``CFFOperator``
    itself as a frozen dataclass holding the operator's identifying
    key (b0, b1) and its mnemonic name. This is a superset of the
    upstream surface, kept compatible: callers using only
    :func:`get_operator` see the same behaviour as upstream.
    """

    b0: int
    b1: int
    name: str

    @property
    def key(self) -> int:
        """Internal lookup key: ``(b1 << 8) | b0`` — matches upstream
        ``CFFOperator.calculateKey`` (``CFFOperator.java`` line 66)."""
        return (self.b1 << 8) | self.b0

    # ------------------------------------------------------------------
    # Class-level mirrors of upstream's static methods. Upstream marks
    # ``register`` and ``calculateKey`` as ``private``; we expose them at
    # the same surface area (without enforcing private) so parity scanners
    # see the same method names. The free functions below are kept for
    # callers that already import them.
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_key(b0: int, b1: int = 0) -> int:
        """PDFBox: ``CFFOperator.calculateKey(int, int)``
        (``CFFOperator.java`` lines 66-69). Returns ``(b1 << 8) + b0``.
        """
        return (int(b1) << 8) + int(b0)

    @classmethod
    def get_operator(cls, b0: int, b1: int = 0) -> str | None:
        """PDFBox: ``CFFOperator.getOperator(int)`` /
        ``getOperator(int, int)`` (``CFFOperator.java`` lines 49-64).
        Resolve a byte pair to the operator mnemonic, or ``None`` for an
        unknown operator (upstream returns ``null``).
        """
        op = _KEY_TO_OPERATOR.get(cls.calculate_key(b0, b1))
        return op.name if op is not None else None

    @classmethod
    def register(cls, b0: int, *args: int | str) -> None:
        """PDFBox: ``CFFOperator.register(int, String)`` /
        ``register(int, int, String)`` (``CFFOperator.java`` lines 33-41).
        Adds (or replaces) an operator entry in the shared key map.

        Two upstream overloads collapsed into one Python signature:

        * ``register(b0, name)`` — single-byte operator (``b1 = 0``).
        * ``register(b0, b1, name)`` — two-byte operator.
        """
        if len(args) == 1:
            b1: int = 0
            name = args[0]
        elif len(args) == 2:
            b1 = int(args[0])  # type: ignore[arg-type]
            name = args[1]
        else:
            raise TypeError(
                "register() takes 2 or 3 positional arguments "
                f"(got {len(args) + 1})"
            )
        if not isinstance(name, str):
            raise TypeError("operator name must be a str")
        op = CFFOperator(b0=int(b0), b1=int(b1), name=name)
        _KEY_TO_OPERATOR[op.key] = op


# CFF operator table — Adobe Technote #5176 §9 (Top DICT) + §10 (Private DICT).
# The numeric pairs are read directly from upstream
# ``CFFOperator.java`` static initialiser (lines 73-130) so the
# byte-level wire format stays identical.
_OPERATORS: list[CFFOperator] = [
    # Top DICT operators — single-byte
    CFFOperator(0, 0, "version"),
    CFFOperator(1, 0, "Notice"),
    CFFOperator(2, 0, "FullName"),
    CFFOperator(3, 0, "FamilyName"),
    CFFOperator(4, 0, "Weight"),
    CFFOperator(5, 0, "FontBBox"),
    CFFOperator(13, 0, "UniqueID"),
    CFFOperator(14, 0, "XUID"),
    CFFOperator(15, 0, "charset"),
    CFFOperator(16, 0, "Encoding"),
    CFFOperator(17, 0, "CharStrings"),
    CFFOperator(18, 0, "Private"),
    # Top DICT operators — two-byte (escape 12)
    CFFOperator(12, 0, "Copyright"),
    CFFOperator(12, 1, "isFixedPitch"),
    CFFOperator(12, 2, "ItalicAngle"),
    CFFOperator(12, 3, "UnderlinePosition"),
    CFFOperator(12, 4, "UnderlineThickness"),
    CFFOperator(12, 5, "PaintType"),
    CFFOperator(12, 6, "CharstringType"),
    CFFOperator(12, 7, "FontMatrix"),
    CFFOperator(12, 8, "StrokeWidth"),
    CFFOperator(12, 20, "SyntheticBase"),
    CFFOperator(12, 21, "PostScript"),
    CFFOperator(12, 22, "BaseFontName"),
    CFFOperator(12, 23, "BaseFontBlend"),
    CFFOperator(12, 30, "ROS"),
    CFFOperator(12, 31, "CIDFontVersion"),
    CFFOperator(12, 32, "CIDFontRevision"),
    CFFOperator(12, 33, "CIDFontType"),
    CFFOperator(12, 34, "CIDCount"),
    CFFOperator(12, 35, "UIDBase"),
    CFFOperator(12, 36, "FDArray"),
    CFFOperator(12, 37, "FDSelect"),
    CFFOperator(12, 38, "FontName"),
    # Private DICT operators — single-byte
    CFFOperator(6, 0, "BlueValues"),
    CFFOperator(7, 0, "OtherBlues"),
    CFFOperator(8, 0, "FamilyBlues"),
    CFFOperator(9, 0, "FamilyOtherBlues"),
    CFFOperator(10, 0, "StdHW"),
    CFFOperator(11, 0, "StdVW"),
    CFFOperator(19, 0, "Subrs"),
    CFFOperator(20, 0, "defaultWidthX"),
    CFFOperator(21, 0, "nominalWidthX"),
    # Private DICT operators — two-byte (escape 12)
    CFFOperator(12, 9, "BlueScale"),
    CFFOperator(12, 10, "BlueShift"),
    CFFOperator(12, 11, "BlueFuzz"),
    CFFOperator(12, 12, "StemSnapH"),
    CFFOperator(12, 13, "StemSnapV"),
    CFFOperator(12, 14, "ForceBold"),
    CFFOperator(12, 15, "LanguageGroup"),
    CFFOperator(12, 16, "ExpansionFactor"),
    CFFOperator(12, 17, "initialRandomSeed"),
]

# Build the (b1<<8|b0) → name map to mirror upstream ``keyMap`` directly.
_KEY_TO_OPERATOR: dict[int, CFFOperator] = {op.key: op for op in _OPERATORS}


def get_operator(b0: int, b1: int = 0) -> str | None:
    """Module-level convenience wrapper around
    :meth:`CFFOperator.get_operator` — kept for callers that already
    import the free function form.
    """
    return CFFOperator.get_operator(b0, b1)


def get_operator_entry(b0: int, b1: int = 0) -> CFFOperator | None:
    """Resolve a byte pair to the full :class:`CFFOperator` record.

    Not present in upstream (which only exposes ``getOperator``); added
    so callers that need the (b0, b1) pair back from a parsed name —
    e.g. when re-encoding a DICT — can avoid re-deriving it. Returns
    ``None`` for an unknown operator.
    """
    return _KEY_TO_OPERATOR.get(CFFOperator.calculate_key(b0, b1))


__all__ = ["CFFOperator", "get_operator", "get_operator_entry"]
