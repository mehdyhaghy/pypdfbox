from __future__ import annotations

from fontTools.cffLib import cffStandardStrings  # type: ignore[import-untyped]

# Number of CFF Standard Strings per Adobe Technote #5176 §10:
# SIDs 0..390 index the immutable, font-independent table; SIDs >= 391
# index a per-font STRING INDEX. The fontTools constant
# ``cffStandardStrings`` is exactly that 391-entry table.
NUM_STANDARD_STRINGS: int = len(cffStandardStrings)


class CFFStandardString:
    """Static SID → glyph-name lookup for the CFF Standard Strings.

    Mirrors upstream ``org.apache.fontbox.cff.CFFStandardString``
    (``CFFStandardString.java`` lines 23-433). Upstream this is a
    ``final`` class with a private constructor and a single static
    method ``getName(int)``; we keep the same surface.

    Library-first: rather than carry a 391-entry literal copy of the
    table, we wrap fontTools' ``fontTools.cffLib.cffStandardStrings``
    (MIT). The fontTools table is byte-identical to the one in
    upstream's ``SID2STR`` array — both come straight from the CFF
    spec — so behaviour is preserved.
    """

    def __init__(self) -> None:
        # Upstream constructor is private; we keep the class
        # instantiable but it's purely a namespace.
        msg = "CFFStandardString is a static utility; do not instantiate"
        raise TypeError(msg)

    @staticmethod
    def get_name(sid: int) -> str | None:
        """PDFBox: ``CFFStandardString.getName(int)``
        (``CFFStandardString.java`` lines 35-38) — return the glyph name
        for a Standard SID.

        Upstream throws ``ArrayIndexOutOfBoundsException`` for SIDs
        outside ``[0, 390]`` (because it indexes a fixed Java array).
        We diverge mildly: out-of-range SIDs return ``None``, mirroring
        the typical Python "no entry" idiom and matching how callers
        already null-check the result before falling through to the
        per-font STRING INDEX (see upstream ``CFFParser.readString``,
        line 909).
        """
        if 0 <= sid < NUM_STANDARD_STRINGS:
            return str(cffStandardStrings[sid])
        return None


__all__ = ["NUM_STANDARD_STRINGS", "CFFStandardString"]
