"""Rebuild /AcroForm fields from orphan widget annotations.

Mirrors ``org.apache.pdfbox.pdmodel.fixup.processor.AcroFormOrphanWidgetsProcessor``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AcroFormOrphanWidgetsProcessor.java``).

When a PDF arrives with no entries in /AcroForm/Fields but with widget
annotations sprinkled across pages, Adobe Reader rebuilds the field
list from the widget annotations. This processor mirrors that
behaviour.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .abstract_processor import AbstractProcessor

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

_log = logging.getLogger(__name__)


class AcroFormOrphanWidgetsProcessor(AbstractProcessor):
    """Generate field entries from page-level widget annotations.

    Mirrors the upstream constructor + ``process`` (Java lines 55-76) and
    the private helper chain (``resolveFieldsFromWidgets``,
    ``handleAnnotations``, ``addFontFromWidget``, ``resolveNonRootField``,
    ``ensureFontResources``).
    """

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)

    def process(self) -> None:
        """Mirrors ``process`` (Java line 61)."""
        catalog = self.document.get_document_catalog()
        get_acro_form = getattr(catalog, "get_acro_form", None)
        if get_acro_form is None:
            return
        try:
            acro_form = get_acro_form(None)
        except TypeError:
            acro_form = get_acro_form()
        if acro_form is not None:
            self.resolve_fields_from_widgets(acro_form)

    def resolve_fields_from_widgets(self, acro_form: object) -> None:
        """Rebuild ``/AcroForm/Fields`` from per-page widgets. Mirrors
        upstream's private ``resolveFieldsFromWidgets`` (Java line 85)."""
        _log.debug("rebuilding fields from widgets")
        resources = acro_form.get_default_resources()  # type: ignore[attr-defined]
        if resources is None:
            _log.debug("AcroForm default resources is null")
            return

        fields: list[Any] = []
        non_terminal_fields_map: dict[str, Any] = {}
        for page in self.document.get_pages():
            try:
                annotations = page.get_annotations()
            except OSError as ioe:
                _log.debug("couldn't read annotations for page %s", ioe)
                continue
            self.handle_annotations(
                acro_form, resources, fields, annotations, non_terminal_fields_map
            )

        set_fields = getattr(acro_form, "set_fields", None)
        if set_fields is not None:
            set_fields(fields)

        get_field_tree = getattr(acro_form, "get_field_tree", None)
        if get_field_tree is not None:
            for field in get_field_tree():
                if hasattr(field, "get_default_appearance"):
                    self.ensure_font_resources(resources, field)

    # Back-compat alias kept for callers using the previous leading-underscore name.
    _resolve_fields_from_widgets = resolve_fields_from_widgets

    def handle_annotations(
        self,
        acro_form: object,
        acro_form_resources: object,
        fields: list[Any],
        annotations: list[Any],
        non_terminal_fields_map: dict[str, Any],
    ) -> None:
        """Walk a single page's annotations and rebuild field entries.
        Mirrors upstream's private ``handleAnnotations`` (Java line 120)."""
        try:
            from pypdfbox.cos import COSName
            from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
                PDAnnotationWidget,
            )
            from pypdfbox.pdmodel.interactive.form.pd_field_factory import (
                PDFieldFactory,
            )
        except ImportError:
            return

        for annot in annotations:
            if not isinstance(annot, PDAnnotationWidget):
                continue
            self.add_font_from_widget(acro_form_resources, annot)
            parent = annot.get_cos_object().get_cos_dictionary(COSName.PARENT)
            if parent is not None:
                resolved = self.resolve_non_root_field(
                    acro_form, parent, non_terminal_fields_map
                )
                if resolved is not None:
                    fields.append(resolved)
            else:
                field = PDFieldFactory.create_field(
                    acro_form, annot.get_cos_object(), None
                )
                if field is not None:
                    fields.append(field)

    # Back-compat alias kept for callers using the previous leading-underscore name.
    _handle_annotations = handle_annotations

    def add_font_from_widget(
        self, acro_form_resources: object, annotation: object
    ) -> None:
        """Copy any non-subset font used by a widget into the AcroForm's
        default-resources dictionary. Mirrors upstream's private
        ``addFontFromWidget`` (Java line 167)."""
        normal = annotation.get_normal_appearance_stream()  # type: ignore[attr-defined]
        if normal is None:
            return
        widget_resources = normal.get_resources()
        if widget_resources is None:
            return
        for font_name in list(widget_resources.get_font_names()):
            if font_name.get_name().startswith("+"):
                _log.debug(
                    "font resource for widget was a subsetted font - ignored: %s",
                    font_name.get_name(),
                )
                continue
            try:
                if acro_form_resources.get_font(font_name) is None:  # type: ignore[attr-defined]
                    acro_form_resources.put(  # type: ignore[attr-defined]
                        font_name, widget_resources.get_font(font_name)
                    )
            except OSError:
                _log.debug(
                    "unable to add font to AcroForm for font name %s",
                    font_name.get_name(),
                )

    # Back-compat alias kept for callers using the previous leading-underscore name.
    _add_font_from_widget = add_font_from_widget

    def resolve_non_root_field(
        self,
        acro_form: object,
        parent: object,
        non_terminal_fields_map: dict[str, Any],
    ) -> Any | None:
        """Walk up to the nearest field root and instantiate it as the
        non-terminal parent. Mirrors upstream's private
        ``resolveNonRootField`` (Java line 195)."""
        try:
            from pypdfbox.cos import COSName
            from pypdfbox.pdmodel.interactive.form.pd_field_factory import (
                PDFieldFactory,
            )
        except ImportError:
            return None
        while parent.contains_key(COSName.PARENT):  # type: ignore[attr-defined]
            parent = parent.get_cos_dictionary(COSName.PARENT)  # type: ignore[attr-defined]
            if parent is None:
                return None
        key = parent.get_string(COSName.T)  # type: ignore[attr-defined]
        if non_terminal_fields_map.get(key) is None:
            field = PDFieldFactory.create_field(acro_form, parent, None)
            if field is not None:
                non_terminal_fields_map[field.get_fully_qualified_name()] = field
            return field
        return None

    # Back-compat alias kept for callers using the previous leading-underscore name.
    _resolve_non_root_field = resolve_non_root_field

    def ensure_font_resources(
        self, default_resources: object, field: object
    ) -> None:
        """If a field's ``/DA`` references a font name absent from the
        AcroForm default resources, attempt to import it. Mirrors
        upstream's private ``ensureFontResources`` (Java line 219)."""
        da_string = field.get_default_appearance()  # type: ignore[attr-defined]
        if not (da_string.startswith("/") and len(da_string) > 1):
            return
        try:
            from pypdfbox.cos import COSName

            font_name = COSName.get_pdf_name(
                da_string[1 : da_string.index(" ")]
            )
            if default_resources.get_font(font_name) is None:  # type: ignore[attr-defined]
                # Font mapping infrastructure isn't in scope for this
                # wave; log a parity-faithful hint and bail out.
                _log.debug(
                    "trying to add missing font resource for field %s",
                    field.get_fully_qualified_name(),  # type: ignore[attr-defined]
                )
        except (OSError, ValueError) as exc:
            _log.debug("unable to handle font resources: %s", exc)

    # Back-compat alias kept for callers using the previous leading-underscore name.
    _ensure_font_resources = ensure_font_resources


__all__ = ["AcroFormOrphanWidgetsProcessor"]
