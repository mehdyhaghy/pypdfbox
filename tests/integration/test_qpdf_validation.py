"""qpdf-based differential validation for pypdfbox writer output.

PRD §12 ("Differential Testing Requirement") names ``qpdf --check`` and
``qpdf --qdf`` as part of the release validation stack. This module
builds a small synthetic PDF for each major save flow and asserts that
the system ``qpdf`` binary accepts the output both structurally
(``--check``) and round-trip (``--qdf --object-streams=disable``).

``qpdf`` is a system tool, not a Python dependency. The entire module
is skipped when the binary is not on ``PATH`` so developer laptops and
CI runners without ``qpdf`` installed still get a clean ``pytest -q``.

Flow inventory (kept in lock-step with ``scripts/qpdf_check.py``):

* ``basic_save`` — empty single-page document, default save path.
* ``with_text`` — single page with a Helvetica content stream.
* ``multi_page`` — three-page document, default save path.
* ``incremental_save`` — base save, reload, mutate metadata, save
  incremental.
* ``merge`` — two synthetic docs merged via ``PDFMergerUtility``.
* ``split`` — three-page document split via ``Splitter`` into singletons.
* ``xref_stream`` — save with xref-stream layout (``COSWriter`` knob).
* ``object_streams_disabled`` — save with object streams disabled.

Failures here surface real bugs in ``pypdfbox.pdfwriter`` — anything
``qpdf`` flags is a writer-side correctness issue, not a test bug.
"""
from __future__ import annotations

import io
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

# Skip the whole module when ``qpdf`` is missing — keeps `pytest -q` green
# on machines (and the current dev box) that don't have the tool yet.
QPDF = shutil.which("qpdf")
if QPDF is None:
    pytest.skip(
        "qpdf binary not on PATH; install via `brew install qpdf`.",
        allow_module_level=True,
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


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _assert_qpdf_ok(path: Path) -> None:
    """Run both ``--check`` and ``--qdf`` on ``path`` and assert success."""
    check = _run([QPDF, "--check", str(path)])
    assert check.returncode == 0, (
        f"qpdf --check rejected {path.name}: rc={check.returncode}\n"
        f"stdout={check.stdout}\nstderr={check.stderr}"
    )

    qdf_out = path.with_suffix(path.suffix + ".qdf")
    qdf = _run(
        [QPDF, "--qdf", "--object-streams=disable", str(path), str(qdf_out)]
    )
    assert qdf.returncode == 0, (
        f"qpdf --qdf rejected {path.name}: rc={qdf.returncode}\n"
        f"stdout={qdf.stdout}\nstderr={qdf.stderr}"
    )


# ---------------------------------------------------------------- flow builders

FlowBuilder = Callable[[Path], Path]


def _build_basic_save(tmp_path: Path) -> Path:
    from pypdfbox import PDDocument
    from pypdfbox.pdmodel import PDPage, PDRectangle

    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.LETTER))
    out = tmp_path / "basic_save.pdf"
    doc.save(out)
    return out


def _build_with_text(tmp_path: Path) -> Path:
    from pypdfbox import PDDocument

    doc = PDDocument()
    _add_text_page(doc, "qpdf check")
    out = tmp_path / "with_text.pdf"
    doc.save(out)
    return out


def _build_multi_page(tmp_path: Path) -> Path:
    from pypdfbox import PDDocument

    doc = PDDocument()
    _add_text_page(doc, "page one")
    _add_text_page(doc, "page two")
    _add_text_page(doc, "page three")
    out = tmp_path / "multi_page.pdf"
    doc.save(out)
    return out


def _build_incremental_save(tmp_path: Path) -> Path:
    from pypdfbox import Loader, PDDocument

    doc = PDDocument()
    _add_text_page(doc, "base")
    base = tmp_path / "incremental_base.pdf"
    doc.save(base)

    with Loader.load_pdf(base) as reloaded:
        info = reloaded.get_document_information()
        info.set_title("incremental update")
        out = tmp_path / "incremental_save.pdf"
        sink = io.BytesIO(base.read_bytes())
        reloaded.save_incremental(sink)
        out.write_bytes(sink.getvalue())
    return out


def _build_merge(tmp_path: Path) -> Path:
    from pypdfbox import PDDocument
    from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility

    src_a = tmp_path / "merge_a.pdf"
    src_b = tmp_path / "merge_b.pdf"

    doc_a = PDDocument()
    _add_text_page(doc_a, "doc a page 1")
    doc_a.save(src_a)

    doc_b = PDDocument()
    _add_text_page(doc_b, "doc b page 1")
    _add_text_page(doc_b, "doc b page 2")
    doc_b.save(src_b)

    out = tmp_path / "merge.pdf"
    merger = PDFMergerUtility()
    merger.add_source(str(src_a))
    merger.add_source(str(src_b))
    merger.set_destination_file_name(str(out))
    merger.merge_documents()
    return out


def _build_split(tmp_path: Path) -> Path:
    """Split a 3-page doc and validate the first segment."""
    from pypdfbox import PDDocument
    from pypdfbox.multipdf.splitter import Splitter

    src = PDDocument()
    _add_text_page(src, "split p1")
    _add_text_page(src, "split p2")
    _add_text_page(src, "split p3")

    splitter = Splitter()
    pieces = splitter.split(src)
    assert pieces, "splitter returned no pieces"
    first = pieces[0]
    out = tmp_path / "split_first.pdf"
    first.save(out)
    first.close()
    for extra in pieces[1:]:
        extra.close()
    return out


def _build_xref_stream(tmp_path: Path) -> Path:
    from pypdfbox import PDDocument
    from pypdfbox.pdfwriter import COSWriter

    doc = PDDocument()
    _add_text_page(doc, "xref stream")
    out = tmp_path / "xref_stream.pdf"
    with (
        out.open("wb") as fh,
        COSWriter(fh, xref_stream=True) as writer,  # type: ignore[arg-type]
    ):
        writer.write(doc)
    return out


def _build_object_streams_disabled(tmp_path: Path) -> Path:
    from pypdfbox import PDDocument
    from pypdfbox.pdfwriter import COSWriter

    doc = PDDocument()
    _add_text_page(doc, "no object streams")
    out = tmp_path / "no_object_streams.pdf"
    with (
        out.open("wb") as fh,
        COSWriter(fh, object_stream=False) as writer,  # type: ignore[arg-type]
    ):
        writer.write(doc)
    return out


FLOWS: dict[str, FlowBuilder] = {
    "basic_save": _build_basic_save,
    "with_text": _build_with_text,
    "multi_page": _build_multi_page,
    "incremental_save": _build_incremental_save,
    "merge": _build_merge,
    "split": _build_split,
    "xref_stream": _build_xref_stream,
    "object_streams_disabled": _build_object_streams_disabled,
}


# ---------------------------------------------------------------- tests


@pytest.mark.parametrize("flow_name", sorted(FLOWS))
def test_qpdf_accepts_pypdfbox_output(flow_name: str, tmp_path: Path) -> None:
    """Each save flow must pass ``qpdf --check`` and ``qpdf --qdf``."""
    builder = FLOWS[flow_name]
    pdf_path = builder(tmp_path)
    assert pdf_path.exists() and pdf_path.stat().st_size > 0, (
        f"flow {flow_name} produced empty output at {pdf_path}"
    )
    _assert_qpdf_ok(pdf_path)
