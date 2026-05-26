"""Live PDFBox differential parity for predefined-CMap loading.

A Type0/CID font's encoding CMap is resolved either from an embedded stream or,
for the Adobe predefined names, from the bundled CMap resources under
``pypdfbox/fontbox/cmap/resources/``. For correct glyph selection
``CMapManager.get_predefined_cmap(name)`` must yield the same WMode, the same
``to_cid(code)`` for every input code, and the same codespace-assigned code
length that Apache PDFBox's ``CMapParser.parsePredefined(name)`` does.

The oracle output is produced by ``oracle/probes/PredefCMapProbe.java``:

    CMAP <name>
    WMODE <wmode>
    CID <hexcode> -> <cid> len=<codeLength>   (one per probed byte sequence)

``<cid>`` is ``CMap.toCID(int)`` over the big-endian value of the bytes and
``<codeLength>`` is how many bytes ``CMap.readCode(InputStream)`` consumes for
that sequence — i.e. the length the codespace assigns to the leading bytes.
The Python side reconstructs the identical line format, so a divergence in
WMode, CID, or codespace length surfaces as a single differing line.

CMaps covered span every shape in the bundled set:

* ``Identity-H`` / ``Identity-V`` — the programmatic 2-byte identity builders
  (the -V case exercises WMode 1).
* ``90ms-RKSJ-H`` / ``90ms-RKSJ-V`` — a mixed 1-byte/2-byte Shift-JIS
  codespace; the -V variant exercises ``usecmap`` chaining with vertical CID
  overrides (e.g. ``8340`` maps to a different CID under -V than -H).
* ``GB-EUC-H`` / ``KSC-EUC-H`` / ``B5pc-H`` — legacy EUC / Big5 1+2-byte
  codespaces.
* ``UniGB-UTF16-H`` / ``UniCNS-UTF16-H`` / ``UniKS-UTF16-H`` /
  ``UniJIS-UTF16-H`` / ``UniJIS-UCS2-H`` — the Unicode-encoding 2-byte CMaps.
* ``Adobe-Japan1-UCS2`` / ``Adobe-GB1-UCS2`` — the ``*-UCS2`` Unicode-mapping
  CMaps, which have no CID mappings (``toCID`` returns 0 everywhere) but a
  2-byte codespace.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap_manager import CMapManager
from tests.oracle.harness import requires_oracle, run_probe_text

# CMap name -> list of input byte sequences (hex) to probe. Sequences cover the
# 1-byte and 2-byte codespace cases for the mixed-width CMaps, plus boundary
# values (0x00, 0xFFFF) where the codespace edge matters.
_CASES: dict[str, list[str]] = {
    "Identity-H": ["0000", "0041", "FFFF"],
    "Identity-V": ["0000", "0041", "FFFF"],
    "90ms-RKSJ-H": ["20", "41", "8140", "8340", "E040"],
    "90ms-RKSJ-V": ["20", "8140", "8340", "E040"],
    "GB-EUC-H": ["20", "41", "A1A1", "B0A1"],
    "KSC-EUC-H": ["20", "41", "A1A1", "B0A1"],
    "B5pc-H": ["20", "41", "A140", "C940"],
    "UniGB-UTF16-H": ["0041", "4E00", "FFFF"],
    "UniCNS-UTF16-H": ["0041", "4E00", "FFFF"],
    "UniKS-UTF16-H": ["0041", "AC00", "FFFF"],
    "UniJIS-UTF16-H": ["0041", "3042", "FFFF"],
    "UniJIS-UCS2-H": ["0041", "3042", "FFFF"],
    "Adobe-Japan1-UCS2": ["0001", "0020", "0343"],
    "Adobe-GB1-UCS2": ["0001", "0020", "0343"],
}


def _to_int(data: bytes) -> int:
    code = 0
    for b in data:
        code = (code << 8) | (b & 0xFF)
    return code


def _py_predefined_lines(name: str, codes: list[str]) -> list[str]:
    """Reconstruct the PredefCMapProbe output from pypdfbox for ``name``.

    Mirrors the probe line-for-line: header (CMAP/WMODE) then one CID line per
    probed byte sequence in order. ``read_code(bytes, 0)`` returns the
    ``(code, code_byte_length)`` pair, the second element being the
    codespace-assigned length the probe reads off ``readCode``'s consumption.
    """
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None, f"bundled CMap failed to load: {name}"
    lines = [f"CMAP {cmap.get_name()}", f"WMODE {cmap.get_wmode()}"]
    for hexcode in codes:
        data = bytes.fromhex(hexcode)
        cid = cmap.to_cid(_to_int(data))
        _, code_len = cmap.read_code(data, 0)
        lines.append(f"CID {hexcode.upper()} -> {cid} len={code_len}")
    return lines


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES))
def test_predefined_cmap_matches_pdfbox(name: str) -> None:
    """pypdfbox's predefined-CMap WMode + per-code CID + codespace length must
    equal Apache PDFBox's for every probed byte sequence.

    A differing ``WMODE`` line means the loader lost the writing mode; a
    differing ``CID ... len=`` line means either the CID lookup or the
    codespace partitioning diverged from upstream.
    """
    codes = _CASES[name]
    java = run_probe_text("PredefCMapProbe", name, *codes).splitlines()
    py = _py_predefined_lines(name, codes)
    assert py == java, (
        f"predefined-CMap parity broken for {name}:\n"
        f"  JAVA: {java}\n"
        f"  PY:   {py}"
    )
