"""Wave 1369 — Type 1 subroutine dispatch via ``callsubr 0..N``.

Type 1 ``/Subrs`` are positional — index ``K`` in the dict refers to
slot ``K`` in the pre-sized subrs array. There is NO bias (Type 2 /
CFF biases by 107 for short, 1131 for medium, 32768 for long; Type 1
just uses the raw index). This test file locks that in by:

* parsing a Type 1 Private dict whose ``/Subrs`` array contains four
  entries at indexes 0..3 with deterministic payloads, then asserting
  each lands in the right slot of ``font_dict["Private"]["Subrs"]``;

* parsing the same dict with the entries declared OUT OF ORDER (3, 1,
  0, 2) — upstream pre-sizes the slot list with ``null`` and slots
  each into its declared index, so out-of-order should still produce
  the same result;

* parsing an array longer than the entries — unused slots stay as
  empty bytes (upstream uses ``null``; we use ``b""``);

* a single subr containing the standard ``hsbw`` + ``endchar``
  byte-program (Adobe Type 1 spec §6.3 charstring opcodes) and
  verifying the payload survives charstring decryption byte-for-byte
  — proving Type 1 subrs use the charstring cipher (seed 4330) and
  NOT the eexec cipher (seed 55665).
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

_PFA_HEADER = b"%!PS-AdobeFont-1.0: T 001.000\n6 dict begin\n/FontName /T def\n"


def _make_eexec_with_subrs(entries: list[tuple[int, bytes]], length: int) -> bytes:
    """Build an eexec ciphertext containing a Private dict whose
    ``/Subrs`` array length is ``length`` and which carries the given
    ``(index, plaintext_payload)`` entries. Each entry's payload is
    charstring-encrypted in-line (len_iv = 4)."""
    out: list[bytes] = []
    out.append(b"dup /Private 5 dict dup begin\n/lenIV 4 def\n")
    out.append(f"/Subrs {length} array\n".encode("latin-1"))
    for idx, plain in entries:
        cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
        out.append(f"dup {idx} {len(cipher)} RD ".encode("latin-1"))
        out.append(cipher)
        out.append(b" NP\n")
    out.append(b"def\n")
    # /CharStrings is required by parse() to terminate the Private dict.
    out.append(b"/CharStrings 0 dict dup begin end\nend\n")
    return Type1FontUtil.eexec_encrypt(b"".join(out))


# ---------- dispatch ordering ----------


def test_subrs_dispatch_0_through_N_in_order() -> None:
    payloads = [
        b"\x0e",                        # endchar
        b"\x01\x0e",                    # hstem, endchar
        b"\x80\x01\x80\x02\x0e",        # rmoveto-like, endchar
        b"\x0a",                        # callsubr opcode
    ]
    entries = list(enumerate(payloads))
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, _make_eexec_with_subrs(entries, length=4))
    subrs = parser.font_dict["Private"]["Subrs"]
    assert len(subrs) == 4
    for i, expected in enumerate(payloads):
        assert subrs[i] == expected, f"slot {i} mismatch"


def test_subrs_dispatch_out_of_order_declaration_preserves_slot_index() -> None:
    # Declare entries in 3, 1, 0, 2 order. The slot list must end up
    # with payload[K] in slot K regardless.
    payloads = {
        0: b"slot-0",
        1: b"slot-1",
        2: b"slot-2",
        3: b"slot-3",
    }
    decl_order = [3, 1, 0, 2]
    entries = [(k, payloads[k]) for k in decl_order]
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, _make_eexec_with_subrs(entries, length=4))
    subrs = parser.font_dict["Private"]["Subrs"]
    assert subrs[0] == b"slot-0"
    assert subrs[1] == b"slot-1"
    assert subrs[2] == b"slot-2"
    assert subrs[3] == b"slot-3"


def test_subrs_unused_slots_remain_empty_bytes() -> None:
    # Array length 5 but only slots 0 and 4 populated.
    entries = [(0, b"first"), (4, b"last")]
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, _make_eexec_with_subrs(entries, length=5))
    subrs = parser.font_dict["Private"]["Subrs"]
    assert len(subrs) == 5
    assert subrs[0] == b"first"
    assert subrs[4] == b"last"
    # Unused slots are empty bytes (NOT None).
    assert subrs[1] == b""
    assert subrs[2] == b""
    assert subrs[3] == b""


def test_subrs_no_bias_index_zero_is_first_slot() -> None:
    # Type 1 has NO subr bias — index 0 IS slot 0. (CFF/Type 2 biases.)
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, _make_eexec_with_subrs([(0, b"bias-check")], length=1))
    assert parser.font_dict["Private"]["Subrs"][0] == b"bias-check"


# ---------- subr cipher: must use charstring key 4330, not eexec 55665 ----------


def test_subr_payload_uses_charstring_cipher_not_eexec() -> None:
    # If the parser mistakenly tried to decrypt with the EEXEC seed it
    # would produce different bytes. A round-trip via the charstring
    # encryptor + parser decrypt confirms key 4330 is in use.
    plain = b"\x0d\x0e"  # closepath, endchar
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, _make_eexec_with_subrs([(0, plain)], length=1))
    assert parser.font_dict["Private"]["Subrs"][0] == plain


# ---------- variable len_iv ----------


@pytest.mark.parametrize("len_iv", [0, 4, 8], ids=["leniv_0", "leniv_4", "leniv_8"])
def test_subr_payload_round_trip_with_explicit_len_iv(len_iv: int) -> None:
    plain = b"hsbw rmoveto endchar"
    # Build an eexec body that declares /lenIV explicitly so the parser
    # picks it up before reading the Subrs.
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=len_iv)
    body = (
        b"dup /Private 5 dict dup begin\n"
        + f"/lenIV {len_iv} def\n".encode("latin-1")
        + b"/Subrs 1 array\n"
        + f"dup 0 {len(cipher)} RD ".encode("latin-1")
        + cipher
        + b" NP\n"
        + b"def\n"
        + b"/CharStrings 0 dict dup begin end\nend\n"
    )
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, Type1FontUtil.eexec_encrypt(body))
    assert parser.font_dict["Private"]["Subrs"][0] == plain


# ---------- known subr opcodes ----------


def test_subr_payload_with_callsubr_opcodes_round_trips() -> None:
    # 0x0a is the Type 1 charstring ``callsubr`` opcode (consumes one
    # number then dispatches). The cipher must NOT inspect or alter
    # these bytes — they are opaque to the parser.
    plain = bytes([0x80, 0x05, 0x0a, 0x0e])  # int 5, callsubr, endchar
    parser = Type1Parser()
    parser.parse(_PFA_HEADER, _make_eexec_with_subrs([(0, plain)], length=1))
    assert parser.font_dict["Private"]["Subrs"][0] == plain


# ---------- accessor surface ----------


def test_subrs_array_accessor_via_type1_font() -> None:
    # Verify the high-level Type1Font.get_subrs_array surfaces the
    # parser's slot list intact.
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    payloads = [b"\x0e", b"\x0d\x0e", b"\x80\x05\x0a\x0e"]
    entries = list(enumerate(payloads))
    cipher = _make_eexec_with_subrs(entries, length=3)
    font = Type1Font.create_with_segments(_PFA_HEADER, cipher)
    arr = font.get_subrs_array()
    assert arr == payloads
