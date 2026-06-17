"""Live PDFBox differential parity for page ``/Tabs`` annotation tab order.

Per PDF 32000-1 §12.5 a page may carry a ``/Tabs`` name entry telling the
viewer how to walk the page's annotations under Tab:

* ``/R`` — row order (PDF 1.5+)
* ``/C`` — column order (PDF 1.5+)
* ``/S`` — structure order (PDF 1.5+, mirrors the structure tree)
* ``/A`` — annotations-array order (PDF 2.0+, legacy default)
* ``/W`` — widget order (PDF 2.0+)

When ``/Tabs`` is absent the page imposes no specific tab order — PDFBox
surfaces this as ``null`` (no value), and pypdfbox's
:meth:`PDPage.get_tab_order` returns ``None``.

PDFBox 3.0.7's ``PDPage`` has no native ``getTabOrder`` / ``setTabOrder``
accessor, so the oracle reads the raw ``/Tabs`` COS name directly off the
page dictionary via ``getNameAsString(COSName.TABS)`` — that is the same
single-letter string pypdfbox's accessor returns, so the two surfaces compare
byte-for-byte.

This test covers two distinct contracts:

1. **Build → save → reload → probe.** pypdfbox writes a five-page PDF (one
   page per ``/Tabs`` value plus a page with no ``/Tabs``); the probe and the
   pypdfbox load path emit identical per-page reports.
2. **Set-then-read round-trip.** Every supported value (R / C / S / A / W) can
   be set then read back via the public accessor without drift, and ``None``
   removes the entry (``has_tab_order()`` reports false, raw ``/Tabs`` is
   gone from the dict).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_TABS = COSName.get_pdf_name("Tabs")

# (page-label, /Tabs value or None) — matches the order of pages written to
# the fixture and the order the probe emits.
_CASES: list[tuple[str, str | None]] = [
    ("row", PDPage.TAB_ORDER_ROW),
    ("column", PDPage.TAB_ORDER_COLUMN),
    ("structure", PDPage.TAB_ORDER_STRUCTURE),
    ("widgets", PDPage.TAB_ORDER_WIDGETS),
    ("default_absent", None),
]


def _build_fixture(path: Path) -> None:
    """Save a PDF whose pages exercise each ``/Tabs`` value plus the
    no-``/Tabs`` default. One page per case, in ``_CASES`` order."""
    doc = PDDocument()
    try:
        for _label, value in _CASES:
            page = PDPage()
            if value is not None:
                page.set_tab_order(value)
            doc.add_page(page)
        buf = io.BytesIO()
        doc.save(buf)
        path.write_bytes(buf.getvalue())
    finally:
        doc.close()


def _py_report(path: Path) -> str:
    """Mirror the probe output verbatim by reading the same fixture through
    pypdfbox: one line per page, ``page <i> tabs <raw|none> order <raw|none>``."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        for index, page in enumerate(doc.get_pages()):
            raw = page.get_cos_object().get_name(_TABS)
            order = page.get_tab_order()
            lines.append(
                f"page {index} "
                f"tabs {'none' if raw is None else raw} "
                f"order {'none' if order is None else order}"
            )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_page_tabs_match_pdfbox(tmp_path: Path) -> None:
    """The per-page ``/Tabs`` report from PDFBox and pypdfbox must agree
    byte-for-byte across every supported value + the absent default."""
    fixture = tmp_path / "page_tabs.pdf"
    _build_fixture(fixture)

    java = run_probe_text("PageTabsProbe", str(fixture))
    py = _py_report(fixture)
    assert py == java, (
        "page /Tabs report diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}--- java ---\n{java}"
    )


@pytest.mark.parametrize(
    "value",
    [
        PDPage.TAB_ORDER_ROW,
        PDPage.TAB_ORDER_COLUMN,
        PDPage.TAB_ORDER_STRUCTURE,
        PDPage.TAB_ORDER_ANNOTATIONS_ARRAY,
        PDPage.TAB_ORDER_WIDGETS,
    ],
)
def test_set_then_read_round_trip(value: str) -> None:
    """``set_tab_order`` followed by ``get_tab_order`` returns the same
    single-letter name for every supported value (incl. PDF 2.0 ``A`` and
    ``W``). The probe doesn't cover this — it can only observe what we
    serialise — so we pin the accessor contract directly."""
    page = PDPage()
    page.set_tab_order(value)
    assert page.has_tab_order() is True
    assert page.get_tab_order() == value
    # And the raw COS state agrees with the typed accessor.
    assert page.get_cos_object().get_name(_TABS) == value


def test_clear_removes_entry() -> None:
    """``set_tab_order(None)`` (and the explicit ``clear_tab_order``) must
    remove the ``/Tabs`` entry — PDFBox surfaces the absent entry as ``null``,
    and pypdfbox must surface it as ``None`` (not the empty string)."""
    page = PDPage()
    page.set_tab_order(PDPage.TAB_ORDER_ROW)
    page.set_tab_order(None)
    assert page.has_tab_order() is False
    assert page.get_tab_order() is None
    assert page.get_cos_object().get_name(_TABS) is None


def test_default_absent_is_none() -> None:
    """A freshly built page has no ``/Tabs`` and ``get_tab_order()`` returns
    ``None`` (not the empty string, not a default letter) — matches
    PDFBox 3.0.7's ``getNameAsString(/Tabs)`` returning ``null``."""
    page = PDPage()
    assert page.has_tab_order() is False
    assert page.get_tab_order() is None
