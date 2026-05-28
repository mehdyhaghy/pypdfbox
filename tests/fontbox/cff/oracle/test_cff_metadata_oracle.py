"""Live Apache PDFBox differential parity for fontbox **CFF Top DICT
metadata strings** — ``/version``, ``/Notice``, ``/Copyright``,
``/FullName``, ``/FamilyName``, ``/Weight``.

Each Top DICT metadata operator carries a SID; per Adobe Technote
#5176 §10 the SID resolves via the predefined Standard Strings table
when ``0 <= SID < 391`` (font-independent), and via the per-font
STRING INDEX otherwise. The high-value differential case is the
boundary between the two — a parser that always reads SIDs as
STRING-INDEX offsets (or always reads them as predefined Standard
Strings) would silently surface the wrong string here.

Two synthetic name-keyed CFFs (generated deterministically — see
``tests/fixtures/fontbox/cff/make_metadata_fixtures.py``) cover both
paths:

* ``metadata_strindex.cff`` — five metadata strings live in the STRING
  INDEX (SIDs 391..395); ``/Weight = "Bold"`` exercises the predefined
  SID 384.
* ``metadata_predef.cff`` — ``/version = "001.000"`` (SID 379) and
  ``/Weight = "Regular"`` (SID 388) both resolve via predefined SIDs;
  the remaining three string fields live in the STRING INDEX.

Both engines read the *same* CFF bytes, so any divergence is a real
metadata-string resolution bug, not a byte-layout artifact.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"

_STRINDEX_CFF = _CFF_FIXTURES / "metadata_strindex.cff"
_PREDEF_CFF = _CFF_FIXTURES / "metadata_predef.cff"

_METADATA_KEYS = ("version", "Notice", "Copyright", "FullName", "FamilyName", "Weight")


# --------------------------------------------------------------------------- #
# Probe-line parsing — see oracle/probes/CffMetadataProbe.java for the schema.
# --------------------------------------------------------------------------- #


def _parse_probe(text: str) -> tuple[str, dict[str, str]]:
    name = ""
    meta: dict[str, str] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        tag = cols[0]
        if tag == "NAME" and len(cols) >= 2:
            name = cols[1]
        elif tag == "META" and len(cols) >= 3:
            meta[cols[1]] = cols[2]
    return name, meta


def _py_facts(data: bytes) -> tuple[str, dict[str, str]]:
    font = CFFParser().parse(data)[0]
    name = font.get_name()
    meta: dict[str, str] = {}
    for key in _METADATA_KEYS:
        value = font.get_property(key)
        meta[key] = "<null>" if value is None else str(value)
    return name, meta


def _assert_metadata_parity(probe_text: str, data: bytes) -> None:
    java_name, java_meta = _parse_probe(probe_text)
    py_name, py_meta = _py_facts(data)
    assert py_name == java_name, ("name", py_name, java_name)
    for key in _METADATA_KEYS:
        assert py_meta[key] == java_meta[key], (
            "metadata key",
            key,
            py_meta[key],
            java_meta[key],
        )


# --------------------------------------------------------------------------- #
# Differential tests.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_metadata_string_index_sids_match_pdfbox() -> None:
    """Five of six metadata operators carry SIDs >= 391 (STRING INDEX);
    ``/Weight = "Bold"`` carries SID 384 (predefined). Each resolved
    string must match PDFBox's ``CFFFont.getTopDict().get(key)``
    exactly. This pins the STRING-INDEX path — every entry must come
    back as the round-tripped Latin-1 string, not as the raw SID
    integer or a STRING-INDEX-offset misread."""
    data = _STRINDEX_CFF.read_bytes()
    probe = run_probe_text("CffMetadataProbe", str(_STRINDEX_CFF))
    _assert_metadata_parity(probe, data)


@requires_oracle
def test_metadata_predefined_sids_match_pdfbox() -> None:
    """``/version`` resolves via SID 379 (predefined ``"001.000"``) and
    ``/Weight`` via SID 388 (predefined ``"Regular"``); the rest of the
    metadata strings live in the STRING INDEX. The predefined-SID
    boundary is the load-bearing case — a parser that mis-classifies
    SID 379 as a STRING-INDEX offset would read garbage from the
    per-font table (or hit index -12 and yield an empty string)."""
    data = _PREDEF_CFF.read_bytes()
    probe = run_probe_text("CffMetadataProbe", str(_PREDEF_CFF))
    _assert_metadata_parity(probe, data)


@requires_oracle
def test_metadata_keys_resolved_via_top_dict_snapshot() -> None:
    """``CFFFont.get_top_dict()`` snapshot (PDFBox: ``CFFFont.getTopDict()``)
    must carry the same resolved string values as
    ``CFFFont.get_property(key)``. Pins the contract that the Top DICT
    map returned by the snapshot is the *resolved* string map — not a
    raw-SID map that callers would have to look up themselves."""
    data = _STRINDEX_CFF.read_bytes()
    font = CFFParser().parse(data)[0]
    top_dict = font.get_top_dict()
    for key in _METADATA_KEYS:
        snapshot_value = top_dict.get(key)
        property_value = font.get_property(key)
        assert snapshot_value == property_value, (
            "snapshot vs property",
            key,
            snapshot_value,
            property_value,
        )
        # And neither should be a raw int (which would mean the SID
        # never got resolved).
        assert not isinstance(snapshot_value, int), (
            "metadata still a raw SID",
            key,
            snapshot_value,
        )
