"""Port of ``CreateVisibleSignature`` (upstream 1-480)."""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import IO

from pypdfbox.examples.signature.create_signature_base import CreateSignatureBase
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.interactive.digitalsignature.signature_options import (
    SignatureOptions,
)


class CreateVisibleSignature(CreateSignatureBase):
    """Detached PKCS#7 signer that draws a visible appearance widget."""

    def __init__(self, keystore_bytes: bytes, pin: str | bytes | None) -> None:
        super().__init__(keystore_bytes, pin)
        self._visible_sign_designer = None
        self._visible_signature_properties = None
        self._late_external_signing = False
        self._stream_cache_create_function: Callable | None = None

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 407)."""
        if len(args) < 4:
            CreateVisibleSignature.usage()
            raise SystemExit(
                "usage: create_visible_signature <pkcs12> <password> <pdf> <image>"
            )
        keystore = Path(args[0]).read_bytes()
        signer = CreateVisibleSignature(keystore, args[1])
        with Path(args[3]).open("rb") as img:
            signer.set_visible_sign_designer(args[3], 0, 0, 100, image_stream=img)
            signer.set_visible_signature_properties(
                "Example User", "Earth", "Testing", preferred_size=0
            )
            in_pdf = Path(args[2])
            signer.sign_pdf(in_pdf, in_pdf.with_name(in_pdf.stem + "_signed.pdf"))

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream)."""
        import sys

        sys.stderr.write(
            "usage: CreateVisibleSignature <pkcs12-keystore> <password> "
            "<pdf-to-sign> <image>\n",
        )

    # ----- properties --------------------------------------------------
    def is_late_external_signing(self) -> bool:
        return self._late_external_signing

    def set_late_external_signing(self, value: bool) -> None:
        self._late_external_signing = value

    def get_stream_cache_create_function(self) -> Callable | None:
        return self._stream_cache_create_function

    def set_stream_cache_create_function(self, stream_cache: Callable | None) -> None:
        self._stream_cache_create_function = stream_cache

    def set_visible_sign_designer(
        self,
        filename: str | None,
        x: int,
        y: int,
        zoom_percent: int,
        image_stream: IO[bytes] | None = None,
        page: int = 0,
    ) -> None:
        """Capture visible-signature placement; designer is wired lazily."""
        self._visible_sign_designer = {
            "filename": filename,
            "x": x,
            "y": y,
            "zoom": zoom_percent,
            "image_stream": image_stream,
            "page": page,
        }

    def set_visible_signature_properties(
        self,
        name: str,
        location: str,
        reason: str,
        preferred_size: int = 0,
        page: int = 0,
        visual_signature_enabled: bool = True,
    ) -> None:
        self._visible_signature_properties = {
            "name": name,
            "location": location,
            "reason": reason,
            "preferred_size": preferred_size,
            "page": page,
            "visual_signature_enabled": visual_signature_enabled,
        }

    # ----- main API ----------------------------------------------------
    def sign_pdf(
        self,
        input_file: Path | str,
        signed_file: Path | str,
        tsa_url: str | None = None,
        signature_field_name: str | None = None,
    ) -> None:
        in_path = Path(input_file)
        out_path = Path(signed_file)
        if not in_path.exists():
            raise FileNotFoundError("Document for signing does not exist")
        self.set_tsa_url(tsa_url)

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
        props = self._visible_signature_properties or {}
        signature.set_name(props.get("name", "Example User"))
        signature.set_location(props.get("location", ""))
        signature.set_reason(props.get("reason", "Testing"))
        signature.set_sign_date_as_datetime(_dt.datetime.now(_dt.UTC))

        options = SignatureOptions()
        preferred = props.get("preferred_size", 0) or SignatureOptions.DEFAULT_SIGNATURE_SIZE * 2
        options.set_preferred_signature_size(preferred)

        # Visible signature placeholder — designer wiring is delegated to
        # the consumer's chosen appearance generator.
        if self._visible_sign_designer and self._visible_sign_designer.get("image_stream"):
            options.set_visual_signature(
                BytesIO(self._visible_sign_designer["image_stream"].read())
            )

        document.add_signature(signature, self, options)
        document.save_incremental(output)

    def find_existing_signature(self, doc, sig_field_name: str):
        """Locate an existing signature field by name (upstream private 364)."""
        for field in doc.get_document_catalog().get_acro_form().get_fields():
            if getattr(field, "get_partial_name", lambda: None)() == sig_field_name:
                return field
        return None
