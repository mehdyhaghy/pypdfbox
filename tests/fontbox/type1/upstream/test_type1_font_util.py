"""Ported from upstream Apache PDFBox 3.0.x
``fontbox/src/test/java/org/apache/fontbox/type1/Type1FontUtilTest.java``.

Upstream covers the round-trip property of the eexec / charstring
ciphers and the hex helpers. We mirror each ``@Test`` method one-to-one;
where the upstream test depends on a JUnit-only mechanism (e.g.
parameterised seeds) we substitute the equivalent pytest pattern.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil


def test_eexec_encryption_decryption_round_trip() -> None:
    """Upstream: ``testEExecEncryption`` — encrypt, decrypt, expect equality."""
    plain = b"This is a test for the eexec encryption."
    encrypted = Type1FontUtil.eexec_encrypt(plain)
    decrypted = Type1FontUtil.eexec_decrypt(encrypted)
    assert decrypted == plain


def test_charstring_encryption_decryption_round_trip() -> None:
    """Upstream: ``testCharstringEncryption`` — same round-trip property
    against the charstring cipher (different seed, lenIV=4)."""
    plain = b"This is a test for the charstring encryption."
    encrypted = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    decrypted = Type1FontUtil.charstring_decrypt(encrypted, len_iv=4)
    assert decrypted == plain


def test_hex_encoding_decoding_round_trip() -> None:
    """Upstream: ``testHexEncoding`` — ``hexEncode(hexDecode(x)) == x``
    and vice versa for the PostScript hex helpers."""
    raw = b"Round-trip me through hex."
    hexed = Type1FontUtil.hex_encode(raw)
    assert Type1FontUtil.hex_decode(hexed) == raw


@pytest.mark.parametrize("size", [0, 1, 16, 256, 1024])
def test_eexec_round_trip_various_sizes(size: int) -> None:
    """Upstream uses a fixed payload; we sweep across sizes (parametrised)
    so any boundary mishandling shows up as a clear failure."""
    plain = bytes((i & 0xFF for i in range(size)))
    assert Type1FontUtil.eexec_decrypt(Type1FontUtil.eexec_encrypt(plain)) == plain


@pytest.mark.parametrize("size", [0, 1, 16, 256])
def test_charstring_round_trip_various_sizes(size: int) -> None:
    plain = bytes((i & 0xFF for i in range(size)))
    encrypted = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    assert Type1FontUtil.charstring_decrypt(encrypted, len_iv=4) == plain
