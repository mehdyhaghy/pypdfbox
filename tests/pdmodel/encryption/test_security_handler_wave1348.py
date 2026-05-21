"""Wave 1348 coverage-boost tests for ``pypdfbox.pdmodel.encryption.security_handler``.

Targets the residual uncovered branches:

  * Base ``compute_encrypted_key`` ``StandardSecurityHandler`` dispatch
    (line 370) — reachable only by calling the base method explicitly,
    because the subclass shadows it (see latent-bug note in CHANGES).
  * ``decrypt`` dispatch on ``COSStream`` (line 467).
  * ``decrypt_stream_in_place`` ``ImportError`` fallback for ``COSName``
    (lines 523-524) and ``get_item("Type")`` arm (lines 532-533).
  * ``decrypt_stream_in_place`` broad-except after ``get_raw_bytes``
    raises (lines 555-556).
  * ``_decrypt_array`` setter path (line 620).
"""
from __future__ import annotations

import builtins

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler

# ---------- minimal concrete handler ----------


class _ConcreteHandler(SecurityHandler):
    """Concrete subclass that doesn't override compute_encrypted_key."""

    def prepare_for_decryption(self, encryption, document_id, decryption_material):
        return None

    def prepare_document(self, document):
        return None

    def _decrypt(self, data: bytes, _obj_num: int, _gen_num: int) -> bytes:
        # Trivial pass-through so decrypt_stream_in_place can run end-to-end.
        return data


def _handler() -> _ConcreteHandler:
    h = _ConcreteHandler()
    h.set_encryption_key(b"\x00" * 16)
    h.set_aes(False)
    h.set_revision(4)
    h.set_key_length(128)
    return h


# ---------- compute_encrypted_key — base method on StandardSecurityHandler ----


def test_compute_encrypted_key_base_raises_type_error() -> None:
    """Wave 1374 closure of audit item 3: the base method no longer
    delegates to :class:`StandardSecurityHandler` — Python's MRO
    already routes ``self.compute_encrypted_key(...)`` to the subclass
    override when ``self`` is a Standard handler, so the previous
    delegation was structurally unreachable. The base now raises
    :class:`TypeError` for any handler that doesn't override (e.g.
    :class:`PublicKeySecurityHandler`)."""
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardSecurityHandler,
    )

    handler = StandardSecurityHandler()
    handler.set_revision(2)
    handler.set_key_length(40)
    # Invoking the base directly (bypassing MRO) now raises rather than
    # silently delegating — proves the dead-code path was removed.
    with pytest.raises(TypeError, match="does not derive keys from a password"):
        SecurityHandler.compute_encrypted_key(
            handler,
            password=b"foo",
            o=b"\x00" * 32,
            u=b"\x00" * 32,
            oe=b"\x00" * 16,
            ue=b"\x00" * 16,
            permissions=-4,
            document_id=b"\x00" * 16,
            revision=2,
            length_in_bits=40,
            encrypt_metadata=True,
        )


# ---------- decrypt dispatch — COSStream arm ----------


def test_decrypt_dispatch_routes_cos_stream() -> None:
    """Line 467: a COSStream is routed to ``_decrypt_stream_if_absent``."""
    handler = _handler()
    cos = COSStream()
    cos.set_data(b"payload")
    out = handler.decrypt(cos, 7, 0)
    assert out is cos  # in-place op returns the same instance


# ---------- decrypt_stream_in_place — COSName ImportError ----------


def test_decrypt_stream_in_place_handles_cos_name_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 523-524: if ``COSName`` import raises ``ImportError`` mid-call,
    the helper continues without the type-skip optimization."""
    handler = _handler()
    cos = COSStream()
    cos.set_data(b"payload")

    real_import = builtins.__import__

    def _patched_import(name, *args, **kwargs):
        if name == "pypdfbox.cos.cos_name":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _patched_import)
    # Must not raise — fallback path skips the type-name check.
    handler.decrypt_stream_in_place(cos, 7, 0)


# ---------- decrypt_stream_in_place — get_item("Type") arm ----------


def test_decrypt_stream_in_place_uses_get_item_when_no_get_cos_name() -> None:
    """Lines 532-533: when the stream exposes ``get_item`` but no
    ``get_cos_name`` (the modern accessor), the helper falls back to
    ``get_item("Type")``."""
    handler = _handler()

    captured: list[str] = []

    class _LegacyStream:
        """Duck typed: only get_item exists (no get_cos_name)."""

        def get_item(self, key: str):
            captured.append(key)
            return COSName.get_pdf_name("XRef")

        def get_raw_bytes(self):
            return b""

        def set_raw_bytes(self, _data: bytes) -> None:
            pass

    stream = _LegacyStream()
    handler.decrypt_stream_in_place(stream, 8, 0)
    # Confirms the get_item("Type") branch fired.
    assert "Type" in captured


# ---------- decrypt_stream_in_place — broad-except on body raw ----------


def test_decrypt_stream_in_place_broad_except_on_raw_read() -> None:
    """Lines 555-556: an exception from ``get_raw_bytes`` is swallowed
    (mirrors upstream tolerant decrypt)."""
    handler = _handler()

    class _BoomStream:
        def get_cos_name(self, _key):
            return None

        def get_item(self, _key):
            return None

        def get_raw_bytes(self):
            raise RuntimeError("raw broken")

        def set_raw_bytes(self, _data):
            pass

    # Must not raise.
    handler.decrypt_stream_in_place(_BoomStream(), 9, 0)


# ---------- _decrypt_array — setter path ----------


def test_decrypt_array_uses_setter_when_present() -> None:
    """Line 620: ``COSArray`` exposes ``set`` so replacement entries go
    through the upstream-named setter instead of ``__setitem__``."""
    handler = _handler()
    inside = COSString("hello")
    arr = COSArray([inside])

    # Make a synthetic /Type-style array containing a string so the
    # dispatch in decrypt() flows: COSArray → _decrypt_array → decrypt(
    # COSString) → _decrypt_string_if_absent (replaces the bytes via
    # set_value). The decrypt-string path is identity in this test
    # (our _decrypt returns input unchanged), so we just verify the
    # decryption walk completes without error.
    out = handler.decrypt(arr, 11, 0)
    assert out is arr
    # The original COSString remains in place (identity decrypt).
    assert arr.get_object(0) is inside
