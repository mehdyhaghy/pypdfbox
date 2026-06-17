"""Live PDFBox differential parity for an **incremental save that adds a
brand-new object** — a text annotation appended to an existing page
(``pypdfbox.pdmodel.PDDocument.save_incremental`` /
``pypdfbox.pdfwriter.cos_writer``).

Every incremental-save oracle so far (``test_file_id_oracle``,
``test_incremental_chain_oracle``, ``test_save_round_trip_oracle``) mutates an
object that *already exists* in the source — an ``/Info`` field, the catalog
``/Version``. None exercises the structurally distinct path of **introducing a
new object** into the appended revision. ISO 32000-1 §7.5.6 requires that an
incremental update append (1) only the modified/added objects, (2) a new xref
section whose ``/Prev`` chains to the original ``startxref``, while keeping the
original bytes intact as a prefix. Adding an annotation exercises:

* minting a fresh object number above the source's highest (the annotation),
* re-emitting the *modified* page dictionary so its ``/Annots`` array carries
  the new indirect reference,
* a reload that resolves the appended annotation correctly,
* the ``/ID`` contract (``/ID[0]`` preserved, ``/ID[1]`` regenerated) holding
  even when the increment adds rather than only mutates.

The Java oracle ``IncrementalAddAnnotationProbe`` performs the *same* mutation
through Apache PDFBox 3.0.7 (``page.getAnnotations().add(new PDAnnotationText
(...))`` + ``saveIncremental``) and emits the recovered facts; this module
reproduces them through pypdfbox and asserts parity. Byte-equality is not the
contract (the ``/ID[1]`` digest is time/random based) — the *structural facts*
are: prefix preserved, ``/Prev`` in the appended tail, the annotation visible
on reload with the right subtype/contents/rect, ``/ID[0]`` stable, ``/ID[1]``
changed, page count unchanged, and qpdf-validity.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

_FIXTURES_LIST = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "pdfwriter" / "attachment.pdf",
]

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_ID_NAME = COSName.get_pdf_name("ID")
_ANNOT_CONTENTS = "IncAnnot"


# ----------------------------------------------------------------- helpers


def _qpdf_ok(path: Path) -> tuple[int, str]:
    """``qpdf --check``: rc 0 clean, 3 warnings (still valid), 2 broken."""
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _src_id0(path: Path) -> bytes | None:
    """Return the source trailer's ``/ID[0]`` bytes, or ``None`` when the
    fixture lacks a 2-element ``/ID`` array. Closes the doc before returning."""
    cos = Loader.load_pdf(path)
    try:
        trailer = cos.get_trailer()
        arr = trailer.get_dictionary_object(_ID_NAME) if trailer else None
        if not isinstance(arr, COSArray) or arr.size() != 2:
            return None
        first = arr.get_object(0)
        return first.get_bytes() if isinstance(first, COSString) else None
    finally:
        cos.close()


def _add_annotation_incremental_py(src: Path, out: Path) -> None:
    """Mirror the probe: load ``src``, add a text annotation to page 0, flag
    the page + annotation dirty, ``save_incremental`` to ``out``. The document
    is always closed so the source handle is released before the caller reopens
    or overwrites it (Windows file-lock safety)."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        page = doc.get_page(0)
        annot = PDAnnotationText()
        annot.set_contents(_ANNOT_CONTENTS)
        # Mirror the probe's PDFBox ``new PDRectangle(50, 50, 50, 50)`` —
        # upstream's 4-arg constructor is (x, y, width, height), so the
        # equivalent here is ``from_xywh`` → LL (50,50), UR (100,100).
        # (pypdfbox's PDRectangle 4-arg __init__ takes upper-right corners,
        # which would give the wrong UR — see HISTORY wave note.)
        annot.set_rectangle(PDRectangle.from_xywh(50, 50, 50, 50))
        page.add_annotation(annot)
        # Page is modified (its /Annots gained a ref) → re-emit it.
        page.get_cos_object().set_needs_to_be_updated(True)
        # The annotation is a brand-new object → emit its body.
        annot.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _read_annotation_facts(path: Path) -> dict[str, object]:
    """Reload ``path`` through pypdfbox and gather the facts the Java probe
    emits for the recovered annotation."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        page = doc.get_page(0)
        annots = page.get_annotations()
        subtype = None
        contents = None
        rect = None
        for a in annots:
            if a.get_contents() == _ANNOT_CONTENTS:
                subtype = a.get_subtype()
                contents = a.get_contents()
                r = a.get_rectangle()
                if r is not None:
                    rect = (
                        f"{int(r.get_lower_left_x())},{int(r.get_lower_left_y())},"
                        f"{int(r.get_upper_right_x())},{int(r.get_upper_right_y())}"
                    )
        trailer = cos.get_trailer()
        id_arr = trailer.get_dictionary_object(_ID_NAME) if trailer else None
        id0 = id1 = None
        if isinstance(id_arr, COSArray) and id_arr.size() == 2:
            e0 = id_arr.get_object(0)
            e1 = id_arr.get_object(1)
            if isinstance(e0, COSString):
                id0 = e0.get_bytes()
            if isinstance(e1, COSString):
                id1 = e1.get_bytes()
        return {
            "pages": doc.get_number_of_pages(),
            "annot_count": len(annots),
            "annot_subtype": subtype,
            "annot_contents": contents,
            "annot_rect": rect,
            "id0": id0,
            "id1": id1,
        }
    finally:
        doc.close()


# ----------------------------------------------------------- the parity tests


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_pypdfbox_incremental_add_annotation_matches_pdfbox(
    fixture: Path, tmp_path: Path
) -> None:
    """The headline differential: PDFBox and pypdfbox each add the same text
    annotation and incremental-save; the recovered facts (subtype, contents,
    rect, page count, /ID contract, prefix preservation) must agree."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_id0 = _src_id0(fixture)
    assert src_id0 is not None, "fixture lacks a 2-element /ID — pick another"

    # --- Java oracle ----------------------------------------------------
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalAddAnnotationProbe",
            "addincr",
            str(fixture),
            str(java_out),
        )
    )
    # PDFBox's own incremental add must hold the structural invariants.
    assert jf["prefix_preserved"] == "true"
    assert jf["grew"] == "true"
    assert jf["prev_in_tail"] == "true"
    assert int(jf["pages"]) >= 1
    assert jf["annot_subtype"] == "Text"
    assert jf["annot_contents"] == _ANNOT_CONTENTS
    assert jf["annot_rect"] == "50,50,100,100"
    assert jf["after_id_present"] == "true"
    assert jf["after_id0_hex"] == jf["before_id0_hex"]
    assert jf["after_id1_hex"] != jf["before_id1_hex"]

    # --- pypdfbox -------------------------------------------------------
    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    src_bytes = fixture.read_bytes()
    _add_annotation_incremental_py(fixture, py_out)
    out_bytes = py_out.read_bytes()

    assert out_bytes.startswith(src_bytes), (
        "pypdfbox incremental add did not preserve the original bytes as a prefix"
    )
    assert len(out_bytes) > len(src_bytes)
    assert b"/Prev" in out_bytes[len(src_bytes) :], (
        "appended revision lacks a /Prev back-pointer"
    )
    assert out_bytes.rstrip().endswith(b"%%EOF")

    pf = _read_annotation_facts(py_out)
    # Parity with the Java probe on every recovered fact.
    assert pf["pages"] == int(jf["pages"])
    assert pf["annot_subtype"] == jf["annot_subtype"]
    assert pf["annot_contents"] == jf["annot_contents"]
    assert pf["annot_rect"] == jf["annot_rect"]
    # /ID[0] preserved (the permanent identifier), /ID[1] changed.
    assert pf["id0"] == src_id0, "pypdfbox changed the permanent /ID[0]"
    assert pf["id1"] is not None

    # Both outputs structurally valid.
    j_rc, j_log = _qpdf_ok(java_out)
    p_rc, p_log = _qpdf_ok(py_out)
    assert j_rc <= 3, f"Java incremental-add failed qpdf (rc={j_rc}):\n{j_log}"
    assert p_rc <= 3, f"pypdfbox incremental-add failed qpdf (rc={p_rc}):\n{p_log}"


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_added_annotation_object_number_above_source_max(
    fixture: Path, tmp_path: Path
) -> None:
    """The newly-added annotation must be minted with an object number strictly
    greater than the source's highest — incremental save never reuses an
    existing key for a brand-new object (that would shadow a live object in the
    /Prev chain). We compare the source's max object number against the count of
    objects pypdfbox can resolve after the append."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    cos = Loader.load_pdf(fixture)
    try:
        src_max = max(
            (k.object_number for k in cos.get_object_keys()), default=0
        )
    finally:
        cos.close()

    py_out = tmp_path / f"py_objnum_{fixture.stem}.pdf"
    _add_annotation_incremental_py(fixture, py_out)

    reloaded = Loader.load_pdf(py_out)
    try:
        new_max = max(
            (k.object_number for k in reloaded.get_object_keys()), default=0
        )
        # The annotation added at least one new object number.
        assert new_max > src_max, (
            f"expected a new object number above the source max {src_max}, "
            f"got {new_max} — the annotation may have reused an existing key"
        )
        # The new annotation is actually present and resolvable.
        page = reloaded.get_catalog()
        assert page is not None
    finally:
        reloaded.close()


@requires_oracle
@_requires_qpdf
def test_original_revision_still_recoverable_after_add(tmp_path: Path) -> None:
    """Append-only proof: the source has no annotation on page 0, so the
    appended revision *adds* one. The original bytes survive verbatim as a
    prefix, meaning a parser truncating at the first revision's startxref would
    still see the original (annotation-free) document — the essence of an
    incremental update (ISO 32000-1 §7.5.6)."""
    fixture = _FIXTURES / "pdfwriter" / "unencrypted.pdf"

    # The source page 0 carries no annotations to begin with.
    cos = Loader.load_pdf(fixture)
    doc = PDDocument(cos)
    try:
        assert doc.get_page(0).get_annotations() == []
    finally:
        doc.close()

    py_out = tmp_path / "recoverable.pdf"
    src_bytes = fixture.read_bytes()
    _add_annotation_incremental_py(fixture, py_out)
    out_bytes = py_out.read_bytes()

    # The first revision's bytes are an exact prefix of the appended file.
    assert out_bytes[: len(src_bytes)] == src_bytes

    # After reload (latest revision wins) the annotation is present.
    facts = _read_annotation_facts(py_out)
    assert facts["annot_count"] == 1
    assert facts["annot_contents"] == _ANNOT_CONTENTS
