"""Font /Type + /Subtype pairing helper.

Mirrors the private inner class
``org.apache.pdfbox.pdmodel.font.PDFontFactory.FontType`` (PDFBox 3.0,
``PDFontFactory.java`` lines 64-114). Surfaced here as a standalone
module-level class so callers outside ``PDFontFactory`` can ask the same
"is this descendant a CIDFontType0 / CIDFontType2?" routing question
without poking the factory's private machinery.

Upstream is *not* a Java ``enum`` despite its enum-flavoured shape; the
upstream type is a regular inner class with three overloaded
constructors. We mirror that here: a single Python ``__init__`` that
accepts ``COSName`` or ``str`` for the subtype, plus an optional-subtype
overload that mirrors the no-subtype constructor.

The ``PDFontFactory.get_font_type_from_font`` callsite (java L170) uses
:meth:`get_subtype` to consult the descendant CIDFont's effective
/Subtype, and :meth:`is_cid_subtype` is used downstream by ``createFont``
to keep the dispatch readable. Both behaviours are preserved verbatim
here so a future ``PDFontFactory`` rewrite can switch to this helper
without behavioural drift.
"""

from __future__ import annotations

from pypdfbox.cos.cos_name import COSName

# Upstream ``PDFontFactory.FONT_TYPE1C`` (java L42). Kept as a
# module-level constant so the CID-classification table below stays
# self-contained even when this module is consumed outside the factory.
_FONT_TYPE1C: str = "Type1C"


class FontType:
    """Pair a top-level /Type COSName with an effective /Subtype.

    Upstream Java: private inner ``PDFontFactory.FontType``
    (``PDFontFactory.java`` lines 64-114, Apache PDFBox 3.0). Upstream
    has three constructors:

    * ``FontType(COSName type, String subtypeString)`` (L73-88) —
      classifies a *descendant* subtype string against the two CID
      lookup tables, mapping Type1/Type1C onto ``CIDFontType0`` and
      TrueType/OpenType onto ``CIDFontType2``; anything else collapses
      to ``None``.
    * ``FontType(COSName type, COSName subtype)`` (L90-94) — direct
      pass-through, no classification.
    * ``FontType(COSName type)`` (L96-99) — convenience for the
      no-subtype case; delegates to the previous form with
      ``null``.

    All three are reachable through this Python ``__init__`` by
    choosing the ``subtype`` argument type: ``str`` triggers the
    classifying constructor, anything else (``COSName`` or ``None``)
    is taken as-is.
    """

    # Upstream ``cidType0Types`` (java L66-67): the set of descendant
    # /Subtype strings that should be reported as ``CIDFontType0``.
    # Upstream uses ``COSName.TYPE1.getName()`` + the ``FONT_TYPE1C``
    # constant; ``COSName`` here doesn't predefine the font subtype
    # constants, so we inline the same name strings ("Type1", "Type1C")
    # — matching upstream's resolved values verbatim.
    _CID_TYPE0_TYPES: frozenset[str] = frozenset({"Type1", _FONT_TYPE1C})
    # Upstream ``cidType2Types`` (java L68-69): descendant /Subtype
    # strings that should be reported as ``CIDFontType2``. Upstream
    # uses ``COSName.TRUE_TYPE.getName()`` + ``COSName.OPEN_TYPE.getName()``.
    _CID_TYPE2_TYPES: frozenset[str] = frozenset({"TrueType", "OpenType"})

    __slots__ = ("type", "subtype")

    def __init__(
        self,
        type_: COSName,
        subtype: COSName | str | None = None,
    ) -> None:
        self.type: COSName = type_
        if isinstance(subtype, str):
            # String constructor (java L73-88): classify against the
            # CID lookup tables.
            if subtype in self._CID_TYPE0_TYPES:
                self.subtype: COSName | None = COSName.get_pdf_name(
                    "CIDFontType0"
                )
            elif subtype in self._CID_TYPE2_TYPES:
                self.subtype = COSName.get_pdf_name("CIDFontType2")
            else:
                self.subtype = None
        else:
            # COSName / None constructors (java L90-99): direct
            # assignment; ``None`` mirrors the no-subtype overload.
            self.subtype = subtype

    def get_subtype(self) -> COSName | None:
        """Return the recorded /Subtype name, or ``None`` if absent.

        Mirrors upstream ``COSName getSubtype()`` (java L101-104).
        Returns the *classified* /Subtype (``CIDFontType0`` /
        ``CIDFontType2``) when constructed from a descendant subtype
        string, or the verbatim ``COSName`` when constructed directly.
        """
        return self.subtype

    def is_cid_subtype(self, cid_subtype: COSName) -> bool:
        """Return ``True`` when this pair represents a /Type0 font whose
        descendant /Subtype matches ``cid_subtype``.

        Mirrors upstream ``boolean isCIDSubtype(COSName cidSubtype)``
        (java L106-113). The /Type0 gate is identical to upstream:
        non-Type0 fonts always return ``False`` even if the subtype
        coincidentally equals one of the CID names. The equality check
        uses ``COSName.__eq__`` semantics (interned-by-name), so a
        caller comparing against ``COSName.CID_FONT_TYPE0`` or the
        result of :meth:`COSName.get_pdf_name` will agree.
        """
        if self.type != COSName.get_pdf_name("Type0"):
            return False
        return self.subtype is not None and self.subtype == cid_subtype


__all__ = ["FontType"]
