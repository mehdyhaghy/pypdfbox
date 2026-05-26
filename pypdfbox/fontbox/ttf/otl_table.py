from __future__ import annotations

from .ttf_table import TTFTable


class OTLTable(TTFTable):
    """An OpenType Layout (OTL) common table.

    Mirrors ``org.apache.fontbox.ttf.OTLTable`` (``OTLTable.java`` lines
    24-34). Upstream uses this as a generic placeholder for the OpenType
    Layout tables that PDFBox does not parse in detail — ``BASE``,
    ``GDEF``, ``GPOS`` and ``JSTF`` (the ``TAG`` constant names the
    justification table). The class adds no behaviour over
    :class:`TTFTable`; it exists so :class:`OTFParser` can return a
    distinctly-typed table for those tags while leaving the per-table
    decode to fontTools.
    """

    # Upstream surfaces the justification-table tag as a ``public static
    # final String`` (``OTLTable.java`` line 26) so callers can refer to
    # it by name.
    TAG: str = "JSTF"


__all__ = ["OTLTable"]
