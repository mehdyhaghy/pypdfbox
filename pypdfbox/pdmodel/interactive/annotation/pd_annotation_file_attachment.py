from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
        PDFileSpecification,
    )

_FS: COSName = COSName.get_pdf_name("FS")
_NAME: COSName = COSName.get_pdf_name("Name")


class PDAnnotationFileAttachment(PDAnnotation):
    """
    File attachment annotation — ``/Subtype /FileAttachment``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment``.

    A file attachment annotation embeds (or references) an external file
    via ``/FS`` and renders an icon selected by ``/Name``
    (PDF 32000-1:2008 §12.5.6.15).
    """

    SUB_TYPE: str = "FileAttachment"

    # Icon name constants (PDF 32000-1:2008 §12.5.6.15 Table 184).
    ATTACHMENT_NAME_GRAPH: str = "Graph"
    ATTACHMENT_NAME_PAPERCLIP: str = "Paperclip"
    ATTACHMENT_NAME_PUSH_PIN: str = "PushPin"  # spec default
    ATTACHMENT_NAME_TAG: str = "Tag"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /FS (file specification) ----------

    def get_file(self) -> PDFileSpecification | None:
        from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
            PDFileSpecification,
        )

        value = self._dict.get_dictionary_object(_FS)
        return PDFileSpecification.create_fs(value)

    def set_file(self, fs: PDFileSpecification | None) -> None:
        if fs is None:
            self._dict.remove_item(_FS)
            return
        self._dict.set_item(_FS, fs.get_cos_object())

    # ---------- /Name (icon) ----------

    def get_attachment_name(self) -> str:
        """Default per spec is ``PushPin``."""
        value = self._dict.get_name(_NAME)
        return value if value is not None else self.ATTACHMENT_NAME_PUSH_PIN

    def set_attachment_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)


__all__ = ["PDAnnotationFileAttachment"]
