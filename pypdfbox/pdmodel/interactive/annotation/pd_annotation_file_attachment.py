from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation_markup import PDAnnotationMarkup

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
        PDFileSpecification,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler

_FS: COSName = COSName.get_pdf_name("FS")
_NAME: COSName = COSName.get_pdf_name("Name")


class PDAnnotationFileAttachment(PDAnnotationMarkup):
    """
    File attachment annotation — ``/Subtype /FileAttachment``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment``.

    A file attachment annotation embeds (or references) an external file
    via ``/FS`` and renders an icon selected by ``/Name``
    (PDF 32000-1:2008 §12.5.6.15). Extends :class:`PDAnnotationMarkup` so
    review-workflow fields (``/CreationDate``, ``/Subj``, ``/IRT``, ``/IT``,
    ``/CA``, ``/RT``) come for free.
    """

    SUB_TYPE: str = "FileAttachment"

    # Icon name constants (PDF 32000-1:2008 §12.5.6.15 Table 184).
    ATTACHMENT_NAME_GRAPH: str = "Graph"
    ATTACHMENT_NAME_PAPERCLIP: str = "Paperclip"
    ATTACHMENT_NAME_PUSH_PIN: str = "PushPin"  # spec default
    ATTACHMENT_NAME_TAG: str = "Tag"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        self._custom_appearance_handler: PDAppearanceHandler | None = None
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``. Pass ``None`` to
        clear the custom handler and restore the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def get_custom_appearance_handler(self) -> PDAppearanceHandler | None:
        """Return the custom appearance handler previously set via
        :meth:`set_custom_appearance_handler`, or ``None`` when the default
        construction path is in use. No upstream getter exists (the field is
        package-private in Java); this is the Pythonic accessor used by tests
        and downstream code that needs to inspect the wired handler.
        """
        return self._custom_appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate file-attachment annotation appearances.

        A custom handler, when configured, is invoked exactly as upstream does.
        The built-in ``PDFileAttachmentAppearanceHandler`` is not ported yet,
        so the default path remains a no-op like the base annotation
        implementation.
        """
        if self._custom_appearance_handler is not None:
            self._custom_appearance_handler.generate_appearance_streams()
            return None
        return super().construct_appearances(document)

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

    def has_file(self) -> bool:
        """``True`` when ``/FS`` is present (regardless of contents).

        Predicate companion to :meth:`get_file`; useful for callers that
        want to distinguish "no file attached" from "attached but spec is
        malformed" without paying the cost of constructing a typed
        :class:`PDFileSpecification`.
        """
        return self._dict.get_dictionary_object(_FS) is not None

    def clear_file(self) -> None:
        """Remove ``/FS`` entirely.

        Equivalent to ``set_file(None)`` but reads more clearly at call
        sites that explicitly intend to clear the attached file.
        """
        self._dict.remove_item(_FS)

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

    def has_attachment_name(self) -> bool:
        """``True`` when ``/Name`` is explicitly set (vs. relying on the
        ``"PushPin"`` spec default).
        """
        return self._dict.get_name(_NAME) is not None

    def clear_attachment_name(self) -> None:
        """Remove the explicit ``/Name`` entry, reverting to the spec
        default (``"PushPin"``).

        Equivalent to ``set_attachment_name(None)`` but makes intent
        explicit at the call site.
        """
        self._dict.remove_item(_NAME)

    def is_default_attachment_name(self) -> bool:
        """``True`` when the icon resolves to the spec default ``"PushPin"``,
        whether because ``/Name`` is absent or explicitly set to it.

        Distinct from :meth:`has_attachment_name` (which reflects raw entry
        presence) and from :meth:`is_push_pin` (which it shares its return
        value with — kept separate to make spec-default intent clear at
        call sites).
        """
        return self.get_attachment_name() == self.ATTACHMENT_NAME_PUSH_PIN

    def is_known_attachment_name(self) -> bool:
        """``True`` when the resolved icon name is one of the four spec
        constants (``Graph``, ``Paperclip``, ``PushPin``, ``Tag`` —
        Table 184). ``False`` when ``/Name`` carries a vendor extension.
        """
        return self.get_attachment_name() in {
            self.ATTACHMENT_NAME_GRAPH,
            self.ATTACHMENT_NAME_PAPERCLIP,
            self.ATTACHMENT_NAME_PUSH_PIN,
            self.ATTACHMENT_NAME_TAG,
        }

    # ---------- icon predicates ----------

    def is_push_pin(self) -> bool:
        """Predicate matching the spec default icon (``PushPin``)."""
        return self.get_attachment_name() == self.ATTACHMENT_NAME_PUSH_PIN

    def is_paperclip(self) -> bool:
        return self.get_attachment_name() == self.ATTACHMENT_NAME_PAPERCLIP

    def is_graph(self) -> bool:
        return self.get_attachment_name() == self.ATTACHMENT_NAME_GRAPH

    def is_tag(self) -> bool:
        return self.get_attachment_name() == self.ATTACHMENT_NAME_TAG


__all__ = ["PDAnnotationFileAttachment"]
