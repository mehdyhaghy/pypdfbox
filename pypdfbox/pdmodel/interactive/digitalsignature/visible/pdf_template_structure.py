"""State bag carrying the assembled visible-signature pieces.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDFTemplateStructure``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PDFTemplateStructure.java``).
Pure data holder — getters and setters for the 27 intermediate objects
produced by the builder pipeline.
"""

from __future__ import annotations

from typing import Any


class PDFTemplateStructure:
    """Mutable state shared across the visible-signature build pipeline.

    Each attribute corresponds to one of the upstream private fields.
    Per CLAUDE.md, getter/setter pairs use snake_case (``get_page`` /
    ``set_page``); the underlying attribute is stored on a ``_``-prefixed
    private name so accidental attribute access doesn't bypass the
    accessor surface.
    """

    def __init__(self) -> None:
        # Mirrors the private-field declarations starting at Java line 45.
        self._page: Any = None
        self._template: Any = None
        self._acro_form: Any = None
        self._signature_field: Any = None
        self._pd_signature: Any = None
        self._acro_form_dictionary: Any = None
        self._signature_rectangle: Any = None
        self._affine_transform: Any = None
        self._proc_set: Any = None
        self._image: Any = None
        self._formatter_rectangle: Any = None
        self._holder_form_stream: Any = None
        self._holder_form_resources: Any = None
        self._holder_form: Any = None
        self._appearance_dictionary: Any = None
        self._inner_form_stream: Any = None
        self._inner_form_resources: Any = None
        self._inner_form: Any = None
        self._image_form_stream: Any = None
        self._image_form_resources: Any = None
        self._acro_form_fields: Any = None
        self._inner_form_name: Any = None
        self._image_form_name: Any = None
        self._image_name: Any = None
        self._visual_signature: Any = None
        self._image_form: Any = None
        self._widget_dictionary: Any = None

    # --- page ---------------------------------------------------------------

    def get_page(self) -> Any:
        return self._page

    def set_page(self, page: Any) -> None:
        self._page = page

    # --- template -----------------------------------------------------------

    def get_template(self) -> Any:
        return self._template

    def set_template(self, template: Any) -> None:
        self._template = template

    # --- AcroForm -----------------------------------------------------------

    def get_acro_form(self) -> Any:
        return self._acro_form

    def set_acro_form(self, acro_form: Any) -> None:
        self._acro_form = acro_form

    # --- signature field ----------------------------------------------------

    def get_signature_field(self) -> Any:
        return self._signature_field

    def set_signature_field(self, signature_field: Any) -> None:
        self._signature_field = signature_field

    # --- PDSignature --------------------------------------------------------

    def get_pd_signature(self) -> Any:
        return self._pd_signature

    def set_pd_signature(self, pd_signature: Any) -> None:
        self._pd_signature = pd_signature

    # --- AcroForm dictionary -----------------------------------------------

    def get_acro_form_dictionary(self) -> Any:
        return self._acro_form_dictionary

    def set_acro_form_dictionary(self, acro_form_dictionary: Any) -> None:
        self._acro_form_dictionary = acro_form_dictionary

    # --- signature rectangle ----------------------------------------------

    def get_signature_rectangle(self) -> Any:
        return self._signature_rectangle

    def set_signature_rectangle(self, signature_rectangle: Any) -> None:
        self._signature_rectangle = signature_rectangle

    # --- affine transform --------------------------------------------------

    def get_affine_transform(self) -> Any:
        return self._affine_transform

    def set_affine_transform(self, affine_transform: Any) -> None:
        self._affine_transform = affine_transform

    # --- proc set ----------------------------------------------------------

    def get_proc_set(self) -> Any:
        return self._proc_set

    def set_proc_set(self, proc_set: Any) -> None:
        self._proc_set = proc_set

    # --- image -------------------------------------------------------------

    def get_image(self) -> Any:
        return self._image

    def set_image(self, image: Any) -> None:
        self._image = image

    # --- formatter rectangle ----------------------------------------------

    def get_formatter_rectangle(self) -> Any:
        return self._formatter_rectangle

    def set_formatter_rectangle(self, formatter_rectangle: Any) -> None:
        self._formatter_rectangle = formatter_rectangle

    # --- holder form -------------------------------------------------------

    def get_holder_form_stream(self) -> Any:
        return self._holder_form_stream

    def set_holder_form_stream(self, holder_form_stream: Any) -> None:
        self._holder_form_stream = holder_form_stream

    def get_holder_form(self) -> Any:
        return self._holder_form

    def set_holder_form(self, holder_form: Any) -> None:
        self._holder_form = holder_form

    def get_holder_form_resources(self) -> Any:
        return self._holder_form_resources

    def set_holder_form_resources(self, holder_form_resources: Any) -> None:
        self._holder_form_resources = holder_form_resources

    # --- appearance dictionary --------------------------------------------

    def get_appearance_dictionary(self) -> Any:
        return self._appearance_dictionary

    def set_appearance_dictionary(self, appearance_dictionary: Any) -> None:
        self._appearance_dictionary = appearance_dictionary

    # --- inner form --------------------------------------------------------

    def get_inner_form_stream(self) -> Any:
        return self._inner_form_stream

    def set_innter_form_stream(self, inner_form_stream: Any) -> None:
        # Preserve the upstream typo ``setInnterFormStream`` (Java line 380)
        # so call-sites that depend on the parity surface still resolve.
        self._inner_form_stream = inner_form_stream

    def set_inner_form_stream(self, inner_form_stream: Any) -> None:
        """Pythonic alias for the upstream-typo'd setter — keeps idiomatic
        code paths from having to mirror the misspelling."""
        self._inner_form_stream = inner_form_stream

    def get_inner_form_resources(self) -> Any:
        return self._inner_form_resources

    def set_inner_form_resources(self, inner_form_resources: Any) -> None:
        self._inner_form_resources = inner_form_resources

    def get_inner_form(self) -> Any:
        return self._inner_form

    def set_inner_form(self, inner_form: Any) -> None:
        self._inner_form = inner_form

    def get_inner_form_name(self) -> Any:
        return self._inner_form_name

    def set_inner_form_name(self, inner_form_name: Any) -> None:
        self._inner_form_name = inner_form_name

    # --- image form --------------------------------------------------------

    def get_image_form_stream(self) -> Any:
        return self._image_form_stream

    def set_image_form_stream(self, image_form_stream: Any) -> None:
        self._image_form_stream = image_form_stream

    def get_image_form_resources(self) -> Any:
        return self._image_form_resources

    def set_image_form_resources(self, image_form_resources: Any) -> None:
        self._image_form_resources = image_form_resources

    def get_image_form(self) -> Any:
        return self._image_form

    def set_image_form(self, image_form: Any) -> None:
        self._image_form = image_form

    def get_image_form_name(self) -> Any:
        return self._image_form_name

    def set_image_form_name(self, image_form_name: Any) -> None:
        self._image_form_name = image_form_name

    def get_image_name(self) -> Any:
        return self._image_name

    def set_image_name(self, image_name: Any) -> None:
        self._image_name = image_name

    # --- visual signature & widget ----------------------------------------

    def get_visual_signature(self) -> Any:
        return self._visual_signature

    def set_visual_signature(self, visual_signature: Any) -> None:
        self._visual_signature = visual_signature

    def get_acro_form_fields(self) -> Any:
        return self._acro_form_fields

    def set_acro_form_fields(self, acro_form_fields: Any) -> None:
        self._acro_form_fields = acro_form_fields

    def get_widget_dictionary(self) -> Any:
        return self._widget_dictionary

    def set_widget_dictionary(self, widget_dictionary: Any) -> None:
        self._widget_dictionary = widget_dictionary


__all__ = ["PDFTemplateStructure"]
