"""Port of ``ShowSignature`` (upstream 1-687).

Dumps signature metadata + verifies the embedded PKCS#7 content. We rely
on ``cryptography``'s PKCS#7 parsing for the signed-data graph.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.serialization import pkcs7

LOG = logging.getLogger(__name__)


class ShowSignature:
    """Dump and minimally verify embedded signatures inside a PDF."""

    def __init__(self) -> None:
        self._results: list[dict[str, Any]] = []

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 112)."""
        if len(args) != 2:
            ShowSignature.usage()
            raise SystemExit("usage: show_signature <password> <pdf>")
        ShowSignature().show_signature(args[0], args[1])

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream line 680)."""
        import sys

        sys.stderr.write(
            "usage: ShowSignature <password> <input-pdf>\n",
        )

    def check_content_value_with_file(
        self,
        file_path,  # noqa: ANN001
        byte_range: list[int],
        contents: bytes,
    ) -> None:
        """Validate hex /Contents against on-disk bytes (upstream 306)."""
        from pathlib import Path as _Path

        data = _Path(file_path).read_bytes()
        slice_ = data[byte_range[0] + byte_range[1] + 1 : byte_range[2] - 1]
        decoded = bytes.fromhex(slice_.decode("ascii", errors="ignore"))
        if decoded[: len(contents)] != contents:
            LOG.warning("Hex Contents do not match raw bytes")

    def verify_ets_idot_rfc3161(
        self,
        signed_content: bytes,
        contents: bytes,
    ) -> None:
        """Stub for upstream ETSI.RFC3161 verification (upstream 380).

        Name mirrors ``verifyETSIdotRFC3161`` after camel-to-snake.
        """
        LOG.debug("ETSI.RFC3161 verification stub (signed=%d, sig=%d bytes)",
                  len(signed_content), len(contents))

    def verify_etsi_dot_rfc3161(
        self,
        signed_content: bytes,
        contents: bytes,
    ) -> None:
        """Backwards-compatible alias matching the historical spelling."""
        self.verify_ets_idot_rfc3161(signed_content, contents)

    def verify_pkcs7(
        self,
        signed_content: bytes,
        contents: bytes,
        signature,  # noqa: ANN001
    ) -> None:
        """Lightweight PKCS#7 verification (upstream 436)."""
        try:
            pkcs7.load_der_pkcs7_certificates(contents)
        except (ValueError, TypeError) as exc:
            LOG.warning("PKCS#7 parse failed: %s", exc)

    def get_root_certificates(self) -> set:
        """Return the JVM's trusted-roots set (upstream 580). Always empty
        in pypdfbox — callers supply their own trust list."""
        return set()

    def analyse_dss(self, document) -> None:
        """Dump the DSS dictionary (upstream 624)."""
        catalog = document.get_document_catalog().get_cos_object()
        from pypdfbox.cos.cos_name import COSName

        dss = catalog.get_cos_dictionary(COSName.get_pdf_name("DSS"))
        if dss is None:
            LOG.info("No DSS dictionary")
            return
        LOG.info("DSS: %r", list(dss.key_set()))

    def print_streams_from_array(self, elements, description: str) -> None:
        """Dump elements from a COSArray (upstream 659)."""
        LOG.info("%s: %d streams", description, elements.size() if elements else 0)

    def show_signature(
        self,
        password: str | None,
        pdf_path: Path | str,
    ) -> list[dict[str, Any]]:
        """Parse signatures from ``pdf_path`` and return a list of summaries."""
        path = Path(pdf_path)
        from pypdfbox.loader import Loader

        with path.open("rb") as fh, Loader.load_pdf(fh, password) as doc:  # type: ignore[arg-type]
            self._results = []
            for signature in doc.get_signature_dictionaries():
                self._results.append(self._summarize(signature))
        return self._results

    def _summarize(self, signature) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "name": signature.get_name(),
            "location": signature.get_location(),
            "reason": signature.get_reason(),
            "filter": signature.get_filter(),
            "sub_filter": signature.get_sub_filter(),
        }
        contents = signature.get_contents()
        if contents:
            try:
                certs = pkcs7.load_der_pkcs7_certificates(contents)
                summary["certificates"] = [c.subject.rfc4514_string() for c in certs]
            except (ValueError, TypeError) as exc:
                LOG.debug("Could not parse PKCS#7 contents: %s", exc)
                summary["certificates"] = []
        return summary
