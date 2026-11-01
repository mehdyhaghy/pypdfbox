"""Ported from upstream ``TestCreateSignature.java`` (PDFBox 3.0 branch,
``examples/src/test/java/org/apache/pdfbox/examples/pdmodel``).

Only ``testSignEncrypted`` (PDFBOX-6289, commit c2451488) is ported here.
Upstream encrypts ``sign_me.pdf`` and signs it with the keystore of the
test resources; that fixture isn't shipped, so a generated one-page PDF and
the in-memory self-signed keystore of ``conftest.py`` stand in. Upstream's
``checkSignature`` relies on Bouncy Castle CMS verification; the port checks
that the signed bytes digest to the CMS ``messageDigest`` instead.
"""

import hashlib

import pytest

from pypdfbox.examples.signature.create_signature import CreateSignature
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.interactive.digitalsignature.sig_utils import (
    extract_pkcs7_message_digest,
    strip_signature_padding,
)


@pytest.mark.parametrize("externally_sign", [False, True], ids=["internal", "external"])
def test_sign_encrypted(externally_sign, tmp_path, pkcs12_bytes, tsa_password):
    """PDFBOX-6289: sign an encrypted PDF and check that the placeholder
    wasn't encrypted."""
    password = "12345"

    # encrypt
    with PDDocument() as doc:
        doc.add_page(PDPage())
        spp = StandardProtectionPolicy("owner", password, AccessPermission())
        spp.set_prefer_aes(True)
        doc.protect(spp)
        suffix = "_ext" if externally_sign else ""
        encrypted_file = tmp_path / f"PDFBOX-6289-encrypted{suffix}.pdf"
        doc.save(str(encrypted_file))

    # sign PDF
    signing = CreateSignature(pkcs12_bytes, tsa_password)
    signing.set_external_signing(externally_sign)
    signed_file = tmp_path / f"PDFBOX-6289-encrypted_signed{suffix}.pdf"
    signing.sign_detached(encrypted_file, signed_file, None, password)

    raw = signed_file.read_bytes()
    with PDDocument.load(str(signed_file), password) as doc:
        sig = doc.get_last_signature_dictionary()
        contents = sig.get_contents()
        assert contents[-1] == 0
        assert contents[-2] == 0
        assert contents[-3] == 0
        assert contents[-4] == 0
        assert contents[-5] == 0

        # stands in for upstream's checkSignature()
        byte_range = sig.get_byte_range()
        signed_content = (
            raw[byte_range[0] : byte_range[0] + byte_range[1]]
            + raw[byte_range[2] : byte_range[2] + byte_range[3]]
        )
        digest = extract_pkcs7_message_digest(strip_signature_padding(contents))
        assert digest == hashlib.sha256(signed_content).digest()
