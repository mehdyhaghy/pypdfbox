"""Differential Type 1 (.pfb) parse fuzz vs Apache FontBox 3.0.7 (wave 1507).

The Type 1 sibling of the wave-1507 bare-CFF parse fuzz
(``tests/fontbox/cff/oracle/test_cff_parse_fuzz_oracle.py``) and the wave-1506
TTF/OTF parse fuzz, applying the same deterministic-corpus method to the
*lenient Type 1 parse contract* — the path ``Type1Font.create_with_pfb(bytes)``
drives when it is handed a (possibly malformed) .pfb font program.

Unlike the CFF arm (which is fontTools-backed and so mostly characterises
library gaps), pypdfbox's Type 1 parser is a hand port of upstream
``Type1Parser`` / ``Type1Lexer`` / ``PfbParser``, so this arm is a sharp port
regression-pin: nearly every mutation produces the *identical* projection on
both engines.

For a small bundled base .pfb (``DemoType1.pfb``) we apply a fixed set of
byte-level mutations that exercise the PFB record demuxer and the cleartext /
eexec parser: PFB segment-header corruption (bad start marker, bad record type,
record-size lies — huge / negative / zero / short), truncations at structural
points, eexec binary corruption (byte flips inside segment 2), and cleartext
token corruption (/FontName, /Encoding). Both engines parse the *identical*
bytes and are compared on a stable projection:

    ok=true
    name=<PostScript name>
    fontName=<FontName>
    nGlyphs=<int>
    subrs=<int>
    wA=<advance width of glyph "A">
    enc65=<encoding glyph name for code 65>

or the sole line ``ok=false`` on any parse-time throw. The Java side is
``oracle/probes/Type1ParserFuzzProbe.java`` (parses via
``Type1Font.createWithPFB(bytes)``); ``_py_dump`` reproduces the same
fingerprint on the pypdfbox side.

BUG FIXED IN THIS WAVE. Building this corpus surfaced a real divergence: a .pfb
with a missing / truncated segment 2 (empty eexec block) made pypdfbox's
``create_with_pfb`` raise ``ValueError`` from the eexec decryptor, while
upstream ``Type1Parser.decrypt`` returns an empty plaintext for an empty /
short ciphertext (``cipherBytes.length == 0 || n > cipherBytes.length``) and so
parses to an empty font. Fixed in ``type1_parser.py`` (apply upstream's lenient
empty-ciphertext guard at the eexec call site) + ``type1_font.py``
(``_charstrings_dict`` defaults to ``{}`` like upstream's always-initialised
``charstrings`` LinkedHashMap). See CHANGES.md.

DOCUMENTED DIVERGENCES (NOT pinned):
  * *Tolerant binary-segment parse.* pypdfbox's ``Type1Parser.parse`` wraps the
    eexec/Private second-stage parse in a best-effort try/except (a pre-existing
    documented divergence), so a *garbled* (non-empty) eexec block parses to an
    empty font (ok=true) where upstream throws (ok=false). The empty-eexec case
    above is genuine leniency parity; the garbled-eexec case is the broader
    tolerant-defaults divergence and is excluded.
  * *Empty-font width fallback.* ``get_width`` of a missing glyph returns 0.0 in
    pypdfbox vs an upstream throw when there is no ``.notdef`` either, so the
    empty-font (``trunc_seg1_only``) projection differs on the ``wA`` field
    only; excluded.

Deterministic generator, fixed PRNG seed ``random.Random(1507)``.
"""

from __future__ import annotations

import os
import random
import struct
import tempfile
from contextlib import suppress
from pathlib import Path

import pytest

from pypdfbox.fontbox.type1.type1_font import Type1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_RNG = random.Random(1507)

_REPO = Path(__file__).resolve().parents[4]
_T1_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "type1"
_BASE_PATH = _T1_FIXTURES / "DemoType1.pfb"
_BASE = bytearray(_BASE_PATH.read_bytes()) if _BASE_PATH.is_file() else bytearray()

# PFB record layout of DemoType1.pfb (derived once at import):
#   rec1 ASCII  @0    0x80 0x01 size=501  payload[6:507]
#   rec2 BINARY @507  0x80 0x02 size=523  payload[513:1036]
#   rec3 ASCII  @1036 0x80 0x01 size=552  payload[1042:1594]  (cleartomark)
#   EOF         @1594 0x80 0x03
_REC1_SIZE_OFF = 2
_SEG2_HDR = 507  # 0x80 marker of segment 2
_SEG2_TYPE = 508
_SEG2_SIZE_OFF = 509
_SEG2_DATA = 513
_SEG2_DATA_END = 1036

_PROBE_GLYPH = "A"
_PROBE_CODE = 65


_Mut = tuple[str, bytes]


def _put(base: bytearray, offset: int, fmt: str, value: int) -> bytearray:
    b = bytearray(base)
    struct.pack_into(fmt, b, offset, value)
    return b


def _set(base: bytearray, offset: int, value: int) -> bytearray:
    b = bytearray(base)
    b[offset] = value
    return b


def _find(tok: bytes) -> int:
    return _BASE.find(tok)


def _generate_corpus() -> list[_Mut]:
    if not _BASE:
        return []
    base = _BASE
    out: list[_Mut] = [("clean", bytes(base))]

    # -- PFB segment-header corruption ----------------------------------
    out.append(("rec1_marker_bad", bytes(_set(base, 0, 0x81))))
    out.append(("rec1_type_bad", bytes(_set(base, 1, 9))))
    out.append(("rec1_size_huge", bytes(_put(base, _REC1_SIZE_OFF, "<i", 0x7FFFFFFF))))
    out.append(("rec1_size_neg", bytes(_put(base, _REC1_SIZE_OFF, "<i", -5))))
    out.append(("rec1_size_zero", bytes(_put(base, _REC1_SIZE_OFF, "<i", 0))))
    out.append(("rec1_size_short", bytes(_put(base, _REC1_SIZE_OFF, "<i", 100))))
    out.append(("rec2_marker_bad", bytes(_set(base, _SEG2_HDR, 0x00))))
    out.append(("rec2_type_bad", bytes(_set(base, _SEG2_TYPE, 7))))
    out.append(("rec2_size_huge", bytes(_put(base, _SEG2_SIZE_OFF, "<i", 0x7FFFFFFF))))
    out.append(("rec2_size_neg", bytes(_put(base, _SEG2_SIZE_OFF, "<i", -1))))
    out.append(("rec2_size_zero", bytes(_put(base, _SEG2_SIZE_OFF, "<i", 0))))

    # -- truncations at structural points -------------------------------
    out.append(("trunc_empty", b""))
    out.append(("trunc_1", bytes(base[:1])))
    out.append(("trunc_6", bytes(base[:6])))
    out.append(("trunc_mid_seg1", bytes(base[:200])))
    out.append(("trunc_mid_seg2", bytes(base[:700])))
    out.append(("trunc_before_eof", bytes(base[:1594])))

    # -- eexec binary corruption (last-byte flip is tolerated by both;
    #    earlier flips fall into the tolerant-defaults divergence and are
    #    excluded) --------------------------------------------------------
    out.append(
        ("seg2_last_flip", bytes(_set(base, _SEG2_DATA_END - 1, base[_SEG2_DATA_END - 1] ^ 0xFF)))
    )

    # -- cleartext token corruption -------------------------------------
    fontname_off = _find(b"/FontName")
    encoding_off = _find(b"/Encoding")
    if fontname_off >= 0:
        out.append(("fontname_token_garbled", bytes(_set(base, fontname_off + 1, ord("X")))))
    if encoding_off >= 0:
        out.append(("encoding_token_garbled", bytes(_set(base, encoding_off + 1, ord("X")))))

    # -- deterministic random flips inside the segment-2 *binary header*
    #    (the 0x80/type/size record header bytes 507..512). A flip there
    #    corrupts the record geometry so both engines reject (bad marker /
    #    type / size). Flips in the eexec *payload* fall into the
    #    tolerant-defaults divergence and are excluded. ------------------
    for i in range(4):
        b = bytearray(base)
        pos = _RNG.randrange(_SEG2_HDR, _SEG2_DATA)
        b[pos] ^= 1 << _RNG.randrange(8)
        out.append((f"seg2_hdr_rand_flip_{i}", bytes(b)))

    return out


_CORPUS = _generate_corpus()
_CORPUS_IDS = [m[0] for m in _CORPUS]


def _fmt_width(w: object) -> str:
    try:
        wf = float(w)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(w)
    if wf == int(wf):
        return str(int(wf))
    return repr(wf)


def _py_dump(mutated: bytes) -> str:
    try:
        font = Type1Font.create_with_pfb(mutated)
    except Exception:
        return "ok=false\n"
    try:
        cs = font.get_char_strings_dict()
        try:
            subrs = len(font.get_subrs_array())
        except Exception:
            subrs = -1
        try:
            wa = _fmt_width(font.get_width(_PROBE_GLYPH))
        except Exception:
            wa = "-1"
        try:
            enc = font.get_encoding()
            enc65 = enc.get(_PROBE_CODE, "?") if isinstance(enc, dict) else "?"
        except Exception:
            enc65 = "?"
        lines = [
            "ok=true",
            f"name={font.get_name()}",
            f"fontName={font.get_font_name()}",
            f"nGlyphs={len(cs)}",
            f"subrs={subrs}",
            f"wA={wa}",
            f"enc65={enc65}",
        ]
        return "\n".join(lines) + "\n"
    except Exception:
        return "ok=false\n"


def _java_dump(mutated: bytes) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".pfb")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(mutated)
        return run_probe_text("Type1ParserFuzzProbe", tmp)
    finally:
        with suppress(OSError):
            os.unlink(tmp)


@requires_oracle
@pytest.mark.skipif(not _CORPUS, reason="base PFB fixture missing")
@pytest.mark.parametrize(("name", "mutated"), _CORPUS, ids=_CORPUS_IDS)
def test_type1_parse_fuzz_parity(name: str, mutated: bytes) -> None:
    java = _java_dump(mutated)
    py = _py_dump(mutated)
    assert py == java, (
        f"divergence on Type1 parse mutant {name!r}:\n java={java!r}\n  py={py!r}"
    )


@pytest.mark.skipif(not _CORPUS, reason="base PFB fixture missing")
def test_clean_base_projection_non_trivial() -> None:
    dump = _py_dump(bytes(_BASE))
    assert dump.startswith("ok=true\n")
    assert "name=DemoType1" in dump
    assert "nGlyphs=5" in dump
    assert "wA=600" in dump
    assert "enc65=A" in dump
