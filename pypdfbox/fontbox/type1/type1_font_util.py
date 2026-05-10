"""Static helpers for Adobe Type 1 ``eexec`` / charstring encryption.

Mirrors :class:`org.apache.fontbox.type1.Type1FontUtil` in upstream
PDFBox. The two ciphers are toy stream ciphers documented in the Adobe
Type 1 Font Format spec §7 (eexec) and §6.2 (charstring) — they are NOT
secure, they only obscure the binary section of a PFA / PFB so the file
parses uniformly.

Both ciphers use the same recurrence::

    cipher = plain ^ (R >> 8)
    R      = ((cipher + R) * c1 + c2) & 0xFFFF

with ``c1 = 52845`` and ``c2 = 22719``. They differ only in the seed
``R`` (eexec uses 55665, charstrings 4330) and in the random prefix
``n`` prepended on encrypt / discarded on decrypt (eexec uses 4 bytes,
charstrings use ``lenIV`` which defaults to 4).

We expose a class with classmethods so the call sites read the same way
as the upstream Java statics.
"""

from __future__ import annotations

import secrets

# Adobe Type 1 Font Format spec §7 — fixed cipher constants.
_C1 = 52845
_C2 = 22719

# Per-cipher seeds.
_EEXEC_SEED = 55665
_CHARSTRING_SEED = 4330

# eexec prefixes a random 4-byte garbage header (§7); charstrings
# prefix ``lenIV`` random bytes (§6.2) — usually 4, sometimes 0.
_EEXEC_RANDOM_BYTES = 4


def _encrypt(plain: bytes, seed: int, random_bytes: int) -> bytes:
    """Common encrypt path. Prepends ``random_bytes`` of fresh entropy
    so the recipient's seed-warm-up loop discards them."""
    if random_bytes < 0:
        raise ValueError("random_bytes must be >= 0")
    # Pad the plaintext with random prefix bytes — first ``random_bytes``
    # output bytes are the recipient's discarded warm-up.
    prefix = secrets.token_bytes(random_bytes) if random_bytes else b""
    buf = prefix + plain
    out = bytearray(len(buf))
    r = seed & 0xFFFF
    for i, b in enumerate(buf):
        cipher = (b ^ (r >> 8)) & 0xFF
        out[i] = cipher
        r = ((cipher + r) * _C1 + _C2) & 0xFFFF
    return bytes(out)


def _decrypt(cipher: bytes, seed: int, random_bytes: int) -> bytes:
    """Common decrypt path. Drops the leading ``random_bytes`` bytes
    (warm-up garbage) and returns the recovered plaintext."""
    if random_bytes < 0:
        raise ValueError("random_bytes must be >= 0")
    if len(cipher) < random_bytes:
        raise ValueError(
            f"ciphertext shorter ({len(cipher)}) than random prefix ({random_bytes})"
        )
    out = bytearray(len(cipher))
    r = seed & 0xFFFF
    for i, c in enumerate(cipher):
        plain = (c ^ (r >> 8)) & 0xFF
        out[i] = plain
        r = ((c + r) * _C1 + _C2) & 0xFFFF
    return bytes(out[random_bytes:])


class Type1FontUtil:
    """Static helpers for Type 1 eexec / charstring crypto.

    Ported (algorithm only) from ``org.apache.fontbox.type1.Type1FontUtil``.
    Mirrors the upstream signatures::

        eexecEncrypt(byte[]) -> byte[]
        eexecDecrypt(byte[]) -> byte[]
        charstringEncrypt(byte[], int lenIV) -> byte[]
        charstringDecrypt(byte[], int lenIV) -> byte[]

    Plus PostScript-style hex helpers (``hexEncode`` / ``hexDecode``)
    used by the parser when normalising ASCII-form eexec sections.
    """

    # ---------- eexec ----------

    @classmethod
    def eexec_encrypt(cls, plain: bytes | bytearray) -> bytes:
        """Encrypt ``plain`` under the eexec cipher (seed 55665, 4-byte
        random prefix). Returns the ciphertext, ready to splice into a
        PFB segment 2."""
        return _encrypt(bytes(plain), _EEXEC_SEED, _EEXEC_RANDOM_BYTES)

    @classmethod
    def eexec_decrypt(cls, cipher: bytes | bytearray) -> bytes:
        """Decrypt an eexec-encrypted block. Strips the leading 4 bytes
        of warm-up garbage and returns the recovered PostScript."""
        return _decrypt(bytes(cipher), _EEXEC_SEED, _EEXEC_RANDOM_BYTES)

    # ---------- charstring ----------

    @classmethod
    def charstring_encrypt(cls, plain: bytes | bytearray, len_iv: int = 4) -> bytes:
        """Encrypt a single charstring (seed 4330, ``len_iv`` random
        prefix bytes — default 4). Used when re-emitting modified Type 1
        glyph programs."""
        return _encrypt(bytes(plain), _CHARSTRING_SEED, len_iv)

    @classmethod
    def charstring_decrypt(cls, cipher: bytes | bytearray, len_iv: int = 4) -> bytes:
        """Decrypt a single charstring. ``len_iv`` matches the value in
        the font's ``Private`` dict (defaults to 4)."""
        return _decrypt(bytes(cipher), _CHARSTRING_SEED, len_iv)

    # ---------- low-level cipher (mirror upstream private statics) ----------
    #
    # Upstream ``Type1FontUtil`` keeps ``encrypt(plaintextBytes, r, n)`` and
    # ``decrypt(ciphertextBytes, r, n)`` as private static helpers (Java
    # lines 95 and 140). We expose them as classmethods so callers that
    # need a custom seed (e.g. interoperability shims, fuzzing harnesses)
    # can drive the cipher directly without reaching into the module's
    # underscored functions.
    #
    # NOTE: these mirror upstream byte-for-byte: the prefix slot is
    # zero-padded (NOT random), so the output is fully deterministic.
    # The high-level :meth:`eexec_encrypt` / :meth:`charstring_encrypt`
    # entries diverge from upstream by using fresh random bytes for the
    # prefix (Adobe Type 1 spec §7), which is recorded in CHANGES.md.

    @classmethod
    def encrypt(cls, plaintext_bytes: bytes | bytearray, r: int, n: int) -> bytes:
        """Generic Adobe Type 1 encrypt with explicit seed ``r`` and
        zero-prefix length ``n``.

        Mirrors upstream ``encrypt(byte[], int, int)`` (Java line 95)
        exactly: the leading ``n`` bytes of the buffer are zeros, not
        random. Use :meth:`eexec_encrypt` / :meth:`charstring_encrypt`
        for spec-correct random-prefix behaviour."""
        if n < 0:
            raise ValueError("n must be >= 0")
        plain = bytes(plaintext_bytes)
        # Upstream allocates length+n and copies plaintext starting at
        # index n — leaving n leading zero bytes, then encrypts the lot.
        buf = bytes(n) + plain
        out = bytearray(len(buf))
        rr = r & 0xFFFF
        for i, b in enumerate(buf):
            cipher = (b ^ (rr >> 8)) & 0xFF
            out[i] = cipher
            rr = ((cipher + rr) * _C1 + _C2) & 0xFFFF
        return bytes(out)

    @classmethod
    def decrypt(cls, ciphertext_bytes: bytes | bytearray, r: int, n: int) -> bytes:
        """Generic Adobe Type 1 decrypt with explicit seed ``r`` and
        random-prefix length ``n``.

        Mirrors upstream ``decrypt(byte[], int, int)`` (Java line 140).
        The first ``n`` output bytes are the cipher's warm-up garbage
        and are dropped before the result is returned."""
        return _decrypt(bytes(ciphertext_bytes), r, n)

    # ---------- PostScript hex helpers ----------
    #
    # PFA (ASCII) Type 1 fonts present the eexec section as ASCII hex
    # with whitespace allowed between any two nybbles. Upstream uses
    # ``Hex`` from commons-codec; we inline because the rules are tiny.

    @classmethod
    def hex_encode(cls, data: bytes | bytearray) -> str:
        """Uppercase-hex encoding without whitespace."""
        return bytes(data).hex().upper()

    @classmethod
    def hex_decode(cls, text: str) -> bytes:
        """Decode a PostScript-style hex string. Whitespace (spaces,
        newlines, tabs) is silently stripped before decoding so PFA
        inputs round-trip cleanly. Odd-length inputs raise ``ValueError``
        — matching the upstream commons-codec behaviour."""
        cleaned = "".join(ch for ch in text if not ch.isspace())
        if len(cleaned) % 2:
            raise ValueError("hex string has odd length")
        try:
            return bytes.fromhex(cleaned)
        except ValueError as exc:  # pragma: no cover — re-wrap for clarity
            raise ValueError(f"invalid hex character: {exc}") from exc


__all__ = ["Type1FontUtil"]
