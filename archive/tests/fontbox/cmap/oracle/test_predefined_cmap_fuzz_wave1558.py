"""Live PDFBox differential fuzz of the predefined-CMap *registry*.

The sibling oracles pin a thin shortlist: ``test_predefined_cmap_oracle.py`` and
``test_predefined_cmap_type0_oracle.py`` cover name/WMode/toCID/readCode length
on a few Japan1/GB1 CMaps; ``test_predefined_cmap_info_oracle.py`` pins the
CIDSystemInfo triple on a fixed eight-name list. None of them sweep the registry
lookup across *all four* Adobe orderings (Japan1, GB1, CNS1, Korea1) at once,
nor pin the UNKNOWN-name error path, nor the WMode of the full -V set.

This module closes those gaps via ``oracle/probes/PredefinedCMapFuzzProbe.java``:

* **Registry sweep (``info`` mode).** ~25 predefined names spanning every
  bundled ordering and both the CID-mapping (``Uni*``/legacy EUC/RKSJ) and the
  Unicode-mapping (``Adobe-*-UCS2``) shapes — pinning registry/ordering/
  supplement/WMode/has_cid/has_unicode. Guards against a hard-coded supplement
  or a registry/ordering that leaks across orderings.
* **Unknown predefined name → error.** ``parsePredefined`` throws ``IOException``
  upstream; pypdfbox raises ``OSError`` from ``parse_predefined`` and returns
  ``None`` from the manager. The probe catches the Java exception and emits
  ``ERROR IOException``; the Python side asserts the corresponding ``OSError``.
* **code→CID sweep (``cid`` mode).** Sample codes per registry, including the
  ``usecmap`` override on ``90ms-RKSJ-V`` (``<8340>`` 925→7928 while ``<8140>``
  stays 633) and the variable-width ``read_code`` length each codespace assigns.

Every Java-derived literal in ``_INFO_EXPECTED`` / ``_CID_EXPECTED`` was produced
live against ``pdfbox-app-3.0.7.jar`` (wave 1558), so the no-JVM regression pins
below stay honest even when the oracle is absent.

Result: pypdfbox matched Apache PDFBox on every field across all four registries
and the error path — no production divergence. The registry is byte-for-byte
faithful to the 3.0.7 predefined set.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap_manager import CMapManager
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser
from tests.oracle.harness import requires_oracle, run_probe_text


@pytest.fixture(autouse=True)
def _clear_predefined_cache():
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


# name -> the PredefinedCMapFuzzProbe `info` block, as emitted by PDFBox 3.0.7.
# Spans all four Adobe orderings (Japan1/GB1/CNS1/Korea1) + Identity, both H and
# V variants, and both mapping shapes (CID vs Unicode UCS2).
_INFO_EXPECTED: dict[str, dict[str, object]] = {
    "Identity-H": {"reg": "Adobe", "ord": "Identity", "sup": 0, "w": 0,
                   "cid": True, "uni": False},
    "Identity-V": {"reg": "Adobe", "ord": "Identity", "sup": 0, "w": 1,
                   "cid": True, "uni": False},
    "90ms-RKSJ-H": {"reg": "Adobe", "ord": "Japan1", "sup": 2, "w": 0,
                    "cid": True, "uni": False},
    "90ms-RKSJ-V": {"reg": "Adobe", "ord": "Japan1", "sup": 2, "w": 1,
                    "cid": True, "uni": False},
    "UniJIS-UCS2-H": {"reg": "Adobe", "ord": "Japan1", "sup": 4, "w": 0,
                      "cid": True, "uni": False},
    "UniJIS-UTF16-H": {"reg": "Adobe", "ord": "Japan1", "sup": 6, "w": 0,
                       "cid": True, "uni": False},
    "UniGB-UCS2-H": {"reg": "Adobe", "ord": "GB1", "sup": 4, "w": 0,
                     "cid": True, "uni": False},
    "UniGB-UCS2-V": {"reg": "Adobe", "ord": "GB1", "sup": 4, "w": 1,
                     "cid": True, "uni": False},
    "GBK-EUC-H": {"reg": "Adobe", "ord": "GB1", "sup": 2, "w": 0,
                  "cid": True, "uni": False},
    "GBK-EUC-V": {"reg": "Adobe", "ord": "GB1", "sup": 2, "w": 1,
                  "cid": True, "uni": False},
    "UniGB-UTF16-V": {"reg": "Adobe", "ord": "GB1", "sup": 5, "w": 1,
                      "cid": True, "uni": False},
    "UniCNS-UCS2-H": {"reg": "Adobe", "ord": "CNS1", "sup": 3, "w": 0,
                      "cid": True, "uni": False},
    "UniCNS-UCS2-V": {"reg": "Adobe", "ord": "CNS1", "sup": 3, "w": 1,
                      "cid": True, "uni": False},
    "B5pc-H": {"reg": "Adobe", "ord": "CNS1", "sup": 0, "w": 0,
               "cid": True, "uni": False},
    "B5pc-V": {"reg": "Adobe", "ord": "CNS1", "sup": 0, "w": 1,
               "cid": True, "uni": False},
    "UniKS-UCS2-H": {"reg": "Adobe", "ord": "Korea1", "sup": 1, "w": 0,
                     "cid": True, "uni": False},
    "UniKS-UCS2-V": {"reg": "Adobe", "ord": "Korea1", "sup": 1, "w": 1,
                     "cid": True, "uni": False},
    "KSC-EUC-H": {"reg": "Adobe", "ord": "Korea1", "sup": 0, "w": 0,
                  "cid": True, "uni": False},
    "KSC-EUC-V": {"reg": "Adobe", "ord": "Korea1", "sup": 0, "w": 1,
                  "cid": True, "uni": False},
    # The UCS2 CMaps: inverse shape — no CID mappings, Unicode (bfrange) only,
    # ordering carries the unusual underscore form (Adobe_Japan1_UCS2).
    "Adobe-Japan1-UCS2": {"reg": "Adobe", "ord": "Adobe_Japan1_UCS2", "sup": 6,
                          "w": 0, "cid": False, "uni": True},
    "Adobe-GB1-UCS2": {"reg": "Adobe", "ord": "Adobe_GB1_UCS2", "sup": 5,
                       "w": 0, "cid": False, "uni": True},
    "Adobe-CNS1-UCS2": {"reg": "Adobe", "ord": "Adobe_CNS1_UCS2", "sup": 5,
                        "w": 0, "cid": False, "uni": True},
    "Adobe-Korea1-UCS2": {"reg": "Adobe", "ord": "Adobe_Korea1_UCS2", "sup": 2,
                          "w": 0, "cid": False, "uni": True},
}

# Predefined names PDFBox cannot resolve -> IOException (probe emits
# ``ERROR IOException``); pypdfbox raises OSError from parse_predefined.
_UNKNOWN_NAMES: list[str] = ["NotARealCMap", "Foo-Bar-H"]

# (name, hexcode) -> (cid, read_code_length), live from PDFBox 3.0.7.
_CID_EXPECTED: dict[str, list[tuple[str, int, int]]] = {
    # Japan1 base + usecmap override on the -V variant.
    "90ms-RKSJ-H": [("8140", 633, 2), ("8340", 925, 2), ("41", 264, 1),
                    ("2121", 0, 1)],
    "90ms-RKSJ-V": [("8140", 633, 2), ("8340", 7928, 2)],
    # GB1 — UCS2 input, full match at <FFFF> -> CID 0.
    "UniGB-UCS2-H": [("0041", 34, 2), ("4E00", 4162, 2), ("FFFF", 0, 2)],
    "UniGB-UCS2-V": [("0041", 34, 2), ("4E00", 4162, 2)],
    # CNS1.
    "UniCNS-UCS2-H": [("0041", 34, 2), ("4E00", 595, 2)],
    "B5pc-H": [("41", 34, 1), ("A140", 99, 2)],
    # Korea1.
    "UniKS-UCS2-H": [("0041", 34, 2), ("AC00", 1086, 2)],
    "UniKS-UCS2-V": [("0041", 34, 2), ("AC00", 1086, 2)],
    # Identity.
    "Identity-H": [("0000", 0, 2), ("0041", 65, 2), ("ABCD", 43981, 2),
                   ("FFFF", 65535, 2)],
}


def _py_info_block(name: str) -> list[str]:
    """Reconstruct one ``info`` block from pypdfbox for ``name``.

    Mirrors the probe: an unresolved name yields ``ERROR OSError`` (Python's
    counterpart of the Java ``IOException``); otherwise the full metadata block,
    with Java's lowercase ``true``/``false`` boolean rendering.
    """
    try:
        cmap = CMapParser.parse_predefined(name)
    except OSError:
        return [f"CMAP {name}", "ERROR OSError"]
    return [
        f"CMAP {cmap.get_name()}",
        f"REGISTRY {cmap.get_registry()}",
        f"ORDERING {cmap.get_ordering()}",
        f"SUPPLEMENT {cmap.get_supplement()}",
        f"WMODE {cmap.get_wmode()}",
        f"HASCID {str(cmap.has_cid_mappings()).lower()}",
        f"HASUNICODE {str(cmap.has_unicode_mappings()).lower()}",
    ]


def _java_info_block(name: str) -> list[str]:
    """The Java probe's ``info`` block for ``name``, normalising ``IOException``
    to ``OSError`` so the divergence (exception class spelling only) is folded
    out — the contract is "Java threw, pypdfbox threw"."""
    lines = run_probe_text("PredefinedCMapFuzzProbe", "info", name).splitlines()
    if len(lines) == 2 and lines[1].startswith("ERROR "):
        return [lines[0], "ERROR OSError"]
    return lines


# ---------- no-JVM regression pins (PDFBox-3.0.7 literals) ----------


@pytest.mark.parametrize("name", list(_INFO_EXPECTED))
def test_registry_metadata_pinned(name: str) -> None:
    """Registry/ordering/supplement/WMode/has_cid/has_unicode pinned to the
    PDFBox 3.0.7 literals across all four Adobe orderings (no JVM needed)."""
    exp = _INFO_EXPECTED[name]
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None, f"bundled CMap failed to load: {name}"
    assert cmap.get_registry() == exp["reg"]
    assert cmap.get_ordering() == exp["ord"]
    assert cmap.get_supplement() == exp["sup"]
    assert cmap.get_wmode() == exp["w"]
    assert cmap.has_cid_mappings() is exp["cid"]
    assert cmap.has_unicode_mappings() is exp["uni"]


@pytest.mark.parametrize("name", _UNKNOWN_NAMES)
def test_unknown_predefined_name_raises(name: str) -> None:
    """An unknown predefined name raises ``OSError`` from
    ``parse_predefined`` (PDFBox throws ``IOException``) and the manager
    degrades to ``None`` instead of propagating."""
    with pytest.raises(OSError):
        CMapParser.parse_predefined(name)
    assert CMapManager.get_predefined_cmap(name) is None


@pytest.mark.parametrize(
    "name,hexcode,cid,length",
    [(n, h, c, length) for n, rows in _CID_EXPECTED.items()
     for (h, c, length) in rows],
    ids=[f"{n}-{h}" for n, rows in _CID_EXPECTED.items() for (h, _, _) in rows],
)
def test_code_to_cid_pinned(name: str, hexcode: str, cid: int, length: int) -> None:
    """``to_cid`` and ``read_code`` byte-length pinned to PDFBox 3.0.7 across
    registries, including the ``90ms-RKSJ-V`` usecmap override (no JVM)."""
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None, f"bundled CMap failed to load: {name}"
    raw = bytes.fromhex(hexcode)
    value = 0
    for b in raw:
        value = (value << 8) | (b & 0xFF)
    # ``to_cid`` consumes the full big-endian value (matching the Java probe's
    # ``toCID(toInt(code))``); ``read_code`` consumes only ``length`` bytes and
    # so returns the int of that leading-byte prefix (e.g. <2121> reads <21>).
    assert cmap.to_cid(value) == cid
    code, read_len = cmap.read_code(raw, 0)
    expected_code = 0
    for b in raw[:length]:
        expected_code = (expected_code << 8) | (b & 0xFF)
    assert (code, read_len) == (expected_code, length)


# ---------- live differential (requires the oracle) ----------


@requires_oracle
@pytest.mark.parametrize("name", list(_INFO_EXPECTED))
def test_registry_metadata_matches_pdfbox(name: str) -> None:
    """pypdfbox's ``info`` metadata block must equal Apache PDFBox's for every
    predefined name across all four registries. A differing REGISTRY/ORDERING/
    SUPPLEMENT line means the CIDSystemInfo triple leaked or was mis-parsed; a
    differing HASCID/HASUNICODE line means a mapping shape was mis-classified."""
    java = _java_info_block(name)
    py = _py_info_block(name)
    assert py == java, (
        f"predefined-CMap registry parity broken for {name}:\n"
        f"  JAVA: {java}\n"
        f"  PY:   {py}"
    )


@requires_oracle
@pytest.mark.parametrize("name", _UNKNOWN_NAMES)
def test_unknown_name_error_matches_pdfbox(name: str) -> None:
    """Both sides treat an unknown predefined name as an error (Java
    ``IOException`` <-> Python ``OSError``)."""
    java = _java_info_block(name)
    py = _py_info_block(name)
    assert java == [f"CMAP {name}", "ERROR OSError"]
    assert py == java


@requires_oracle
@pytest.mark.parametrize("name", list(_CID_EXPECTED))
def test_code_to_cid_matches_pdfbox(name: str) -> None:
    """code→CID and ``read_code`` length must equal Apache PDFBox's for every
    sampled code, across registries and the usecmap-override -V variant."""
    rows = _CID_EXPECTED[name]
    args = [h for (h, _, _) in rows]
    java = run_probe_text(
        "PredefinedCMapFuzzProbe", "cid", name, *args
    ).splitlines()
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None
    py = [f"CMAP {cmap.get_name()}"]
    for hexcode in args:
        value = 0
        for b in bytes.fromhex(hexcode):
            value = (value << 8) | (b & 0xFF)
        cid = cmap.to_cid(value)
        _, read_len = cmap.read_code(bytes.fromhex(hexcode), 0)
        py.append(f"CID {hexcode.upper()} -> {cid} len={read_len}")
    assert py == java, (
        f"predefined-CMap code->CID parity broken for {name}:\n"
        f"  JAVA: {java}\n"
        f"  PY:   {py}"
    )
