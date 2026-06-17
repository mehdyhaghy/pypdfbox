"""Live Apache PDFBox differential parity for ``PDOutputIntent`` /
``/OutputIntents`` reading.

The Java side is ``oracle/probes/OutputIntentProbe.java``: it loads a PDF and,
for every ``PDOutputIntent`` in ``catalog.getOutputIntents()``, emits canonical
lines for the four string fields (output condition, output condition
identifier, registry name, info) plus the embedded ``/DestOutputProfile`` ICC
profile's decoded byte length and SHA-1. Null string fields are emitted as the
literal token ``null``.

The Python side reconstructs the same view through
``catalog.get_output_intents()`` and the ``PDOutputIntent`` getters, decoding
the ``/DestOutputProfile`` stream via :meth:`PDStream.to_byte_array`, and
asserts byte-for-byte equality with PDFBox.

Two fixtures:

* ``tests/fixtures/multipdf/PDFA3A.pdf`` — a real PDF/A-3 file carrying one
  ``GTS_PDFA1`` output intent with an embedded sRGB ICC profile (3144 decoded
  bytes). Tests the read path against an upstream-produced file.
* A synthetic PDF built by pypdfbox in this test: a fresh ``PDOutputIntent``
  embedding a Pillow-generated sRGB ICC profile, saved once to a temp file,
  then re-read by both PDFBox and pypdfbox. Tests the write+read round-trip
  agrees with PDFBox's reader.

A field mismatch or a wrong / missing ICC profile length-or-hash is a real bug
in ``pd_output_intent.py`` (or the catalog accessor).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures"
_PDFA3A = _FIXTURES / "multipdf" / "PDFA3A.pdf"


# ---------- canonical record shared by both sides ----------


def _none_to_null(value: str | None) -> str:
    """Render a string field the way the Java probe does: ``None`` -> the
    literal token ``null`` so both sides compare on identical text."""
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


def _pypdfbox_records(path: Path) -> list[dict[str, str]]:
    """Reproduce the probe's records from pypdfbox. Closes the document in a
    finally so an open handle never locks the file on Windows."""
    doc = PDDocument.load(path)
    try:
        records: list[dict[str, str]] = []
        for oi in doc.get_document_catalog().get_output_intents():
            stream = oi.get_dest_output_profile()
            if stream is None:
                icc_len = "-1"
                icc_sha1 = "-"
            else:
                data = stream.to_byte_array()
                icc_len = str(len(data))
                icc_sha1 = hashlib.sha1(data).hexdigest()  # noqa: S324
            records.append(
                {
                    "condition": _none_to_null(oi.get_output_condition()),
                    "conditionIdentifier": _none_to_null(
                        oi.get_output_condition_identifier()
                    ),
                    "registryName": _none_to_null(oi.get_registry_name()),
                    "info": _none_to_null(oi.get_info()),
                    "icc.len": icc_len,
                    "icc.sha1": icc_sha1,
                }
            )
        return records
    finally:
        doc.close()


def _assert_parity(path: Path) -> list[dict[str, str]]:
    java = _parse_probe(run_probe_text("OutputIntentProbe", str(path)))
    py = _pypdfbox_records(path)
    assert len(py) == len(java), (
        f"output-intent count: pypdfbox {len(py)} != PDFBox {len(java)}"
    )
    for i, (j, p) in enumerate(zip(java, py, strict=True)):
        for key in (
            "condition",
            "conditionIdentifier",
            "registryName",
            "info",
            "icc.len",
            "icc.sha1",
        ):
            assert p[key] == j[key], (
                f"intent {i} field {key!r}: pypdfbox {p[key]!r} != "
                f"PDFBox {j[key]!r}"
            )
    return java


# ---------- fixture-based parity ----------


@requires_oracle
def test_output_intent_parity_pdfa3a() -> None:
    """pypdfbox's view of the PDFA3A.pdf output intent (fields + embedded ICC
    length/SHA) matches PDFBox byte-for-byte."""
    records = _assert_parity(_PDFA3A)
    # Sanity: the fixture really does carry one GTS_PDFA1 intent with an
    # embedded sRGB ICC profile, so we know the parity assertions exercised a
    # non-trivial record (not an empty list trivially equal on both sides).
    assert len(records) == 1
    rec = records[0]
    assert rec["conditionIdentifier"] == "sRGB"
    assert rec["registryName"] == "http://www.color.org"
    assert rec["condition"] == "null"
    assert int(rec["icc.len"]) > 0
    assert rec["icc.sha1"] != "-"


# ---------- synthetic write+read round-trip parity ----------


def _build_srgb_icc() -> bytes:
    """An sRGB ICC profile via Pillow's ImageCms (LittleCMS2-backed). RGB
    colour space, so /N == 3. Pillow is already a declared dependency."""
    from PIL import ImageCms

    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


@requires_oracle
def test_output_intent_parity_synthetic_roundtrip() -> None:
    """Build a PDF via pypdfbox with an output intent embedding an sRGB ICC
    profile, save once, and confirm PDFBox reads back the same fields and the
    same decoded ICC bytes (length + SHA-1) as pypdfbox does."""
    from pypdfbox.pdmodel.graphics.color.pd_output_intent import PDOutputIntent

    icc = _build_srgb_icc()
    assert icc[36:40] == b"acsp", "generated profile lacks ICC 'acsp' magic"

    # mkstemp returns an os-level fd (no open Python file object) so we can
    # close it immediately and let pypdfbox / PDFBox own the path — avoids the
    # Windows "file opened exclusively by NamedTemporaryFile" reopen problem.
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    out_path = Path(tmp_name)
    try:
        doc = PDDocument()
        try:
            # A page so the saved file is a well-formed PDF PDFBox will load.
            from pypdfbox.pdmodel.pd_page import PDPage

            doc.add_page(PDPage())
            intent = PDOutputIntent(doc, icc)
            intent.set_output_condition_identifier("sRGB IEC61966-2.1")
            intent.set_registry_name("http://www.color.org")
            intent.set_info("synthetic sRGB output intent")
            doc.get_document_catalog().add_output_intent(intent)
            doc.save(str(out_path))
        finally:
            doc.close()

        java = _assert_parity(out_path)
        assert len(java) == 1
        rec = java[0]
        assert rec["conditionIdentifier"] == "sRGB IEC61966-2.1"
        assert rec["registryName"] == "http://www.color.org"
        assert rec["info"] == "synthetic sRGB output intent"
        # condition was never set -> absent -> null on both sides.
        assert rec["condition"] == "null"
        # The decoded ICC bytes PDFBox reads back must equal what we embedded.
        assert int(rec["icc.len"]) == len(icc)
        assert rec["icc.sha1"] == hashlib.sha1(icc).hexdigest()  # noqa: S324
    finally:
        out_path.unlink()
