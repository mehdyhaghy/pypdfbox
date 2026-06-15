"""Live Apache PDFBox differential fuzz of the ``SecurityHandler`` DECRYPT
DATA PATH — the AES/RC4 cipher DISPATCH + byte transform on malformed
ciphertext (wave 1532).

The sibling ``StandardSecurityHandlerFuzzProbe`` (wave 1524) covers KEY
DERIVATION + password authentication; ``CryptFilterFuzzProbe`` drives the whole
document open path. NEITHER pokes the actual cipher dispatch + AES/RC4 transform
with deliberately malformed ciphertext. That is this wave's surface.

The probe (``DecryptDataFuzzProbe``) drives PDFBox's private
``SecurityHandler.encryptData(objNum, genNum, InputStream, OutputStream,
decrypt)`` via reflection — the single funnel for both encrypt and decrypt:

    useAES && key.length == 32  -> encryptDataAES256   (file key, 16-byte IV)
    useAES                      -> encryptDataAESother  (per-object key, IV)
    else                        -> encryptDataRC4       (per-object key)

Fuzz vectors: AES ciphertext shorter than 16 bytes (partial IV), exactly 16
bytes (IV only, empty payload), non-block-multiple length, empty input, RC4 of
empty/short, AES-256 (32-byte key) vs AES-128 (per-object key) routing, corrupt
padding, and a zero-length key. All inputs are deterministic fixed bytes.

Validation, not blind pinning: the Java line is ground truth for every case.

Real divergences fixed in production to match upstream (CHANGES.md wave 1532):

1. ``SecurityHandler._decrypt`` / ``_encrypt`` selected the AES-256 file-key
   path by ``revision >= 5``; upstream ``encryptData`` selects it by
   ``useAES && encryptionKey.length == 32``. A 32-byte AES key with a low /R now
   routes to the file-key path (and a 16-byte AES key to the per-object path),
   matching upstream byte-for-byte.
2. ``_aes_cbc_decrypt`` returned empty for ANY ``len(data) < 16``; upstream only
   skips on EMPTY input — a partial IV (``0 < n < 16``) raises an IOException
   (mapped to OSError).
3. ``_aes_cbc_decrypt`` returned the raw (still-padded) bytes on a PKCS#7
   failure. Upstream behaviour splits by call site: the AES-128 per-object path
   (``Cipher.update``+``doFinal``) raises; the AES-256 path
   (``CipherInputStream``) silently drops the bad final block and emits only the
   cleanly-decrypted leading blocks.
"""

from __future__ import annotations

import hashlib

import pytest

from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler as _S,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# --- Deterministic fixed keys ------------------------------------------------
_K256 = bytes(range(32))  # 32-byte file key → AES-256 path
_K16 = bytes(range(16))  # 16-byte file key → AES-128 per-object / RC4 path
_IV = bytes([0xAA] * 16)  # fixed IV for the well-formed ciphertexts


def _calc_final_key(file_key: bytes, obj_num: int, gen_num: int, aes: bool) -> bytes:
    buf = bytearray(file_key)
    buf += bytes(
        [
            obj_num & 0xFF,
            (obj_num >> 8) & 0xFF,
            (obj_num >> 16) & 0xFF,
            gen_num & 0xFF,
            (gen_num >> 8) & 0xFF,
        ]
    )
    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(buf)
    if aes:
        md5.update(b"sAlT")
    return md5.digest()[: min(len(file_key) + 5, 16)]


def _aes_enc(key: bytes, plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(_IV)).encryptor()
    return _IV + enc.update(padded) + enc.finalize()


# Well-formed ciphertexts of b"hello" for each routing. The AES-128 case uses
# the per-object key derived for obj=1 gen=0 (what the dispatch will recompute).
_CT256 = _aes_enc(_K256, b"hello").hex()
_CT128 = _aes_enc(_calc_final_key(_K16, 1, 0, True), b"hello").hex()

# Multi-block (31-byte) plaintext, well-formed + corrupted last byte.
_LONG_PT = b"hello world this is long enough"
_CT256_LONG = _aes_enc(_K256, _LONG_PT)
_CT256_LONG_GOOD = _CT256_LONG.hex()
_bad = bytearray(_CT256_LONG)
_bad[-1] ^= 0xFF
_CT256_LONG_BAD = bytes(_bad).hex()

_K256H = _K256.hex()
_K16H = _K16.hex()


# Each entry: (id, key-hex, aes, obj, gen, data-hex)  — decrypt is always true.
_PARITY_CASES = [
    # Well-formed round-trips (dispatch correctness).
    ("aes256_ok", _K256H, "true", "1", "0", _CT256),
    ("aes128_ok", _K16H, "true", "1", "0", _CT128),
    ("aes256_long_ok", _K256H, "true", "1", "0", _CT256_LONG_GOOD),
    # IV only (no ciphertext) → empty.
    ("aes256_iv_only", _K256H, "true", "1", "0", "aa" * 16),
    ("aes128_iv_only", _K16H, "true", "1", "0", "aa" * 16),
    # Empty input → empty (silent skip).
    ("aes256_empty", _K256H, "true", "1", "0", "-"),
    ("aes128_empty", _K16H, "true", "1", "0", "-"),
    # Non-block-multiple tail after the IV.
    ("aes256_nonblock", _K256H, "true", "1", "0", "aa" * 16 + "0102030405"),
    # Bad padding, single block: AES-256 drops it → empty (CipherInputStream).
    ("aes256_badpad", _K256H, "true", "1", "0", "aa" * 32),
    # Bad padding, two blocks: AES-256 emits the first block, drops the second.
    ("aes256_2blk_badlast", _K256H, "true", "1", "0", _CT256_LONG_BAD),
    # RC4 empty / short — RC4 is a pure stream cipher, no IV / padding.
    ("rc4_empty", _K16H, "false", "1", "0", "-"),
    ("rc4_short", _K16H, "false", "1", "0", "aabbcc"),
    ("rc4_block", _K16H, "false", "1", "0", "aa" * 16),
    # Per-object keying varies with obj/gen (RC4) — distinct output proves the
    # per-object key derivation is wired through the dispatch.
    ("rc4_obj2", _K16H, "false", "2", "0", "aabbcc"),
    ("rc4_gen1", _K16H, "false", "1", "1", "aabbcc"),
]

# Pinned divergences — both sides raise but the exception CLASS is unalignable.
# Java raises (any exception); pypdfbox raises the mapped type. The byte
# behaviour is identical (both refuse the input); only the class name differs.
_PINNED_CASES = [
    # Partial IV (3 of 16 bytes): Java IOException ("AES initialization vector
    # not fully read") ↔ pypdfbox OSError (project-wide I/O mapping).
    ("aes256_short_iv", _K256H, "true", "1", "0", "aabbcc", OSError),
    ("aes128_short_iv", _K16H, "true", "1", "0", "aabbcc", OSError),
    # AES-128 per-object bad padding (Cipher.update+doFinal): Java wraps the
    # BadPaddingException as IOException ↔ pypdfbox OSError.
    ("aes128_badpad", _K16H, "true", "1", "0", "aa" * 32, OSError),
    # Zero-length key: AES rejects it (InvalidKeyException upstream) ↔ pypdfbox
    # surfaces the underlying ``cryptography`` ValueError (not remapped).
    ("aes256_zerokey", "-", "true", "1", "0", "aa" * 32, ValueError),
    ("aes128_zerokey", "-", "true", "1", "0", "aa" * 32, ValueError),
]


def _py_eval(key_h: str, aes: str, obj: str, gen: str, data_h: str) -> str:
    """Project pypdfbox's decrypt_data result into the probe's line grammar."""
    try:
        handler = _S()
        handler.set_encryption_key(b"" if key_h in ("-", "") else bytes.fromhex(key_h))
        handler.set_aes(aes == "true")
        data = b"" if data_h in ("-", "") else bytes.fromhex(data_h)
        result = handler.decrypt_data(data, int(obj), int(gen))
        return "out=" + result.hex()
    except Exception as exc:  # noqa: BLE001 — projecting the exception class
        return "ERR:" + type(exc).__name__


def _spec(cid: str, key_h: str, aes: str, obj: str, gen: str, data_h: str) -> str:
    # Probe field order: key aes objnum gennum decrypt data
    return "|".join([cid, key_h, aes, obj, gen, "true", data_h])


def _run_java() -> dict[str, str]:
    specs = [_spec(c[0], c[1], c[2], c[3], c[4], c[5]) for c in _PARITY_CASES]
    specs += [
        _spec(c[0], c[1], c[2], c[3], c[4], c[5]) for c in _PINNED_CASES
    ]
    raw = run_probe_text("DecryptDataFuzzProbe", *specs)
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("CASE "):
            _, name, val = line.split(" ", 2)
            out[name] = val
    return out


@pytest.fixture(scope="module")
def java_results() -> dict[str, str]:
    return _run_java()


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "key_h", "aes", "obj", "gen", "data_h"),
    _PARITY_CASES,
    ids=[c[0] for c in _PARITY_CASES],
)
def test_decrypt_data_parity(
    case_id: str,
    key_h: str,
    aes: str,
    obj: str,
    gen: str,
    data_h: str,
    java_results: dict[str, str],
) -> None:
    """pypdfbox's decrypt dispatch matches PDFBox 3.0.7 byte-for-byte."""
    assert java_results[case_id] == _py_eval(key_h, aes, obj, gen, data_h)


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "key_h", "aes", "obj", "gen", "data_h", "exc"),
    _PINNED_CASES,
    ids=[c[0] for c in _PINNED_CASES],
)
def test_pinned_divergences(
    case_id: str,
    key_h: str,
    aes: str,
    obj: str,
    gen: str,
    data_h: str,
    exc: type[Exception],
    java_results: dict[str, str],
) -> None:
    """Both sides are pinned: Java raises (any exception class) on a zero-length
    AES key; pypdfbox surfaces the underlying ``cryptography`` ``ValueError``.
    Asserting both halves keeps the divergence intentional."""
    java = java_results[case_id]
    py = _py_eval(key_h, aes, obj, gen, data_h)
    assert java.startswith("ERR:")
    assert py == "ERR:" + exc.__name__
