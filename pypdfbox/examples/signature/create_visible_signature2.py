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

        from pypdfbox.loader import Loader

        with (
            in_path.open("rb") as fh,
            Loader.load_pdf(fh) as doc,  # type: ignore[arg-type]
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
        from pypdfbox.pdmodel.common.pd_rectangle import PDRectangle

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

        Generates a minimal in-memory PDF carrying the appearance dictionary.
        """
        raise NotImplementedError(
            "create_visual_signature_template awaits PDAppearanceStream porting.",
        )

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
