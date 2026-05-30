"""Live PDFBox differential parity for hex-string ``< ... >`` parsing leniency.

Drives raw operand byte snippets through both Apache PDFBox 3.0.7 (via the
``HexStringParseProbe`` Java oracle) and pypdfbox's :class:`PDFStreamParser`,
comparing the decoded byte payload of the parsed hex string. This pins the
shared ``BaseParser.parseCOSHexString`` / ``COSString.parseHex`` leniency that
real-world malformed PDFs depend on:

  - even-length and odd-length runs (odd → implicit trailing ``0`` pad,
    ISO 32000-1 §7.3.4.3);
  - embedded whitespace / newlines / tabs between hex digits (ignored), even
    when they split a logical byte across the gap;
  - a stray non-hex character mid-string — PDFBox discards any dangling
    half-pair and then skips to the closing ``>``, decoding only the clean
    leading pairs (``<4865ZZ...>`` → ``He``; ``<486Z...>`` → ``H``;
    ``<G>`` → empty).

The signal is ``str(<hex-of-decoded-bytes>)`` (or ``error``), identical on both
sides — see ``HexStringParseProbe.java``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _pypdfbox_signal(data: bytes) -> str:
    """First COSString token's decoded bytes as ``str(<hex>)``; ``error`` if
    the snippet yields no string token / fails to parse."""
    try:
        parser = PDFStreamParser.from_bytes(data)
        for tok in parser.tokens():
            if isinstance(tok, COSString):
                return f"str({tok.get_bytes().hex()})\n"
    except Exception:  # noqa: BLE001 — mirror probe's catch-all -> "error"
        return "error\n"
    return "error\n"


# (name, raw operand bytes). ``name`` doubles as the parametrize id.
_CASES: dict[str, bytes] = {
    "even": b"<48656C6C6F>",
    "odd_pad": b"<48656C6C6>",
    "odd_single": b"<4>",
    "ws_spaces": b"<48 65 6C 6C 6F>",
    "ws_newlines_tabs": b"<48\n65\t6C\r6C 6F>",
    "ws_splits_byte": b"<4 8 6 5 6>",
    "nonhex_mid_even": b"<4865ZZ6C6C6F>",
    "nonhex_after_odd": b"<486Z6C6C6F>",
    "nonhex_first": b"<G>",
    "empty": b"<>",
    "only_ws": b"<   >",
    "lowercase": b"<deadbeef>",
    "mixed_case": b"<DeAdBeEf>",
}


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_hex_string_parse_matches_pdfbox(name: str, tmp_path: Path) -> None:
    data = _CASES[name]
    snippet = tmp_path / f"{name}.bin"
    snippet.write_bytes(data)
    java = run_probe_text("HexStringParseProbe", str(snippet))
    py = _pypdfbox_signal(data)
    assert py == java
