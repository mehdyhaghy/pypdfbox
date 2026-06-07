"""Live Apache PDFBox differential parse-fuzz for the embedded-CMap parser
(``CMapParser.parse(RandomAccessRead)``), wave 1508.

Same shape as the prior parse-fuzz waves (wave 1506 TTF, wave 1507 CFF/Type1):
a deterministic, seed-free corpus of *valid* ToUnicode / CID CMap source blobs
is mutated (truncation, malformed hex tokens, empty ``<>`` tokens, oversized /
mismatched codespace ranges, bfchar/bfrange over- and under-counts, reversed
ranges, the PDFBOX-4720 identity-bfrange special case, surrogate-pair and
3/4-byte dst values, cross-byte CID ranges, ``usecmap`` directives, nested
garbage dicts, missing ``end*`` operators, NUL whitespace padding) and fed to
*both* sides. The Java side runs ``oracle/probes/CMapParseFuzzProbe.java``
(``new CMapParser().parse(...)``); the Python side reconstructs the identical
projection so any divergence in tokenisation, lenient recovery, codespace
partitioning, CID/Unicode mapping or end-token handling surfaces as a single
differing line.

Projection (one block per blob), matching the probe verbatim::

    ok=false                         (sole line on any parse-time throw)
  -- or --
    ok=true
    name=<cmapName>
    wmode=<wmode>
    type=<cmapType>
    registry=<registry>
    ordering=<ordering>
    CID <codeHex> -> <cid> len=<readCodeLen>
    UNI <codeHex> -> U+XXXX[ U+YYYY...]   (or "(none)")

Two DOCUMENTED both-sides divergences are handled out-of-band rather than
asserted for line parity (see ``_NO_CODESPACE_CASES`` and CHANGES.md / wave
1508):

1. **No-codespace ``readCode`` (stream form).** When a blob is truncated (or
   otherwise corrupt) such that *no* ``begincodespacerange`` block is parsed,
   ``CMap`` keeps the constructor defaults ``minCodeLength=4``,
   ``maxCodeLength=0`` (verified against the 3.0.7 ``CMap.<init>`` bytecode).
   Upstream ``CMap.readCode(InputStream)`` then does
   ``new byte[maxCodeLength]`` → ``new byte[0]`` followed by
   ``in.read(bytes, 0, minCodeLength)`` i.e. ``read(byte[0], 0, 4)``, which
   throws ``IndexOutOfBoundsException`` on a ``ByteArrayInputStream`` (the
   probe reports ``len=-1``). pypdfbox **deliberately** hardens this path —
   ``_read_code_from_stream`` short-circuits ``max_len <= 0`` to "read one
   byte" (pinned by ``test_cmap.test_empty_cmap_read_code_reads_one_byte_
   without_crashing``). So the ``CID ... len=`` lines diverge (``-1`` vs ``1``)
   for these blobs even though the header projection and the resolved CID
   value (``0``) agree. We assert the header parity + the CID *value* parity
   for the no-codespace cases and pin the documented ``len`` divergence
   explicitly.

The inline ``/CIDSystemInfo << /Registry (..) /Ordering (..) >>`` dict form is
NOT used in this corpus for any registry/ordering assertion: upstream
``CMapParser`` populates Registry/Ordering only from top-level ``/Registry (..)
def`` literals, whereas pypdfbox additionally mines the inline dict (an
intentional enrichment landed in wave 1397 with its own branch-coverage tests).
The corpus therefore declares Registry/Ordering as top-level literals so the
two parsers agree on every blob.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

# A canonical 2-byte ToUnicode CMap with bfchar (incl. array-form bfrange).
_BASE = b"""%!PS-Adobe-3.0 Resource-CMap
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Adobe-Test-UCS2 def
/CMapType 2 def
/WMode 0 def
/Registry (Adobe) def
/Ordering (UCS) def
/Supplement 0 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
2 beginbfchar
<0001> <0041>
<0002> <0042>
endbfchar
2 beginbfrange
<0010> <0012> <0050>
<0020> <0022> [<0060> <0061> <0062>]
endbfrange
endcmap
end
end
"""

# A 2-band mixed-width CID CMap (Adobe-Japan1 shape).
_CID_BASE = b"""%!PS-Adobe-3.0
begincmap
/CMapName /CidTest def
/CMapType 1 def
/WMode 0 def
/Registry (Adobe) def
/Ordering (Japan1) def
/Supplement 0 def
2 begincodespacerange
<00> <80>
<8140> <9FFC>
endcodespacerange
2 begincidchar
<20> 1
<8140> 633
endcidchar
1 begincidrange
<8141> <817E> 634
endcidrange
endcmap
end
"""

# A 2-byte CMap with surrogate-pair / lone-surrogate dst values.
_SURROGATE = b"""%!PS-Adobe-3.0
begincmap
/CMapName /Surr def
/CMapType 2 def
/WMode 0 def
/Registry (Adobe) def
/Ordering (UCS) def
/Supplement 0 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
3 beginbfchar
<0001> <D83DDE00>
<0002> <D800>
<0003> <DC00>
endbfchar
endcmap
end
"""

# Probe codes exercised against every blob (mix of 1- and 2-byte widths).
_CODES = [
    "0001", "0002", "0003", "0010", "0011", "0012",
    "0020", "0021", "0022", "00", "20", "0099", "FFFF", "41", "0041",
    "8140", "8141", "817E",
]


def _mutants() -> dict[str, bytes]:
    """Deterministic, seed-free mutant corpus (no time/random source)."""
    m: dict[str, bytes] = {}

    # ---- valid baselines (negative controls) ----
    m["base"] = _BASE
    m["cid_base"] = _CID_BASE
    m["surrogate"] = _SURROGATE

    # ---- truncation (fixed fractions, deterministic) ----
    for pct in (30, 50, 70, 85, 95):
        m[f"trunc_{pct}"] = _BASE[: (len(_BASE) * pct) // 100]
    for pct in (40, 75):
        m[f"cid_trunc_{pct}"] = _CID_BASE[: (len(_CID_BASE) * pct) // 100]

    # ---- malformed hex tokens ----
    m["odd_hex"] = _BASE.replace(b"<0001>", b"<001>")
    m["bad_hex_char"] = _BASE.replace(b"<0001>", b"<00G1>")
    m["odd_hex_dst"] = _BASE.replace(b"<0001> <0041>", b"<0001> <041>")

    # ---- empty <> tokens ----
    m["empty_dst"] = _BASE.replace(b"<0001> <0041>", b"<0001> <>")
    m["empty_src"] = _BASE.replace(b"<0001> <0041>", b"<> <0041>")
    m["empty_array_entry"] = _BASE.replace(
        b"[<0060> <0061> <0062>]", b"[<0060> <> <0062>]"
    )

    # ---- surrogate / multi-byte dst ----
    m["astral_dst"] = _BASE.replace(b"<0001> <0041>", b"<0001> <D83DDE00>")
    m["three_byte_dst"] = _BASE.replace(b"<0001> <0041>", b"<0001> <01F600>")
    m["four_byte_dst"] = _BASE.replace(b"<0001> <0041>", b"<0001> <00410042>")

    # ---- codespace edge cases ----
    m["wide_codespace"] = _BASE.replace(b"<0000> <FFFF>", b"<000000> <FFFFFF>")
    m["codespace_len_mismatch"] = _BASE.replace(b"<0000> <FFFF>", b"<00> <FFFF>")
    m["dup_codespace"] = _BASE.replace(
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange",
        b"2 begincodespacerange\n<0000> <00FF>\n<0000> <FFFF>\nendcodespacerange",
    )

    # ---- bfchar / bfrange count mismatches ----
    m["bfchar_overcount"] = _BASE.replace(b"2 beginbfchar", b"5 beginbfchar")
    m["bfchar_undercount"] = _BASE.replace(b"2 beginbfchar", b"1 beginbfchar")
    m["bfrange_overcount"] = _BASE.replace(b"2 beginbfrange", b"9 beginbfrange")
    m["huge_count"] = _BASE.replace(b"2 beginbfchar", b"99999 beginbfchar")
    m["float_count"] = _BASE.replace(b"2 beginbfchar", b"2.0 beginbfchar")
    m["no_count_bfchar"] = _BASE.replace(b"2 beginbfchar", b"beginbfchar")

    # ---- bfrange special cases ----
    m["bfrange_reversed"] = _BASE.replace(
        b"<0010> <0012> <0050>", b"<0012> <0010> <0050>"
    )
    m["bfrange_identity"] = _BASE.replace(
        b"<0010> <0012> <0050>", b"<0000> <FFFF> <0000>"
    )
    m["bfrange_array_short"] = _BASE.replace(
        b"[<0060> <0061> <0062>]", b"[<0060> <0061>]"
    )
    m["name_dst"] = _BASE.replace(b"<0002> <0042>", b"<0002> /space")

    # ---- CID range edge cases ----
    m["cid_crossbyte"] = _CID_BASE.replace(b"<8141> <817E> 634", b"<41> <8200> 634")
    m["cid_reversed_range"] = _CID_BASE.replace(
        b"<8141> <817E> 634", b"<817E> <8141> 634"
    )
    m["cid_difflen_range"] = _CID_BASE.replace(
        b"<8141> <817E> 634", b"<41> <817E> 634"
    )
    m["cid_wmode1"] = _CID_BASE.replace(b"/WMode 0 def", b"/WMode 1 def")
    m["cid_wmode2"] = _CID_BASE.replace(b"/WMode 0 def", b"/WMode 2 def")

    # ---- usecmap directives ----
    m["bad_usecmap"] = _BASE.replace(
        b"begincmap\n", b"begincmap\n/NoSuchCMap usecmap\n"
    )
    m["identity_usecmap"] = _CID_BASE.replace(
        b"begincmap\n", b"begincmap\n/Identity-H usecmap\n"
    )

    # ---- structural garbage / missing operators ----
    m["garbage_dict"] = _BASE.replace(
        b"begincmap\n", b"begincmap\n/Extra << /A /B /C 1 >> def\n"
    )
    m["no_endcmap"] = _BASE.replace(b"endcmap\n", b"")
    m["no_endbfchar"] = _BASE.replace(b"endbfchar\n", b"")
    m["no_endcodespace"] = _BASE.replace(b"endcodespacerange\n", b"")
    m["no_type"] = _BASE.replace(b"/CMapType 2 def\n", b"")
    m["no_name"] = _BASE.replace(b"/CMapName /Adobe-Test-UCS2 def\n", b"")
    m["trailing_garbage"] = _BASE + b"\n%%garbage operator zzz 123 <ABCD>\n"
    m["nul_pad"] = _BASE.replace(b" ", b"\x00", 5)

    return m


_MUTANTS = _mutants()

# Blobs whose corruption strips the codespace section entirely → no codespace
# ranges parsed → the documented no-codespace readCode divergence. These are
# asserted out-of-band (header + CID value parity, len divergence pinned).
_NO_CODESPACE_CASES = {"trunc_30", "trunc_50", "cid_trunc_40"}


def _to_int(data: bytes) -> int:
    code = 0
    for b in data:
        code = (code << 8) | (b & 0xFF)
    return code


def _read_len(cmap: CMap, code: bytes) -> int:
    try:
        _, length = cmap.read_code(code, 0)
        return length
    except Exception:  # pragma: no cover - parity with probe's catch-all
        return -1


def _fmt(value: str | None) -> str:
    return "null" if value is None else value


def _py_lines(stream: bytes, codes: list[str]) -> list[str]:
    """Reconstruct the probe projection from pypdfbox for one blob."""
    try:
        cmap = CMapParser().parse(RandomAccessReadBuffer(stream))
    except Exception:
        return ["ok=false"]
    lines = [
        "ok=true",
        f"name={_fmt(cmap.get_name())}",
        f"wmode={cmap.get_wmode()}",
        f"type={cmap.get_type()}",
        f"registry={_fmt(cmap.get_registry())}",
        f"ordering={_fmt(cmap.get_ordering())}",
    ]
    for hexcode in codes:
        data = bytes.fromhex(hexcode)
        ci = _to_int(data)
        try:
            cid = cmap.to_cid(ci)
        except Exception:
            cid = -2
        lines.append(f"CID {hexcode.upper()} -> {cid} len={_read_len(cmap, data)}")
        try:
            uni = cmap.to_unicode_with_length(ci, len(data))
        except Exception:
            uni = None
        if not uni:
            lines.append(f"UNI {hexcode.upper()} -> (none)")
        else:
            u = " ".join(f"U+{ord(c):04X}" for c in uni)
            lines.append(f"UNI {hexcode.upper()} -> {u}")
    return lines


def _strip_cid_len(lines: list[str]) -> list[str]:
    """Drop the ``len=`` suffix from CID lines (for the documented
    no-codespace divergence) so header + CID value + UNI parity is still
    asserted line-for-line."""
    out: list[str] = []
    for line in lines:
        if line.startswith("CID ") and " len=" in line:
            out.append(line[: line.rindex(" len=")])
        else:
            out.append(line)
    return out


@requires_oracle
@pytest.mark.parametrize("name", list(_MUTANTS))
def test_cmap_parse_fuzz_matches_pdfbox(name: str) -> None:
    """pypdfbox ``CMapParser.parse`` + the resulting ``CMap``'s ``to_cid`` /
    ``to_unicode`` / ``read_code`` projection must equal Apache PDFBox 3.0.7
    on every mutant — except the documented no-codespace ``readCode`` length
    divergence, where header + CID value + Unicode parity is still required.
    """
    stream = _MUTANTS[name]
    java = run_probe_text("CMapParseFuzzProbe", stream.hex(), *_CODES).splitlines()
    py = _py_lines(stream, _CODES)

    if name in _NO_CODESPACE_CASES:
        # Documented intentional divergence (see module docstring + CHANGES.md
        # wave 1508): upstream readCode throws on a no-codespace CMap
        # (new byte[0] + read(buf,0,4)) → probe len=-1; pypdfbox reads one
        # byte. Assert everything but the CID len suffix is byte-identical.
        assert _strip_cid_len(py) == _strip_cid_len(java), (
            f"cmap parse-fuzz parity (sans len) broken for {name}:\n"
            f"  JAVA: {java}\n  PY:   {py}"
        )
        # Pin the divergence direction explicitly so a future change is caught.
        java_lens = {ln for ln in java if ln.startswith("CID ") and ln.endswith("len=-1")}
        py_lens = {ln for ln in py if ln.startswith("CID ") and ln.endswith("len=1")}
        assert java_lens, f"expected Java no-codespace readCode throw for {name}"
        assert py_lens, f"expected pypdfbox lenient one-byte readCode for {name}"
        return

    assert py == java, (
        f"cmap parse-fuzz parity broken for {name}:\n"
        f"  JAVA: {java}\n  PY:   {py}"
    )


@requires_oracle
def test_no_codespace_readcode_documented_divergence() -> None:
    """Pin the root-cause both-sides contract directly (independent of the
    mutant corpus): a ``CMap`` with no codespace ranges keeps the upstream
    constructor defaults ``minCodeLength=4`` / ``maxCodeLength=0``; upstream
    ``readCode`` throws (probe ``len=-1``) while pypdfbox reads one byte
    (``test_cmap.test_empty_cmap_read_code_reads_one_byte_without_crashing``).
    """
    empty = b"%!PS-Adobe-3.0 Resource-CMap\nbegincmap\n/CMapName /Empty def\nendcmap\nend\n"
    java = run_probe_text("CMapParseFuzzProbe", empty.hex(), "00").splitlines()
    # Java probe: header parses, but readLen of <00> throws -> len=-1.
    assert "ok=true" in java
    assert any(ln == "CID 00 -> 0 len=-1" for ln in java), java

    cmap = CMapParser().parse(RandomAccessReadBuffer(empty))
    assert cmap.get_min_code_length() == 4
    assert cmap.get_max_code_length() == 0
    # pypdfbox deliberately reads one byte instead of crashing.
    code, length = cmap.read_code(b"\x00", 0)
    assert (code, length) == (0x00, 1)
