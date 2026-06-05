"""Ensure /AcroForm has the Adobe-default DA / DR / Helv / ZaDb entries.

Mirrors ``org.apache.pdfbox.pdmodel.fixup.processor.AcroFormDefaultsProcessor``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AcroFormDefaultsProcessor.java``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_processor import AbstractProcessor

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_ADOBE_DEFAULT_APPEARANCE = "/Helv 0 Tf 0 g "


class AcroFormDefaultsProcessor(AbstractProcessor):
    """Verify / create the AcroForm defaults Adobe expects.

    Mirrors the upstream constructor + ``process`` (Java lines 41-60) and
    the private ``verifyOrCreateDefaults`` (Java line 70).
    """

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)

    def process(self) -> None:
        """Mirrors ``process`` (Java line 47)."""
        catalog = self.document.get_document_catalog()
        get_acro_form = getattr(catalog, "get_acro_form", None)
        if get_acro_form is None:
            return
        try:
            acro_form = get_acro_form(None)
        except TypeError:
            acro_form = get_acro_form()
        if acro_form is None:
            return
        self._verify_or_create_defaults(acro_form)

    def verify_or_create_defaults(self, acro_form: object) -> None:
        """Mirrors upstream ``verifyOrCreateDefaults(PDAcroForm)``
        (Java line 70) — public delegate to the underscore-prefixed helper
        so the parity scanner sees the upstream name."""
        self._verify_or_create_defaults(acro_form)

    def _verify_or_create_defaults(self, acro_form: object) -> None:
        from pypdfbox.cos import COSDictionary, COSName
        from pypdfbox.pdmodel.pd_resources import PDResources

        # COSName predefined constants for the AcroForm-default fonts
        # are not always declared on the COSName class itself — fall
        # back to the interned ``get_pdf_name`` form.
        font_key = getattr(COSName, "FONT", None) or COSName.get_pdf_name("Font")
        helv_key = getattr(COSName, "HELV", None) or COSName.get_pdf_name("Helv")
        zadb_key = getattr(COSName, "ZA_DB", None) or COSName.get_pdf_name("ZaDb")

        # DA entry is required
        try:
            da = acro_form.get_default_appearance()  # type: ignore[attr-defined]
        except Exception:
            da = ""
        if not da:
            acro_form.set_default_appearance(_ADOBE_DEFAULT_APPEARANCE)  # type: ignore[attr-defined]
            cos_obj = acro_form.get_cos_object()  # type: ignore[attr-defined]
            need_update = getattr(cos_obj, "set_need_to_be_updated", None)
            if need_update is not None:
                need_update(True)

        # DR entry is required
        default_resources = acro_form.get_default_resources()  # type: ignore[attr-defined]
        if default_resources is None:
            default_resources = PDResources()
            acro_form.set_default_resources(default_resources)  # type: ignore[attr-defined]
            cos_obj = acro_form.get_cos_object()  # type: ignore[attr-defined]
            need_update = getattr(cos_obj, "set_need_to_be_updated", None)
            if need_update is not None:
                need_update(True)

        # /Helv + /ZaDb fonts (PDFBOX-3732 / PDFBOX-4393)
        # ``get_cos_object`` may be absent on a duck-typed resources object
        # (some callers swap ``get_default_resources`` for a minimal font
        # host); upstream assumes a real ``PDResources`` here, so when the
        # COS surface is unavailable there is no /DR dictionary to seed —
        # skip the font injection rather than raising.
        get_cos = getattr(default_resources, "get_cos_object", None)
        if get_cos is None:
            return
        dr_cos = get_cos()
        font_dict = dr_cos.get_cos_dictionary(font_key)
        if font_dict is None:
            font_dict = COSDictionary()
            dr_cos.set_item(font_key, font_dict)
        self._ensure_font(
            default_resources, font_dict, helv_key, font_name="Helvetica"
        )
        self._ensure_font(
            default_resources,
            font_dict,
            zadb_key,
            font_name="ZapfDingbats",
        )

    def _ensure_font(
        self,
        default_resources: object,
        font_dict: object,
        cos_name: object,
        *,
        font_name: str,
    ) -> None:
        contains = getattr(font_dict, "contains_key", None)
        if contains is not None and contains(cos_name):
            return
        try:
            from pypdfbox.cos import COSDictionary, COSName
            from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

            # Mirror upstream ``new PDType1Font(FontName.HELVETICA)`` /
            # ``new PDType1Font(FontName.ZAPF_DINGBATS)``: build the
            # standard-14 /Type1 font dictionary (Type/Subtype/BaseFont)
            # and wrap it. pypdfbox's ``PDType1Font`` constructor takes a
            # COS dictionary rather than a FontName enum.
            font_cos = COSDictionary()
            font_cos.set_item(COSName.TYPE, COSName.FONT)
            font_cos.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
            font_cos.set_item(COSName.BASE_FONT, COSName.get_pdf_name(font_name))
            font = PDType1Font(font_cos)
        except Exception:  # pragma: no cover - defensive parity stub
            return
        put = getattr(default_resources, "put", None)
        if put is not None:
            put(cos_name, font)
        need_update = getattr(default_resources.get_cos_object(), "set_need_to_be_updated", None)
        if need_update is not None:
            need_update(True)
        need_update = getattr(font_dict, "set_need_to_be_updated", None)
        if need_update is not None:
            need_update(True)


__all__ = ["AcroFormDefaultsProcessor"]
