"""Wave 1275 parity test for SecurityHandler.encrypt_data_ae_sother."""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


def test_encrypt_data_ae_sother_round_trip() -> None:
    handler = StandardSecurityHandler()
    key = bytes(range(16))  # 16-byte AES key
    plaintext = b"hello aes per-object key"
    cipher = handler.encrypt_data_ae_sother(key, plaintext, decrypt=False)
    assert cipher != plaintext
    decoded = handler.encrypt_data_ae_sother(key, cipher, decrypt=True)
    assert decoded == plaintext


def test_encrypt_data_ae_sother_writes_to_output_when_provided() -> None:
    import io as _io

    handler = StandardSecurityHandler()
    key = b"\x00" * 16
    sink = _io.BytesIO()
    result = handler.encrypt_data_ae_sother(key, b"payload", sink, decrypt=False)
    assert sink.getvalue() == result
