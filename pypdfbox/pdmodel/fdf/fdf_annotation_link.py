from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_A: COSName = COSName.get_pdf_name("A")


class FDFAnnotationLink(FDFAnnotation):
    """FDF Link annotation — ``/Subtype /Link``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationLink``. When built
    from an XFDF element the upstream constructor reads the
    ``OnActivation/Action/URI`` node and stores the ``Name`` attribute as a
    ``/A`` URI action; :meth:`init_action_uri` exposes that step (the XFDF DOM
    walk itself lives in the FDF/XFDF parser).
    """

    SUBTYPE: str = "Link"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    def init_action_uri(self, uri: str | None) -> None:
        """Store ``uri`` as a ``/A`` URI action.

        Mirrors the XFDF ``OnActivation/Action/URI`` handling in upstream's
        ``FDFAnnotationLink(Element)`` constructor (Java lines 75-99): the
        ``Name`` attribute of the ``URI`` node becomes a :class:`PDActionURI`
        stored under ``/A``. A ``None`` value is a no-op so callers can forward
        the extracted attribute directly (matches upstream's null guard).
        """
        if uri is None:
            return
        action_uri = PDActionURI()
        action_uri.set_uri(uri)
        self._annot.set_item(_A, action_uri.get_cos_object())


__all__ = ["FDFAnnotationLink"]
