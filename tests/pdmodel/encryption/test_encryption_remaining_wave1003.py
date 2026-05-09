from __future__ import annotations

from tests.pdmodel.encryption.test_encryption_remaining_wave755 import _BareHandler


def test_bare_handler_preparation_overrides_are_noops() -> None:
    handler = _BareHandler()

    assert handler.prepare_for_decryption(object(), b"doc-id", object()) is None
    assert handler.prepare_document(object()) is None
