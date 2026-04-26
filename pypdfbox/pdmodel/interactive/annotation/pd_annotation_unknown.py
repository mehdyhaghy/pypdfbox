from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_annotation import PDAnnotation


class PDAnnotationUnknown(PDAnnotation):
    """
    Catch-all wrapper for any ``/Subtype`` the factory doesn't recognise.
    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationUnknown``.

    Exposes the raw COS dictionary and the base accessors only — no
    subtype-specific behaviour. The cluster #5 lite truncated dispatch
    table funnels Widget, FreeText, FileAttachment, Highlight,
    Underline, … into this class so a parser round-trip never loses
    annotation data.
    """

    def __init__(self, annotation_dict: COSDictionary) -> None:
        # Upstream takes a required COSDictionary — there's no useful
        # default subtype to assign.
        super().__init__(annotation_dict)


__all__ = ["PDAnnotationUnknown"]
