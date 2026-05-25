"""Wave 1396 branch-coverage tests for ``SecurityHandler`` helpers.

Closes False-branch arrows for the ``output is not None`` /
``callable(write)`` guards in the encrypt-data helpers:

* 679->681 — ``encrypt_aes_init_vector`` writes IV only when output has callable .write
* 716->718 — ``encrypt_data_rc4`` writes only when output has callable .write
* 755->757 — ``encrypt_data_ae_sother`` writes only when output has callable .write
* 785->787 — ``encrypt_data_aes256`` writes only when output has callable .write

Also closes 210->215 — ``compute_version_number`` getter not callable
(neither ``is_prefer_aes`` nor ``is_preferred_aes`` returns callable).
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler


class _ConcreteHandler(SecurityHandler):
    def prepare_for_decryption(self, encryption, document_id, decryption_material):  # noqa: ARG002
        return None

    def prepare_document(self, document):  # noqa: ARG002
        return None


def _make_handler(*, key: bytes = b"\x00" * 16, revision: int = 4) -> _ConcreteHandler:
    handler = _ConcreteHandler()
    handler.set_encryption_key(key)
    handler.set_aes(True)
    handler.set_revision(revision)
    handler.set_key_length(len(key) * 8)
    return handler


def test_encrypt_data_rc4_output_lacks_write_skips_silently() -> None:
    """RC4 encrypt with an output that has no .write attribute does not raise.

    Closes False arm at line 716 (``callable(write)``).
    """
    handler = _make_handler()

    class SinkNoWrite:
        # No .write method.
        pass

    # Returns the encrypted bytes; write skipped.
    result = handler.encrypt_data_rc4(b"\x00" * 16, b"hello", SinkNoWrite())
    assert isinstance(result, bytes)
    assert len(result) == len(b"hello")


def test_encrypt_data_ae_sother_output_lacks_write_skips_silently() -> None:
    """AES-other encrypt with non-writable output skips the write.

    Closes False arm at line 755.
    """
    handler = _make_handler()

    class SinkNoWrite:
        pass

    result = handler.encrypt_data_ae_sother(
        b"\x00" * 16, b"payload-data", SinkNoWrite(), decrypt=False,
    )
    assert isinstance(result, bytes)


def test_encrypt_data_aes256_output_lacks_write_skips_silently() -> None:
    """AES-256 encrypt with non-writable output skips the write.

    Closes False arm at line 785.
    """
    handler = _make_handler(key=b"\x00" * 32, revision=6)

    class SinkNoWrite:
        pass

    result = handler.encrypt_data_aes256(b"data16-byte-pld!", SinkNoWrite(), decrypt=False)
    assert isinstance(result, bytes)


def test_compute_version_number_getter_not_callable_keeps_default() -> None:
    """Policy whose is_prefer_aes / is_preferred_aes is a non-callable
    attribute falls through to V=2.

    Closes False arm at line 210 (``callable(getter)``).
    """
    handler = _make_handler()
    handler.set_key_length(128)

    class _Policy:
        # Both are non-callables (just truthy string attributes).
        is_prefer_aes = "yes"
        is_preferred_aes = "yes"

    handler._protection_policy = _Policy()  # noqa: SLF001
    # Should not prefer AES — getter wasn't callable.
    assert handler.compute_version_number() == 2
