from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature import PDSeedValueCertificate


def test_wave311_add_key_usage_rejects_wrong_length() -> None:
    cert = PDSeedValueCertificate()

    with pytest.raises(ValueError, match="9 characters"):
        cert.add_key_usage("1XX")

    assert cert.get_key_usage() is None


def test_wave311_set_key_usage_rejects_invalid_entry_without_writing_array() -> None:
    cert = PDSeedValueCertificate()

    with pytest.raises(ValueError, match="0, 1, X"):
        cert.set_key_usage(["1XX0X1XXX", "1xx0x1xxx"])

    assert cert.get_key_usage() is None
