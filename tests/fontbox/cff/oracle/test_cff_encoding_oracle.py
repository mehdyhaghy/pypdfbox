"""Live Apache PDFBox differential parity for fontbox **CFFType1Font /Encoding**
resolution — the Top DICT ``/Encoding`` path covering predefined (ID 0 / 1)
and embedded (Format0 / Format1) on-disk encodings.

The high-value differential cases this oracle pins down:

* The predefined-vs-embedded *class* identity. A CFF Top DICT operand of 0
  must surface as :class:`CFFStandardEncoding`, an operand of 1 as
  :class:`CFFExpertEncoding`, an offset > 1 as :class:`Format0Encoding` /
  :class:`Format1Encoding`. A predefined ID misread as a Format0 offset
  (the classic bug — interpreting the byte as an offset into the program
  rather than as a sentinel) blows up here.
* The predefined ID-0 / ID-1 code→name mapping. StandardEncoding /
  ExpertEncoding are font-independent canonical tables (Adobe Technote
  #5176 Appendix B) — every code 0..255 must agree with PDFBox's own
  resolved value.
* The embedded encoding's per-code SID resolution: fontTools decompiles
  the Format0 table into a 256-entry name list; pypdfbox lifts that into
  a :class:`Format0Encoding` whose ``get_name`` mirrors the upstream
  ``CFFParser$Format0Encoding.getName`` exactly.

Fixtures
--------
Two synthetic name-keyed CFFs (generated deterministically — see
``tests/fixtures/fontbox/cff/make_encoding_fixtures.py``) cover the
predefined IDs (Standard / Expert), and one real-world embedded /Type1C
program (extracted from a corpus PDF, written to a tmp file) covers the
Format0 path.

Both engines read the *same* CFF bytes, so any divergence is a real
encoding-resolution bug, not a byte-layout artifact.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"
_PDF_FIXTURES = _REPO / "tests" / "fixtures" / "pdmodel" / "font"

_STD_ENC_CFF = _CFF_FIXTURES / "std_enc.cff"
_EXPERT_ENC_CFF = _CFF_FIXTURES / "expert_enc.cff"
_EMBEDDED_PDF = _PDF_FIXTURES / "PDFBOX-3044-010197-p5-ligatures.pdf"


# --------------------------------------------------------------------------- #
# Probe-line parsing — see oracle/probes/CffEncodingProbe.java for the schema.
# --------------------------------------------------------------------------- #


class _EncFacts:
    def __init__(self) -> None:
        self.font_class: str = ""
        self.enc_class: str = ""
        self.enc_full: str = ""
        self.map: dict[int, str] = {}


def _parse_probe(text: str) -> _EncFacts:
    f = _EncFacts()
    for line in text.splitlines():
        cols = line.split("\t")
        tag = cols[0]
        if tag == "FONT" and len(cols) >= 2:
            f.font_class = cols[1]
        elif tag == "ENC" and len(cols) >= 2:
            f.enc_class = cols[1]
        elif tag == "ENC_FULL" and len(cols) >= 2:
            f.enc_full = cols[1]
        elif tag == "MAP" and len(cols) >= 3:
            f.map[int(cols[1])] = cols[2]
    return f


# --------------------------------------------------------------------------- #
# pypdfbox-side fact extraction — mirrors the probe field-for-field.
# --------------------------------------------------------------------------- #


def _py_facts(data: bytes) -> _EncFacts:
    f = _EncFacts()
    font = CFFParser().parse(data)[0]
    f.font_class = type(font).__name__
    if isinstance(font, CFFType1Font):
        enc = font.get_encoding()
        if enc is None:
            f.enc_class = "NULL"
            f.enc_full = "NULL"
        else:
            f.enc_class = type(enc).__name__
            f.enc_full = f"{type(enc).__module__}.{type(enc).__name__}"
            for code in range(256):
                name = enc.get_name(code)
                if name and name != ".notdef":
                    f.map[code] = name
    else:
        f.enc_class = "NONE"
        f.enc_full = "NONE"
    return f


def _assert_enc_parity(probe_text: str, data: bytes) -> None:
    java = _parse_probe(probe_text)
    py = _py_facts(data)
    assert py.font_class == java.font_class, (
        "font_class",
        py.font_class,
        java.font_class,
    )
    # Simple class name parity — the load-bearing predefined-vs-embedded
    # distinction lives here.
    assert py.enc_class == java.enc_class, (
        "enc_class",
        py.enc_class,
        java.enc_class,
    )
    # Per-code mapping parity (only non-".notdef" codes are emitted by
    # both sides).
    assert set(py.map) == set(java.map), (
        "code key sets differ",
        sorted(set(py.map) ^ set(java.map)),
    )
    for code, jname in java.map.items():
        assert py.map[code] == jname, ("code -> name", code, py.map[code], jname)


# --------------------------------------------------------------------------- #
# Differential tests.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_predefined_standard_encoding_matches_pdfbox() -> None:
    """Top DICT ``/Encoding 0`` resolves to :class:`CFFStandardEncoding`.
    Every Standard-encoded code (32..126, 161..251 per Adobe Standard
    Encoding) matches the upstream PDFBox name. The predefined-ID-0
    case is the high-value bug: a parser that mis-reads operand ``0``
    as a Format0 offset would land at byte 0 (header magic) and
    silently produce garbage names — this test pins that down."""
    data = _STD_ENC_CFF.read_bytes()
    probe = run_probe_text("CffEncodingProbe", str(_STD_ENC_CFF))
    _assert_enc_parity(probe, data)


@requires_oracle
def test_predefined_expert_encoding_matches_pdfbox() -> None:
    """Top DICT ``/Encoding 1`` resolves to :class:`CFFExpertEncoding`.
    The Expert table differs from Standard in nearly every code (e.g.
    code 33 → ``exclamsmall`` instead of ``exclam``); per-code parity
    therefore proves the predefined-ID-1 dispatch is correct."""
    data = _EXPERT_ENC_CFF.read_bytes()
    probe = run_probe_text("CffEncodingProbe", str(_EXPERT_ENC_CFF))
    _assert_enc_parity(probe, data)


@requires_oracle
def test_embedded_format0_encoding_matches_pdfbox() -> None:
    """A real-world /FontFile3 /Type1C program with an embedded Format0
    encoding (Top DICT operand > 1 — offset into the CFF program). Each
    such /FontFile3 in PDFBOX-3044-010197-p5-ligatures.pdf must surface
    as a :class:`Format0Encoding`, and every code→name pair matches the
    upstream ``CFFParser$Format0Encoding.getName`` resolution. This is
    the *other* half of the predefined-vs-embedded dichotomy — the
    parser must NOT mis-classify these as predefined."""
    doc = PDDocument.load(str(_EMBEDDED_PDF))
    try:
        seen = 0
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                fd = font.get_font_descriptor()
                if fd is None:
                    continue
                ff3 = fd.get_cos_object().get_dictionary_object(
                    COSName.get_pdf_name("FontFile3")
                )
                if ff3 is None:
                    continue
                sub = ff3.get_dictionary_object(COSName.get_pdf_name("Subtype"))
                if sub is None or sub.get_name() != "Type1C":
                    continue
                stream = ff3.create_input_stream()
                try:
                    data = bytes(stream.read())
                finally:
                    stream.close()
                # mkstemp (not NamedTemporaryFile) so the handle is closed
                # before the Java probe reopens the path by name — on
                # Windows a still-open NamedTemporaryFile is locked
                # against re-open.
                fd_handle, tmp_path = tempfile.mkstemp(suffix=".cff")
                try:
                    with os.fdopen(fd_handle, "wb") as tmp:
                        tmp.write(data)
                    probe = run_probe_text("CffEncodingProbe", tmp_path)
                finally:
                    os.unlink(tmp_path)
                # Some Type1C programs in the wild can carry a predefined
                # encoding too — only assert parity on the embedded ones.
                java = _parse_probe(probe)
                if java.enc_class not in ("Format0Encoding", "Format1Encoding"):
                    continue
                _assert_enc_parity(probe, data)
                seen += 1
        assert seen >= 1, (
            "no embedded Format0/Format1 /Type1C encoding found in fixture"
        )
    finally:
        doc.close()
