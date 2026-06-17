"""Live PDFBox differential parity for ``Overlay`` stamp overlaying
(``pypdfbox.multipdf.overlay``).

Drives Apache PDFBox's ``org.apache.pdfbox.multipdf.Overlay.overlay(Map)`` with
a *default overlay* — a single-page stamp PDF laid onto every page of a base
PDF — saves, reloads, and fingerprints the overlaid structure. pypdfbox runs the
identical overlay through ``Overlay.overlay({})`` and the recoverable facts must
agree:

* **total page count** — overlaying must not add or drop pages.
* **per-page extracted text, in order** — the text extractor sees *both* layers,
  so both the base marker and the stamp marker appear on every page. A drop of
  either layer (overlay not applied, or original content clobbered) shows up
  immediately.
* **per-page /XObject count + the "OL"-prefixed overlay-form key** — Overlay
  registers the overlay form XObject under an ``OL`` prefix
  (``resources.add(overlayFormXObject, "OL")`` upstream); both sides must expose
  exactly one such key per page.
* both outputs pass ``qpdf --check`` (structurally valid).

Inputs are built through pypdfbox so they are byte-identical on both sides of the
comparison. Object count / xref style are deliberately NOT compared — that is a
documented writer-strategy difference (see the pdfwriter oracle module).

The lower-left-corner centering (PDFBOX-6048) is exercised indirectly: a stamp
smaller than the base page is centred, and the round-trip text extraction
confirms the overlaid form's content is present and reachable on the page.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# ----------------------------------------------------------------- builders


def _text_page(
    doc: PDDocument,
    message: str,
    media_box: PDRectangle,
    x: float = 72.0,
    y: float = 700.0,
) -> PDPage:
    """Append a page of ``media_box`` size to ``doc`` showing ``message``."""
    page = PDPage(media_box)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 12)
    cs.new_line_at_offset(x, y)
    cs.show_text(message)
    cs.end_text()
    cs.close()
    return page


def _build_base(path: Path, markers: list[str]) -> None:
    """Build a multi-page Letter base PDF, one marker per page."""
    doc = PDDocument()
    for marker in markers:
        _text_page(doc, marker, PDRectangle.LETTER)
    doc.save(str(path))
    doc.close()


def _build_stamp(path: Path, marker: str) -> None:
    """Build a single-page stamp PDF (smaller than Letter so it is centred)."""
    doc = PDDocument()
    _text_page(doc, marker, PDRectangle.from_width_height(200.0, 200.0), x=20.0, y=100.0)
    doc.save(str(path))
    doc.close()


# ------------------------------------------------------------- fact readers


def _qpdf_check(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class _OverlayFacts:
    """The recoverable overlaid facts compared across the Java/pypdfbox boundary."""

    __slots__ = ("ol_keys", "page_text", "pages", "xobject_counts")

    def __init__(
        self,
        pages: int,
        page_text: list[str],
        xobject_counts: list[int],
        ol_keys: list[bool],
    ) -> None:
        self.pages = pages
        self.page_text = page_text
        self.xobject_counts = xobject_counts
        self.ol_keys = ol_keys

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _OverlayFacts):
            return NotImplemented
        return (
            self.pages == other.pages
            and self.page_text == other.page_text
            and self.xobject_counts == other.xobject_counts
            and self.ol_keys == other.ol_keys
        )

    def __repr__(self) -> str:  # pragma: no cover - only on assert failure
        return (
            f"_OverlayFacts(pages={self.pages}, page_text={self.page_text}, "
            f"xobject_counts={self.xobject_counts}, ol_keys={self.ol_keys})"
        )


def _unescape(s: str) -> str:
    return (
        s.replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def _parse_probe(text: str) -> _OverlayFacts:
    pages = 0
    page_text_map: dict[int, str] = {}
    xobject_map: dict[int, int] = {}
    ol_map: dict[int, bool] = {}
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "pages":
            pages = int(rest)
        elif head == "page":
            idx, _, body = rest.partition(" ")
            page_text_map[int(idx)] = _unescape(body)
        elif head == "xobject":
            idx, _, count = rest.partition(" ")
            xobject_map[int(idx)] = int(count)
        elif head == "olkey":
            idx, _, val = rest.partition(" ")
            ol_map[int(idx)] = val == "true"
    page_text = [page_text_map.get(i, "") for i in range(pages)]
    xobject_counts = [xobject_map.get(i, 0) for i in range(pages)]
    ol_keys = [ol_map.get(i, False) for i in range(pages)]
    return _OverlayFacts(pages, page_text, xobject_counts, ol_keys)


def _overlay_py(base: Path, stamp: Path, out: Path, position: Position) -> None:
    with (
        PDDocument.load(str(base)) as base_doc,
        PDDocument.load(str(stamp)) as stamp_doc,
        Overlay() as overlay,
    ):
        overlay.set_input_pdf(base_doc)
        overlay.set_default_overlay_pdf(stamp_doc)
        overlay.set_overlay_position(position)
        result = overlay.overlay({})
        result.save(str(out))


def _read_py_facts(path: Path) -> _OverlayFacts:
    doc = PDDocument.load(path)
    try:
        n = doc.get_number_of_pages()
        stripper = PDFTextStripper()
        page_text: list[str] = []
        for i in range(n):
            stripper.set_start_page(i + 1)
            stripper.set_end_page(i + 1)
            page_text.append(stripper.get_text(doc).strip())

        xobject_counts: list[int] = []
        ol_keys: list[bool] = []
        for i in range(n):
            res = doc.get_page(i).get_resources()
            count = 0
            has_ol = False
            if res is not None:
                for name in res.get_xobject_names():
                    count += 1
                    if name.get_name().startswith("OL"):
                        has_ol = True
            xobject_counts.append(count)
            ol_keys.append(has_ol)

        return _OverlayFacts(n, page_text, xobject_counts, ol_keys)
    finally:
        doc.close()


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("position", [Position.BACKGROUND, Position.FOREGROUND])
def test_overlay_default_stamp_matches_pdfbox(
    tmp_path: Path, position: Position
) -> None:
    """Overlay a single-page stamp onto every page of a 3-page base through
    Java PDFBox and through pypdfbox; every recoverable overlaid fact must
    agree and both outputs must be qpdf-valid.

    High-value invariants:
      * page count unchanged (3 in, 3 out),
      * both the base marker and the stamp marker extractable on every page
        (overlay content present, original content preserved),
      * exactly one "OL"-prefixed overlay-form XObject per page.
    """
    markers = ["BASE-ALPHA", "BASE-BRAVO", "BASE-CHARLIE"]
    base = tmp_path / "base.pdf"
    stamp = tmp_path / "stamp.pdf"
    _build_base(base, markers)
    _build_stamp(stamp, "STAMP-MARK")

    java_out = tmp_path / "java_overlaid.pdf"
    java_text = run_probe_text(
        "OverlayProbe", str(java_out), str(base), str(stamp), position.value
    )
    java_facts = _parse_probe(java_text)

    py_out = tmp_path / "py_overlaid.pdf"
    _overlay_py(base, stamp, py_out, position)
    py_facts = _read_py_facts(py_out)

    java_rc, java_log = _qpdf_check(java_out)
    py_rc, py_log = _qpdf_check(py_out)
    assert java_rc <= 3, f"Java overlay failed qpdf --check (rc={java_rc}):\n{java_log}"
    assert py_rc <= 3, f"pypdfbox overlay failed qpdf --check (rc={py_rc}):\n{py_log}"

    assert py_facts.pages == java_facts.pages == 3, (
        f"overlaid page count: pypdfbox {py_facts.pages} vs PDFBox {java_facts.pages}"
    )

    # Both layers reachable on every page.
    for i, marker in enumerate(markers):
        assert marker in py_facts.page_text[i], (
            f"pypdfbox page {i} missing base marker {marker!r}: {py_facts.page_text[i]!r}"
        )
        assert "STAMP-MARK" in py_facts.page_text[i], (
            f"pypdfbox page {i} missing stamp marker: {py_facts.page_text[i]!r}"
        )

    assert py_facts.page_text == java_facts.page_text, (
        f"per-page two-layer text divergence:\n"
        f"  pypdfbox: {py_facts.page_text}\n  PDFBox:   {java_facts.page_text}"
    )

    # Overlay-form XObject registered under the OL prefix on every page.
    assert py_facts.ol_keys == java_facts.ol_keys == [True, True, True], (
        f"OL-prefixed overlay-form key divergence:\n"
        f"  pypdfbox: {py_facts.ol_keys}\n  PDFBox:   {java_facts.ol_keys}"
    )
    assert py_facts.xobject_counts == java_facts.xobject_counts, (
        f"/XObject count divergence:\n"
        f"  pypdfbox: {py_facts.xobject_counts}\n  PDFBox:   {java_facts.xobject_counts}"
    )

    assert py_facts == java_facts
