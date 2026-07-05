"""Fuzz + live-oracle parity for ``SaslPrep`` (RFC 4013, wave 1598).

Targets ``org.apache.pdfbox.pdmodel.encryption.SaslPrep`` — the password
canonicalisation the R6/AES-256 security handler applies before UTF-8
encoding (``saslPrepQuery`` at parse time, ``saslPrepStored`` at encrypt
time). A divergence here is user-visible as "PDFBox opens the document but
pypdfbox does not" (or vice versa) for any non-trivial Unicode password.

Two layers:

* Pinned tests (run everywhere) — expectations verified against the live
  PDFBox 3.0.7 oracle on 2026-07-05, covering the RFC 4013 mapping /
  normalisation / prohibition / bidi steps and the upstream ``(char)``
  narrowing quirk in ``prohibited(int)`` (astral codepoints whose low 16
  bits alias a non-ASCII space or ASCII control are prohibited: U+12000
  aliases U+2000, U+10000 aliases U+0000, ...). Wave 1598 fixed pypdfbox to
  mirror that truncation.

* Live differentials (``requires_oracle``) — drive the same case table plus
  a seeded random battery through ``SaslPrepFuzzProbe`` and compare
  ok/error status and result codepoints one-to-one.

Unicode-version note: the dev interpreter ships Unicode 16 data while Java
21 ships Unicode 15.x; the case table deliberately avoids codepoints whose
assignment status or properties changed between those versions.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.pdmodel.encryption.sasl_prep import SaslPrep
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Shared case table (mode, codepoints) — mirrored 1:1 by the Java probe.      #
# --------------------------------------------------------------------------- #

_CASES: list[tuple[str, tuple[int, ...]]] = [
    # -- basics / RFC 4013 §3 examples -------------------------------------
    ("Q", (0x75, 0x73, 0x65, 0x72)),  # "user"
    ("S", (0x55, 0x53, 0x45, 0x52)),  # "USER"
    ("Q", ()),  # empty string
    ("Q", (0x49, 0x00AD, 0x58)),  # I<soft hyphen>X -> IX
    ("Q", (0x00AA,)),  # FEMININE ORDINAL -> a
    ("S", (0x2168,)),  # ROMAN NUMERAL NINE -> IX
    ("Q", (0x0007,)),  # BEL -> prohibited
    ("Q", (0x0627, 0x0031)),  # ALEF + digit -> bidi error
    # -- step 1: non-ASCII spaces map to U+0020 -----------------------------
    ("Q", (0x61, 0x00A0, 0x62)),
    ("Q", (0x61, 0x1680, 0x62)),
    ("Q", (0x61, 0x2000, 0x62)),
    ("Q", (0x61, 0x2003, 0x62)),
    ("S", (0x61, 0x200B, 0x62)),  # ZWSP is space-mapped BEFORE mapped-to-nothing
    ("Q", (0x61, 0x202F, 0x62)),
    ("Q", (0x61, 0x205F, 0x62)),
    ("S", (0x61, 0x3000, 0x62)),
    # -- step 1: mapped-to-nothing dropped ----------------------------------
    ("Q", (0x61, 0x00AD, 0x62)),
    ("Q", (0x61, 0x034F, 0x62)),
    ("S", (0x61, 0x1806, 0x62)),
    ("Q", (0x61, 0x180B, 0x62)),
    ("Q", (0x61, 0x200C, 0x62)),  # ZWNJ dropped (also nonAsciiControl — drop wins)
    ("Q", (0x61, 0x200D, 0x62)),
    ("S", (0x61, 0x2060, 0x62)),
    ("Q", (0x61, 0xFE00, 0x62)),
    ("Q", (0x61, 0xFE0F, 0x62)),
    ("Q", (0x61, 0xFEFF, 0x62)),
    ("Q", (0xFEFF,)),  # BOM alone -> dropped -> empty result, NOT an error
    # -- step 2: NFKC before prohibition ------------------------------------
    ("Q", (0x61, 0xFB01)),  # fi ligature -> "afi"
    ("S", (0x0130,)),  # LATIN CAPITAL I WITH DOT ABOVE (stable under NFKC)
    ("Q", (0x61, 0x0340)),  # 0340 is changeDisplayProperties but NFKC -> 0300 first
    ("Q", (0x61, 0x0341)),  # -> 0301
    ("S", (0x2126,)),  # OHM SIGN -> GREEK CAPITAL OMEGA
    ("Q", (0xFF76,)),  # halfwidth katakana KA -> 30AB
    ("Q", (0xFDFA,)),  # ARABIC LIGATURE SLM -> multi-char expansion w/ spaces
    # -- step 3: prohibited singletons --------------------------------------
    ("Q", (0x0000,)),
    ("S", (0x001F,)),
    ("Q", (0x007F,)),
    ("Q", (0x0080,)),
    ("S", (0x009F,)),
    ("Q", (0x06DD,)),  # ARABIC END OF AYAH (nonAsciiControl)
    ("Q", (0x070F,)),
    ("S", (0x180E,)),  # MONGOLIAN VOWEL SEPARATOR (nonAsciiControl, NOT dropped)
    ("Q", (0x2028,)),
    ("Q", (0x2029,)),
    ("Q", (0x2061,)),  # FUNCTION APPLICATION (nonAsciiControl, NOT dropped)
    ("S", (0x2063,)),
    ("Q", (0x200E,)),  # LRM (changeDisplayProperties)
    ("Q", (0x202E,)),  # RLO
    ("S", (0x206F,)),
    ("Q", (0x2FF0,)),  # ideographic description char (inappropriateForCanonical)
    ("Q", (0x2FFB,)),
    ("S", (0xFFF9,)),  # interlinear annotation anchor
    ("Q", (0xFFFC,)),
    ("Q", (0xFFFD,)),  # REPLACEMENT CHARACTER
    ("Q", (0xFDD0,)),  # noncharacter
    ("S", (0xFFFE,)),
    ("Q", (0xE000,)),  # private use
    ("Q", (0xF8FF,)),
    ("S", (0xF0000,)),
    ("Q", (0x10FFFD,)),
    ("Q", (0x1D173,)),  # musical symbol BEGIN BEAM (nonAsciiControl, astral)
    ("S", (0x1D17A,)),
    ("Q", (0xE0001,)),  # LANGUAGE TAG (tagging)
    ("Q", (0xE0020,)),
    ("S", (0xE007F,)),
    ("Q", (0x2FFFE,)),  # plane-2 noncharacter
    ("Q", (0x10FFFF,)),  # plane-16 noncharacter
    # -- lone surrogates -----------------------------------------------------
    ("Q", (0xD800,)),
    ("Q", (0xDC00,)),
    ("S", (0xD800, 0x61)),
    # -- upstream (char) narrowing quirk in prohibited(int) ------------------
    ("Q", (0x10000,)),  # LINEAR B SYLLABLE B008 A -> aliases U+0000 (asciiControl)
    ("Q", (0x1001F,)),  # aliases U+001F
    ("S", (0x2007F,)),  # CJK ext B -> aliases U+007F
    ("Q", (0x12000,)),  # CUNEIFORM SIGN A -> aliases U+2000 (nonAsciiSpace)
    ("Q", (0x1202F,)),  # aliases U+202F
    ("S", (0x1205F,)),  # aliases U+205F
    ("Q", (0x13000,)),  # EGYPTIAN HIEROGLYPH A001 -> aliases U+3000
    ("Q", (0x100A0,)),  # LINEAR B IDEOGRAM B107M -> aliases U+00A0
    ("Q", (0x1F600,)),  # emoji: aliases U+F600 (NOT prohibited — allowed)
    ("S", (0x1F600, 0x1F3FB)),  # emoji + modifier: allowed
    ("Q", (0x10400,)),  # DESERET CAPITAL LONG I: aliases U+0400 — allowed
    ("Q", (0xE0100,)),  # variation selector supplement: aliases U+0100 — allowed
    # -- bidi (RFC 3454 §6 as upstream implements it) ------------------------
    ("Q", (0x05D0, 0x05D1)),  # all RandAL -> ok
    ("Q", (0x0627, 0x0644)),  # Arabic -> ok
    ("S", (0x05D0,)),  # single RandAL char (first == last) -> ok
    ("Q", (0x05D0, 0x61)),  # RandAL then L -> error
    ("Q", (0x61, 0x05D0)),  # L then RandAL -> error (contains both)
    ("Q", (0x05D0, 0x31)),  # RandAL first, EN last -> error (last not RandAL)
    ("Q", (0x31, 0x05D0)),  # EN first, RandAL last -> upstream allows
    ("S", (0x05D0, 0x20, 0x05D1)),  # RandAL with interior space -> ok
    ("Q", (0x05D0, 0x00A0, 0x05D1)),  # space-mapped interior -> ok
    ("Q", (0x05D0, 0x200D, 0x05D1)),  # ZWJ dropped -> ok
    ("Q", (0x05D0, 0x0378, 0x05D1)),  # unassigned mid-string, query -> ok
    # -- step 4: unassigned --------------------------------------------------
    ("Q", (0x0378,)),  # unassigned BMP: query allows
    ("S", (0x0378,)),  # ... stored rejects
    ("Q", (0x3FFFD,)),  # unassigned astral (no truncation alias): query allows
    ("S", (0x3FFFD,)),
]

# Seeded random battery over an alphabet mixing every behavioural class.
_ALPHABET = [
    0x61, 0x41, 0x31, 0x20,  # plain ASCII
    0x00AD, 0x1806, 0xFE0F, 0xFEFF,  # mapped to nothing
    0x00A0, 0x200B, 0x3000,  # space-mapped
    0xFB01, 0x2168, 0x0340, 0x2126,  # NFKC-unstable
    0x05D0, 0x0627,  # RandAL
    0x0007, 0x2028, 0x2061, 0xFFFD, 0xE000, 0xE0001,  # prohibited
    0x0378,  # unassigned
    0xD800, 0xDC00,  # lone surrogates
    0x1F600, 0x12000, 0x10000, 0x100A0, 0x3FFFD,  # astral incl. aliasing quirk
]
_rng = random.Random(1598)
for _i in range(24):
    _CASES.append(
        (
            "Q" if _i % 2 == 0 else "S",
            tuple(_rng.choice(_ALPHABET) for _ in range(_rng.randint(1, 6))),
        )
    )

# prohibited(int) predicate sweep (P-mode) — boundaries + truncation aliases.
_PREDICATE_CASES: list[int] = [
    0x0000, 0x001F, 0x0020, 0x007E, 0x007F, 0x0080, 0x009F, 0x00A0, 0x00A1,
    0x0340, 0x06DD, 0x070F, 0x1680, 0x180E,
    0x1FFF, 0x2000, 0x200B, 0x200C, 0x200E, 0x202E, 0x202F, 0x2030,
    0x205F, 0x2060, 0x2061, 0x2063, 0x2064, 0x206A, 0x206F, 0x2070,
    0x2FEF, 0x2FF0, 0x2FFB, 0x2FFC, 0x3000, 0x3001,
    0xD7FF, 0xD800, 0xDFFF, 0xE000, 0xF8FF, 0xF900,
    0xFDCF, 0xFDD0, 0xFDEF, 0xFDF0, 0xFEFF,
    0xFFF8, 0xFFF9, 0xFFFB, 0xFFFC, 0xFFFD, 0xFFFE, 0xFFFF,
    0x10000, 0x1001F, 0x10020, 0x100A0, 0x10400,
    0x12000, 0x1202F, 0x13000, 0x1D172, 0x1D173, 0x1D17A, 0x1D17B, 0x1F600,
    0x2007F, 0x2FFFE, 0x2FFFF, 0x30000,
    0xE0000, 0xE0001, 0xE0002, 0xE001F, 0xE0020, 0xE007F, 0xE0080, 0xE0100,
    0xEFFFE, 0xF0000, 0xFFFFD, 0xFFFFE,
    0x100000, 0x10FFFD, 0x10FFFE, 0x10FFFF,
]


def _py_line(mode: str, cps: tuple[int, ...]) -> str:
    """Run a case through pypdfbox; format like the probe's output line."""
    value = "".join(chr(cp) for cp in cps)
    fn = SaslPrep.sasl_prep_query if mode == "Q" else SaslPrep.sasl_prep_stored
    try:
        result = fn(value)
    except ValueError:
        return "ERR"
    if not result:
        return "OK"
    return "OK " + " ".join(f"{ord(ch):x}" for ch in result)


def _case_id(mode: str, cps: tuple[int, ...]) -> str:
    return mode + "_" + ("-".join(f"{cp:04x}" for cp in cps) or "empty")


# --------------------------------------------------------------------------- #
# Live differentials against PDFBox 3.0.7.                                    #
# --------------------------------------------------------------------------- #


@requires_oracle
def test_sasl_prep_query_stored_matches_pdfbox(tmp_path):
    infile = tmp_path / "cases.txt"
    lines = [
        mode + "".join(f" {cp:x}" for cp in cps) for mode, cps in _CASES
    ]
    infile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    java_lines = run_probe_text("SaslPrepFuzzProbe", str(infile)).splitlines()
    assert len(java_lines) == len(_CASES)
    mismatches = []
    for (mode, cps), java in zip(_CASES, java_lines, strict=True):
        py = _py_line(mode, cps)
        java_norm = "ERR" if java.startswith("ERR") else java
        if py != java_norm:
            mismatches.append(f"{_case_id(mode, cps)}: java={java!r} py={py!r}")
    assert not mismatches, "\n".join(mismatches)


@requires_oracle
def test_prohibited_predicate_matches_pdfbox(tmp_path):
    infile = tmp_path / "predicates.txt"
    infile.write_text(
        "".join(f"P {cp:x}\n" for cp in _PREDICATE_CASES), encoding="utf-8"
    )
    java_lines = run_probe_text("SaslPrepFuzzProbe", str(infile)).splitlines()
    assert len(java_lines) == len(_PREDICATE_CASES)
    mismatches = [
        f"U+{cp:04X}: java={java} py={int(SaslPrep.prohibited(cp))}"
        for cp, java in zip(_PREDICATE_CASES, java_lines, strict=True)
        if str(int(SaslPrep.prohibited(cp))) != java
    ]
    assert not mismatches, "\n".join(mismatches)


# --------------------------------------------------------------------------- #
# Pinned expectations (oracle-verified 2026-07-05) — run everywhere.          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cp",
    [0x10000, 0x1001F, 0x2007F, 0x12000, 0x1202F, 0x1205F, 0x13000, 0x100A0],
    ids=lambda cp: f"U+{cp:04X}",
)
def test_astral_low16_alias_is_prohibited(cp):
    """Upstream prohibited(int) narrows to char for the space/control checks."""
    assert SaslPrep.prohibited(cp)
    with pytest.raises(ValueError):
        SaslPrep.sasl_prep_query(chr(cp))
    with pytest.raises(ValueError):
        SaslPrep.sasl_prep_stored(chr(cp))


@pytest.mark.parametrize(
    "cp",
    [0x1F600, 0x10400, 0xE0100, 0x1D171],
    ids=lambda cp: f"U+{cp:04X}",
)
def test_astral_without_alias_is_allowed(cp):
    assert not SaslPrep.prohibited(cp)
    assert SaslPrep.sasl_prep_query(chr(cp)) == chr(cp)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("I\u00adX", "IX"),
        ("user", "user"),
        ("USER", "USER"),
        ("\u00aa", "a"),
        ("\u2168", "IX"),
        ("a\ufb01", "afi"),
        # U+0340/0341 are changeDisplayProperties-prohibited, but NFKC folds
        # them to U+0300/0301 (then composes with the base) BEFORE the
        # prohibition scan.
        ("a\u0340", "\u00e0"),
        ("a\u0341", "\u00e1"),
        ("\u2126", "\u03a9"),
        ("\uff76", "\u30ab"),
        (
            "\ufdfa",
            "\u0635\u0644\u0649 \u0627\u0644\u0644\u0647"
            " \u0639\u0644\u064a\u0647 \u0648\u0633\u0644\u0645",
        ),
        ("", ""),
        ("\ufeff", ""),  # BOM alone: dropped in step 1, empty result
    ],
    ids=[
        "soft_hyphen", "user", "USER", "feminine_ordinal", "roman_nine",
        "fi_ligature", "combining_grave_tone", "combining_acute_tone",
        "ohm_sign", "halfwidth_ka", "arabic_ligature_slm", "empty",
        "bom_alone",
    ],
)
def test_map_normalize_pinned(value, expected):
    assert SaslPrep.sasl_prep_query(value) == expected
    assert SaslPrep.sasl_prep_stored(value) == expected


@pytest.mark.parametrize(
    "cp",
    [0x00A0, 0x1680, 0x2000, 0x2003, 0x200B, 0x202F, 0x205F, 0x3000],
    ids=lambda cp: f"U+{cp:04X}",
)
def test_non_ascii_space_maps_to_space(cp):
    # U+200B is both space-mapped and mapped-to-nothing; upstream checks the
    # space table first, so it becomes ' ' rather than vanishing.
    assert SaslPrep.sasl_prep_query(f"a{chr(cp)}b") == "a b"


@pytest.mark.parametrize(
    "cp",
    [0x00AD, 0x034F, 0x1806, 0x180B, 0x200C, 0x200D, 0x2060, 0xFE00, 0xFE0F,
     0xFEFF],
    ids=lambda cp: f"U+{cp:04X}",
)
def test_mapped_to_nothing_dropped(cp):
    assert SaslPrep.sasl_prep_stored(f"a{chr(cp)}b") == "ab"


@pytest.mark.parametrize(
    "cp",
    [0x0000, 0x001F, 0x007F, 0x0080, 0x009F, 0x06DD, 0x070F, 0x180E, 0x2028,
     0x2029, 0x2061, 0x2063, 0x200E, 0x202E, 0x206F, 0x2FF0, 0x2FFB, 0xFFF9,
     0xFFFC, 0xFFFD, 0xFDD0, 0xFFFE, 0xE000, 0xF8FF, 0xF0000, 0x10FFFD,
     0x1D173, 0x1D17A, 0xE0001, 0xE0020, 0xE007F, 0x2FFFE, 0x10FFFF, 0xD800,
     0xDC00],
    ids=lambda cp: f"U+{cp:04X}",
)
def test_prohibited_singletons(cp):
    assert SaslPrep.prohibited(cp)
    with pytest.raises(ValueError):
        SaslPrep.sasl_prep_query(chr(cp))


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("\u05d0\u05d1", True),  # all RandAL
        ("\u0627\u0644", True),  # Arabic
        ("\u05d0", True),  # single char is its own first+last
        ("\u05d0a", False),  # RandAL first, L last
        ("a\u05d0", False),  # contains both L and RandAL
        ("\u05d01", False),  # RandAL first, EN last -> last not RandAL
        ("1\u05d0", True),  # EN first: upstream skips the first/last rule
        ("\u05d0 \u05d1", True),  # interior ASCII space
        ("\u05d0\u00a0\u05d1", True),  # interior space-mapped NBSP
        ("\u05d0\u200d\u05d1", True),  # interior ZWJ dropped
    ],
    ids=[
        "hebrew_pair", "arabic_pair", "single_hebrew", "randal_then_l",
        "l_then_randal", "randal_then_en", "en_then_randal",
        "interior_space", "interior_nbsp", "interior_zwj",
    ],
)
def test_bidi_rules(value, ok):
    if ok:
        assert SaslPrep.sasl_prep_query(value)
    else:
        with pytest.raises(ValueError):
            SaslPrep.sasl_prep_query(value)


@pytest.mark.parametrize(
    "cp", [0x0378, 0x3FFFD], ids=["U+0378", "U+3FFFD"]
)
def test_unassigned_query_allows_stored_rejects(cp):
    assert SaslPrep.sasl_prep_query(chr(cp)) == chr(cp)
    with pytest.raises(ValueError):
        SaslPrep.sasl_prep_stored(chr(cp))
