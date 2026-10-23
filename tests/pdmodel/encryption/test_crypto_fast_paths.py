"""Differential tests for the optimized crypto helpers and decrypt walk.

Each fast path is checked against a straightforward reference (the
pre-optimization implementation, or the pure-Python RC4 port) over random
keys, payload lengths and object graphs, so the speed-ups stay provably
output-identical.
"""

import hashlib
import os
import random

import pytest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdmodel.encryption import security_handler as sh
from pypdfbox.pdmodel.encryption import standard_security_handler as ssh
from pypdfbox.pdmodel.encryption.rc4_cipher import RC4Cipher
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4
except ImportError:  # pragma: no cover - older cryptography releases
    from cryptography.hazmat.primitives.ciphers.algorithms import ARC4

# Key sizes (bytes) the ``cryptography`` ARC4 binding accepts.
_ARC4_SIZES = frozenset({5, 7, 8, 10, 16, 20, 24, 32})


# ------------------------------------------------------------- references


def _ref_rc4_cryptography(key: bytes, data: bytes) -> bytes:
    enc = Cipher(ARC4(key), mode=None).encryptor()
    return enc.update(data) + enc.finalize()


def _ref_rc4_pure(key: bytes, data: bytes) -> bytes:
    """Textbook RC4 (KSA + PRGA), independent of both implementations."""
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def _ref_object_key(
    file_key: bytes, obj_num: int, gen_num: int, aes: bool
) -> bytes:
    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(file_key)
    md5.update(
        bytes(
            [
                obj_num & 0xFF,
                (obj_num >> 8) & 0xFF,
                (obj_num >> 16) & 0xFF,
                gen_num & 0xFF,
                (gen_num >> 8) & 0xFF,
            ]
        )
    )
    if aes:
        md5.update(b"sAlT")
    return md5.digest()[: min(len(file_key) + 5, 16)]


def _ref_aes_decrypt(key: bytes, data: bytes, tolerant: bool) -> object:
    """Pre-optimization ``_aes_cbc_decrypt``; returns bytes or the error."""
    if len(data) == 0:
        return b""
    if len(data) < 16:
        return ("OSError", "iv")
    iv, ct = data[:16], data[16:]
    if len(ct) == 0:
        return b""
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    if len(ct) % 16 != 0:
        if tolerant:
            whole = ct[: len(ct) - (len(ct) % 16)]
            return dec.update(whole) + dec.finalize()
        return ("OSError", "block")
    padded = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError:
        if tolerant:
            return padded[:-16] if len(padded) >= 16 else b""
        return ("OSError", "padding")


def _ref_aes_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return iv + enc.update(padded) + enc.finalize()


def _outcome(fn, *args, **kwargs) -> object:
    try:
        return fn(*args, **kwargs)
    except OSError as exc:
        msg = str(exc)
        if "initialization vector" in msg:
            return ("OSError", "iv")
        if "multiple of the block size" in msg:
            return ("OSError", "block")
        return ("OSError", "padding")


# -------------------------------------------------------------------- RC4


@pytest.mark.parametrize("key_len", range(1, 33))
def test_rc4_c_backed_matches_reference(key_len: int) -> None:
    rnd = random.Random(key_len)
    for data_len in (0, 1, 2, 15, 16, 17, 255, 256, 257, 1023, 1024, 4099):
        key = rnd.randbytes(key_len)
        data = rnd.randbytes(data_len)
        expected = _ref_rc4_pure(key, data)
        cipher = RC4Cipher()
        cipher.set_key(key)
        out = _BytesSink()
        cipher.write(data, out)
        assert out.value == expected
        # Sizes the binding rejects fall back to RC4Cipher (PDFBOX-5955).
        assert sh._rc4(key, data) == expected
        assert ssh._rc4(key, data) == expected
        if key_len in _ARC4_SIZES:
            assert _ref_rc4_cryptography(key, data) == expected


def test_rc4_cipher_state_carries_across_writes() -> None:
    rnd = random.Random(7)
    key = rnd.randbytes(11)
    data = rnd.randbytes(3000)
    cipher = RC4Cipher()
    cipher.set_key(key)
    out = _BytesSink()
    for start in range(0, len(data), 97):
        cipher.write(data[start : start + 97], out)
    assert out.value == _ref_rc4_pure(key, data)


def test_rc4_cipher_stream_input_matches_bytes_input() -> None:
    import io

    key = b"stream-key"
    data = random.Random(3).randbytes(5000)
    cipher = RC4Cipher()
    cipher.set_key(key)
    out = _BytesSink()
    cipher.write(io.BytesIO(data), out)
    assert out.value == _ref_rc4_pure(key, data)


def test_rc4_cipher_subclass_encrypt_override_is_honoured() -> None:
    class _Xor(RC4Cipher):
        def encrypt(self, a_byte: int) -> int:
            return a_byte ^ 0xFF

    cipher = _Xor()
    cipher.set_key(b"k")
    out = _BytesSink()
    cipher.write(b"\x00\x0f", out)
    assert out.value == b"\xff\xf0"


class _BytesSink:
    def __init__(self) -> None:
        self.value = b""

    def write(self, data: bytes) -> None:
        self.value += data


# ----------------------------------------------------------- object keys


class _Handler(SecurityHandler):
    def prepare_for_decryption(self, encryption, document_id, material):
        return None

    def prepare_document(self, document):
        return None


def test_object_key_matches_reference() -> None:
    rnd = random.Random(11)
    handler = _Handler()
    handler.set_revision(4)
    for _ in range(400):
        file_key = rnd.randbytes(rnd.randint(1, 16))
        handler.set_encryption_key(file_key)
        obj_num = rnd.choice([0, 1, 255, 256, 65535, 0xFFFFFF, 1 << 30, -1, -77])
        obj_num = obj_num if rnd.random() < 0.5 else rnd.randint(-(1 << 25), 1 << 25)
        gen_num = rnd.choice([0, 1, 255, 65535, 70000, -1, rnd.randint(0, 1 << 17)])
        aes = rnd.random() < 0.5
        expected = _ref_object_key(file_key, obj_num, gen_num, aes)
        assert handler.compute_object_key(obj_num, gen_num, aes=aes) == expected
        handler.set_aes(aes)
        assert handler.compute_object_key(obj_num, gen_num) == expected


def test_object_key_cache_tracks_in_place_key_mutation() -> None:
    handler = _Handler()
    handler.set_revision(3)
    key = bytearray(b"\x01" * 16)
    handler._encryption_key = key  # type: ignore[assignment]
    first = handler.compute_object_key(5, 0)
    key[0] = 2
    assert handler.compute_object_key(5, 0) == _ref_object_key(bytes(key), 5, 0, False)
    assert handler.compute_object_key(5, 0) != first


def test_object_key_revision_5_uses_file_key() -> None:
    handler = _Handler()
    handler.set_revision(6)
    handler.set_encryption_key(b"k" * 32)
    assert handler.compute_object_key(9, 9) == b"k" * 32


# -------------------------------------------------------------------- AES


def _aes_payloads(rnd: random.Random, key: bytes) -> list[bytes]:
    payloads = [b"", b"\x00", rnd.randbytes(15), rnd.randbytes(16)]
    for n_blocks in range(1, 6):
        for tail in (0, 1, 15):
            payloads.append(rnd.randbytes(16 + 16 * n_blocks + tail))
    # Well-formed ciphertexts (valid padding) of every plaintext length mod 16.
    for length in range(40):
        iv = rnd.randbytes(16)
        payloads.append(_ref_aes_encrypt(key, iv, rnd.randbytes(length)))
    # Forged final blocks whose padding is valid only for some pad lengths.
    for pad in range(18):
        iv = rnd.randbytes(16)
        block = rnd.randbytes(16 - min(pad, 16)) + bytes([pad & 0xFF]) * min(pad, 16)
        enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        payloads.append(iv + enc.update(rnd.randbytes(16) + block) + enc.finalize())
        bad = bytearray(block)
        if pad >= 2:
            bad[-2] ^= 1
        enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        payloads.append(iv + enc.update(bytes(bad)) + enc.finalize())
    return payloads


@pytest.mark.parametrize("key_len", [16, 32])
@pytest.mark.parametrize("tolerant", [True, False])
def test_aes_decrypt_matches_reference(key_len: int, tolerant: bool) -> None:
    rnd = random.Random(key_len * 2 + tolerant)
    key = rnd.randbytes(key_len)
    for data in _aes_payloads(rnd, key):
        expected = _ref_aes_decrypt(key, data, tolerant)
        got = _outcome(sh._aes_cbc_decrypt, key, data, tolerant_padding=tolerant)
        assert got == expected
        # Non-bytes buffers decrypt identically.
        assert _outcome(
            sh._aes_cbc_decrypt, key, bytearray(data), tolerant_padding=tolerant
        ) == expected
        if tolerant == (key_len == 32):
            assert _outcome(ssh._aes128_cbc_decrypt, key, data) == expected


@pytest.mark.parametrize("key_len", [16, 32])
def test_aes_encrypt_matches_reference(
    key_len: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    rnd = random.Random(key_len)
    key = rnd.randbytes(key_len)
    for length in list(range(50)) + [255, 256, 1000]:
        data = rnd.randbytes(length)
        iv = rnd.randbytes(16)
        monkeypatch.setattr(os, "urandom", lambda n, iv=iv: iv[:n])
        expected = _ref_aes_encrypt(key, iv, data)
        assert sh._aes_cbc_encrypt(key, data) == expected
        assert ssh._aes128_cbc_encrypt(key, data) == expected
        assert sh._aes_cbc_decrypt(key, expected, tolerant_padding=False) == data


def test_aes_invalid_key_still_raises_value_error() -> None:
    with pytest.raises(ValueError):
        sh._aes_cbc_decrypt(b"short", b"\x00" * 32)
    with pytest.raises(ValueError):
        sh._aes_cbc_decrypt(b"short", b"\x00" * 33, tolerant_padding=False)
    with pytest.raises(OSError):
        sh._aes_cbc_decrypt(b"short", b"\x00" * 5)
    assert sh._aes_cbc_decrypt(b"short", b"\x00" * 16) == b""


# ------------------------------------------------------------ decrypt walk


class _GenericWalkHandler(StandardSecurityHandler):
    """Overrides ``decrypt`` (identically) so the generic walk is used."""

    def decrypt(self, obj: object, obj_num: int, gen_num: int) -> object:
        return super().decrypt(obj, obj_num, gen_num)


def _random_graph(rnd: random.Random, depth: int = 0) -> object:
    roll = rnd.random()
    if depth > 4 or roll < 0.35:
        leaf = rnd.random()
        if leaf < 0.6:
            return COSString(rnd.randbytes(rnd.randint(0, 40)))
        if leaf < 0.8:
            return COSInteger.get(rnd.randint(-5, 500))
        return COSName.get_pdf_name(rnd.choice(["A", "Sig", "XRef", "Metadata"]))
    if roll < 0.6:
        arr = COSArray()
        for _ in range(rnd.randint(0, 5)):
            arr.add(_random_graph(rnd, depth + 1))
        return arr
    d = COSStream() if roll < 0.68 else COSDictionary()
    for _ in range(rnd.randint(0, 5)):
        key = rnd.choice(["K1", "K2", "K3", "K4", "Contents", "ByteRange", "Type"])
        d.set_item(key, _random_graph(rnd, depth + 1))
    extra = rnd.random()
    if extra < 0.1:
        d.set_item("Type", COSName.get_pdf_name(rnd.choice(["Sig", "DocTimeStamp"])))
    elif extra < 0.15:
        d.set_item("CF", COSDictionary())
    elif extra < 0.25:
        d.set_item("Contents", COSString(b"sig-bytes"))
        d.set_item("ByteRange", COSArray([COSInteger.get(0)]))
    return d


def _snapshot(obj: object) -> object:
    if isinstance(obj, COSString):
        return ("s", obj.get_bytes())
    if isinstance(obj, COSDictionary):
        return (
            type(obj).__name__,
            [(k.get_name(), _snapshot(v)) for k, v in obj.entry_set()],
        )
    if isinstance(obj, COSArray):
        return ("a", [_snapshot(v) for v in obj])
    return ("o", repr(obj))


def _make(cls: type, aes: bool, string_identity: bool) -> SecurityHandler:
    handler = cls()
    handler.set_encryption_key(b"\x11" * 16)
    handler.set_revision(4 if aes else 3)
    handler.set_aes(aes)
    if string_identity:
        handler.set_string_filter_name(COSName.get_pdf_name("Identity"))
    return handler


@pytest.mark.parametrize("aes", [False, True])
@pytest.mark.parametrize("string_identity", [False, True])
def test_fast_walk_matches_generic_walk(aes: bool, string_identity: bool) -> None:
    for seed in range(250):
        graphs = []
        for _ in range(2):
            rnd = random.Random(seed)
            graph = _random_graph(rnd)
            if aes:
                # AES strings must be well formed; re-encrypt every string.
                _encrypt_strings(graph, seed)
            graphs.append(graph)
        fast = _make(StandardSecurityHandler, aes, string_identity)
        slow = _make(_GenericWalkHandler, aes, string_identity)
        assert fast._fast_walk()
        assert not slow._fast_walk()
        out_fast = _outcome(fast.decrypt, graphs[0], seed, 0)
        out_slow = _outcome(slow.decrypt, graphs[1], seed, 0)
        assert (out_fast is graphs[0]) == (out_slow is graphs[1])
        assert _snapshot(graphs[0]) == _snapshot(graphs[1])
        assert len(fast._objects_seen()) == len(slow._objects_seen())


def _encrypt_strings(obj: object, seed: int) -> None:
    key = _ref_object_key(b"\x11" * 16, seed, 0, True)
    rnd = random.Random(seed)
    stack = [obj]
    visited: set[int] = set()
    while stack:
        cur = stack.pop()
        if id(cur) in visited:
            continue
        visited.add(id(cur))
        if isinstance(cur, COSString):
            cur.set_value(_ref_aes_encrypt(key, rnd.randbytes(16), cur.get_bytes()))
        elif isinstance(cur, COSDictionary):
            stack.extend(v for _k, v in cur.entry_set())
        elif isinstance(cur, COSArray):
            stack.extend(cur)


def test_instance_level_decrypt_override_disables_fast_walk() -> None:
    handler = _make(StandardSecurityHandler, False, False)
    calls: list[object] = []

    def _spy(obj: object, obj_num: int, gen_num: int) -> object:
        calls.append(obj)
        return obj

    handler.decrypt = _spy  # type: ignore[method-assign]
    assert not handler._fast_walk()
    d = COSDictionary()
    d.set_item("A", COSInteger.get(1))
    d.set_item("B", COSString(b"x"))
    handler._decrypt_dictionary(d, 1, 0)
    assert len(calls) == 2


def test_spec_mock_string_is_classified_like_isinstance() -> None:
    from unittest.mock import MagicMock

    handler = _make(StandardSecurityHandler, False, False)
    fake = MagicMock(spec=COSString)
    fake.get_bytes.return_value = b"abc"
    handler.decrypt(fake, 1, 0)
    fake.set_value.assert_called_once()
