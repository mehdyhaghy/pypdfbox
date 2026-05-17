"""Port of ``CreateSignature`` (upstream 1-227)."""

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


class CreateSignature(CreateSignatureBase):
    """Detached PKCS#7 signature creator for PDFs."""

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 170)."""
        if len(args) < 3:
            CreateSignature.usage()
            raise SystemExit(
                "usage: create_signature <pkcs12> <password> <pdf_to_sign> "
                "[-tsa <url>] [-e]"
            )
        from pathlib import Path as _Path

        tsa_url: str | None = None
        external = False
        idx = 3
        while idx < len(args):
            if args[idx] == "-tsa":
                tsa_url = args[idx + 1]
                idx += 2
                continue
            if args[idx] == "-e":
                external = True
            idx += 1
        keystore = _Path(args[0]).read_bytes()
        signer = CreateSignature(keystore, args[1])
        signer.set_external_signing(external)
        in_file = _Path(args[2])
        out_file = in_file.with_name(in_file.stem + "_signed.pdf")
        signer.sign_detached(in_file, out_file, tsa_url)

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream)."""
        import sys

        sys.stderr.write(
            "usage: CreateSignature <pkcs12-keystore> <password> "
            "<pdf-to-sign> [-tsa <url>] [-e]\n",
        )

    def sign_detached(
        self,
        in_file: Path | str,
        out_file: Path | str | None = None,
        tsa_url: str | None = None,
    ) -> None:
        """Sign ``in_file``; if ``out_file`` is None, sign in place (upstream 76)."""
        in_path = Path(in_file)
        if not in_path.exists():
            raise FileNotFoundError("Document for signing does not exist")
        out_path = in_path if out_file is None else Path(out_file)
        self.set_tsa_url(tsa_url)

        from pypdfbox.pdmodel.pd_document import PDDocument

        with (
            in_path.open("rb") as fh,
            PDDocument.load(fh) as doc,
            out_path.open("wb") as out,
        ):
            self.sign_detached_document(doc, out)

    def sign_detached_document(self, document, output: IO[bytes]) -> None:
        """Apply a detached PKCS#7 signature to ``document`` (upstream 116)."""
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

        if access_permissions == 0:
            SigUtils.set_mdp_permission(document, signature, 2)

        if self.is_external_signing():
            document.add_signature(signature)
            external = document.save_incremental_for_external_signing(output)
            cms_signature = self.sign(external.get_content())
            external.set_signature(cms_signature)
        else:
            options = SignatureOptions()
            options.set_preferred_signature_size(SignatureOptions.DEFAULT_SIGNATURE_SIZE * 2)
            document.add_signature(signature, self, options)
            document.save_incremental(output)
