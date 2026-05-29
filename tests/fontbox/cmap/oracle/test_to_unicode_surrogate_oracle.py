"""Live PDFBox differential parity for /ToUnicode bfchar / bfrange UTF-16BE
destination decoding of NON-BMP and MULTI-CHARACTER destinations.

A ``/ToUnicode`` CMap maps a character code to a UTF-16BE byte string. Most
destinations are a single BMP code point (``<0041>`` -> ``A``), but three
shapes need correct decoding:

* **surrogate pair** — a 4-byte destination whose two 16-bit units form a
  high+low surrogate pair must collapse to a single astral code point
  (``<D83DDE00>`` -> U+1F600 grinning face).
* **multi-character** — a destination of several BMP units must be preserved
  as a multi-char string (an ffi-ligature code -> ``"ffi"``).
* **bfrange array form** — a ``beginbfrange`` entry whose destination is a
  ``[ <dst0> <dst1> ... ]`` array, one UTF-16BE string per source code, where
  some entries are themselves surrogate pairs.

``oracle/probes/ToUnicodeSurrogateProbe.java`` parses the same raw CMap stream
through Apache PDFBox's ``CMapParser`` and queries ``CMap.toUnicode(byte[])``;
this test parses it through pypdfbox's :class:`CMapParser` and asserts the
per-code Unicode code points match line-for-line. Python's ``str`` iterates
code points natively, so a surrogate pair already appears as one ``U+1XXXX``;
the probe uses ``String.codePoints()`` to collapse Java's UTF-16 the same way.
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap.cmap_parser import CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

# A self-contained embedded /ToUnicode CMap exercising every non-trivial
# destination shape. Codes are 2-byte (codespace <0000>-<FFFF>).
#
#   beginbfchar:
#     <0001> <D83DDE00>       surrogate pair  -> U+1F600
#     <0002> <006600660069>   multi-char      -> "ffi" (U+0066 U+0066 U+0069)
#     <0003> <0041>           plain BMP       -> U+0041
#     <0004> <D834DD1E0301>   astral+combining-> U+1D11E U+0301
#   beginbfrange (array form), source 0010..0012:
#     <0010> <0012> [ <D83DDE01> <0041> <D83DDE02> ]
#       0x0010 -> U+1F601 ; 0x0011 -> U+0041 ; 0x0012 -> U+1F602
#   beginbfrange (incrementing low-byte form), source 0020..0022 -> <0061>:
#     0x0020 -> U+0061 ; 0x0021 -> U+0062 ; 0x0022 -> U+0063
_CMAP_TEXT = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CMapName /Adobe-Identity-UCS def\n"
    "/CMapType 2 def\n"
    "1 begincodespacerange\n"
    "<0000> <FFFF>\n"
    "endcodespacerange\n"
    "4 beginbfchar\n"
    "<0001> <D83DDE00>\n"
    "<0002> <006600660069>\n"
    "<0003> <0041>\n"
    "<0004> <D834DD1E0301>\n"
    "endbfchar\n"
    "2 beginbfrange\n"
    "<0010> <0012> [<D83DDE01> <0041> <D83DDE02>]\n"
    "<0020> <0022> <0061>\n"
    "endbfrange\n"
    "endcmap\n"
    "CMapName currentdict /CMap defineresource pop\n"
    "end\n"
    "end\n"
)

_CMAP_BYTES = _CMAP_TEXT.encode("latin-1")
_CMAP_HEX = _CMAP_BYTES.hex()

# Two-byte codes to query (hex, big-endian), covering each destination shape.
_CODES_HEX = [
    "0001",  # surrogate pair
    "0002",  # multi-char ffi
    "0003",  # plain BMP
    "0004",  # astral + combining
    "0010",  # bfrange array -> surrogate
    "0011",  # bfrange array -> BMP
    "0012",  # bfrange array -> surrogate
    "0020",  # bfrange incrementing
    "0021",
    "0022",
    "00FF",  # unmapped -> (none)
]


def _fmt_unicode(s: str) -> str:
    """Render ``s`` as the probe does: space-separated ``U+XXXX`` per code
    point (Python iterates code points natively, so surrogate pairs already
    appear as a single astral entry)."""
    return " ".join(f"U+{ord(ch):04X}" for ch in s)


def _py_lines() -> list[str]:
    cmap = CMapParser().parse(RandomAccessReadBuffer(_CMAP_BYTES))
    lines: list[str] = []
    for code_hex in _CODES_HEX:
        code = bytes.fromhex(code_hex)
        uni = cmap.to_unicode_bytes(code)
        if not uni:
            lines.append(f"UNI {code_hex.upper()} -> (none)")
        else:
            lines.append(f"UNI {code_hex.upper()} -> {_fmt_unicode(uni)}")
    return lines


def test_python_decodes_expected_codepoints() -> None:
    """Value pin (runs without the oracle): the decoded code points match the
    UTF-16BE destinations declared in the CMap, including the surrogate-pair
    collapse and the multi-char ffi destination."""
    lines = _py_lines()
    assert lines == [
        "UNI 0001 -> U+1F600",
        "UNI 0002 -> U+0066 U+0066 U+0069",
        "UNI 0003 -> U+0041",
        "UNI 0004 -> U+1D11E U+0301",
        "UNI 0010 -> U+1F601",
        "UNI 0011 -> U+0041",
        "UNI 0012 -> U+1F602",
        "UNI 0020 -> U+0061",
        "UNI 0021 -> U+0062",
        "UNI 0022 -> U+0063",
        "UNI 00FF -> (none)",
    ]


@requires_oracle
def test_to_unicode_surrogate_matches_pdfbox() -> None:
    """pypdfbox's CMap.to_unicode must equal Apache PDFBox's CMap.toUnicode for
    surrogate-pair, multi-char, and bfrange-array UTF-16BE destinations."""
    java = run_probe_text(
        "ToUnicodeSurrogateProbe", _CMAP_HEX, *_CODES_HEX
    ).splitlines()
    py = _py_lines()
    assert py == java, (
        "CMap surrogate/multi-char decode diverged:\n"
        + "\n".join(
            f"  java={j!r} py={p!r}"
            for j, p in zip(java, py, strict=False)
            if j != p
        )
    )
