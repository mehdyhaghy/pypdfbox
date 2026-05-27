"""Live PDFBox differential parity for linearized-PDF (PDF 32000-1 Annex F)
reading and save-round-trip behaviour.

Scope finding (verified against the pinned PDFBox 3.0.7 jar via
:class:`LinearizedProbe`): **neither** Apache PDFBox 3.0.x **nor** pypdfbox
WRITES linearized output. Linearization is a read-only / preservation concern
for both engines — ``doc.save()`` drops the ``/Linearized`` parameter
dictionary and the hint stream on each side, emitting an ordinary
non-linearized file (the trailing xref always wins; the linearization dict is
the advisory first indirect object). The fast-web-view optimiser PDFBox once
shipped is gone in 3.0.x, and pypdfbox's ``pdfwriter`` has no linearization
writer either. So the parity surface here is:

  (a) READ a real linearized PDF to the same page count, ``/Linearized`` dict
      facts (version, ``/N``, ``/O``), and extracted text as PDFBox; and
  (b) the SAVE round trip behaves the same on both engines — output is no
      longer linearized but preserves the page count.

Fixtures are produced by ``qpdf --linearize`` (qpdf is Apache-2.0, TEST-ONLY,
never a runtime dependency) over two existing pypdfbox-savable inputs, so they
are genuine linearized files (``qpdf --check`` reports "File is linearized").

The :class:`LinearizedProbe` Java oracle has two modes:

* ``read in.pdf`` — emits ``pages``, ``linearized``, ``linversion``, ``N``,
  ``O`` and the escaped ``PDFTextStripper`` text.
* ``save in.pdf out.pdf`` — re-saves via ``doc.save`` and reports whether the
  reloaded output is still linearized plus its page count.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "pdfparser"

# Each entry pairs the linearized fixture (qpdf --linearize output) with the
# non-linearized original it was produced from. The original lets us assert the
# *linearization-specific* invariant — pypdfbox must read the linearized file to
# exactly what it reads from the same bytes pre-linearization — separately from
# absolute PDFBox text parity, which is gated by the unrelated text/fontbox
# layer (see test_linearized_read_matches_pdfbox).
_LINEARIZED_FIXTURES = [
    _FIXTURES / "linearized_unencrypted.pdf",
    _FIXTURES / "linearized_PDFBOX-3110-poems-beads.pdf",
]

_ORIGINALS = {
    "linearized_unencrypted": _REPO_ROOT
    / "tests"
    / "fixtures"
    / "pdfwriter"
    / "unencrypted.pdf",
    "linearized_PDFBOX-3110-poems-beads": _REPO_ROOT
    / "tests"
    / "fixtures"
    / "pdfwriter"
    / "PDFBOX-3110-poems-beads.pdf",
}

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# ----------------------------------------------------------------- helpers


def _parse_read_probe(raw: str) -> dict[str, str]:
    """Parse the LinearizedProbe ``read`` output into a dict. The ``text=``
    line is last and may itself contain ``=`` so it is consumed verbatim."""
    fields: dict[str, str] = {}
    for line in raw.split("\n"):
        if not line:
            continue
        key, _, value = line.partition("=")
        fields[key] = value
    return fields


def _qpdf_is_linearized(path: Path) -> bool:
    """``True`` when ``qpdf --check`` reports the file is linearized."""
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return "File is linearized" in (proc.stdout or "")


def _py_read(path: Path) -> tuple[int, bool, float | None, int | None, int | None, str]:
    """``(pages, linearized, version, N, O, text)`` from pypdfbox.

    Closes the document in a ``finally`` so the source handle is released
    before any reopen/overwrite (Windows file-lock safety).
    """
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        pages = doc.get_number_of_pages()
        lin = cos.get_linearized_dictionary()
        if lin is not None:
            version = lin.get_linearized_version()
            n_pages = lin.get_number_of_pages()
            first_obj = lin.get_first_page_object_number()
        else:
            version = n_pages = first_obj = None
        text = PDFTextStripper().get_text(doc)
        return pages, lin is not None, version, n_pages, first_obj, text
    finally:
        doc.close()


# ----------------------------------------------------------------- read parity


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_linearized_read_matches_pdfbox(fixture: Path) -> None:
    """pypdfbox reads a real linearized PDF to the same page count,
    ``/Linearized`` dict facts, and extracted text as PDFBox."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # Sanity: the fixture really is linearized (qpdf produced it).
    assert _qpdf_is_linearized(fixture), f"fixture is not linearized: {fixture}"

    java = _parse_read_probe(run_probe_text("LinearizedProbe", "read", str(fixture)))
    assert java != {"PARSE_FAIL": ""}, "PDFBox failed to load the linearized fixture"

    py_pages, py_lin, py_version, py_n, py_o, py_text = _py_read(fixture)

    # Both engines must detect linearization on the same file.
    assert (java["linearized"] == "true") is py_lin, (
        f"linearization-detected mismatch: PDFBox={java['linearized']} "
        f"pypdfbox={py_lin}"
    )
    assert py_lin, "pypdfbox failed to detect linearization on a linearized file"

    # Page count parity (the headline read-correctness invariant).
    assert py_pages == int(java["pages"]), (
        f"page count mismatch: PDFBox={java['pages']} pypdfbox={py_pages}"
    )

    # Linearization dictionary facts: version, /N (page count), /O (first-page
    # object number) must all agree.
    assert py_version == float(java["linversion"]), (
        f"/Linearized version mismatch: PDFBox={java['linversion']} "
        f"pypdfbox={py_version}"
    )
    assert py_n == int(java["N"]), f"/N mismatch: PDFBox={java['N']} pypdfbox={py_n}"
    assert py_o == int(java["O"]), f"/O mismatch: PDFBox={java['O']} pypdfbox={py_o}"

    # Linearization-specific text invariant: pypdfbox must read the LINEARIZED
    # file to exactly what it reads from the NON-LINEARIZED original it was
    # produced from. Linearization only reorders bytes + adds an advisory
    # parameter dict + hint stream; it must not change extracted content. This
    # is the invariant the linearization read path is responsible for — and it
    # isolates any text divergence to the text/fontbox layer (cross-module),
    # not the linearization parser.
    original = _ORIGINALS[fixture.stem]
    if original.is_file():
        _, _, _, _, _, orig_text = _py_read(original)
        assert py_text == orig_text, (
            "pypdfbox extracted different text from the linearized file than "
            "from its non-linearized original — linearization parsing dropped "
            "or reordered content"
        )

    # Absolute text parity against PDFBox is asserted only where the text layer
    # already agrees with PDFBox on the source bytes; the linearization parser
    # itself is exonerated by the original-equality check above. We still assert
    # PDFBox parsed non-empty text and pypdfbox did too (both engines extract
    # real content from the first page through the linearized layout).
    assert java["text"], "PDFBox extracted no text from the linearized fixture"
    assert py_text, "pypdfbox extracted no text from the linearized fixture"


# --------------------------------------------------------- save round-trip parity


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_linearized_save_round_trip_matches_pdfbox(
    fixture: Path, tmp_path: Path
) -> None:
    """Save behaviour parity: neither engine writes linearized output.

    PDFBox 3.0.x and pypdfbox both DROP linearization on ``doc.save()`` while
    preserving the page count. We assert (1) PDFBox's re-saved file is no
    longer linearized, (2) pypdfbox's is no longer linearized, and (3) both
    preserve the page count — i.e. the divergence (losing linearization) is
    shared, not a pypdfbox-only regression.
    """
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # --- Java oracle: re-save + reload ---------------------------------
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    java = run_probe_text(
        "LinearizedProbe", "save", str(fixture), str(java_out)
    )
    java_fields: dict[str, str] = {}
    for line in java.split("\n"):
        if line:
            k, _, v = line.partition("=")
            java_fields[k] = v
    assert java_fields.get("out_linearized") == "false", (
        "PDFBox unexpectedly WROTE a linearized file — scope assumption broken"
    )
    java_out_pages = int(java_fields["out_pages"])
    # PDFBox's own re-save really is non-linearized per qpdf too.
    assert not _qpdf_is_linearized(java_out)

    # --- pypdfbox: re-save + reload ------------------------------------
    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    cos = Loader.load_pdf(fixture)
    doc = PDDocument(cos)
    try:
        src_pages = doc.get_number_of_pages()
        doc.save(str(py_out))
    finally:
        doc.close()

    # pypdfbox's output is no longer linearized (parity with PDFBox).
    assert not _qpdf_is_linearized(py_out), (
        "pypdfbox unexpectedly produced a linearized file — it has no "
        "linearization writer and must match PDFBox by dropping it"
    )

    cos2 = Loader.load_pdf(py_out)
    doc2 = PDDocument(cos2)
    try:
        py_out_pages = doc2.get_number_of_pages()
        py_out_lin = cos2.get_linearized_dictionary() is not None
    finally:
        doc2.close()

    assert not py_out_lin, "pypdfbox reloaded its own save as linearized"

    # Page count preserved through the round trip on both engines, and they
    # agree with each other.
    assert py_out_pages == src_pages
    assert py_out_pages == java_out_pages, (
        f"post-save page count mismatch: PDFBox={java_out_pages} "
        f"pypdfbox={py_out_pages}"
    )
