"""Live PDFBox differential parity for COSString *raw-byte text decoding*
(wave 1523).

Distinct surface from ``test_cos_string_text_oracle.py`` (which builds the
COSString via ``parseHex`` and shares its battery with the date parser) and
from the literal-escape / write probes: this drives the
``new COSString(byte[]).getString()`` path — how a *stored byte payload*
becomes a Unicode text string — through the live ``CosStringTextDecodeFuzzProbe``
against PDFBox 3.0.7.

Focus areas: empty bytes, lone BOMs with no payload, incomplete UTF-16 units,
malformed UTF-16 surrogate sequences (lone high / low, high+non-low,
high+truncation), PDFDocEncoding undefined slots (0x7F / 0x9F → U+FFFD), the
NUL-defaulted 0xAD, the full 0x80-0xA0 special range, embedded NULs, and no-BOM
bytes that resemble UTF-16.

Each ``CASES`` entry is just the literal stored byte payload as hex; the oracle
supplies the expected code-point fingerprint, so a regression in pypdfbox's
decoder is caught against Java's actual output rather than a hand-translated
expectation.

The UTF-8-BOM cases live in their own test: pypdfbox forward-ports PDF 2.0 §
7.9.2.2 (strip ``EF BB BF``, decode UTF-8) while PDFBox 3.0.7 decodes those
bytes as PDFDocEncoding. That divergence is pinned BOTH sides (CHANGES.md).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text

# Short id -> stored byte payload (hex). Ids stay short (Windows 32 KB env cap).
CASES: dict[str, str] = {
    # --- empty / lone BOMs (no payload) ---------------------------------- #
    "empty": "",
    "be_bom_only": "feff",
    "le_bom_only": "fffe",
    # --- incomplete UTF-16 units (odd trailing byte after BOM) ----------- #
    "be_odd1": "feffff",
    "be_a_odd": "feff0041ff",
    "le_odd1": "fffeff",
    "le_a_odd": "fffe4100ff",
    # --- UTF-16BE surrogate edge cases ----------------------------------- #
    "be_pair": "feffd83dde00",  # valid pair -> U+1F600
    "be_two_pairs": "feffd83dde00d83dde01",
    "be_lone_high": "feffd83d",  # high at EOF -> one U+FFFD
    "be_lone_low": "feffde00",  # lone low -> one U+FFFD
    "be_high_high": "feffd83dd83d",  # high+high -> ONE U+FFFD (Java rule)
    "be_high_ascii": "feffd83d0041",  # high+BMP -> ONE U+FFFD (A dropped)
    "be_a_high_a": "feff0041d83d0042",  # A, then high+A -> '41 fffd'
    "be_pair_high": "feffd83dde00d83d",  # pair + lone high
    "be_low_low": "feffde00de01",
    "be_a_low_a": "feff0041de000042",
    "be_high_byte": "feffd83dde",  # high + 1 byte -> one U+FFFD
    "be_e9": "feff00e9",  # é
    # --- UTF-16LE surrogate edge cases ----------------------------------- #
    "le_pair": "fffe3dd800de",
    "le_lone_high": "fffe3dd8",
    "le_lone_low": "fffe00de",
    "le_high_ascii": "fffe3dd84100",
    "le_a_low_a": "fffe410000de4200",
    # --- PDFDocEncoding identity / ASCII --------------------------------- #
    "ascii": "48656c6c6f",  # 'Hello'
    "ascii_nul": "41424300",  # 'ABC' + NUL
    "iso_e9": "e9",  # é identity slot
    # --- PDFDocEncoding high-range deviations (0x80-0xA0) ----------------- #
    "pde_lo_run": "808182838485868788898a8b8c8d8e8f90",
    "pde_hi_run": "9192939495969798999a9b9c9d9e9fa0",
    "pde_euro": "a0",
    # --- PDFDocEncoding undefined / NUL-default slots -------------------- #
    "pde_7f": "7f",  # undefined -> U+FFFD
    "pde_9f": "9f",  # undefined -> U+FFFD
    "pde_ad": "ad",  # SOFT HYPHEN undefined -> U+0000 (int[] default)
    "pde_block1": "18191a1b1c1d1e1f",  # 0x18-0x1F deviations
    # --- embedded NULs --------------------------------------------------- #
    "nul_mid": "41004200",  # 'A' NUL 'B' NUL (no BOM -> PDFDocEncoding)
    "nul_only": "00",
    # --- no-BOM bytes that look like UTF-16 ------------------------------ #
    "looks_be": "00410042",  # decoded as PDFDocEncoding, not UTF-16
    "fe_only": "fe",  # single 0xFE -> thorn
    "ff_only": "ff",  # single 0xFF -> ydieresis
}


def _py_codepoint_hex(hex_payload: str) -> str:
    """pypdfbox ``new COSString(bytes).get_string()`` as code-point hex."""
    s = COSString(bytes.fromhex(hex_payload)).get_string()
    return " ".join(format(ord(ch), "x") for ch in s)


@requires_oracle
@pytest.mark.parametrize("payload", list(CASES.values()), ids=list(CASES.keys()))
def test_cos_string_raw_decode_matches_pdfbox(payload: str) -> None:
    java = run_probe_text("CosStringTextDecodeFuzzProbe", payload)
    assert _py_codepoint_hex(payload) == java


# --------------------------------------------------------------------------- #
# UTF-8 BOM: documented forward-port divergence, pinned BOTH sides.
# --------------------------------------------------------------------------- #

# Short id -> (stored bytes hex, expected pypdfbox code-point hex).
_UTF8_BOM_CASES: dict[str, tuple[str, str]] = {
    "bom_only": ("efbbbf", ""),  # BOM stripped, empty remainder
    "bom_ascii": ("efbbbf41", "41"),  # 'A'
    "bom_2byte": ("efbbbfc3a9", "e9"),  # é via UTF-8
    "bom_bad_cont": ("efbbbfc328", "fffd 28"),  # bad continuation -> U+FFFD
    "bom_lone_cont": ("efbbbf80", "fffd"),  # lone continuation -> U+FFFD
}


@requires_oracle
@pytest.mark.parametrize(
    ("payload", "expected_py"),
    list(_UTF8_BOM_CASES.values()),
    ids=list(_UTF8_BOM_CASES.keys()),
)
def test_utf8_bom_divergence_pinned_both_sides(payload: str, expected_py: str) -> None:
    """pypdfbox strips a UTF-8 BOM and decodes UTF-8 (PDF 2.0 forward-port);
    PDFBox 3.0.7 has no such branch and decodes the bytes as PDFDocEncoding.
    Pin pypdfbox's behaviour AND confirm Java genuinely differs so the
    divergence stays load-bearing (CHANGES.md)."""
    py = _py_codepoint_hex(payload)
    assert py == expected_py
    java = run_probe_text("CosStringTextDecodeFuzzProbe", payload)
    assert java != py  # PDFBox 3.0.7 keeps the BOM as PDFDocEncoding bytes
