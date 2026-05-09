from __future__ import annotations

from tests.pdmodel.encryption import test_encryption_tail_wave791 as wave791


def test_tail_handler_concrete_noop_hooks_return_none() -> None:
    handler = wave791._TailHandler()  # noqa: SLF001

    assert handler.prepare_for_decryption(object(), b"id", object()) is None
    assert handler.prepare_document(object()) is None
