"""Live PDFBox differential parity for predefined CJK CMaps on a Type0 font.

This complements ``test_predefined_cmap_oracle.py`` (which probes the raw
``CMap.readCode`` / ``CMap.toCID`` surface) by covering two facets that file
does not:

* The **Adobe Unicode (UCS2) encoding CMaps** ``UniGB-UCS2-H``,
  ``UniCNS-UCS2-H``, ``UniKS-UCS2-H`` and the **GBK** encoding ``GBK-EUC-H`` —
  the high-traffic CJK names a real-world Type0 font references. ``GBK-EUC-H``
  is the highest-value case: a *mixed-width* codespace where a leading byte in
  ``0x00..0x80`` is a 1-byte code while a leading byte in ``0x81..0xFE`` opens a
  2-byte code, so ``readCode`` must consume a variable number of bytes.
* The **Type0 font** ``PDType0Font.code_to_cid`` path — distinct from the raw
  ``CMap.toCID`` path because PDFBox routes ``codeToCID`` through the descendant
  CIDFont (``PDCIDFontType0.codeToCID`` = ``cmap.toCID(code)``;
  ``PDCIDFontType2.codeToCID`` adds a Unicode-mapping fallback). A code the CMap
  maps to CID ``0`` must surface ``0`` (not the raw code).

The oracle output is produced by ``oracle/probes/PredefCMapType0Probe.java``:

    cmap mode:   CMAP <name> / WMODE <w> / CID <hex> -> <cid> len=<n>
    type0 mode:  TYPE0 <name> / WMODE <w> / CODETOCID <hex> -> <cid> len=<n>

``<cid>`` is the big-endian value's CID; ``<n>`` is how many bytes
``readCode`` consumes for the leading byte(s). The Python side reconstructs the
identical line format so any divergence in tokenization or CID surfaces as a
single differing line.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.fontbox.cmap.cmap_manager import CMapManager
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from tests.oracle.harness import requires_oracle, run_probe_text

# CMap name -> probe codes. Mixed-width cases (GBK-EUC-H, 90ms-RKSJ-H) include
# both a 1-byte leading byte (e.g. 0x20/0x41) and a 2-byte sequence so the
# codespace partitioning is exercised on both sides of the variable-length
# boundary. FFFF is the canonical "CMap maps it to CID 0" boundary value.
_CMAP_CASES: dict[str, list[str]] = {
    "UniGB-UCS2-H": ["0041", "4E00", "3000", "FFFF"],
    "UniCNS-UCS2-H": ["0041", "4E00", "FFFF"],
    "UniKS-UCS2-H": ["0041", "AC00", "FFFF"],
    "GBK-EUC-H": ["20", "41", "80", "A1A1", "8140", "FE40"],
    "90ms-RKSJ-H": ["20", "41", "8140", "8340", "E040"],
    "Identity-H": ["0000", "0041", "FFFF"],
}

# Type0 codeToCID cases. The Adobe-GB1 descendant is a CIDFontType2 so the
# Unicode-mapping fallback (for a *-UCS2 collection used directly as
# /Encoding) is reachable via Adobe-GB1-UCS2.
_TYPE0_CASES: dict[str, tuple[str, list[str]]] = {
    # encoding name -> (descendant ordering, codes)
    "UniGB-UCS2-H": ("GB1", ["0041", "4E00", "3000", "FFFF"]),
    "GBK-EUC-H": ("GB1", ["41", "A1A1", "8140", "FE40"]),
    "Identity-H": ("GB1", ["0000", "0041", "FFFF"]),
    "Adobe-GB1-UCS2": ("GB1", ["0041", "0343"]),
}


def _to_int(data: bytes) -> int:
    code = 0
    for b in data:
        code = (code << 8) | (b & 0xFF)
    return code


def _py_cmap_lines(name: str, codes: list[str]) -> list[str]:
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None, f"bundled CMap failed to load: {name}"
    lines = [f"CMAP {cmap.get_name()}", f"WMODE {cmap.get_wmode()}"]
    for hexcode in codes:
        data = bytes.fromhex(hexcode)
        cid = cmap.to_cid(_to_int(data))
        _, code_len = cmap.read_code(data, 0)
        lines.append(f"CID {hexcode.upper()} -> {cid} len={code_len}")
    return lines


def _build_type0(cmap_name: str, ordering: str) -> PDType0Font:
    """Build a Type0 font over a CIDFontType2 (Adobe-<ordering>) descendant
    with ``/Encoding`` set to the predefined CMap name. Mirrors the
    minimal-dict construction in ``PredefCMapType0Probe.buildType0``.
    """
    csi = COSDictionary()
    csi.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    csi.set_string(COSName.get_pdf_name("Ordering"), ordering)
    csi.set_int(COSName.get_pdf_name("Supplement"), 5)

    descendant = COSDictionary()
    descendant.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    descendant.set_item(COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType2"))
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "STSong-Light")
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), csi)

    descendants = COSArray()
    descendants.add(descendant)

    type0 = COSDictionary()
    type0.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    type0.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
    type0.set_name(COSName.get_pdf_name("BaseFont"), "STSong-Light-" + cmap_name)
    type0.set_name(COSName.get_pdf_name("Encoding"), cmap_name)
    type0.set_item(COSName.get_pdf_name("DescendantFonts"), descendants)
    return PDType0Font(type0)


def _py_type0_lines(name: str, ordering: str, codes: list[str]) -> list[str]:
    font = _build_type0(name, ordering)
    lines = [f"TYPE0 {name}", f"WMODE {1 if font.is_vertical() else 0}"]
    for hexcode in codes:
        data = bytes.fromhex(hexcode)
        cid = font.code_to_cid(_to_int(data))
        _, code_len = font.read_code(data, 0)
        lines.append(f"CODETOCID {hexcode.upper()} -> {cid} len={code_len}")
    return lines


@requires_oracle
@pytest.mark.parametrize("name", list(_CMAP_CASES))
def test_predefined_cmap_readcode_and_tocid_matches_pdfbox(name: str) -> None:
    """pypdfbox's predefined-CMap ``read_code`` byte-count and ``to_cid``
    mapping must equal Apache PDFBox's for every probed byte sequence —
    including the mixed-width ``GBK-EUC-H`` / ``90ms-RKSJ-H`` codespaces
    where a leading byte selects a 1- or 2-byte code.
    """
    codes = _CMAP_CASES[name]
    java = run_probe_text("PredefCMapType0Probe", "cmap", name, *codes).splitlines()
    py = _py_cmap_lines(name, codes)
    assert py == java, (
        f"predefined-CMap parity broken for {name}:\n"
        f"  JAVA: {java}\n  PY:   {py}"
    )


@requires_oracle
@pytest.mark.parametrize("name", list(_TYPE0_CASES))
def test_type0_code_to_cid_matches_pdfbox(name: str) -> None:
    """pypdfbox's ``PDType0Font.code_to_cid`` must equal Apache PDFBox's
    ``PDType0Font.codeToCID`` for every probed code.

    Critically, a code the encoding CMap maps to CID ``0`` (e.g. ``0xFFFF``
    under ``UniGB-UCS2-H``) must surface ``0`` — matching upstream's
    descendant-delegated ``codeToCID`` — rather than echoing the raw code.
    """
    ordering, codes = _TYPE0_CASES[name]
    java = run_probe_text(
        "PredefCMapType0Probe", "type0", name, *codes
    ).splitlines()
    py = _py_type0_lines(name, ordering, codes)
    assert py == java, (
        f"Type0 code_to_cid parity broken for {name}:\n"
        f"  JAVA: {java}\n  PY:   {py}"
    )
