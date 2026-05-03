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

    #: All 14 standard stamp icon names from Table 183 — the values a
    #: conforming reader is required to recognise. Useful for validating
    #: ``/Name`` against the spec set.
    STANDARD_NAMES: frozenset[str] = frozenset(
        {
            NAME_APPROVED,
            NAME_AS_IS,
            NAME_CONFIDENTIAL,
            NAME_DEPARTMENTAL,
            NAME_DRAFT,
            NAME_EXPERIMENTAL,
            NAME_EXPIRED,
            NAME_FINAL,
            NAME_FOR_COMMENT,
            NAME_FOR_PUBLIC_RELEASE,
            NAME_NOT_APPROVED,
            NAME_NOT_FOR_PUBLIC_RELEASE,
            NAME_SOLD,
            NAME_TOP_SECRET,
        }
    )

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

    def is_standard_name(self) -> bool:
        """Return ``True`` if ``/Name`` is one of the 14 spec-defined icons.

        Conforming readers (PDF 32000-1:2008 §12.5.6.14) must recognise the
        icons in :data:`STANDARD_NAMES`; non-standard ``/Name`` values are
        permitted but their appearance is reader-defined. The default
        ``Draft`` (the spec default when ``/Name`` is absent) is treated as
        standard.
        """
        return self.get_name() in self.STANDARD_NAMES

    def has_name(self) -> bool:
        """Return ``True`` when ``/Name`` is explicitly present in the dict.

        Distinct from :meth:`get_name`, which substitutes the spec default
        ``Draft`` when the entry is absent. Useful for round-trip tools that
        want to preserve the producer's choice (or its absence) verbatim.
        """
        return self._dict.contains_key(_NAME)

    def is_default_name(self) -> bool:
        """Predicate matching the spec default icon (``Draft``).

        Returns ``True`` whether ``/Name`` is missing (defaulted) or
        explicitly set to :data:`NAME_DRAFT`, mirroring the behavior of
        :meth:`get_name`.
        """
        return self.get_name() == self.NAME_DRAFT

    # ---------- per-icon predicates ----------

    def is_approved(self) -> bool:
        return self.get_name() == self.NAME_APPROVED

    def is_confidential(self) -> bool:
        return self.get_name() == self.NAME_CONFIDENTIAL

    def is_draft(self) -> bool:
        """Alias of :meth:`is_default_name` — ``Draft`` is the spec default."""
        return self.get_name() == self.NAME_DRAFT

    def is_final(self) -> bool:
        return self.get_name() == self.NAME_FINAL

    def is_top_secret(self) -> bool:
        return self.get_name() == self.NAME_TOP_SECRET


__all__ = ["PDAnnotationStamp"]
