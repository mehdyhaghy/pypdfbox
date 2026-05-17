"""Port of ``CreateEmbeddedTimeStamp`` (upstream 1-239)."""

from __future__ import annotations

import binascii
from pathlib import Path
from typing import IO

from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.examples.signature.validation_time_stamp import ValidationTimeStamp


class CreateEmbeddedTimeStamp:
    """Embed a TSA signed timestamp into an existing signature placeholder."""

    def __init__(self, tsa_url: str) -> None:
        self._tsa_url = tsa_url
        self._document = None
        self._signature = None
        self._changed_encoded_signature: bytes | None = None

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 197)."""
        if len(args) != 3 or "-tsa" not in args:
            CreateEmbeddedTimeStamp.usage()
            raise SystemExit("usage: create_embedded_time_stamp <pdf> -tsa <url>")
        tsa_idx = args.index("-tsa")
        tsa_url = args[tsa_idx + 1]
        in_file = Path(args[0])
        out_file = in_file.with_name(in_file.stem + "_eTs.pdf")
        CreateEmbeddedTimeStamp(tsa_url).embed_time_stamp(in_file, out_file)

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream line 233)."""
        import sys

        sys.stderr.write(
            "usage: CreateEmbeddedTimeStamp <pdf> -tsa <url>\n",
        )

    def _process_time_stamping_internal(self) -> None:
        """Upstream private hook (line 110); exposed for subclassing."""
        if self._document is None or self._signature is None:
            return

    def embed_time_stamp(
        self,
        in_file: Path | str,
        out_file: Path | str | None = None,
    ) -> None:
        in_path = Path(in_file)
        if not in_path.exists():
            raise FileNotFoundError("Document for signing does not exist")
        out_path = in_path if out_file is None else Path(out_file)

        from pypdfbox.pdmodel.pd_document import PDDocument

        with in_path.open("rb") as fh, PDDocument.load(fh) as doc:
            self._document = doc
            self.process_time_stamping(in_path, out_path)

    def process_time_stamping(self, in_path: Path, out_path: Path) -> None:
        """Mirrors ``processTimeStamping`` (upstream line 110)."""
        document_bytes = in_path.read_bytes()
        self.process_relevant_signatures(document_bytes)
        if self._changed_encoded_signature is None:
            raise RuntimeError("No signature")
        with out_path.open("wb") as out:
            self.embed_new_signature_into_document(document_bytes, out)

    def process_relevant_signatures(self, document_bytes: bytes) -> None:
        """Mirrors ``processRelevantSignatures`` (upstream line 141)."""
        self._signature = SigUtils.get_last_relevant_signature(self._document)
        if self._signature is None:
            return

        sig_block = self._signature.get_contents_from_bytes(document_bytes)
        validation = ValidationTimeStamp(self._tsa_url) if self._tsa_url else None
        new_signed = validation.add_signed_time_stamp(sig_block) if validation else sig_block

        new_encoded = binascii.hexlify(new_signed).upper()
        byte_range = self._signature.get_byte_range()
        max_size = byte_range[2] - byte_range[1]
        if len(new_encoded) > max_size - 2:
            raise OSError(
                "New Signature is too big for existing Signature-Placeholder. "
                f"Max Place: {max_size}"
            )
        self._changed_encoded_signature = new_encoded

    def embed_new_signature_into_document(self, doc_bytes: bytes, output: IO[bytes]) -> None:
        """Mirrors ``embedNewSignatureIntoDocument`` (upstream line 185)."""
        assert self._signature is not None
        byte_range = self._signature.get_byte_range()
        output.write(doc_bytes[byte_range[0] : byte_range[0] + byte_range[1] + 1])
        assert self._changed_encoded_signature is not None
        output.write(self._changed_encoded_signature)
        adding_length = (
            byte_range[2] - byte_range[1] - 2 - len(self._changed_encoded_signature)
        )
        zeroes = binascii.hexlify(b"\x00" * ((adding_length + 1) // 2)).upper()
        output.write(zeroes)
        output.write(doc_bytes[byte_range[2] - 1 : byte_range[2] - 1 + byte_range[3] + 1])
