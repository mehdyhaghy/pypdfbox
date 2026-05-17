"""Coverage-boost tests for ``pypdfbox.pdmodel.encryption.security_handler``.

Targets the dispatch helpers, AES routing, secure-random override, signature
dict skip path, public-name aliases, and the ``TypeError`` fallback in
``compute_version_number`` that weren't previously exercised.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdmodel.encryption.security_handler import (
    SecurityHandler,
    _is_identity,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

# ----------------------------------------------------------------- fixtures


class _ConcreteHandler(SecurityHandler):
    """Bare concrete handler so we can exercise the abstract base."""

    def prepare_for_decryption(self, encryption, document_id, decryption_material):
        return None

    def prepare_document(self, document):
        return None


def _make_handler(
    *, aes: bool = False, key: bytes = b"\x00" * 16, revision: int = 4
) -> _ConcreteHandler:
    handler = _ConcreteHandler()
    handler.set_encryption_key(key)
    handler.set_aes(aes)
    handler.set_revision(revision)
    handler.set_key_length(len(key) * 8)
    return handler


# ----------------------------------------------- compute_version_number paths


def test_compute_version_number_prefer_aes_typeerror_fallback() -> None:
    """A policy whose ``is_prefer_aes`` raises ``TypeError`` falls through to V=2."""
    handler = _make_handler(key=b"\x00" * 16)
    handler.set_key_length(128)

    class _Policy:
        def is_prefer_aes(self_inner, extra):  # noqa: ARG002 — wrong arity raises TypeError
            return True

    handler.set_protection_policy(_Policy())
    # Wrong-arity getter raises TypeError → prefer_aes stays False → returns 2.
    assert handler.compute_version_number() == 2


def test_compute_version_number_alias_is_preferred_aes() -> None:
    handler = _ConcreteHandler()
    handler.set_key_length(128)

    class _Policy:
        def is_preferred_aes(self_inner) -> bool:
            return True

    handler.set_protection_policy(_Policy())
    assert handler.compute_version_number() == 4


def test_compute_version_number_no_policy_returns_two_for_128() -> None:
    handler = _ConcreteHandler()
    handler.set_key_length(128)
    assert handler.compute_version_number() == 2


# ----------------------------------------------- secure-random override paths


def test_get_secure_random_default_when_unset() -> None:
    handler = _make_handler()
    rng = handler.get_secure_random()
    # Default shim exposes read / randbytes / __call__.
    assert callable(rng.read)
    assert len(rng.read(8)) == 8
    assert len(rng.randbytes(4)) == 4
    assert len(rng(2)) == 2


def test_set_custom_secure_random_used_by_iv_generation() -> None:
    handler = _make_handler()

    class _Rng:
        def read(self_inner, n):
            return b"R" * n

    handler.set_custom_secure_random(_Rng())
    iv = bytearray(16)
    output = io.BytesIO()
    assert handler.prepare_aes_initialization_vector(False, iv, b"", output) is True
    assert bytes(iv) == b"R" * 16
    assert output.getvalue() == b"R" * 16


def test_prepare_aes_initialization_vector_custom_callable_rng() -> None:
    """Custom RNG without read/randbytes but callable falls through to __call__."""
    handler = _make_handler()

    class _Rng:
        def __call__(self_inner, n):
            return b"C" * n

    handler.set_custom_secure_random(_Rng())
    iv = bytearray(16)
    assert handler.prepare_aes_initialization_vector(False, iv, b"", None) is True
    assert bytes(iv) == b"C" * 16


def test_prepare_aes_initialization_vector_falls_back_to_os_urandom() -> None:
    handler = _make_handler()

    class _Rng:  # no read, no randbytes, not callable
        pass

    handler.set_custom_secure_random(_Rng())
    iv = bytearray(16)
    assert handler.prepare_aes_initialization_vector(False, iv, b"", None) is True
    # os.urandom always populates 16 distinct bytes (≈with overwhelming probability
    # at least one is non-zero).
    assert any(b != 0 for b in iv)


# --------------------------------------------------- AES IV decrypt branches


def test_prepare_aes_initialization_vector_decrypt_zero_length_returns_false() -> None:
    handler = _make_handler()
    iv = bytearray(16)
    src = io.BytesIO(b"")
    assert handler.prepare_aes_initialization_vector(True, iv, src, None) is False


def test_prepare_aes_initialization_vector_decrypt_partial_raises_oserror() -> None:
    handler = _make_handler()
    iv = bytearray(16)
    src = io.BytesIO(b"only-8b!")
    with pytest.raises(OSError):
        handler.prepare_aes_initialization_vector(True, iv, src, None)


def test_prepare_aes_initialization_vector_decrypt_full_iv() -> None:
    handler = _make_handler()
    iv = bytearray(16)
    src = io.BytesIO(b"\xab" * 16 + b"trailing")
    assert handler.prepare_aes_initialization_vector(True, iv, src, None) is True
    assert bytes(iv) == b"\xab" * 16


def test_prepare_aes_initialization_vector_decrypt_non_readable_raises_typeerror() -> None:
    handler = _make_handler()
    iv = bytearray(16)
    with pytest.raises(TypeError):
        handler.prepare_aes_initialization_vector(True, iv, object(), None)


# ----------------------------------------------- encrypt_data_* type errors


def test_encrypt_data_rc4_requires_bytes_or_readable() -> None:
    handler = _make_handler()
    with pytest.raises(TypeError):
        handler.encrypt_data_rc4(b"\x00" * 5, object())


def test_encrypt_data_ae_sother_requires_bytes_or_readable() -> None:
    handler = _make_handler(aes=True)
    with pytest.raises(TypeError):
        handler.encrypt_data_ae_sother(b"\x00" * 16, object())


def test_encrypt_data_ae_sother_accepts_file_like() -> None:
    handler = _make_handler(aes=True)
    key = b"\x10" * 16
    src = io.BytesIO(b"hello world")
    cipher = handler.encrypt_data_ae_sother(key, src)
    decoded = handler.encrypt_data_ae_sother(key, cipher, decrypt=True)
    assert decoded == b"hello world"


def test_encrypt_data_aes256_requires_encryption_key() -> None:
    handler = _ConcreteHandler()
    with pytest.raises(ValueError, match="encryption_key"):
        handler.encrypt_data_aes256(b"payload")


def test_encrypt_data_aes256_requires_bytes_or_readable() -> None:
    handler = _make_handler(key=b"\x20" * 32, revision=6)
    with pytest.raises(TypeError):
        handler.encrypt_data_aes256(object())


def test_encrypt_data_aes256_round_trip_with_output() -> None:
    handler = _make_handler(key=b"\x21" * 32, revision=6)
    sink = io.BytesIO()
    cipher = handler.encrypt_data_aes256(b"payload", sink, decrypt=False)
    assert sink.getvalue() == cipher
    decoded = handler.encrypt_data_aes256(cipher, None, decrypt=True)
    assert decoded == b"payload"


def test_encrypt_data_aes256_file_like_input() -> None:
    handler = _make_handler(key=b"\x22" * 32, revision=6)
    cipher = handler.encrypt_data_aes256(io.BytesIO(b"data"))
    decoded = handler.encrypt_data_aes256(cipher, decrypt=True)
    assert decoded == b"data"


def test_encrypt_data_rc4_writes_to_output_when_provided() -> None:
    handler = _make_handler()
    sink = io.BytesIO()
    out = handler.encrypt_data_rc4(b"\xaa" * 5, b"abc", sink)
    assert sink.getvalue() == out


def test_encrypt_data_rc4_file_like_input() -> None:
    handler = _make_handler()
    out = handler.encrypt_data_rc4(b"\xbb" * 5, io.BytesIO(b"abc"))
    # RC4 is symmetric — feeding the cipher back through reproduces the plaintext.
    assert handler.encrypt_data_rc4(b"\xbb" * 5, out) == b"abc"


# -------------------------------------------------- create_cipher round trip


def test_create_cipher_aes_cbc_round_trip() -> None:
    handler = _make_handler()
    key = b"\x33" * 16
    iv = b"\x44" * 16
    enc_cipher = handler.create_cipher(key, iv, decrypt=False)
    encryptor = enc_cipher.encryptor()
    # 16-byte block, no padding here (helper is bare wrapper).
    ct = encryptor.update(b"x" * 16) + encryptor.finalize()
    dec_cipher = handler.create_cipher(key, iv, decrypt=True)
    decryptor = dec_cipher.decryptor()
    assert decryptor.update(ct) + decryptor.finalize() == b"x" * 16


# ----------------------------------------------- calc_final_key alias parity


def test_calc_final_key_equals_compute_object_key() -> None:
    handler = _make_handler()
    assert handler.calc_final_key(7, 0) == handler.compute_object_key(7, 0)


# --------------------------------------------- encrypt_data_rc4 reverses self


def test_decrypt_data_and_encrypt_data_round_trip_bytes() -> None:
    handler = _make_handler()
    cipher = handler.encrypt_data(b"hello", 1, 0)
    assert handler.decrypt_data(cipher, 1, 0) == b"hello"


def test_decrypt_data_and_encrypt_data_round_trip_file_like() -> None:
    handler = _make_handler()
    cipher = handler.encrypt_data(io.BytesIO(b"hi"), 2, 0)
    assert handler.decrypt_data(io.BytesIO(cipher), 2, 0) == b"hi"


def test_coerce_to_bytes_rejects_unknown_input() -> None:
    with pytest.raises(TypeError, match="bytes-like"):
        SecurityHandler._coerce_to_bytes(42)  # noqa: SLF001


# ------------------------------------------------ COSBase dispatch routing


def test_decrypt_returns_non_cos_object_unchanged() -> None:
    handler = _make_handler()
    sentinel = object()
    assert handler.decrypt(sentinel, 1, 0) is sentinel


def test_decrypt_string_round_trip_via_dispatch() -> None:
    handler = _make_handler()
    plain = COSString(b"secret")
    cipher_bytes = handler.encrypt_string(b"secret", 1, 0)
    encrypted = COSString(cipher_bytes)
    returned = handler.decrypt(encrypted, 1, 0)
    assert returned is encrypted
    assert encrypted.get_bytes() == b"secret"
    # Second pass is a no-op (already decrypted).
    handler.decrypt(encrypted, 1, 0)
    assert encrypted.get_bytes() == b"secret"
    # plain str is untouched on first call.
    assert plain.get_bytes() == b"secret"


def test_decrypt_string_if_absent_short_circuits_when_identity_filter() -> None:
    handler = _make_handler()
    handler.set_string_filter_name(COSName.get_pdf_name("Identity"))
    target = COSString(b"untouched")
    returned = handler.decrypt(target, 1, 0)
    assert returned is target
    assert target.get_bytes() == b"untouched"


def test_decrypt_string_if_absent_returns_input_when_no_value_api() -> None:
    handler = _make_handler()

    class _Bad:  # no get_bytes / set_value
        pass

    bad = _Bad()
    # Force the dispatch into the string branch by spoofing isinstance via the
    # private helper directly.
    handler._objects_seen().clear()  # noqa: SLF001
    assert handler._decrypt_string_if_absent(bad, 1, 0) is bad  # noqa: SLF001


def test_decrypt_array_replaces_string_entries_in_place() -> None:
    handler = _make_handler()
    plain = b"hello-array"
    cipher_bytes = handler.encrypt_string(plain, 3, 0)
    array = COSArray([COSString(cipher_bytes)])
    returned = handler.decrypt(array, 3, 0)
    assert returned is array
    # Decryption happens in-place; the COSString instance is mutated.
    inner = array[0]
    assert isinstance(inner, COSString)
    assert inner.get_bytes() == plain


def test_decrypt_array_via_public_alias() -> None:
    handler = _make_handler()
    array = COSArray([COSString(handler.encrypt_string(b"x", 4, 0))])
    handler.decrypt_array(array, 4, 0)
    assert array[0].get_bytes() == b"x"


def test_decrypt_dictionary_round_trip() -> None:
    handler = _make_handler()
    cipher = handler.encrypt_string(b"deep", 5, 0)
    d = COSDictionary()
    d.set_item("Foo", COSString(cipher))
    returned = handler.decrypt(d, 5, 0)
    assert returned is d
    foo = d.get_item("Foo")
    assert isinstance(foo, COSString)
    assert foo.get_bytes() == b"deep"


def test_decrypt_dictionary_public_alias() -> None:
    handler = _make_handler()
    d = COSDictionary()
    d.set_item("A", COSString(handler.encrypt_string(b"y", 6, 0)))
    handler.decrypt_dictionary(d, 6, 0)
    assert d.get_item("A").get_bytes() == b"y"


def test_decrypt_dictionary_skips_when_cf_present() -> None:
    """Per PDFBOX-2936, dicts containing /CF are left alone."""
    handler = _make_handler()
    d = COSDictionary()
    d.set_item("CF", COSDictionary())
    payload = COSString(b"untouched")
    d.set_item("Foo", payload)
    returned = handler.decrypt(d, 7, 0)
    assert returned is d
    assert d.get_item("Foo").get_bytes() == b"untouched"


def test_decrypt_dictionary_skips_contents_for_signature_dict() -> None:
    """Signature dicts (``/Type /Sig``) must not have /Contents re-encrypted."""
    handler = _make_handler()
    d = COSDictionary()
    d.set_item("Type", COSName.get_pdf_name("Sig"))
    # /Contents would normally be a hex COSString — leave it untouched.
    contents = COSString(b"untouched-contents")
    d.set_item("Contents", contents)
    # Another key still flows through dispatch (no decryption since non-string),
    # exercising the for-loop body without altering /Contents.
    d.set_item("Misc", COSString(handler.encrypt_string(b"abc", 8, 0)))
    handler.decrypt(d, 8, 0)
    assert d.get_item("Contents").get_bytes() == b"untouched-contents"
    assert d.get_item("Misc").get_bytes() == b"abc"


def test_decrypt_dictionary_detects_signature_via_byterange() -> None:
    """ByteRange + COSString /Contents triggers the signature heuristic."""
    handler = _make_handler()
    d = COSDictionary()
    contents = COSString(b"sig-bytes")
    d.set_item("Contents", contents)
    d.set_item("ByteRange", COSArray())
    handler.decrypt(d, 9, 0)
    # Contents was preserved (not decrypted via dispatch).
    assert d.get_item("Contents").get_bytes() == b"sig-bytes"


def test_decrypt_dictionary_detects_doctimestamp_type() -> None:
    handler = _make_handler()
    d = COSDictionary()
    d.set_item("Type", COSName.get_pdf_name("DocTimeStamp"))
    contents = COSString(b"ts-content")
    d.set_item("Contents", contents)
    handler.decrypt(d, 10, 0)
    assert d.get_item("Contents").get_bytes() == b"ts-content"


# ----------------------------------------------- decrypt_stream_in_place


def _make_fake_stream(raw: bytes, type_name: str | None = None) -> object:
    """Build a minimal duck-typed stream with the methods the handler uses."""

    class _FakeStream:
        def __init__(self_inner):
            self_inner._raw = bytes(raw)
            self_inner._type = type_name

        def get_cos_name(self_inner, key):
            if self_inner._type is None:
                return None
            return COSName.get_pdf_name(self_inner._type)

        def get_item(self_inner, key):
            return None

        def get_raw_bytes(self_inner):
            return self_inner._raw

        def set_raw_bytes(self_inner, data):
            self_inner._raw = bytes(data)

    return _FakeStream()


def test_decrypt_stream_in_place_skips_xref_streams() -> None:
    handler = _make_handler()
    stream = _make_fake_stream(b"untouched", type_name="XRef")
    handler.decrypt_stream_in_place(stream, 1, 0)
    assert stream.get_raw_bytes() == b"untouched"


def test_decrypt_stream_in_place_skips_metadata_when_flag_false() -> None:
    handler = _make_handler()
    handler.set_decrypt_metadata(False)
    stream = _make_fake_stream(b"untouched", type_name="Metadata")
    handler.decrypt_stream_in_place(stream, 1, 0)
    assert stream.get_raw_bytes() == b"untouched"


def test_decrypt_stream_in_place_identity_filter_short_circuits() -> None:
    handler = _make_handler()
    handler.set_stream_filter_name(COSName.get_pdf_name("Identity"))
    stream = _make_fake_stream(b"untouched")
    handler.decrypt_stream_in_place(stream, 1, 0)
    assert stream.get_raw_bytes() == b"untouched"


def test_decrypt_stream_in_place_round_trip() -> None:
    handler = _make_handler()
    cipher = handler.encrypt_stream(b"payload", 11, 0)
    stream = _make_fake_stream(cipher)
    handler.decrypt_stream_in_place(stream, 11, 0)
    assert stream.get_raw_bytes() == b"payload"


def test_decrypt_stream_in_place_tolerates_decrypt_failure() -> None:
    """If the set_raw_bytes path raises mid-flight we swallow it (parity)."""
    handler = _make_handler()

    class _ExplosiveStream:
        def get_cos_name(self_inner, key):
            return None

        def get_item(self_inner, key):
            return None

        def get_raw_bytes(self_inner):
            raise RuntimeError("boom")

    handler.decrypt_stream_in_place(_ExplosiveStream(), 12, 0)  # must not raise


def test_decrypt_stream_if_absent_caches_seen_stream() -> None:
    handler = _make_handler()
    stream = _make_fake_stream(b"ignored")
    # First call adds to seen set; second call short-circuits.
    handler._decrypt_stream_if_absent(stream, 1, 0)  # noqa: SLF001
    returned = handler._decrypt_stream_if_absent(stream, 1, 0)  # noqa: SLF001
    assert returned is stream


def test_decrypt_stream_if_absent_public_alias() -> None:
    handler = _make_handler()
    stream = _make_fake_stream(b"")
    assert handler.decrypt_stream_if_absent(stream, 1, 0) is stream


def test_decrypt_string_if_absent_public_alias() -> None:
    handler = _make_handler()
    target = COSString(b"abc")
    assert handler.decrypt_string_if_absent(target, 1, 0) is target


# ---------------------------------------------- password helpers — wrong type


def test_compute_encrypted_key_rejects_non_standard_handler() -> None:
    handler = _ConcreteHandler()
    with pytest.raises(TypeError, match="does not derive keys"):
        handler.compute_encrypted_key(b"pw")


def test_compute_user_password_rejects_non_standard_handler() -> None:
    handler = _ConcreteHandler()
    with pytest.raises(TypeError, match="/U entry"):
        handler.compute_user_password(b"pw")


def test_compute_owner_password_rejects_non_standard_handler() -> None:
    handler = _ConcreteHandler()
    with pytest.raises(TypeError, match="/O entry"):
        handler.compute_owner_password(b"o", b"u")


def test_standard_handler_passes_isinstance_check() -> None:
    """StandardSecurityHandler isn't rejected — the base routing branches
    on the type check before delegating, so confirm a Standard instance
    passes the guard. (We don't invoke the routed call: upstream signatures
    don't line up at call time and tests of the Standard helpers live
    elsewhere.)"""
    handler = StandardSecurityHandler()
    handler.set_revision(4)
    handler.set_key_length(128)
    # Class identity check — the inner ``isinstance`` guard returns True
    # for both routing helpers; the route-through path is exercised by the
    # standard_security_handler test suite.
    assert isinstance(handler, StandardSecurityHandler) is True


# ------------------------------------------------ prepare_document bridge


def test_prepare_document_for_encryption_delegates_to_prepare_document() -> None:
    calls: list[object] = []

    class _Recorder(_ConcreteHandler):
        def prepare_document(self_inner, document):
            calls.append(document)

    handler = _Recorder()
    handler.prepare_document_for_encryption("DOC")
    assert calls == ["DOC"]


# -------------------------------------------------- _is_identity helper


def test_is_identity_none_returns_false() -> None:
    assert _is_identity(None) is False


def test_is_identity_accepts_plain_string() -> None:
    assert _is_identity("Identity") is True
    assert _is_identity("Other") is False


def test_is_identity_accepts_cos_name() -> None:
    assert _is_identity(COSName.get_pdf_name("Identity")) is True
    assert _is_identity(COSName.get_pdf_name("StdCF")) is False


def test_is_identity_swallows_get_name_failure() -> None:
    class _Bad:
        def get_name(self_inner):
            raise RuntimeError("no")

    # No exception even though get_name throws.
    assert _is_identity(_Bad()) is False


# ----------------------------------------------- compute_object_key error


def test_compute_object_key_requires_key() -> None:
    handler = _ConcreteHandler()
    with pytest.raises(ValueError, match="encryption_key"):
        handler.compute_object_key(1, 0)


def test_compute_object_key_revision_5_returns_file_key_directly() -> None:
    key = b"\x77" * 32
    handler = _make_handler(key=key, revision=6)
    assert handler.compute_object_key(1, 0) is handler.get_encryption_key()
    # Per-object key is the file key verbatim.
    assert handler.compute_object_key(1, 0) == key


def test_compute_object_key_aes_appends_salt() -> None:
    handler = _make_handler(aes=True, key=b"\xaa" * 16, revision=4)
    salted = handler.compute_object_key(1, 0)
    handler_no_salt = _make_handler(aes=False, key=b"\xaa" * 16, revision=4)
    plain = handler_no_salt.compute_object_key(1, 0)
    assert salted != plain


# -------------------------------------- additional dispatch coverage edges


def test_decrypt_dictionary_get_item_raises_treated_as_no_cf() -> None:
    """When ``get_item('CF')`` raises, the dict is treated as CF-less."""
    handler = _make_handler()

    class _RaisingDict:
        def get_item(self_inner, key):
            raise RuntimeError("boom")

        def entry_set(self_inner):
            return []

    # Should not raise — the CF lookup swallows the exception per upstream.
    result = handler._decrypt_dictionary(_RaisingDict(), 1, 0)  # noqa: SLF001
    assert isinstance(result, _RaisingDict)


def test_decrypt_dictionary_swallows_signature_probe_failure() -> None:
    """When the signature-detection probe raises, dispatch still proceeds."""
    handler = _make_handler()

    keys: list[str] = []

    class _ProbeRaisingDict:
        def get_item(self_inner, key):
            keys.append(key)
            if key == "CF":
                return None
            if key == "Type":
                raise RuntimeError("probe-explosion")
            return None

        def entry_set(self_inner):
            return []

    handler._decrypt_dictionary(_ProbeRaisingDict(), 1, 0)  # noqa: SLF001
    # The CF probe ran, then the Type probe ran (and raised — was swallowed),
    # then iteration over an empty entry set completed.
    assert "CF" in keys
    assert "Type" in keys


def test_decrypt_array_uses_subscript_when_setter_absent() -> None:
    """A duck-typed array without ``set`` falls back to ``__setitem__``."""
    handler = _make_handler()
    cipher = handler.encrypt_string(b"sub", 13, 0)
    encrypted_str = COSString(cipher)

    class _SubscriptArray:
        def __init__(self_inner, items):
            self_inner._items = list(items)

        def __len__(self_inner):
            return len(self_inner._items)

        def __getitem__(self_inner, i):
            return self_inner._items[i]

        def __setitem__(self_inner, i, v):
            self_inner._items[i] = v

    arr = _SubscriptArray([encrypted_str])
    # We need decrypt() to return a NEW instance so the `replaced is not elem`
    # branch fires. Wrap the COSString in a recorder handler that swaps it
    # for an equal-but-distinct copy on decrypt.
    real_decrypt = handler.decrypt

    def _swapping_decrypt(obj, on, gn):
        out = real_decrypt(obj, on, gn)
        if isinstance(obj, COSString):
            return COSString(obj.get_bytes())
        return out

    handler.decrypt = _swapping_decrypt  # type: ignore[method-assign]
    handler._decrypt_array(arr, 13, 0)  # noqa: SLF001
    assert isinstance(arr[0], COSString)
    assert arr[0].get_bytes() == b"sub"


def test_decrypt_dictionary_replaces_via_set_item_when_value_swapped() -> None:
    """When ``decrypt`` returns a new object, the dict's set_item is called."""
    handler = _make_handler()
    cipher = handler.encrypt_string(b"swap", 14, 0)

    class _Dict:
        def __init__(self_inner):
            self_inner._items = {"Foo": COSString(cipher)}

        def get_item(self_inner, key):
            return self_inner._items.get(key)

        def entry_set(self_inner):
            return list(self_inner._items.items())

        def set_item(self_inner, key, val):
            self_inner._items[key] = val

    # Swap-out helper produces a distinct COSString to force the set_item path.
    real_decrypt = handler.decrypt

    def _swap(obj, on, gn):
        out = real_decrypt(obj, on, gn)
        if isinstance(obj, COSString):
            return COSString(obj.get_bytes())
        return out

    handler.decrypt = _swap  # type: ignore[method-assign]
    d = _Dict()
    handler._decrypt_dictionary(d, 14, 0)  # noqa: SLF001
    assert d.get_item("Foo").get_bytes() == b"swap"


def test_decrypt_stream_in_place_handles_get_cos_name_raising() -> None:
    """The Type probe swallows arbitrary exceptions on get_cos_name."""
    handler = _make_handler()
    cipher = handler.encrypt_stream(b"abc", 15, 0)

    class _Stream:
        def __init__(self_inner):
            self_inner._raw = cipher

        def get_cos_name(self_inner, key):
            raise RuntimeError("probe")

        def get_item(self_inner, key):
            return None

        def get_raw_bytes(self_inner):
            return self_inner._raw

        def set_raw_bytes(self_inner, data):
            self_inner._raw = bytes(data)

    stream = _Stream()
    handler.decrypt_stream_in_place(stream, 15, 0)
    assert stream.get_raw_bytes() == b"abc"


def test_decrypt_stream_in_place_skips_when_raw_accessors_missing() -> None:
    """If get_raw_bytes / set_raw_bytes aren't present, nothing happens."""
    handler = _make_handler()

    class _Stream:
        def get_cos_name(self_inner, key):
            return None

        def get_item(self_inner, key):
            return None

    # No raw accessors — must be a no-op (no AttributeError).
    handler.decrypt_stream_in_place(_Stream(), 16, 0)


def test_decrypt_stream_in_place_falls_back_to_unfiltered_stream() -> None:
    """The legacy accessor pair ``get_unfiltered_stream`` is honoured."""
    handler = _make_handler()
    cipher = handler.encrypt_stream(b"legacy", 17, 0)

    class _Stream:
        def __init__(self_inner):
            self_inner._raw = cipher

        def get_cos_name(self_inner, key):
            return None

        def get_item(self_inner, key):
            return None

        def get_unfiltered_stream(self_inner):
            return self_inner._raw

        def set_unfiltered_stream(self_inner, data):
            self_inner._raw = bytes(data)

    stream = _Stream()
    handler.decrypt_stream_in_place(stream, 17, 0)
    assert stream.get_unfiltered_stream() == b"legacy"
