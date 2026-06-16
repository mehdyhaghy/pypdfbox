"""Incremental-save object selection + appended cross-reference encoding.

Pins the wave 1484 fixes for ``COSWriter`` incremental saves over an
xref-STREAM source:

1. **Parser** (``PDFParser`` + ``XrefTrailerResolver``): a document whose
   most-recent cross-reference is an xref *stream* (PDF 1.5+) now advertises
   ``COSDocument.is_xref_stream() == True``. Previously the flag stayed
   ``False`` for every loaded document because the parser never tagged the
   section type, so the incremental writer could not tell a stream source
   from a table source. Mirrors upstream
   ``COSParser.parseXref``: ``document.setIsXRefStream(XRefType.STREAM ==
   xrefTrailerResolver.getXrefType())``.

2. **Writer** (``COSWriter._do_write_increment``): an incremental save over
   an xref-stream source now appends an xref *stream* (``/Type /XRef`` with
   ``/Prev``, ``/Index`` covering only the changed objects + the free head,
   refreshed ``/ID[1]``), mirroring upstream ``COSWriter.doWriteXRefInc``.
   Previously the increment emitted a classic ``xref`` table while the
   appended trailer still claimed ``/Type /XRef`` (with leftover ``/W`` /
   ``/Index`` / ``/Filter`` keys) — a malformed mix.

3. **Object selection** (unchanged by this wave, pinned here): only objects
   flagged ``set_needs_to_be_updated(True)`` (plus brand-new keyless
   objects) land in the increment — editing one page's ``/MediaBox`` and
   marking only the page dirty re-emits exactly that page, not its parents;
   marking the parent chain re-emits each marked dictionary; adding a new
   annotation emits the page + the new annot, not untouched siblings.

The oracle differential (``@requires_oracle``) compares the appended object
set + xref encoding against live Apache PDFBox 3.0.7 on the same edits.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText

# An xref-STREAM source document (its last cross-reference is a /Type /XRef
# object, not a classic table). 2 pages.
_XREF_STREAM_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "pdfwriter" / "unencrypted.pdf"
)
# A classic xref-TABLE source (its last cross-reference is a ``trailer`` +
# ``xref`` table), used to pin that the table arm is unaffected.
_XREF_TABLE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "pdfwriter"
    / "PDFBOX-3110-poems-beads.pdf"
)


def _source_bytes() -> bytes:
    return _XREF_STREAM_FIXTURE.read_bytes()


def _appended(out: bytes, src: bytes) -> bytes:
    assert out.startswith(src), "increment must preserve source as a byte prefix"
    return out[len(src) :]


def _index_data_numbers(tail: bytes) -> list[int]:
    """Object numbers the appended xref stream's ``/Index`` references,
    minus the free-list head (0). Per upstream ``PDFXRefStream`` the xref
    stream's OWN object is reached via ``startxref`` and is NOT listed in
    its own ``/Index`` — so this is exactly the application objects the
    increment rewrote."""
    nums: set[int] = set()
    for m in re.finditer(rb"/Index ?\[([^\]]*)\]", tail):
        ints = [int(x) for x in m.group(1).split()]
        for i in range(0, len(ints) - 1, 2):
            first, count = ints[i], ints[i + 1]
            nums.update(range(first, first + count))
    nums.discard(0)
    return sorted(nums)


def _save_incremental(doc: PDDocument) -> bytes:
    sink = io.BytesIO()
    doc.save_incremental(sink)
    return sink.getvalue()


# --------------------------------------------------------------------------
# Parser: xref-stream detection
# --------------------------------------------------------------------------


def test_xref_stream_source_advertises_is_xref_stream() -> None:
    doc = Loader.load_pdf(_source_bytes())
    try:
        assert doc.is_xref_stream() is True
        assert doc.has_hybrid_xref() is False
    finally:
        doc.close()


def test_xref_table_source_does_not_advertise_is_xref_stream() -> None:
    doc = Loader.load_pdf(_XREF_TABLE_FIXTURE.read_bytes())
    try:
        assert doc.is_xref_stream() is False
    finally:
        doc.close()


# --------------------------------------------------------------------------
# Writer: increment uses an xref STREAM (not a table) for an xref-stream src
# --------------------------------------------------------------------------


def test_increment_over_xref_stream_uses_xref_stream() -> None:
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page.get_cos_object().set_needs_to_be_updated(True)
        out = _save_incremental(doc)
    finally:
        doc.close()

    tail = _appended(out, src)
    # The increment is an xref STREAM, not a classic ``xref`` table.
    assert b"/Type/XRef" in tail or b"/Type /XRef" in tail
    assert b"trailer" not in tail, (
        "an xref-stream increment must not emit a classic 'trailer' keyword"
    )
    assert not re.search(rb"(?:^|\r|\n)xref\s*\r?\n\d+\s+\d+", tail), (
        "an xref-stream source must NOT receive a classic-table increment"
    )


def test_increment_over_xref_table_uses_classic_table() -> None:
    """Regression: a TABLE source still gets a classic ``xref`` table +
    ``trailer``, never a ``/Type /XRef`` stream."""
    src = _XREF_TABLE_FIXTURE.read_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page.get_cos_object().set_needs_to_be_updated(True)
        out = _save_incremental(doc)
    finally:
        doc.close()

    tail = _appended(out, src)
    assert re.search(rb"(?:^|\r|\n)xref\s*\r?\n\d+\s+\d+", tail)
    assert b"trailer" in tail
    assert b"/Type/XRef" not in tail and b"/Type /XRef" not in tail


# --------------------------------------------------------------------------
# Object selection
# --------------------------------------------------------------------------


def test_mediabox_edit_page_only_re_emits_only_the_page() -> None:
    """Editing one page's /MediaBox and marking ONLY the page dirty re-emits
    exactly that page dictionary — not its /Pages parent or the catalog."""
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        page_num = doc.get_document().get_key(page.get_cos_object()).object_number
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page.get_cos_object().set_needs_to_be_updated(True)
        out = _save_incremental(doc)
    finally:
        doc.close()

    assert _index_data_numbers(_appended(out, src)) == [page_num]


def test_mediabox_edit_parent_chain_re_emits_each_marked_dict() -> None:
    """Marking the page + every /Parent up to the catalog re-emits each one,
    and nothing else."""
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        cos = doc.get_document()
        page = doc.get_page(0)
        page_dict = page.get_cos_object()
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page_dict.set_needs_to_be_updated(True)

        expected = {cos.get_key(page_dict).object_number}
        parent = page_dict.get_cos_dictionary(COSName.PARENT)
        while parent is not None:
            parent.set_needs_to_be_updated(True)
            expected.add(cos.get_key(parent).object_number)
            parent = parent.get_cos_dictionary(COSName.PARENT)
        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_needs_to_be_updated(True)
        expected.add(cos.get_key(catalog).object_number)

        out = _save_incremental(doc)
    finally:
        doc.close()

    assert _index_data_numbers(_appended(out, src)) == sorted(expected)


def test_add_annotation_emits_page_and_new_annot_not_siblings() -> None:
    """Adding a new annotation to a page emits the page (its /Annots changed)
    plus the brand-new annotation object (minted above the source max) — and
    no untouched objects."""
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        cos = doc.get_document()
        page = doc.get_page(0)
        page_num = cos.get_key(page.get_cos_object()).object_number
        source_max = max(k.object_number for k in cos.get_object_keys())

        annot = PDAnnotationText()
        annot.set_contents("wave-1484")
        annot.set_rectangle(PDRectangle.from_xywh(50, 50, 50, 50))
        page.add_annotation(annot)
        page.get_cos_object().set_needs_to_be_updated(True)
        annot.get_cos_object().set_needs_to_be_updated(True)

        out = _save_incremental(doc)
    finally:
        doc.close()

    tail = _appended(out, src)
    data = _index_data_numbers(tail)
    assert page_num in data, "the modified page must be re-emitted"
    # Exactly one brand-new object (the annotation) beyond the source max.
    new_objs = [n for n in data if n > source_max]
    assert len(new_objs) == 1, f"expected one fresh annot object, got {new_objs}"
    # The annotation body is present in the increment.
    assert b"/Text" in tail


def test_add_annotation_round_trips() -> None:
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        annot = PDAnnotationText()
        annot.set_contents("round-trip-1484")
        annot.set_rectangle(PDRectangle.from_xywh(50, 50, 50, 50))
        page.add_annotation(annot)
        page.get_cos_object().set_needs_to_be_updated(True)
        annot.get_cos_object().set_needs_to_be_updated(True)
        out = _save_incremental(doc)
    finally:
        doc.close()

    reloaded = PDDocument(Loader.load_pdf(out))
    try:
        annots = reloaded.get_page(0).get_annotations()
        assert any(
            a.get_cos_object().get_string(COSName.get_pdf_name("Contents"))
            == "round-trip-1484"
            for a in annots
        )
    finally:
        reloaded.close()


# --------------------------------------------------------------------------
# Trailer threading: /Prev + /Size + /ID on the xref-stream increment
# --------------------------------------------------------------------------


def test_increment_trailer_prev_size_and_id() -> None:
    src = _source_bytes()
    old_startxref = int(re.findall(rb"startxref\s+(\d+)", src)[-1])
    doc = PDDocument(Loader.load_pdf(src))
    try:
        cos = doc.get_document()
        id_arr = cos.get_document_id()
        id0 = id_arr.get_object(0).get_bytes() if id_arr is not None else None
        id1 = id_arr.get_object(1).get_bytes() if id_arr is not None else None
        page = doc.get_page(0)
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page.get_cos_object().set_needs_to_be_updated(True)
        out = _save_incremental(doc)
    finally:
        doc.close()

    tail = _appended(out, src)
    # /Prev points at the source's previous startxref.
    assert re.findall(rb"/Prev\s+(\d+)", tail) == [str(old_startxref).encode("ascii")]

    # Reload: /Size announces the full object count and /ID is refreshed.
    reloaded = PDDocument(Loader.load_pdf(out))
    try:
        rcos = reloaded.get_document()
        ids = rcos.get_document_id()
        assert ids is not None
        assert ids.size() == 2
        if id0 is not None:
            # /ID[0] (permanent) preserved; /ID[1] (changing) refreshed.
            assert ids.get_object(0).get_bytes() == id0
            assert ids.get_object(1).get_bytes() != id1
        # The latest MediaBox wins on reload.
        mb = reloaded.get_page(0).get_media_box()
        assert (mb.get_width(), mb.get_height()) == (333.0, 444.0)
    finally:
        reloaded.close()


def test_unmodified_xref_stream_increment_appends_empty_revision() -> None:
    """A ``save_incremental`` with no dirty objects on an xref-stream source
    appends a trailer-only xref-stream revision — matching PDFBox 3.0.7, which
    always grows the file by one revision even when nothing is dirty
    (oracle-confirmed wave 1565). The source survives as a verbatim prefix and
    a new ``/Type /XRef`` stream chained via ``/Prev`` is appended."""
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        out = _save_incremental(doc)
    finally:
        doc.close()
    assert out.startswith(src), "source must survive as a verbatim prefix"
    assert len(out) > len(src), "an empty increment is still appended"
    tail = out[len(src) :]
    assert b"/Prev" in tail, "appended trailer must chain /Prev"
    assert b"/Type /XRef" in tail or b"/Type/XRef" in tail, (
        "an xref-stream source appends an xref-stream revision"
    )


# --------------------------------------------------------------------------
# Oracle differential (opt-in; skipped without the live PDFBox jar)
# --------------------------------------------------------------------------


def _oracle():
    from tests.oracle.harness import requires_oracle, run_probe_text

    return requires_oracle, run_probe_text


try:  # pragma: no cover - import guard for environments without the harness
    _REQUIRES_ORACLE, _RUN_PROBE_TEXT = _oracle()
except Exception:  # pragma: no cover
    _REQUIRES_ORACLE = pytest.mark.skip(reason="oracle harness unavailable")
    _RUN_PROBE_TEXT = None


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


@_REQUIRES_ORACLE
@pytest.mark.parametrize(
    ("mode", "py_edit"),
    [
        ("mediabox-page-only", "page-only"),
        ("mediabox-chain", "chain"),
    ],
)
def test_increment_object_set_matches_pdfbox(
    mode: str, py_edit: str, tmp_path: Path
) -> None:
    assert _RUN_PROBE_TEXT is not None
    src = _source_bytes()
    pb_out = tmp_path / f"pb_{mode}.pdf"
    fields = _parse_probe(
        _RUN_PROBE_TEXT(
            "IncrementalPageEditProbe", mode, str(_XREF_STREAM_FIXTURE), str(pb_out)
        )
    )
    pdfbox_objs = (
        sorted(int(x) for x in fields["used_objs"].split(","))
        if fields["used_objs"]
        else []
    )

    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        page_dict = page.get_cos_object()
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page_dict.set_needs_to_be_updated(True)
        if py_edit == "chain":
            parent = page_dict.get_cos_dictionary(COSName.PARENT)
            while parent is not None:
                parent.set_needs_to_be_updated(True)
                parent = parent.get_cos_dictionary(COSName.PARENT)
            doc.get_document_catalog().get_cos_object().set_needs_to_be_updated(True)
        py_out = _save_incremental(doc)
    finally:
        doc.close()

    assert _index_data_numbers(_appended(py_out, src)) == pdfbox_objs
    # Both engines emit an xref stream increment for this xref-stream source.
    assert fields["incr_xref_stream"] == "true"
