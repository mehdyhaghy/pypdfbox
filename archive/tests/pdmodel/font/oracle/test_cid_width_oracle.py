"""Live PDFBox differential parity for descendant-CIDFont per-CID widths.

Pins the ``/W`` width-array + ``/DW`` default-width surface (PDF 32000-1
§9.7.4.3) at the :class:`PDCIDFont` level: the two ``/W`` array forms —
``c [w1 w2 ...]`` (consecutive CIDs starting at ``c``) and ``c_first c_last w``
(one width for the whole inclusive range) — parsed into the per-CID width map,
with the ``/DW`` (default 1000) fallback for CIDs absent from ``/W``.

This is a different surface from the two adjacent oracle tests:

* ``test_font_metrics_oracle`` drives ``PDType0Font.getWidth(code)`` — the
  *composite-font* string-advance pipeline.
* ``test_cid_gid_oracle`` drives ``code -> CID -> GID`` glyph indexing.

Here we drive the *descendant* ``PDCIDFont.getWidth(int)`` directly, which
upstream computes as ``getWidthForCID(codeToCID(code))`` =
``widths.get(cid) ?? getDefaultWidth()`` (verified against the 3.0.7 bytecode),
plus ``hasExplicitWidth(int)`` (``/W`` carries the CID specifically) and the
``/DW`` default-width value. Under Identity-H — the encoding every project
Type0 fixture uses — the input code equals the CID, so the ``/W`` CIDs are
exactly the addressable codes.

The oracle output is produced by ``oracle/probes/CidWidthProbe.java``; the
Python side reconstructs the identical line format so a divergence shows up as
a single differing line. Widths are integer-keyed table lookups (no
platform-dependent floating point), so no divergence is tolerated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSName, COSNumber
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Every fixture carrying at least one Type0 / CIDFontType2 font. All use
# Identity-H; "unencrypted.pdf" is the one that exercises BOTH /W forms
# (consecutive-list and c_first c_last range) — see the form audit in the
# wave-1458 report.
_FIXTURES_REL = [
    "text/input/eu-001.pdf",
    "multipdf/PDFBOX-4417-001031.pdf",
    "multipdf/PDFBOX-4417-054080.pdf",
    "multipdf/PDFBOX-5809-509329.pdf",
    "pdfwriter/attachment.pdf",
    "pdfwriter/unencrypted.pdf",  # both /W forms + dense /W
]

# Synthetic codes beyond any fixture's /W coverage — force the /DW default
# fallback in getWidthForCID. Kept in lockstep with CidWidthProbe.DW_FALLBACK.
_DW_FALLBACK = (50000, 60000, 65535)


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _probed_codes(descendant: object) -> list[int]:
    """Mirror ``CidWidthProbe.probedCodes`` exactly.

    CID 0 + every CID covered by /W (both forms, range form capped + both
    ends sampled) + the synthetic /DW-fallback codes, ascending de-duplicated.
    """
    out: set[int] = {0}
    out.update(_DW_FALLBACK)
    w = descendant._dict.get_dictionary_object(COSName.get_pdf_name("W"))
    if isinstance(w, COSArray):
        i = 0
        n = w.size()
        while i < n:
            first = w.get_object(i)
            if not isinstance(first, COSNumber):
                break
            c_first = first.int_value()
            if i + 1 >= n:
                break
            nxt = w.get_object(i + 1)
            if isinstance(nxt, COSArray):
                for k in range(nxt.size()):
                    out.add(c_first + k)
                i += 2
            elif isinstance(nxt, COSNumber):
                if i + 2 >= n:
                    break
                c_last = nxt.int_value()
                upper = min(c_last, c_first + 1024)
                for c in range(c_first, upper + 1):
                    out.add(c)
                out.add(c_last)
                i += 3
            else:
                break
    return sorted(out)


def _py_default_width(descendant: object) -> float:
    """Mirror ``CidWidthProbe.readDefaultWidth``: /DW COSNumber else 1000.0."""
    dw = descendant._dict.get_dictionary_object(COSName.get_pdf_name("DW"))
    if isinstance(dw, COSNumber):
        return dw.float_value()
    return 1000.0


def _py_cid_widths(pdf_path: Path) -> str:
    """Reconstruct the CidWidthProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:
                    continue
                if not isinstance(font, PDType0Font):
                    continue
                descendant = font.get_descendant_font()
                if descendant is None:
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{type(descendant).__name__}\t"
                    f"{_fmt(_py_default_width(descendant))}"
                )
                for code in _probed_codes(descendant):
                    try:
                        width = _fmt(descendant.get_width(code))
                    except Exception:
                        width = "WIDTH_ERR"
                    try:
                        explicit = (
                            "true" if descendant.has_explicit_width(code) else "false"
                        )
                    except Exception:
                        explicit = "EXPLICIT_ERR"
                    lines.append(
                        f"WIDTH\t{page_index}\t{key}\t{code}\t{width}\t{explicit}"
                    )
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_cid_widths_match_pdfbox(fixture_rel: str) -> None:
    """Every descendant-CIDFont per-CID width + explicit flag + /DW default
    must match Apache PDFBox exactly.

    Pins both ``/W`` forms and the ``/DW`` fallback: a divergence in the
    width-array parser (range vs list form), the default-width resolution, or
    the explicit-width predicate surfaces as a single differing line.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("CidWidthProbe", str(pdf_path)).splitlines()
    py = _py_cid_widths(pdf_path).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch for {fixture_rel}: java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"/W + /DW width parity broken for {fixture_rel}:\n" + "\n".join(diffs[:40])
    )


@requires_oracle
def test_at_least_one_fixture_exercises_a_cidfont() -> None:
    """Guard against the parametrised suite silently covering zero CIDFonts.

    If a fixture re-sync drops every Type0 font, the per-fixture tests would
    all pass with empty output. This asserts the corpus still carries the
    surface under test.
    """
    total = 0
    for rel in _FIXTURES_REL:
        out = run_probe_text("CidWidthProbe", str(_FIXTURES / rel))
        total += sum(1 for ln in out.splitlines() if ln.startswith("FONT\t"))
    assert total > 0


@requires_oracle
def test_both_w_forms_are_exercised() -> None:
    """Guard that the corpus still hits BOTH ``/W`` array forms.

    ``unencrypted.pdf`` is the fixture that carries a ``c_first c_last w``
    range entry alongside the ``c [w1 w2 ...]`` list form. If a re-sync drops
    it, the range-form half of this surface would go untested silently.
    """
    pdf_path = _FIXTURES / "pdfwriter/unencrypted.pdf"
    doc = PDDocument.load(pdf_path)
    try:
        saw_list = False
        saw_range = False
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if not isinstance(font, PDType0Font):
                    continue
                descendant = font.get_descendant_font()
                if descendant is None:
                    continue
                w = descendant.get_w()
                if w is None:
                    continue
                i = 0
                n = w.size()
                while i < n:
                    first = w.get_object(i)
                    if not isinstance(first, COSNumber) or i + 1 >= n:
                        break
                    nxt = w.get_object(i + 1)
                    if isinstance(nxt, COSArray):
                        saw_list = True
                        i += 2
                    elif isinstance(nxt, COSNumber):
                        saw_range = True
                        i += 3
                    else:
                        break
        assert saw_list, "no c [w1 w2 ...] list-form /W entry found"
        assert saw_range, "no c_first c_last w range-form /W entry found"
    finally:
        doc.close()


def test_dw_fallback_and_w_forms_synthetic() -> None:
    """Regression pin for the /W parser + /DW fallback (no oracle needed).

    Builds a synthetic descendant CIDFont dictionary exercising both /W forms
    and a non-default /DW, then asserts get_width / has_explicit_width /
    get_default_width match upstream PDCIDFont semantics:

        getWidth(code)          = widths.get(cid) ?? getDefaultWidth()
        getDefaultWidth()       = /DW COSNumber else 1000.0
        hasExplicitWidth(code)  = widths.containsKey(codeToCID(code))
    """
    from pypdfbox.cos import COSDictionary, COSInteger
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    cid = COSDictionary()
    cid.set_name(COSName.get_pdf_name("Type"), "Font")
    cid.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    cid.set_name(COSName.get_pdf_name("BaseFont"), "Test")
    cid.set_int(COSName.get_pdf_name("DW"), 222)

    # /W: list form for CIDs 10,11,12 then range form 20..22 = 500.
    w = COSArray()
    w.add(COSInteger.get(10))
    inner = COSArray()
    inner.add(COSInteger.get(100))
    inner.add(COSInteger.get(200))
    inner.add(COSInteger.get(300))
    w.add(inner)
    w.add(COSInteger.get(20))
    w.add(COSInteger.get(22))
    w.add(COSInteger.get(500))
    cid.set_item(COSName.get_pdf_name("W"), w)

    font = PDCIDFontType2(cid)

    # codeToCID is identity for a bare CIDFontType2 (no encoding wired), so the
    # code IS the CID here — matching the Identity-H fixtures.
    assert font.get_default_width() == 222.0
    # list form
    assert font.get_width(10) == 100.0
    assert font.get_width(11) == 200.0
    assert font.get_width(12) == 300.0
    # range form
    assert font.get_width(20) == 500.0
    assert font.get_width(21) == 500.0
    assert font.get_width(22) == 500.0
    # /DW fallback for absent CIDs
    assert font.get_width(0) == 222.0
    assert font.get_width(13) == 222.0
    assert font.get_width(19) == 222.0
    assert font.get_width(23) == 222.0
    assert font.get_width(65535) == 222.0
    # explicit-width predicate
    for c in (10, 11, 12, 20, 21, 22):
        assert font.has_explicit_width(c), c
    for c in (0, 13, 19, 23, 65535):
        assert not font.has_explicit_width(c), c
