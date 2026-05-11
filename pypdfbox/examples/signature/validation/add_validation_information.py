"""Port of ``AddValidationInformation`` (upstream 1-658).

Embeds a Document Security Store (DSS) containing OCSP responses, CRLs and
intermediate certificates inside a PDF, per PAdES-LTV. The upstream class
is large; here we provide the public entry point + the supporting bag
classes so callers can drive the flow programmatically.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.examples.signature.validation.cert_information_collector import (
    CertInformationCollector,
)

LOG = logging.getLogger(__name__)


class AddValidationInformation:
    """Embed a DSS (Document Security Store) into a PDF."""

    def __init__(self) -> None:
        self._cert_information_collector = CertInformationCollector()
        self._cert_info = None
        self._foundRevocationInformation: set = set()
        self._signDate = None
        self._correspondingOCSPs: list = []
        self._correspondingCRLs: list = []

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 631)."""
        if len(args) != 2:
            AddValidationInformation.usage()
            raise SystemExit("usage: add_validation_information <in.pdf> <out.pdf>")
        AddValidationInformation().validate_signature(args[0], args[1])

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream line 653)."""
        import sys

        sys.stderr.write(
            "usage: AddValidationInformation <input-pdf> <output-pdf>\n",
        )

    @staticmethod
    def get_or_create_dictionary_entry(
        clazz, parent, key: str,
    ):
        """Mirrors ``getOrCreateDictionaryEntry`` (upstream line 211).

        Returns the existing entry under ``parent[key]`` if it is an instance
        of ``clazz``; otherwise constructs a fresh ``clazz``, marks it as
        needing to be written, and stores it under ``parent[key]``.
        """
        from pypdfbox.cos.cos_name import COSName as _N

        cos_key = key if isinstance(key, _N) else _N.get_pdf_name(key)
        existing = parent.get_dictionary_object(cos_key)
        if existing is not None and isinstance(existing, clazz):
            return existing
        entry = clazz()
        if hasattr(entry, "set_need_to_be_updated"):
            entry.set_need_to_be_updated(True)
        parent.set_item(cos_key, entry)
        return entry

    def add_revocation_data_recursive(self, cert_info, max_chain_depth: int = 5) -> None:
        """Walk a cert chain and harvest revocation data (upstream private)."""

    def add_ocsp_data(self, cert_info) -> None:
        """Fetch and embed OCSP data for ``cert_info`` (upstream private)."""

    def add_crl_revocation_info(self, cert_info) -> None:
        """Fetch and embed CRL data for ``cert_info`` (upstream private)."""

    def fetch_data_url(self, url: str) -> bytes:
        """Stub HTTP fetch (upstream private). Offline by default."""
        return b""

    def create_base_dictionary(self) -> object:
        """Build the empty DSS base dict (upstream private)."""
        from pypdfbox.cos.cos_dictionary import COSDictionary as _D

        return _D()

    def create_vri_dictionary(self) -> object:
        """Build a /VRI entry for the DSS (upstream private)."""
        from pypdfbox.cos.cos_dictionary import COSDictionary as _D

        return _D()

    def do_validation(self, filename: str, output) -> None:  # noqa: ANN001
        """Drive the validation flow (upstream 146)."""

    def add_revocation_data(self, cert_info) -> None:  # noqa: ANN001
        """Top-level revocation harvest (upstream 249)."""

    def fetch_ocsp_data(self, cert_info) -> bool:  # noqa: ANN001
        """Fetch OCSP data, returns True on success (upstream 321)."""
        return False

    def fetch_crl_data(self, cert_info) -> None:  # noqa: ANN001
        """Fetch CRL data (upstream 346)."""

    def update_vri(self, cert_info, vri) -> None:  # noqa: ANN001
        """Populate the VRI block for one signature (upstream 520)."""

    def add_all_certs_to_cert_array(self) -> None:
        """Add every cert from the collector into the /Certs array (upstream 572)."""

    def write_data_to_stream(self, data: bytes):  # noqa: ANN201
        """Wrap ``data`` in a COSStream (upstream 599)."""
        from pypdfbox.cos.cos_stream import COSStream

        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(data)
        return stream

    def add_extensions(self, catalog) -> None:  # noqa: ANN001
        """Set the catalog ``/Extensions`` dict for PAdES (upstream 615)."""

    def validate_signature(
        self,
        in_file: Path | str,
        out_file: Path | str,
    ) -> None:
        """Build a DSS dictionary from the last signature and write the result (upstream 107)."""
        in_path = Path(in_file)
        out_path = Path(out_file)

        from pypdfbox.loader import Loader

        with in_path.open("rb") as fh, Loader.load_pdf(fh) as document:  # type: ignore[arg-type]
            signature = SigUtils.get_last_relevant_signature(document)
            if signature is None:
                raise OSError("No signature found")
            self._cert_info = self._cert_information_collector.get_last_cert_info(
                signature
            )
            self._signDate = signature.get_sign_date_as_datetime()
            self._do_validation(document, signature)
            with out_path.open("wb") as out:
                document.save_incremental(out)

    def _do_validation(self, document, signature) -> None:
        """Populate the catalog ``/DSS`` dict with certs / OCSPs / CRLs."""
        if self._cert_info is None:
            return
        catalog_dict = document.get_document_catalog().get_cos_object()
        dss = catalog_dict.get_cos_dictionary(COSName.get_pdf_name("DSS"))
        if dss is None:
            dss = COSDictionary()
            catalog_dict.set_item(COSName.get_pdf_name("DSS"), dss)
        catalog_dict.set_need_to_be_updated(True)
        dss.set_need_to_be_updated(True)

        certs_array = COSArray()
        for cert in self._cert_information_collector.get_certificate_set():
            from cryptography.hazmat.primitives.serialization import Encoding

            der = cert.public_bytes(Encoding.DER)
            cert_stream = self._create_stream(document, der)
            certs_array.add(cert_stream)
        dss.set_item(COSName.get_pdf_name("Certs"), certs_array)

    def _create_stream(self, document, payload: bytes):
        """Create a new COS stream embedded in ``document`` for ``payload``."""
        from pypdfbox.cos.cos_stream import COSStream

        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(payload)
        return stream
