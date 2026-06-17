"""Parity for ``PDCryptFilterDictionary`` default-value decode.

Upstream ``PDCryptFilterDictionary.getLength()`` returns
``getInt(COSName.LENGTH, 40)`` (PDFBox 3.0.7, line 86): the default is **40**
(length in *bits*, a multiple of 8 — see the upstream Javadoc), NOT 5 bytes.
pypdfbox originally returned 5; wave 1495 corrected it to 40 and pins it here
against the live oracle.
"""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from tests.oracle.harness import requires_oracle, run_probe_text


@requires_oracle
def test_default_crypt_filter_length_matches_pdfbox() -> None:
    lines = dict(
        line.split("=", 1)
        for line in run_probe_text("CryptFilterDictDefaultProbe").strip().splitlines()
    )
    cf = PDCryptFilterDictionary(COSDictionary())
    assert cf.get_length() == int(lines["defaultLength"])
    assert cf.get_length() == 40
    assert str(cf.get_encrypt_metadata()).lower() == lines["defaultEncryptMetadata"]
    cf.set_length(8)
    assert cf.get_length() == int(lines["afterSet8Length"])
