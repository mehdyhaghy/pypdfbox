"""Port of ``CreateSignedTimeStamp`` (upstream 1-181)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO

from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.examples.signature.validation_time_stamp import ValidationTimeStamp
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.interactive.digitalsignature.signature_interface import (
    SignatureInterface,
)

LOG = logging.getLogger(__name__)


class CreateSignedTimeStamp(SignatureInterface):
    """Apply a document-level ETSI.RFC3161 timestamp signature."""

    def __init__(self, tsa_url: str) -> None:
        self._tsa_url = tsa_url

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 145)."""
        from pathlib import Path as _Path

        if len(args) != 3 or args[1] != "-tsa":
            CreateSignedTimeStamp.usage()
            raise SystemExit("usage: create_signed_time_stamp <pdf> -tsa <url>")
        signer = CreateSignedTimeStamp(args[2])
        in_file = _Path(args[0])
        out_file = in_file.with_name(in_file.stem + "_timestamped.pdf")
        signer.sign_detached(in_file, out_file)

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream)."""
        import sys

        sys.stderr.write(
            "usage: CreateSignedTimeStamp <pdf> -tsa <url>\n",
        )

    def sign_detached(
        self,
        in_file: Path | str,
        out_file: Path | str | None = None,
    ) -> None:
        in_path = Path(in_file)
        if not in_path.exists():
            raise FileNotFoundError("Document for signing does not exist")
        out_path = in_path if out_file is None else Path(out_file)

        from pypdfbox.loader import Loader

        with (
            in_path.open("rb") as fh,
            Loader.load_pdf(fh) as doc,  # type: ignore[arg-type]
            out_path.open("wb") as out,
        ):
            self.sign_detached_document(doc, out)

    def sign_detached_document(self, document, output: IO[bytes]) -> None:
        access_permissions = SigUtils.get_mdp_permission(document)
        if access_permissions == 1:
            raise RuntimeError(
                "No changes to the document are permitted "
                "due to DocMDP transform parameters dictionary"
            )

        signature = PDSignature()
        signature.set_type(COSName.DOC_TIME_STAMP)
        signature.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
        signature.set_sub_filter(COSName.get_pdf_name("ETSI.RFC3161"))

        document.add_signature(signature, self)
        document.save_incremental(output)

    def sign(self, content: IO[bytes]) -> bytes:
        try:
            validation = ValidationTimeStamp(self._tsa_url)
            return validation.get_time_stamp_token(content)
        except Exception:  # noqa: BLE001 - mirror upstream lenient logging
            LOG.error("Hashing-Algorithm not found for TimeStamping", exc_info=True)
            return b""
