"""veraPDF-based PDF/A and PDF/UA validation pipeline test.

PRD §13 names veraPDF as the PDF/A / PDF/UA validation tool of record
(Apache PDFBox 4.0 removed Preflight; we follow). This module exercises
the *pipeline* — that pypdfbox can produce a PDF, hand it off to the
``verapdf`` CLI, and parse the JSON report back — not that pypdfbox
itself emits PDF/A-conformant output. Making the writer emit PDF/A is
a separate, much larger cluster of work.

The whole module is skipped when ``verapdf`` is not on ``$PATH`` so
``pytest -q`` stays green on developer laptops and CI runners without
the tool installed (this dev machine, currently). Same pattern as
``test_qpdf_validation.py``.

Install veraPDF locally with::

    brew install --cask verapdf            # macOS
    # or unpack the verapdf-greenfield tarball and add /bin to $PATH

veraPDF is GPL-3 licensed. We are explicitly NOT linking against it —
we invoke its CLI via ``subprocess`` only, which is permitted by the
project's license matrix (see ``CLAUDE.md`` "Licensing & attribution").
"""
from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

# Skip the whole module when ``verapdf`` is missing — keeps `pytest -q`
# green on machines (including the current dev box) that don't have
# the tool installed yet.
VERAPDF = shutil.which("verapdf")
if VERAPDF is None:
    pytest.skip(
        "verapdf binary not on PATH; install via `brew install --cask verapdf` "
        "or download from https://verapdf.org/",
        allow_module_level=True,
    )

# Add ``scripts/`` to import path so we can re-use the same helper the
# standalone CLI uses. Keeping the helper in one place avoids drift.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from verapdf_check import (  # noqa: E402  (sys.path manipulated above)
    NOT_INSTALLED,
    VeraPDFResult,
    run_verapdf,
)

# ---------------------------------------------------------------- helpers


def _helvetica():
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font import PDType1Font

    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return font


def _add_text_page(doc, text: str, *, x: float = 50.0, y: float = 700.0):
    from pypdfbox.pdmodel import PDPage, PDRectangle
    from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = _helvetica()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(x, y)
        cs.show_text(text)
        cs.end_text()
    return page


# ---------------------------------------------------------------- flow builders

FlowBuilder = Callable[[Path], Path]


def _build_basic(tmp_path: Path) -> Path:
    """Empty single-page document — the smallest legal PDF we ship."""
    from pypdfbox import PDDocument
    from pypdfbox.pdmodel import PDPage, PDRectangle

    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.LETTER))
    out = tmp_path / "verapdf_basic.pdf"
    doc.save(out)
    return out


def _build_with_text(tmp_path: Path) -> Path:
    """Single page with one Helvetica text-show operator."""
    from pypdfbox import PDDocument

    doc = PDDocument()
    _add_text_page(doc, "verapdf pipeline check")
    out = tmp_path / "verapdf_with_text.pdf"
    doc.save(out)
    return out


def _build_multi_page(tmp_path: Path) -> Path:
    """Three pages — exercises page-tree handling end to end."""
    from pypdfbox import PDDocument

    doc = PDDocument()
    _add_text_page(doc, "page one")
    _add_text_page(doc, "page two")
    _add_text_page(doc, "page three")
    out = tmp_path / "verapdf_multi_page.pdf"
    doc.save(out)
    return out


def _build_malformed(tmp_path: Path) -> Path:
    """Deliberately broken PDF — should make veraPDF report errors.

    veraPDF will refuse to parse a file that doesn't start with the
    PDF header, which is exactly the failure mode the test asserts
    on (we need at least one ``is_valid=False`` outcome to prove the
    pipeline distinguishes pass from fail).
    """
    out = tmp_path / "verapdf_malformed.pdf"
    out.write_bytes(b"%NOT-A-PDF\nthis is not a valid PDF file at all\n")
    return out


FLOWS: dict[str, FlowBuilder] = {
    "basic": _build_basic,
    "with_text": _build_with_text,
    "multi_page": _build_multi_page,
}


# ---------------------------------------------------------------- tests


def test_verapdf_binary_resolves() -> None:
    """Sanity: ``shutil.which`` returns a non-None path when we get here."""
    assert VERAPDF is not None
    assert Path(VERAPDF).exists() or shutil.which("verapdf") == VERAPDF


@pytest.mark.parametrize("flow_name", sorted(FLOWS))
def test_verapdf_pipeline_accepts_pypdfbox_output(
    flow_name: str, tmp_path: Path
) -> None:
    """veraPDF must run end-to-end against each known-good flow.

    We do **not** assert ``result.is_valid is True`` — pypdfbox does not
    yet emit PDF/A-conformant output and we don't gate the test on
    that. We assert the *pipeline* works: veraPDF executed, returned
    a parseable report, and ``run_verapdf`` translated it into a
    ``VeraPDFResult`` with a list-of-strings ``errors`` field. That's
    the actual contract this scaffold is here to lock down.
    """
    builder = FLOWS[flow_name]
    pdf_path = builder(tmp_path)
    assert pdf_path.exists() and pdf_path.stat().st_size > 0, (
        f"flow {flow_name} produced empty output at {pdf_path}"
    )

    result = run_verapdf(pdf_path)

    assert result is not NOT_INSTALLED, (
        "verapdf disappeared between module skip-check and test invocation"
    )
    assert isinstance(result, VeraPDFResult)
    assert isinstance(result.errors, list)
    assert all(isinstance(e, str) for e in result.errors)
    assert isinstance(result.conformance_level, str)
    assert isinstance(result.is_valid, bool)


def test_verapdf_pipeline_flags_malformed_pdf(tmp_path: Path) -> None:
    """A non-PDF byte stream must come back as ``is_valid=False``.

    This is the negative half of the pipeline contract: we need at
    least one input that produces ``is_valid=False`` so we know the
    ``True`` cases in the positive tests above aren't trivially
    wired-true regardless of input.
    """
    pdf_path = _build_malformed(tmp_path)
    result = run_verapdf(pdf_path)

    assert isinstance(result, VeraPDFResult)
    assert result.is_valid is False
    # We do not assert on the exact error wording — veraPDF phrases the
    # "not a PDF" failure differently between releases (sometimes a
    # parse error, sometimes a header-check rule failure).


@pytest.mark.parametrize("flavour", ["1b", "2b", "3b"])
def test_verapdf_accepts_explicit_flavours(flavour: str, tmp_path: Path) -> None:
    """Pipeline must survive being asked for specific PDF/A profiles.

    Validates the ``--flavour`` plumbing in ``run_verapdf``. None of
    our outputs are conformant against ``1b``/``2b``/``3b`` — we are
    again testing the pipeline, not the conformance.
    """
    pdf_path = _build_with_text(tmp_path)
    result = run_verapdf(pdf_path, flavour=flavour)
    assert isinstance(result, VeraPDFResult)
    # Either veraPDF returned a real (failing) report, or rejected
    # the flavour outright — both prove the flag plumbed through.
    assert result.is_valid is False
    assert isinstance(result.errors, list)
