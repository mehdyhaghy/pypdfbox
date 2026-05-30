"""Live Apache PDFBox differential parity for ``PDOutputIntent`` ``/S``
subtype reading and the embedded ``/DestOutputProfile`` stream's ``/N``
(number of ICC colour components).

This complements ``test_output_intent_oracle.py`` (which covers the four
string fields + the ICC profile's decoded byte length / SHA-1) by pinning the
two facets that file does not exercise: the conformance subtype (``/S``, e.g.
``GTS_PDFA1``) and the ``/N`` integer recorded on the ICC profile stream.

Apache PDFBox 3.0's ``PDOutputIntent`` exposes no ``getSubtype()`` /
``getN()`` accessor, so the Java probe
(``oracle/probes/OutputIntentSubtypeProbe.java``) reads ``/S`` straight off the
output-intent ``COSDictionary`` via ``getNameAsString(COSName.S)`` and ``/N``
off the ``/DestOutputProfile`` stream dictionary via ``getInt(COSName.N)``
(which yields ``-1`` when absent). These are exactly the raw entries that
pypdfbox's :meth:`PDOutputIntent.get_subtype` and the ``/N`` integer on the
dest-profile stream resolve.

The Python side reconstructs the same view through
``catalog.get_output_intents()`` and asserts byte-for-byte equality with
PDFBox. A subtype or ``/N`` mismatch is a real bug in ``pd_output_intent.py``
(or the catalog accessor).

Two fixtures:

* ``tests/fixtures/multipdf/PDFA3A.pdf`` — a real PDF/A-3 file carrying one
  ``GTS_PDFA1`` output intent with an embedded sRGB ICC profile. Tests the
  read path against an upstream-produced file.
* A synthetic PDF built by pypdfbox: a fresh ``PDOutputIntent`` (subtype set
  via the ``(document, profile)`` constructor to ``GTS_PDFA1``) embedding a
  Pillow-generated sRGB ICC profile (``/N == 3``), saved once and re-read by
  both readers. Tests the write+read round-trip agrees with PDFBox.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures"
_PDFA3A = _FIXTURES / "multipdf" / "PDFA3A.pdf"

_N: COSName = COSName.get_pdf_name("N")


# ---------- canonical record shared by both sides ----------


def _none_to_null(value: str | None) -> str:
    """Render the subtype the way the Java probe does: ``None`` -> the literal
    token ``null`` so both sides compare on identical text."""
    return "null" if value is None else value


def _parse_probe(text: str) -> list[dict[str, str]]:
    """Parse the probe's ``count=`` header + per-intent blocks into a list of
    field dicts (one per output intent)."""
    lines = [ln for ln in text.splitlines() if ln != ""]
    assert lines, "probe emitted no output"
    assert lines[0].startswith("count="), f"unexpected header: {lines[0]!r}"
    count = int(lines[0].split("=", 1)[1])
    intents: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines[1:]:
        if line.startswith("intent "):
            current = {}
            intents.append(current)
            continue
        assert current is not None, f"field line before 'intent': {line!r}"
        key, _, val = line.partition("=")
        current[key] = val
    assert len(intents) == count, f"count={count} but parsed {len(intents)}"
    return intents


def _dest_profile_n(oi) -> int:
    """Read ``/N`` straight off the ``/DestOutputProfile`` stream dictionary,
    mirroring the Java probe's ``profile.getInt(COSName.N)`` (``-1`` when the
    profile or the entry is absent). Deliberately *not* the header-sniffing
    :meth:`PDOutputIntent.get_n_for_profile`, so this asserts the raw stored
    integer matches upstream byte-for-byte."""
    stream = oi.get_dest_output_intent()
    if not isinstance(stream, COSStream):
        return -1
    return stream.get_int(_N)


def _pypdfbox_records(path: Path) -> list[dict[str, str]]:
    """Reproduce the probe's records from pypdfbox. Closes the document in a
    finally so an open handle never locks the file on Windows."""
    doc = PDDocument.load(path)
    try:
        records: list[dict[str, str]] = []
        for oi in doc.get_document_catalog().get_output_intents():
            records.append(
                {
                    "subtype": _none_to_null(oi.get_subtype()),
                    "n": str(_dest_profile_n(oi)),
                }
            )
        return records
    finally:
        doc.close()


def _assert_parity(path: Path) -> list[dict[str, str]]:
    java = _parse_probe(run_probe_text("OutputIntentSubtypeProbe", str(path)))
    py = _pypdfbox_records(path)
    assert len(py) == len(java), (
        f"output-intent count: pypdfbox {len(py)} != PDFBox {len(java)}"
    )
    for i, (j, p) in enumerate(zip(java, py, strict=True)):
        for key in ("subtype", "n"):
            assert p[key] == j[key], (
                f"intent {i} field {key!r}: pypdfbox {p[key]!r} != "
                f"PDFBox {j[key]!r}"
            )
    return java


# ---------- fixture-based parity ----------


@requires_oracle
def test_output_intent_subtype_parity_pdfa3a() -> None:
    """pypdfbox's view of the PDFA3A.pdf output intent's /S subtype and the
    embedded ICC profile's /N matches PDFBox byte-for-byte."""
    records = _assert_parity(_PDFA3A)
    # Sanity: the fixture really does carry one GTS_PDFA1 intent with an
    # embedded sRGB ICC profile, so the parity assertions exercised a
    # non-trivial record (not an empty list trivially equal on both sides).
    assert len(records) == 1
    rec = records[0]
    assert rec["subtype"] == "GTS_PDFA1"
    assert int(rec["n"]) == 3  # sRGB -> RGB -> 3 components


# ---------- synthetic write+read round-trip parity ----------


def _build_srgb_icc() -> bytes:
    """An sRGB ICC profile via Pillow's ImageCms (LittleCMS2-backed). RGB
    colour space, so /N == 3. Pillow is already a declared dependency."""
    from PIL import ImageCms

    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


@requires_oracle
def test_output_intent_subtype_parity_synthetic_roundtrip() -> None:
    """Build a PDF via pypdfbox with a ``(document, profile)`` output intent
    (subtype defaults to ``GTS_PDFA1``, ``/N`` inferred as 3 for sRGB RGB),
    save once, and confirm PDFBox reads back the same ``/S`` and ``/N`` as
    pypdfbox does."""
    from pypdfbox.pdmodel.graphics.color.pd_output_intent import PDOutputIntent

    icc = _build_srgb_icc()
    assert icc[36:40] == b"acsp", "generated profile lacks ICC 'acsp' magic"

    fd, tmp_name = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    out_path = Path(tmp_name)
    try:
        doc = PDDocument()
        try:
            from pypdfbox.pdmodel.pd_page import PDPage

            doc.add_page(PDPage())
            intent = PDOutputIntent(doc, icc)
            intent.set_output_condition_identifier("sRGB IEC61966-2.1")
            doc.get_document_catalog().add_output_intent(intent)
            # The (document, profile) constructor sets /S = GTS_PDFA1 and
            # infers /N from the ICC header colour-space (RGB -> 3).
            assert intent.get_subtype() == "GTS_PDFA1"
            doc.save(str(out_path))
        finally:
            doc.close()

        java = _assert_parity(out_path)
        assert len(java) == 1
        rec = java[0]
        assert rec["subtype"] == "GTS_PDFA1"
        assert int(rec["n"]) == 3
    finally:
        out_path.unlink()
