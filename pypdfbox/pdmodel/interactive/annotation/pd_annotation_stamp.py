from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_NAME: COSName = COSName.get_pdf_name("Name")


class PDAnnotationStamp(PDAnnotationMarkup):
    """
    Rubber-stamp annotation — ``/Subtype /Stamp``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationRubberStamp``
    in upstream Apache PDFBox 3.0.x.

    Displays text or graphics intended to look as if they had been stamped
    on the page with a rubber stamp (PDF 32000-1:2008 §12.5.6.14). The icon
    is selected by ``/Name`` from the standard set below.

    This class is the modern, ``PDAnnotationMarkup``-rooted equivalent of
    :class:`PDAnnotationRubberStamp` and is the surface that
    :meth:`PDAnnotation.create` returns for ``/Subtype /Stamp`` once the
    factory wiring switches over (legacy ``PDAnnotationRubberStamp`` is
    retained for callers that import it directly).
    """

    SUB_TYPE: str = "Stamp"

    # Standard stamp name constants (PDF 32000-1:2008 §12.5.6.14 Table 183).
    NAME_APPROVED: str = "Approved"
    NAME_AS_IS: str = "AsIs"
    NAME_CONFIDENTIAL: str = "Confidential"
    NAME_DEPARTMENTAL: str = "Departmental"
    NAME_DRAFT: str = "Draft"  # spec default
    NAME_EXPERIMENTAL: str = "Experimental"
    NAME_EXPIRED: str = "Expired"
    NAME_FINAL: str = "Final"
    NAME_FOR_COMMENT: str = "ForComment"
    NAME_FOR_PUBLIC_RELEASE: str = "ForPublicRelease"
    NAME_NOT_APPROVED: str = "NotApproved"
    NAME_NOT_FOR_PUBLIC_RELEASE: str = "NotForPublicRelease"
    NAME_SOLD: str = "Sold"
    NAME_TOP_SECRET: str = "TopSecret"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /Name (icon) ----------

    def get_name(self) -> str:
        """Default per spec is ``Draft``."""
        value = self._dict.get_name(_NAME)
        return value if value is not None else self.NAME_DRAFT

    def set_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)

    def getName(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_name()

    def setName(self, name: str | None) -> None:  # noqa: N802 - upstream Java name
        self.set_name(name)


__all__ = ["PDAnnotationStamp"]
