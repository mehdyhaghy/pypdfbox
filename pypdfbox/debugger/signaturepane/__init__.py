"""Tkinter port of ``org.apache.pdfbox.debugger.signaturepane``.

Hosts the :class:`SignaturePane` widget which renders the embedded
PKCS#7 SignedData blob of a PDF signature dictionary.
"""

from __future__ import annotations

from pypdfbox.debugger.signaturepane.signature_pane import (
    SignaturePane,
    parse_pkcs7_certificates,
)

__all__ = ["SignaturePane", "parse_pkcs7_certificates"]
