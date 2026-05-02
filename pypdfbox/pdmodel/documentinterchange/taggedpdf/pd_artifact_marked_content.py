from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class PDArtifactMarkedContent(PDMarkedContent):
    """
    An artifact marked-content sequence (``/Artifact`` BDC tag). Mirrors
    PDFBox
    ``org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDArtifactMarkedContent``.

    Layout, page, and pagination artifacts are flagged this way so PDF/UA
    consumers can filter them out of the logical content stream. The property
    dictionary carries the artifact's ``/Type`` (e.g. ``Pagination``,
    ``Layout``, ``Page``), ``/Subtype``, optional bounding box ``/BBox``, and
    ``/Attached`` array of edge names (``Top`` / ``Bottom`` / ``Left`` /
    ``Right``).
    """

    def __init__(self, properties: COSDictionary | None) -> None:
        super().__init__(COSName.get_pdf_name("Artifact"), properties)

    # ---------- typed accessors ----------

    def get_type(self) -> str | None:
        """Artifact ``/Type`` (e.g. ``Pagination``, ``Layout``, ``Page``).

        Mirrors upstream ``getProperties().getNameAsString(TYPE)`` which
        accepts both ``COSName`` and ``COSString`` operands.
        """
        return self._name_as_string(COSName.TYPE)

    def get_b_box(self) -> PDRectangle | None:
        """Artifact bounding box ``/BBox``, or ``None`` if absent.

        Mirrors upstream ``getBBox``.
        """
        props = self.get_properties()
        if props is None:
            return None
        a = props.get_dictionary_object(COSName.get_pdf_name("BBox"))
        if isinstance(a, COSArray):
            return PDRectangle.from_cos_array(a)
        return None

    def get_bbox(self) -> PDRectangle | None:
        """Alias for :meth:`get_b_box`.

        ``get_b_box`` follows the PDFBox ``getBBox`` mechanical
        case-conversion; ``get_bbox`` matches the spelling used by
        sibling pypdfbox wrappers (e.g. :meth:`PDPage.get_bbox`).
        """
        return self.get_b_box()

    def is_top_attached(self) -> bool:
        """``True`` iff ``/Attached`` lists ``Top``."""
        return self._is_attached("Top")

    def is_bottom_attached(self) -> bool:
        """``True`` iff ``/Attached`` lists ``Bottom``."""
        return self._is_attached("Bottom")

    def is_left_attached(self) -> bool:
        """``True`` iff ``/Attached`` lists ``Left``."""
        return self._is_attached("Left")

    def is_right_attached(self) -> bool:
        """``True`` iff ``/Attached`` lists ``Right``."""
        return self._is_attached("Right")

    def get_subtype(self) -> str | None:
        """Artifact ``/Subtype`` — e.g. ``Header``, ``Footer``, ``Watermark``
        for pagination; ``PageNum``, ``Bates``, ``LineNum`` are also defined.

        Mirrors upstream ``getProperties().getNameAsString(SUBTYPE)`` which
        accepts both ``COSName`` and ``COSString`` operands.
        """
        return self._name_as_string(COSName.SUBTYPE)

    # ---------- helpers ----------

    def _name_as_string(self, key: COSName) -> str | None:
        """Mirror upstream ``COSDictionary.getNameAsString(COSName)``: a
        ``COSName`` returns its name; a ``COSString`` returns its decoded
        string value; anything else (including absent) returns ``None``.

        pypdfbox's ``COSDictionary.get_name`` strictly requires a
        ``COSName`` operand and returns ``None`` for ``COSString`` —
        which would silently drop ``/Type``/``/Subtype`` entries that
        upstream-produced PDFs encode as strings. Reach through the raw
        operand here to keep the artifact accessor parity-compatible.
        """
        props = self.get_properties()
        if props is None:
            return None
        value = props.get_dictionary_object(key)
        if isinstance(value, COSName):
            return value.get_name()
        if isinstance(value, COSString):
            return value.get_string()
        return None

    def _is_attached(self, edge: str) -> bool:
        props = self.get_properties()
        if props is None:
            return False
        a = props.get_dictionary_object(COSName.get_pdf_name("Attached"))
        if not isinstance(a, COSArray):
            return False
        for i in range(a.size()):
            if a.get_name(i) == edge:
                return True
        return False
