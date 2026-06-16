"""Live PDFBox differential edge-fuzz for the COSString text-decode and
COSFloat / COSInteger leaf surfaces (pypdfbox parity wave 1544).

Combines three projections into one probe (``CosStringNumberFuzzProbe``) at
angles the existing per-surface probes do not pin together:

* **COSString(byte[])**: ``getString()`` code points *and* ``toHexString()`` of
  the SAME stored payload — a decode-vs-store divergence shows up in one record.
  ``CosStringTextDecodeFuzzProbe`` pins only the code points.
* **COSFloat(String)**: the IEEE-754 single-precision bit pattern of
  ``floatValue()`` *and* the ``writePDF`` serialization (the bytes that reach a
  PDF). ``CosNumberFuzzProbe`` pins ``toString()`` via ``COSNumber.get``; here we
  drive the leaf constructor directly so the special-value / hex-float accept set
  is exercised.
* **COSInteger.get(long)**: ``intValue()`` int32-narrowing + ``longValue()`` +
  ``writePDF`` over huge / boundary / leading-zero literals.

REAL BUG FIXED THIS WAVE — ``_parse_float`` in ``pypdfbox/cos/cos_float.py``
now mirrors Java ``Float.parseFloat`` exactly: it accepts the case-sensitive
special spellings ``NaN`` / ``Infinity`` / ``-Infinity`` / ``+Infinity`` (with
surrounding whitespace) and hex floats carrying a binary exponent (``0x1p4`` →
16.0), while still rejecting the lenient Python spellings Java rejects
(``nan``, ``inf``, ``NAN``, ``INFINITY``, bare ``0x10``). Before the fix
``new COSFloat("NaN")`` / ``new COSFloat("Infinity")`` raised ``OSError`` where
Apache PDFBox 3.0.7 returns a NaN / MAX_VALUE float — a behavioural divergence
on the leaf constructor.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text


def _fbits_hex(value: float) -> str:
    """``Integer.toHexString(Float.floatToIntBits(f))`` — lowercase, no leading
    zeros; every NaN collapses to Java's canonical ``7fc00000``."""
    if value != value:  # NaN
        return "7fc00000"
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _code_point_hex(text: str) -> str:
    """Space-separated lowercase hex of each Unicode code point of ``text``."""
    return " ".join(f"{ord(c):x}" for c in text)


def _py_str_record(raw: bytes) -> str:
    cs = COSString(raw)
    return f"cp={_code_point_hex(cs.get_string())}|hex={cs.to_hex_string()}"


def _py_float_record(lit: str) -> str:
    try:
        f = COSFloat(lit)
    except (OSError, ValueError):
        return "error"
    buf = io.BytesIO()
    f.write_pdf(buf)
    fmt = buf.getvalue().decode("iso-8859-1")
    return f"ok|fbits={_fbits_hex(f.float_value())}|fmt={fmt}"


def _py_int_record(decimal: str) -> str:
    # The probe goes through Java ``Long.parseLong`` first; mirror that gate so
    # out-of-Long-range literals are an error on both sides.
    try:
        n = int(decimal)
    except ValueError:
        return "error"
    if not (-(2**63) <= n <= 2**63 - 1):
        return "error"
    ci = COSInteger.get(n)
    buf = io.BytesIO()
    ci.write_pdf(buf)
    w = buf.getvalue().decode("iso-8859-1")
    return f"i={ci.int_value()}|l={ci.long_value()}|w={w}"


# --------------------------------------------------------------------------- #
# COSString byte-decode corpus: (short_id, hexbytes). Passed to the probe as the
# literal stored byte payload (constructor path, NOT parseHex). IDs stay short
# (Windows 32 KB env-var cap on parametrize test IDs — see CLAUDE.md).
# --------------------------------------------------------------------------- #
_STR_CASES: tuple[tuple[str, str], ...] = (
    # ---- UTF-16BE / UTF-16LE BOM detection ----
    ("be_bom_A", "feff0041"),
    ("le_bom_A", "fffe4100"),
    ("be_bom_only", "feff"),
    ("le_bom_only", "fffe"),
    ("be_bom_null", "feff00"),  # BOM + trailing odd byte -> U+FFFD
    ("be_supplementary", "feffd83ddc00"),  # BOM + valid surrogate pair -> U+1F400
    # ---- raw surrogate bytes WITHOUT a BOM -> PDFDocEncoding, byte-per-byte ----
    ("raw_d83d", "d83d"),
    ("raw_dc00", "dc00"),
    ("raw_pair", "d83ddc00"),
    ("raw_high_then_ascii", "d83d0041"),
    # ---- embedded nulls / NUL-leading (no BOM) ----
    ("ascii_AB", "0041"),
    ("just_null", "00"),
    # ---- UTF-8 BOM: forward-port divergence (see CHANGES.md) ----
    ("utf8_bom_A", "efbbbf41"),
    # ---- PDFDocEncoding high-byte slots (table D.2) ----
    ("pde_80_bullet", "80"),
    ("pde_9f_undef", "9f"),  # undefined PDFDocEncoding slot -> U+FFFD
    ("pde_a0_euro", "a0"),
    ("pde_7f_undef", "7f"),  # 0x7F is undefined in PDFDocEncoding -> U+FFFD
    ("pde_18_breve", "18"),
    ("pde_17_ctrl", "17"),
    ("pde_run", "80818283"),
)

_STR_IDS = [c[0] for c in _STR_CASES]


# --------------------------------------------------------------------------- #
# COSFloat(String) corpus: (short_id, literal). Passed as hex of UTF-8 bytes.
# --------------------------------------------------------------------------- #
_FLOAT_CASES: tuple[tuple[str, str], ...] = (
    ("zero", "0.0"),
    ("neg_zero", "-0.0"),
    ("exp_e10", "1e10"),
    ("exp_upper_e_neg", "1E-10"),
    ("lead_dot", ".5"),
    ("trail_dot", "5."),
    ("trailing_zeros", "1.230000"),
    ("over", "1e40"),
    ("over_neg", "-1e40"),
    ("underflow", "1e-45"),
    ("min_value", "1.4e-45"),
    ("max_value", "3.4028235e38"),
    ("mixed", "12345.678"),
    ("tiny", "0.000001"),
    ("ten_million", "10000000"),
    ("nine_nines", "9999999"),
    # ---- malformed-real recovery (PDFBOX-2990 / -3500) ----
    ("rep_dbl_dash", "--16.33"),
    ("rep_zero_dash", "0.-262"),
    # ---- special values: case-sensitive, Java accepts only these spellings ----
    ("nan_exact", "NaN"),
    ("inf_exact", "Infinity"),
    ("inf_neg", "-Infinity"),
    ("inf_pos", "+Infinity"),
    ("inf_ws_trail", "Infinity "),
    ("inf_ws_lead", " Infinity"),
    ("hexfloat", "0x1p4"),
    # ---- spellings Java REJECTS (and so must pypdfbox) ----
    ("nan_lower", "nan"),
    ("inf_lower", "inf"),
    ("nan_upper", "NAN"),
    ("inf_upper", "INFINITY"),
    ("nan_suffix", "NaNx"),
    ("hex_no_p", "0x10"),
    ("alpha", "abc"),
)

_FLOAT_IDS = [c[0] for c in _FLOAT_CASES]


# --------------------------------------------------------------------------- #
# COSInteger.get(long) corpus: (short_id, decimal-literal in Long range).
# --------------------------------------------------------------------------- #
_INT_CASES: tuple[tuple[str, str], ...] = (
    ("zero", "0"),
    ("neg_zero", "-0"),
    ("cache_hi_edge", "256"),
    ("cache_hi_out", "257"),
    ("cache_lo_edge", "-100"),
    ("cache_lo_out", "-101"),
    ("i32_max", "2147483647"),
    ("i32_max_p1", "2147483648"),
    ("wrap_4g", "4294967296"),
    ("long_max", "9223372036854775807"),
    ("long_min", "-9223372036854775808"),
    ("lead_zeros", "007"),
)

_INT_IDS = [c[0] for c in _INT_CASES]


# PINNED DIVERGENCE (already recorded in CHANGES.md): pypdfbox forward-ports the
# PDF 2.0 / PDFBox 4.0 UTF-8-BOM branch — ``EF BB BF`` is stripped and the rest
# decoded as UTF-8 ("A"). The pinned baseline (PDFBox 3.0.7) has no such branch
# and decodes those bytes as PDFDocEncoding (cp=ef bb bf 41). Asserted both-sides
# so the divergence stays documented, not silently drifting.
_STR_PINNED_DIVERGENT = {"efbbbf41"}


@requires_oracle
@pytest.mark.parametrize(
    ("hexbytes"), [c[1] for c in _STR_CASES], ids=_STR_IDS
)
def test_cos_string_decode_matches_pdfbox(hexbytes: str) -> None:
    java = run_probe_text("CosStringNumberFuzzProbe", "str", hexbytes).strip()
    py = _py_str_record(bytes.fromhex(hexbytes))
    if hexbytes in _STR_PINNED_DIVERGENT:
        # PDFBox 3.0.7 PDFDocEncodes the BOM bytes; pypdfbox strips + UTF-8s.
        assert java == "cp=ef bb bf 41|hex=EFBBBF41"
        assert py == "cp=41|hex=EFBBBF41"
    else:
        assert py == java


@requires_oracle
@pytest.mark.parametrize(("lit"), [c[1] for c in _FLOAT_CASES], ids=_FLOAT_IDS)
def test_cos_float_construct_matches_pdfbox(lit: str) -> None:
    java = run_probe_text(
        "CosStringNumberFuzzProbe", "float", lit.encode("utf-8").hex()
    ).strip()
    py = _py_float_record(lit)
    assert py == java


@requires_oracle
@pytest.mark.parametrize(("decimal"), [c[1] for c in _INT_CASES], ids=_INT_IDS)
def test_cos_integer_get_matches_pdfbox(decimal: str) -> None:
    java = run_probe_text("CosStringNumberFuzzProbe", "int", decimal).strip()
    py = _py_int_record(decimal)
    assert py == java


# --------------------------------------------------------------------------- #
# Oracle-independent regression pins for the wave-1544 ``_parse_float`` fix.
# Values translated from Apache PDFBox 3.0.7 / OpenJDK ``Float.parseFloat``.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("lit", "fbits", "fmt"),
    [
        ("NaN", "7fc00000", "NaN"),
        ("Infinity", "7f7fffff", "340282350000000000000000000000000000000"),
        ("-Infinity", "ff7fffff", "-340282350000000000000000000000000000000"),
        ("+Infinity", "7f7fffff", "340282350000000000000000000000000000000"),
        ("Infinity ", "7f7fffff", "340282350000000000000000000000000000000"),
        (" Infinity", "7f7fffff", "340282350000000000000000000000000000000"),
        ("0x1p4", "41800000", "0x1p4"),
    ],
    ids=[
        "nan",
        "inf",
        "inf_neg",
        "inf_pos",
        "inf_ws_trail",
        "inf_ws_lead",
        "hexfloat",
    ],
)
def test_float_special_values_accepted(lit: str, fbits: str, fmt: str) -> None:
    assert _py_float_record(lit) == f"ok|fbits={fbits}|fmt={fmt}"


@pytest.mark.parametrize(
    "lit",
    ["nan", "inf", "NAN", "INFINITY", "NaNx", "0x10", "abc", "Inf", "iNfInItY"],
)
def test_float_lenient_spellings_rejected(lit: str) -> None:
    """Java ``Float.parseFloat`` rejects these; the malformed-number repair
    path also can't fix them, so ``COSFloat(String)`` raises ``OSError``."""
    with pytest.raises(OSError):
        COSFloat(lit)


def test_int_value_int32_narrowing() -> None:
    """``intValue()`` narrows like the JVM ``(int)`` cast; ``longValue()`` keeps
    the full value (Java would store it as a 64-bit long)."""
    assert COSInteger.get(2147483648).int_value() == -2147483648
    assert COSInteger.get(2147483648).long_value() == 2147483648
    assert COSInteger.get(2**63 - 1).int_value() == -1


def test_string_bom_decode_and_hex_roundtrip() -> None:
    """``getString`` honours the BOM while ``toHexString`` always reflects the
    raw stored bytes verbatim (the writer's round-trip contract)."""
    be = COSString(bytes.fromhex("feff0041"))
    assert be.get_string() == "A"
    assert be.to_hex_string() == "FEFF0041"
    # Raw surrogate byte with no BOM is PDFDocEncoded byte-per-byte, not UTF-16.
    raw = COSString(bytes.fromhex("d83d"))
    assert raw.to_hex_string() == "D83D"
    assert len(raw.get_string()) == 2
