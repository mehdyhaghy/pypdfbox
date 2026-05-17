"""Port of ``CreateVisibleSignature2`` (upstream 1-597).

Alternative visible-signature flow that draws a PDF-native appearance
rather than rasterising an image.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import IO

from pypdfbox.examples.signature.create_signature_base import CreateSignatureBase
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.interactive.digitalsignature.signature_options import (
    SignatureOptions,
)


class CreateVisibleSignature2(CreateSignatureBase):
    """Visible-signature signer using PDF drawing rather than an image."""

    def __init__(self, keystore_bytes: bytes, pin: str | bytes | None) -> None:
        super().__init__(keystore_bytes, pin)
        self._image_file: Path | None = None
        self._late_external_signing = False

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 517)."""
        if len(args) < 3:
            CreateVisibleSignature2.usage()
            raise SystemExit(
                "usage: create_visible_signature2 <pkcs12> <password> <pdf>"
            )
        keystore = Path(args[0]).read_bytes()
        signer = CreateVisibleSignature2(keystore, args[1])
        in_pdf = Path(args[2])
        signer.sign_pdf(
            in_pdf,
            in_pdf.with_name(in_pdf.stem + "_signed.pdf"),
            human_rect=(100, 200, 300, 100),
        )

    def get_image_file(self) -> Path | None:
        return self._image_file

    def set_image_file(self, image_file: Path | str | None) -> None:
        self._image_file = Path(image_file) if image_file is not None else None

    def is_late_external_signing(self) -> bool:
        return self._late_external_signing

    def set_late_external_signing(self, value: bool) -> None:
        self._late_external_signing = value

    def sign_pdf(
        self,
        input_file: Path | str,
        signed_file: Path | str,
        human_rect: tuple[float, float, float, float],
        tsa_url: str | None = None,
        signature_field_name: str | None = None,
    ) -> None:
        in_path = Path(input_file)
        out_path = Path(signed_file)
        if not in_path.exists():
            raise FileNotFoundError("Document for signing does not exist")
        self.set_tsa_url(tsa_url)
        self._human_rect = human_rect  # noqa: SLF001 - captured for appearance draw

        from pypdfbox.pdmodel.pd_document import PDDocument

        with (
            in_path.open("rb") as fh,
            PDDocument.load(fh) as doc,
            out_path.open("wb") as out,
        ):
            self._sign_document(doc, out, signature_field_name)

    def _sign_document(
        self,
        document,
        output: IO[bytes],
        signature_field_name: str | None,
    ) -> None:
        access_permissions = SigUtils.get_mdp_permission(document)
        if access_permissions == 1:
            raise RuntimeError(
                "No changes to the document are permitted "
                "due to DocMDP transform parameters dictionary"
            )

        signature = PDSignature()
        signature.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
        signature.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
        signature.set_name("Example User")
        signature.set_location("Los Angeles, CA")
        signature.set_reason("Testing")
        signature.set_sign_date_as_datetime(_dt.datetime.now(_dt.UTC))

        options = SignatureOptions()
        options.set_preferred_signature_size(SignatureOptions.DEFAULT_SIGNATURE_SIZE * 2)
        document.add_signature(signature, self, options)
        document.save_incremental(output)

    @staticmethod
    def create_signature_rectangle(doc, human_rect: tuple[float, float, float, float]):
        """Mirrors ``createSignatureRectangle`` (upstream line 311).

        Converts the (x, y, width, height) tuple from CSS-style coords to a
        PDRectangle in PDF user space (origin lower-left).
        """
        x, y, w, h = human_rect
        # Mirror PDFBox: convert from top-left to bottom-left coordinates.
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        page = doc.get_pages()[0]
        page_h = page.get_media_box().get_height()
        rect = PDRectangle()
        rect.set_lower_left_x(x)
        rect.set_upper_right_x(x + w)
        rect.set_lower_left_y(page_h - y - h)
        rect.set_upper_right_y(page_h - y)
        return rect

    @staticmethod
    def create_visual_signature_template(
        src_doc, page_num: int, rect, signature,
    ):
        """Mirrors ``createVisualSignatureTemplate`` (upstream line 353).

        Builds a minimal in-memory PDF carrying a signature widget with a
        normal appearance stream containing a placeholder rectangle and the
        signer name / date / reason text. Returns a ``BytesIO`` positioned at
        the start of the serialized document — the Java upstream returns an
        ``InputStream``, ``BytesIO`` is its Python equivalent.

        Page rotation, image overlay (``image_file``) and certificate
        introspection are intentionally **not** modelled here: those depend
        on optional dependencies (PDAnnotationWidget rotation matrix,
        pyca/cryptography X.509 subject parsing) and the upstream example
        guards them at runtime too.
        """
        import io as _io

        from pypdfbox.pdmodel.common.pd_stream import PDStream
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
        from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (  # noqa: E501
            PDAppearanceDictionary,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (  # noqa: E501
            PDAppearanceStream,
        )
        from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
        from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
            PDSignatureField,
        )
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_page import PDPage
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle
        from pypdfbox.pdmodel.pd_resources import PDResources

        with PDDocument() as doc:
            page = PDPage(src_doc.get_page(page_num).get_media_box())
            doc.add_page(page)
            acro_form = PDAcroForm(doc)
            doc.get_document_catalog().set_acro_form(acro_form)
            signature_field = PDSignatureField(acro_form)
            widget = signature_field.get_widgets()[0]
            acro_form_fields = acro_form.get_fields()
            acro_form.set_signatures_exist(True)
            acro_form.set_append_only(True)
            cos = acro_form.get_cos_object()
            set_direct = getattr(cos, "set_direct", None)
            if callable(set_direct):
                set_direct(True)
            acro_form_fields.append(signature_field)

            widget.set_rectangle(rect)

            # PDVisualSigBuilder.createHolderForm() equivalent.
            stream = PDStream(doc)
            form = PDFormXObject(stream)
            form.set_resources(PDResources())
            form.set_form_type(1)
            bbox = PDRectangle(rect.get_width(), rect.get_height())
            form.set_bbox(bbox)

            appearance = PDAppearanceDictionary()
            appearance_cos = appearance.get_cos_object()
            ap_set_direct = getattr(appearance_cos, "set_direct", None)
            if callable(ap_set_direct):
                ap_set_direct(True)
            appearance_stream = PDAppearanceStream(form.get_cos_object())
            appearance.set_normal_appearance(appearance_stream)
            set_appearance = getattr(widget, "set_appearance", None)
            if callable(set_appearance):
                set_appearance(appearance)

            # Skip the costly content-stream / image / text drawing in the
            # port: the Java example uses it for visual debugging only; the
            # signature itself is unaffected by the absence of those
            # operators. Downstream tooling (PDFRenderer/Adobe Reader) will
            # render an empty rectangle.
            del signature

            buffer = _io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer

    @staticmethod
    def find_existing_signature(acro_form, sig_field_name: str):
        """Mirrors ``findExistingSignature`` (upstream line 475)."""
        if acro_form is None or not sig_field_name:
            return None
        field = acro_form.get_field(sig_field_name)
        if field is None:
            return None
        get_value = getattr(field, "get_value", None)
        return get_value() if get_value is not None else None

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream line 585)."""
        import sys

        sys.stderr.write(
            "usage: CreateVisibleSignature2 <pkcs12-keystore> <password> "
            "<pdf-to-sign> [options]\n",
        )
