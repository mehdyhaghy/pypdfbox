"""Live PDFBox differential parity for PDF 1.5 hybrid-reference parsing and
/Extends object-stream chains on the READ side.

A *hybrid-reference* file (PDF 32000-1 §7.5.8.4) carries BOTH a classic xref
table and a cross-reference stream pointed at by the trailer's ``/XRefStm``
key. Legacy (pre-1.5) readers use the table; 1.5+ readers must additionally
consult ``/XRefStm`` to find objects listed only there — typically compressed
objects in an ObjStm and marked free/absent in the classic table. A
table-only parser would silently miss such an object.

Separately, an object stream may chain to a prior one via ``/Extends``. The
key parity surface is that an object whose xref entry routes it into the
*extending* ObjStm resolves through that container even though ``/Extends``
references the base ObjStm.

Both invariants are checked against the pinned PDFBox 3.0.7 jar via
:class:`HybridXrefProbe` (modes documented in ``oracle/probes/HybridXrefProbe.java``).

Fixtures (hand-crafted, validated with ``qpdf --check`` reporting no syntax
errors — qpdf is Apache-2.0, TEST-ONLY, never a runtime dependency):

* ``hybrid_xrefstm.pdf`` — classic table lists objects 1-7, object 6 is marked
  free in the table and exists ONLY in ObjStm 7, listed ONLY in the ``/XRefStm``
  cross-reference stream (object 8). A table-only reader misses object 6.
* ``extends_objstm_chain.pdf`` — base ObjStm 7 packs object 6; extending ObjStm
  8 (``/Extends 7 0 R``) packs object 9; a single ``/Type /XRef`` stream routes
  6 -> container 7 and 9 -> container 8.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "pdfparser"

_HYBRID = _FIXTURES / "hybrid_xrefstm.pdf"
_EXTENDS = _FIXTURES / "extends_objstm_chain.pdf"

_MARKER = COSName.get_pdf_name("Marker")
_VALUE = COSName.get_pdf_name("Value")


# ----------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, str]:
    """Parse the probe's ``facts`` output. The ``text=`` line is last and may
    itself contain ``=`` / newlines, so it is consumed verbatim once seen."""
    fields: dict[str, str] = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        key, sep, value = line.partition("=")
        if not sep:
            i += 1
            continue
        if key == "text":
            # Everything from here on is the raw text payload.
            fields["text"] = "\n".join([value, *lines[i + 1 :]])
            break
        fields[key] = value
        i += 1
    return fields


def _py_object_facts(path: Path, *obj_nums: int) -> dict[str, str]:
    """Mirror the probe's facts via pypdfbox: page count, resolved object
    fields, and extracted text. Closes the document in ``finally`` so the
    source handle is released (Windows file-lock safety)."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        fields: dict[str, str] = {"pages": str(doc.get_number_of_pages())}
        for num in obj_nums:
            obj = cos.get_object(COSObjectKey(num, 0))
            base = obj.get_object() if obj is not None else None
            fields[f"resolved_{num}"] = "true" if base is not None else "false"
            if isinstance(base, COSDictionary):
                type_obj = base.get_dictionary_object(COSName.TYPE)
                fields[f"type_{num}"] = (
                    type_obj.get_name() if isinstance(type_obj, COSName) else ""
                )
                marker = base.get_dictionary_object(_MARKER)
                fields[f"marker_{num}"] = (
                    marker.get_string() if isinstance(marker, COSString) else ""
                )
                fields[f"value_{num}"] = str(base.get_int(_VALUE))
        fields["text"] = PDFTextStripper().get_text(doc)
        return fields
    finally:
        doc.close()


# ----------------------------------------------------------------- hybrid /XRefStm


@requires_oracle
def test_hybrid_xrefstm_only_object_matches_pdfbox() -> None:
    """pypdfbox resolves the hybrid-reference file's ``/XRefStm``-only object
    (object 6) to the same dictionary, page count, and text as PDFBox.

    Object 6 is marked FREE in the classic xref table and only appears in the
    ``/XRefStm`` cross-reference stream — a table-only parser would miss it.
    This is the headline regression guard for hybrid parsing.
    """
    assert _HYBRID.is_file(), f"fixture missing: {_HYBRID}"

    java = _parse_facts(
        run_probe_text("HybridXrefProbe", "facts", str(_HYBRID), "6")
    )
    py = _py_object_facts(_HYBRID, 6)

    assert java["resolved_6"] == "true", "PDFBox failed to resolve the hybrid-only object"
    assert py["resolved_6"] == "true", (
        "pypdfbox missed the /XRefStm-only object — it did not consult the "
        "hybrid cross-reference stream"
    )

    assert py["pages"] == java["pages"]
    assert py["type_6"] == java["type_6"] == "HybridOnly"
    assert py["marker_6"] == java["marker_6"] == "only-via-xrefstm"
    assert py["value_6"] == java["value_6"] == "42"
    assert py["text"] == java["text"]


@requires_oracle
def test_hybrid_detected_as_hybrid() -> None:
    """pypdfbox flags the file as hybrid (it consulted ``/XRefStm``)."""
    assert _HYBRID.is_file(), f"fixture missing: {_HYBRID}"
    cos = Loader.load_pdf(_HYBRID)
    doc = PDDocument(cos)
    try:
        assert cos.has_hybrid_xref(), (
            "pypdfbox did not record the file as having a hybrid /XRefStm"
        )
    finally:
        doc.close()


# ----------------------------------------------------------------- /Extends chain


@requires_oracle
def test_extends_objstm_chain_matches_pdfbox() -> None:
    """pypdfbox resolves both the base-ObjStm object (6) and the
    ``/Extends``-chained extending-ObjStm object (9) to the same dictionaries,
    page count, and text as PDFBox."""
    assert _EXTENDS.is_file(), f"fixture missing: {_EXTENDS}"

    java = _parse_facts(
        run_probe_text("HybridXrefProbe", "facts", str(_EXTENDS), "6", "9")
    )
    py = _py_object_facts(_EXTENDS, 6, 9)

    assert java["resolved_6"] == "true" and java["resolved_9"] == "true", (
        "PDFBox failed to resolve a base/extending ObjStm object"
    )
    assert py["resolved_6"] == "true", "pypdfbox missed the base-ObjStm object"
    assert py["resolved_9"] == "true", (
        "pypdfbox missed the /Extends-chained object in the extending ObjStm"
    )

    assert py["pages"] == java["pages"]

    # Base ObjStm object.
    assert py["type_6"] == java["type_6"] == "BaseObjStmEntry"
    assert py["marker_6"] == java["marker_6"] == "in-base-objstm"
    assert py["value_6"] == java["value_6"] == "100"

    # Extending ObjStm object (routed through container 8, which /Extends 7).
    assert py["type_9"] == java["type_9"] == "ExtendedObjStmEntry"
    assert py["marker_9"] == java["marker_9"] == "in-extending-objstm"
    assert py["value_9"] == java["value_9"] == "200"

    assert py["text"] == java["text"]
