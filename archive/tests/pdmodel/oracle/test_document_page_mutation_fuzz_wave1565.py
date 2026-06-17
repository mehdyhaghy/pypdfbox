"""Live PDFBox differential parity for PDDocument-level page-tree MUTATION.

``test_page_tree_mutate_oracle`` pins the internal ``/Kids`` *tree shape* after
a single structural mutation on a hand-rolled unbalanced tree. This module goes
the other way: it fuzzes the high-level ``PDDocument`` mutation API on a FLAT,
freshly created document over ~16 operation sequences and pins, after every op,
the observable mutation semantics — ``get_number_of_pages()``, the live
document-order page widths (each page tagged with a unique integer
``/MediaBox`` width), the root ``/Pages /Count`` field, and any exception
raised — against the live Apache PDFBox 3.0.7 oracle
(``DocumentPageMutationFuzzProbe.java``).

Surface covered: ``add_page`` (to an empty doc and N times), ``remove_page``
by index (first / middle / last / single-page / drain-to-empty) and by
reference (incl. removing an already-removed page), ``import_page`` (deep clone
from a second document — the imported page object is independent and survives a
mutation of the source page), ``add_page`` of a page owned by another document
(re-parenting), ``get_page`` out of range / negative / after removal, and a
remove-then-re-add round trip.

The probe is self-contained (no fixture, no save/reload) so the comparison pins
the in-memory mutation semantics, not the serialized bytes. Expected values are
also hard-pinned (PDFBox-3.0.7-derived) so the suite stays green when the live
oracle jar is absent.

ONE honest divergence is pinned both-sides: ``get_page(-1)``. Upstream's
``getPage(int)`` rejects a negative index with ``IndexOutOfBoundsException``;
pypdfbox's ``PDPageTree.__getitem__`` deliberately supports Python list-style
negative indexing (a documented, separately tested extension — see
``tests/pdmodel/test_pd_page_tree.py::test_negative_index``), so
``get_page(-1)`` returns the last page. We assert pypdfbox's extension value and
note the oracle's exception inline rather than masking the extension.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import oracle_available, run_probe_text

_PARENT = COSName.get_pdf_name("Parent")
_COUNT = COSName.get_pdf_name("Count")


def _page(width: int) -> PDPage:
    # Java's ``new PDRectangle(w, h)`` is lower-left (0,0); pypdfbox's 4-arg
    # ctor takes explicit corners. Marker is baked into the width.
    return PDPage(PDRectangle(0, 0, width, 200))


def _flat(*widths: int) -> PDDocument:
    doc = PDDocument()
    for w in widths:
        doc.add_page(_page(w))
    return doc


class _Projector:
    """Mirror of the probe's per-step ``project`` line formatter."""

    def __init__(self) -> None:
        self.step = 0
        self.lines: list[str] = []

    def project(self, label: str, doc: PDDocument, err: str = "NONE") -> None:
        n = doc.get_number_of_pages()
        order = ",".join(
            str(int(doc.get_page(i).get_media_box().get_width()))
            for i in range(n)
        )
        count_field = doc.get_pages().get_root().get_int(_COUNT, -999)
        self.lines.append(
            f"step{self.step} {label}: count={n} "
            f"count_field={count_field} order=[{order}] err=NONE"
            if err == "NONE"
            else f"step{self.step} {label}: count={n} "
            f"count_field={count_field} order=[{order}] err={err}"
        )
        self.step += 1

    def raw(self, text: str) -> None:
        self.lines.append(f"step{self.step} {text}")
        self.step += 1

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def _exc(e: Exception) -> str:
    # Project all index errors under the upstream Java class name so the
    # error-token comparison is apples-to-apples; pypdfbox raises IndexError /
    # ValueError where upstream raises IndexOutOfBoundsException.
    if isinstance(e, (IndexError, ValueError)):
        return "IndexOutOfBoundsException"
    return type(e).__name__


# ---------------------------------------------------------------------------
# Python re-implementations of each probe scenario. Each returns the projected
# transcript text (matching DocumentPageMutationFuzzProbe's stdout format).
# ---------------------------------------------------------------------------


def _py_add_to_empty() -> str:
    p = _Projector()
    doc = PDDocument()
    try:
        p.project("empty", doc)
        doc.add_page(_page(10))
        p.project("add10", doc)
        doc.add_page(_page(20))
        p.project("add20", doc)
    finally:
        doc.close()
    return p.text()


def _py_add_n_then_count() -> str:
    p = _Projector()
    doc = PDDocument()
    try:
        for i in range(7):
            doc.add_page(_page(100 + i))
        p.project("after_add7", doc)
    finally:
        doc.close()
    return p.text()


def _py_remove_at(idx: int, label: str) -> str:
    p = _Projector()
    doc = _flat(10, 20, 30, 40, 50)
    try:
        p.project("init", doc)
        doc.remove_page(idx)
        p.project(label, doc)
    finally:
        doc.close()
    return p.text()


def _py_remove_last() -> str:
    p = _Projector()
    doc = _flat(10, 20, 30, 40, 50)
    try:
        p.project("init", doc)
        doc.remove_page(doc.get_number_of_pages() - 1)
        p.project("removePage(last)", doc)
    finally:
        doc.close()
    return p.text()


def _py_remove_by_ref() -> str:
    p = _Projector()
    doc = _flat(10, 20, 30, 40, 50)
    try:
        p.project("init", doc)
        mid = doc.get_page(2)
        doc.remove_page(mid)
        p.project("removePage(page@30)", doc)
        err = "NONE"
        try:
            doc.remove_page(mid)
        except Exception as e:  # noqa: BLE001
            err = _exc(e)
        p.project("removePage(page@30)_again", doc, err)
    finally:
        doc.close()
    return p.text()


def _py_remove_single_page_doc() -> str:
    p = _Projector()
    doc = _flat(77)
    try:
        p.project("init", doc)
        doc.remove_page(0)
        p.project("removePage(0)", doc)
        err = "NONE"
        try:
            doc.remove_page(0)
        except Exception as e:  # noqa: BLE001
            err = _exc(e)
        p.project("removePage(0)_on_empty", doc, err)
    finally:
        doc.close()
    return p.text()


def _py_remove_all_sequential() -> str:
    p = _Projector()
    doc = _flat(10, 20, 30)
    try:
        p.project("init", doc)
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
            p.project("removePage(0)", doc)
    finally:
        doc.close()
    return p.text()


def _py_getpage_out_of_range() -> str:
    p = _Projector()
    doc = _flat(10, 20, 30)
    try:
        for idx in (3, 99):
            err = "NONE"
            try:
                doc.get_page(idx)
            except Exception as e:  # noqa: BLE001
                err = _exc(e)
            p.project(f"getPage({idx})", doc, err)
    finally:
        doc.close()
    return p.text()


def _py_getpage_after_removal() -> str:
    p = _Projector()
    doc = _flat(10, 20, 30)
    try:
        p.project("init", doc)
        doc.remove_page(2)
        p.project("removePage(2)", doc)
        err = "NONE"
        try:
            doc.get_page(2)
        except Exception as e:  # noqa: BLE001
            err = _exc(e)
        p.project("getPage(2)_after_removal", doc, err)
    finally:
        doc.close()
    return p.text()


def _py_import_page() -> str:
    p = _Projector()
    dst = _flat(10, 20)
    src = _flat(900)
    try:
        p.project("dst_init", dst)
        src_page = src.get_page(0)
        imported = dst.import_page(src_page)
        p.project("after_import", dst)
        independent = imported.get_cos_object() is not src_page.get_cos_object()
        p.raw(f"imported_independent: {'true' if independent else 'false'}")
        p.project("src_after_import", src)
    finally:
        dst.close()
        src.close()
    return p.text()


def _py_import_then_mutate_source() -> str:
    p = _Projector()
    dst = _flat(10)
    src = _flat(900)
    try:
        imported = dst.import_page(src.get_page(0))
        src.get_page(0).set_media_box(PDRectangle(0, 0, 111, 200))
        imported_width = int(imported.get_media_box().get_width())
        p.raw(f"imported_width_after_src_mutate: {imported_width}")
        p.project("dst", dst)
    finally:
        dst.close()
        src.close()
    return p.text()


def _py_add_page_owned_by_other() -> str:
    p = _Projector()
    dst = _flat(10, 20)
    src = _flat(900)
    try:
        src_page = src.get_page(0)
        p.project("dst_init", dst)
        dst.add_page(src_page)
        p.project("dst_after_add_foreign", dst)
        reparented = (
            src_page.get_cos_object().get_dictionary_object(_PARENT)
            is dst.get_pages().get_root()
        )
        p.raw(f"foreign_reparented_to_dst: {'true' if reparented else 'false'}")
        p.project("src_after_add_foreign", src)
    finally:
        dst.close()
        src.close()
    return p.text()


def _py_remove_then_readd() -> str:
    p = _Projector()
    doc = _flat(10, 20, 30)
    try:
        p.project("init", doc)
        page = doc.get_page(1)
        doc.remove_page(page)
        p.project("removePage(page@20)", doc)
        doc.add_page(page)
        p.project("addPage(page@20)_back", doc)
    finally:
        doc.close()
    return p.text()


def _py_interleaved() -> str:
    p = _Projector()
    doc = PDDocument()
    try:
        p.project("empty", doc)
        doc.add_page(_page(1))
        doc.add_page(_page(2))
        doc.add_page(_page(3))
        p.project("add_1_2_3", doc)
        doc.remove_page(1)
        p.project("removePage(1)", doc)
        doc.add_page(_page(4))
        p.project("addPage(4)", doc)
        doc.remove_page(0)
        p.project("removePage(0)", doc)
        doc.remove_page(doc.get_number_of_pages() - 1)
        p.project("removePage(last)", doc)
    finally:
        doc.close()
    return p.text()


# (scenario-arg, python-callable, expected-transcript) — expected text is the
# PDFBox-3.0.7 oracle output captured from DocumentPageMutationFuzzProbe.
_SCENARIOS: list[tuple[str, object, str]] = [
    (
        "add_to_empty",
        _py_add_to_empty,
        "step0 empty: count=0 count_field=0 order=[] err=NONE\n"
        "step1 add10: count=1 count_field=1 order=[10] err=NONE\n"
        "step2 add20: count=2 count_field=2 order=[10,20] err=NONE\n",
    ),
    (
        "add_n_then_count",
        _py_add_n_then_count,
        "step0 after_add7: count=7 count_field=7 "
        "order=[100,101,102,103,104,105,106] err=NONE\n",
    ),
    (
        "remove_first",
        lambda: _py_remove_at(0, "removePage(0)"),
        "step0 init: count=5 count_field=5 order=[10,20,30,40,50] err=NONE\n"
        "step1 removePage(0): count=4 count_field=4 order=[20,30,40,50] err=NONE\n",
    ),
    (
        "remove_last",
        _py_remove_last,
        "step0 init: count=5 count_field=5 order=[10,20,30,40,50] err=NONE\n"
        "step1 removePage(last): count=4 count_field=4 order=[10,20,30,40] err=NONE\n",
    ),
    (
        "remove_middle",
        lambda: _py_remove_at(2, "removePage(2)"),
        "step0 init: count=5 count_field=5 order=[10,20,30,40,50] err=NONE\n"
        "step1 removePage(2): count=4 count_field=4 order=[10,20,40,50] err=NONE\n",
    ),
    (
        "remove_by_ref",
        _py_remove_by_ref,
        "step0 init: count=5 count_field=5 order=[10,20,30,40,50] err=NONE\n"
        "step1 removePage(page@30): count=4 count_field=4 order=[10,20,40,50] err=NONE\n"
        "step2 removePage(page@30)_again: count=4 count_field=4 "
        "order=[10,20,40,50] err=NONE\n",
    ),
    (
        "remove_single_page_doc",
        _py_remove_single_page_doc,
        "step0 init: count=1 count_field=1 order=[77] err=NONE\n"
        "step1 removePage(0): count=0 count_field=0 order=[] err=NONE\n"
        "step2 removePage(0)_on_empty: count=0 count_field=0 order=[] "
        "err=IndexOutOfBoundsException\n",
    ),
    (
        "remove_all_sequential",
        _py_remove_all_sequential,
        "step0 init: count=3 count_field=3 order=[10,20,30] err=NONE\n"
        "step1 removePage(0): count=2 count_field=2 order=[20,30] err=NONE\n"
        "step2 removePage(0): count=1 count_field=1 order=[30] err=NONE\n"
        "step3 removePage(0): count=0 count_field=0 order=[] err=NONE\n",
    ),
    (
        "getpage_out_of_range",
        _py_getpage_out_of_range,
        "step0 getPage(3): count=3 count_field=3 order=[10,20,30] "
        "err=IndexOutOfBoundsException\n"
        "step1 getPage(99): count=3 count_field=3 order=[10,20,30] "
        "err=IndexOutOfBoundsException\n",
    ),
    (
        "getpage_after_removal",
        _py_getpage_after_removal,
        "step0 init: count=3 count_field=3 order=[10,20,30] err=NONE\n"
        "step1 removePage(2): count=2 count_field=2 order=[10,20] err=NONE\n"
        "step2 getPage(2)_after_removal: count=2 count_field=2 order=[10,20] "
        "err=IndexOutOfBoundsException\n",
    ),
    (
        "import_page",
        _py_import_page,
        "step0 dst_init: count=2 count_field=2 order=[10,20] err=NONE\n"
        "step1 after_import: count=3 count_field=3 order=[10,20,900] err=NONE\n"
        "step2 imported_independent: true\n"
        "step3 src_after_import: count=1 count_field=1 order=[900] err=NONE\n",
    ),
    (
        "import_then_mutate_source",
        _py_import_then_mutate_source,
        "step0 imported_width_after_src_mutate: 900\n"
        "step1 dst: count=2 count_field=2 order=[10,900] err=NONE\n",
    ),
    (
        "add_page_owned_by_other",
        _py_add_page_owned_by_other,
        "step0 dst_init: count=2 count_field=2 order=[10,20] err=NONE\n"
        "step1 dst_after_add_foreign: count=3 count_field=3 order=[10,20,900] err=NONE\n"
        "step2 foreign_reparented_to_dst: true\n"
        "step3 src_after_add_foreign: count=1 count_field=1 order=[900] err=NONE\n",
    ),
    (
        "remove_then_readd",
        _py_remove_then_readd,
        "step0 init: count=3 count_field=3 order=[10,20,30] err=NONE\n"
        "step1 removePage(page@20): count=2 count_field=2 order=[10,30] err=NONE\n"
        "step2 addPage(page@20)_back: count=3 count_field=3 order=[10,30,20] err=NONE\n",
    ),
    (
        "interleaved",
        _py_interleaved,
        "step0 empty: count=0 count_field=0 order=[] err=NONE\n"
        "step1 add_1_2_3: count=3 count_field=3 order=[1,2,3] err=NONE\n"
        "step2 removePage(1): count=2 count_field=2 order=[1,3] err=NONE\n"
        "step3 addPage(4): count=3 count_field=3 order=[1,3,4] err=NONE\n"
        "step4 removePage(0): count=2 count_field=2 order=[3,4] err=NONE\n"
        "step5 removePage(last): count=1 count_field=1 order=[3] err=NONE\n",
    ),
]


@pytest.mark.parametrize(
    ("scenario", "py_fn", "expected"),
    _SCENARIOS,
    ids=[s[0] for s in _SCENARIOS],
)
def test_document_page_mutation_matches_pdfbox(
    scenario: str, py_fn: object, expected: str
) -> None:
    """pypdfbox's PDDocument page-mutation transcript equals PDFBox 3.0.7's.

    Pinned against the hard-coded expected transcript always; additionally
    cross-checked against the LIVE oracle when the jar + JDK are present.
    """
    py = py_fn()  # type: ignore[operator]
    assert py == expected, (
        f"{scenario}: pypdfbox transcript diverges from pinned PDFBox 3.0.7.\n"
        f"--- pypdfbox ---\n{py}\n--- expected ---\n{expected}"
    )

    if oracle_available():
        java = run_probe_text("DocumentPageMutationFuzzProbe", scenario)
        assert py == java, (
            f"{scenario}: pypdfbox transcript diverges from live oracle.\n"
            f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
        )


def test_get_page_negative_index_is_pypdfbox_extension() -> None:
    """Honest both-sides divergence: ``get_page(-1)``.

    Upstream ``PDDocument.getPage(-1)`` rejects the negative index with
    ``IndexOutOfBoundsException`` (verified via DocumentPageMutationFuzzProbe
    ``getpage_negative``). pypdfbox's ``PDPageTree.__getitem__`` deliberately
    supports Python list-style negative indexing (documented extension, see
    ``tests/pdmodel/test_pd_page_tree.py::test_negative_index``), so
    ``get_page(-1)`` returns the LAST page. We pin pypdfbox's superset value.
    """
    doc = _flat(10, 20, 30)
    try:
        last = doc.get_page(-1)
        assert int(last.get_media_box().get_width()) == 30
    finally:
        doc.close()

    if oracle_available():
        java = run_probe_text(
            "DocumentPageMutationFuzzProbe", "getpage_negative"
        )
        # Upstream raises; pypdfbox returns the last page. Confirm the oracle
        # still records the exception so the divergence stays documented.
        assert "err=IndexOutOfBoundsException" in java
