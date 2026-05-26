from __future__ import annotations

from typing import ClassVar


class StandardStructureTypes:
    """
    The standard structure types.

    Ported from
    ``org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.StandardStructureTypes``.

    Holds the PDF 32000-1 §14.8.4 standard structure type names as class
    constants and exposes the sorted collection of every constant value via
    :attr:`types`. Upstream populates ``types`` reflectively from the public
    final ``String`` fields; here the equivalent set is gathered at class
    definition time from the constant attributes declared below.
    """

    # Grouping Elements
    DOCUMENT: ClassVar[str] = "Document"
    PART: ClassVar[str] = "Part"
    ART: ClassVar[str] = "Art"
    SECT: ClassVar[str] = "Sect"
    DIV: ClassVar[str] = "Div"
    BLOCK_QUOTE: ClassVar[str] = "BlockQuote"
    CAPTION: ClassVar[str] = "Caption"
    TOC: ClassVar[str] = "TOC"
    TOCI: ClassVar[str] = "TOCI"
    INDEX: ClassVar[str] = "Index"
    NON_STRUCT: ClassVar[str] = "NonStruct"
    PRIVATE: ClassVar[str] = "Private"

    # Block-Level Structure Elements
    P: ClassVar[str] = "P"
    H: ClassVar[str] = "H"
    H1: ClassVar[str] = "H1"
    H2: ClassVar[str] = "H2"
    H3: ClassVar[str] = "H3"
    H4: ClassVar[str] = "H4"
    H5: ClassVar[str] = "H5"
    H6: ClassVar[str] = "H6"
    L: ClassVar[str] = "L"
    LI: ClassVar[str] = "LI"
    LBL: ClassVar[str] = "Lbl"
    L_BODY: ClassVar[str] = "LBody"
    TABLE: ClassVar[str] = "Table"
    TR: ClassVar[str] = "TR"
    TH: ClassVar[str] = "TH"
    TD: ClassVar[str] = "TD"
    T_HEAD: ClassVar[str] = "THead"
    T_BODY: ClassVar[str] = "TBody"
    T_FOOT: ClassVar[str] = "TFoot"

    # Inline-Level Structure Elements
    SPAN: ClassVar[str] = "Span"
    QUOTE: ClassVar[str] = "Quote"
    NOTE: ClassVar[str] = "Note"
    REFERENCE: ClassVar[str] = "Reference"
    BIB_ENTRY: ClassVar[str] = "BibEntry"
    CODE: ClassVar[str] = "Code"
    LINK: ClassVar[str] = "Link"
    ANNOT: ClassVar[str] = "Annot"
    RUBY: ClassVar[str] = "Ruby"
    RB: ClassVar[str] = "RB"
    RT: ClassVar[str] = "RT"
    RP: ClassVar[str] = "RP"
    WARICHU: ClassVar[str] = "Warichu"
    WT: ClassVar[str] = "WT"
    WP: ClassVar[str] = "WP"

    # Illustration Elements
    # Upstream declares this constant as ``Figure`` (capitalised) rather than
    # the ``FIGURE`` convention used by every sibling; the spelling is
    # preserved so ``StandardStructureTypes.Figure`` resolves identically.
    Figure: ClassVar[str] = "Figure"
    FORMULA: ClassVar[str] = "Formula"
    FORM: ClassVar[str] = "Form"

    # All standard structure types, sorted. Mirrors upstream ``types``, which
    # is built reflectively from the public final ``String`` fields and then
    # ``Collections.sort``-ed. Gathered here from the constant attributes
    # declared above (every upper-case-or-``Figure`` class attribute whose
    # value is a ``str``).
    types: ClassVar[list[str]]

    def __init__(self) -> None:
        # Mirror upstream private no-arg constructor: this is a constants
        # holder and is never meant to be instantiated.
        raise TypeError("StandardStructureTypes is a non-instantiable constants holder")


def _collect_types() -> list[str]:
    collected: list[str] = []
    for name, value in vars(StandardStructureTypes).items():
        if name.startswith("_") or name == "types":
            continue
        if isinstance(value, str):
            collected.append(value)
    collected.sort()
    return collected


StandardStructureTypes.types = _collect_types()
