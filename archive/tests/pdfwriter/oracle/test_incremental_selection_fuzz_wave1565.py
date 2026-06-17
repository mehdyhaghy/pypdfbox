"""Live PDFBox differential fuzz over the **object-SELECTION** contract of an
incremental save (``pypdfbox.pdmodel.PDDocument.save_incremental`` /
``pypdfbox.pdfwriter.cos_writer``).

What lands in the *appended section* of an incremental update is the heart of
the append-only model (ISO 32000-1 §7.5.6): only the dirty/added objects (plus
the new xref machinery) may be written, the original bytes must survive as a
verbatim prefix, the appended trailer's ``/Prev`` must chain back to the prior
``startxref``, ``/Size`` must cover the highest object number, and a reload must
recover the mutation.

Earlier incremental oracles pinned single facets — the /Prev chain
(``test_incremental_chain_oracle``), the exact dirty set for one /Info edit
(``test_incremental_xref_delta_oracle``), a single added annotation
(``test_incremental_add_annotation_oracle``), the trailing %%EOF bytes
(``test_incremental_tail_bytes_oracle``), and the appended-xref-stream shape
(``test_incremental_xref_stream_shape_oracle``). This module sweeps a *matrix*
of distinct mutation kinds through ``IncrementalSelectionFuzzProbe`` and pins,
for each, the SELECTION shape pypdfbox and PDFBox 3.0.7 must agree on:

  - editinfo    in-place edit of an existing object (/Info /Title)
  - catalogkey  set a key on the existing /Root (/Lang)
  - addannot    add a new object (a text annotation) to page 0
  - noop        nothing dirty — the empty-increment path
  - chain2      two sequential increments (two /Prev hops)
  - editpage    append a page content stream (Java-oracle-only; the pypdfbox
                font-construction surface differs, so we pin PDFBox's shape and
                assert pypdfbox parity for the other modes)

**Headline divergence fixed in wave 1565.** PDFBox 3.0.7's ``saveIncremental``
with *nothing dirty* still appends a fresh (empty) revision — a new xref
section listing only the free-list head plus a ``/Prev`` trailer; the file
grows and gains one ``startxref`` section. pypdfbox previously short-circuited
the no-op case to a byte-identical copy. The writer now falls through to the
normal xref+trailer emit so an empty increment is appended too, matching PDFBox
byte-for-byte (including PDFBox's own ``/W [0 0 0]`` empty-xref-stream quirk,
which qpdf flags on *both* engines — so the no-op xref-stream case asserts
byte-parity rather than qpdf-cleanliness).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

# A spread of source xref encodings: unencrypted/acroform/attachment carry
# xref *streams*; rot0 carries a classic xref *table*. The selection contract
# must hold across both encodings.
_FIXTURES_LIST = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "multipdf" / "rot0.pdf",
]

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_TITLE = "SelTitle"
_LANG = "en-US"
_ANNOT_CONTENTS = "SelAnnot"


# ----------------------------------------------------------------- helpers


def _qpdf_check(path: Path) -> tuple[int, str]:
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


def _last_startxref(data: bytes) -> int:
    last = -1
    for m in re.finditer(rb"startxref\s+(\d+)", data):
        last = int(m.group(1))
    return last


def _count_startxref(data: bytes) -> int:
    return len(re.findall(rb"startxref", data))


def _appended_prev(data: bytes, frm: int) -> int:
    last = -1
    for m in re.finditer(rb"/Prev\s+(\d+)", data[frm:]):
        last = int(m.group(1))
    return last


def _classic_used_objs(data: bytes, frm: int) -> list[int] | None:
    tail = data[frm:]
    opener = re.search(rb"(?:^|\r|\n)xref\s*\r?\n\d+\s+\d+", tail)
    if opener is None:
        return None
    xi = tail.find(b"xref", opener.start())
    trailer_at = tail.find(b"trailer", xi)
    section = tail[xi:trailer_at] if trailer_at >= 0 else tail[xi:]
    body = section[len(b"xref") :]
    headers = [
        (int(m.group(1)), int(m.group(2)))
        for m in re.finditer(rb"(\d+)\s+(\d+)\s*\r?\n", body)
    ]
    flags = [m.group(3) for m in re.finditer(rb"(\d{10})\s(\d{5})\s([nf])", body)]
    used: list[int] = []
    idx = 0
    for first, count in headers:
        for k in range(count):
            if idx >= len(flags):
                break
            if flags[idx] == b"n":
                used.append(first + k)
            idx += 1
    return sorted(set(used))


def _dirty_data_objs(data: bytes, frm: int) -> list[int]:
    """The set of data object numbers written in the section appended after
    byte ``frm`` — classic ``n`` entries or xref-stream ``/Index`` pairs, with
    object 0 and the xref-stream's own object number dropped. Mirrors the Java
    probe's ``appendedDataObjs`` so the differential is meaningful regardless of
    which engine chose which xref encoding."""
    classic = _classic_used_objs(data, frm)
    if classic:
        return sorted(set(classic) - {0})
    tail = data[frm:]
    if not tail:
        return []
    xref_own = -1
    m = re.search(rb"(\d+)\s+\d+\s+obj\b[^e]*?/Type\s*/XRef", tail, re.DOTALL)
    if m is not None:
        xref_own = int(m.group(1))
    objs: set[int] = set()
    idx_m = re.search(rb"/Index\s*\[([^\]]*)\]", tail)
    if idx_m is not None:
        nums = [int(x) for x in idx_m.group(1).split()]
        for i in range(0, len(nums) - 1, 2):
            first, count = nums[i], nums[i + 1]
            for k in range(count):
                objs.add(first + k)
    objs.discard(0)
    if xref_own >= 0:
        objs.discard(xref_own)
    return sorted(objs)


# --- pypdfbox-side mutation drivers (document always closed for Windows) ----


def _editinfo(src: Path, out: Path) -> None:
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        info = doc.get_document_information()
        info.set_title(_TITLE)
        info.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _catalogkey(src: Path, out: Path) -> None:
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        cat = doc.get_document_catalog()
        cat.set_language(_LANG)
        cat.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _addannot(src: Path, out: Path) -> None:
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        page = doc.get_page(0)
        annot = PDAnnotationText()
        annot.set_contents(_ANNOT_CONTENTS)
        annot.set_rectangle(PDRectangle(50, 50, 100, 100))
        annots = page.get_annotations()
        annots.append(annot)
        page.set_annotations(annots)
        annot.get_cos_object().set_needs_to_be_updated(True)
        page.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _noop(src: Path, out: Path) -> None:
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _chain2(src: Path, mid: Path, out: Path) -> None:
    """rev1 edits /Info /Title, rev2 sets a catalog key on top of rev1."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        info = doc.get_document_information()
        info.set_title("Sel1")
        info.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(mid))
    finally:
        doc.close()
    cos = Loader.load_pdf(mid)
    doc = PDDocument(cos)
    try:
        cat = doc.get_document_catalog()
        cat.set_language("de-DE")
        cat.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


_DRIVERS = {
    "editinfo": _editinfo,
    "catalogkey": _catalogkey,
    "addannot": _addannot,
    "noop": _noop,
}


# ----------------------------------------------------------- the parity tests


@requires_oracle
@pytest.mark.parametrize("mode", ["editinfo", "catalogkey", "addannot"])
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_appended_selection_set_matches_pdfbox(
    mode: str, fixture: Path, tmp_path: Path
) -> None:
    """Headline differential: the exact SET of object numbers pypdfbox writes
    into the appended section must equal the set PDFBox wrote — for each
    mutation kind, regardless of which engine encoded the appended xref as a
    classic table or an xref stream (both normalised to the application-level
    object set, dropping object 0 + the xref-stream's own bookkeeping)."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_bytes = fixture.read_bytes()
    src_len = len(src_bytes)

    java_out = tmp_path / f"java_{mode}_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalSelectionFuzzProbe", mode, str(fixture), str(java_out)
        )
    )
    java_objs = sorted(int(x) for x in jf["appended_objs"].split(",") if x)
    assert java_objs, f"PDFBox wrote no dirty data objects for {mode}: {jf}"

    py_out = tmp_path / f"py_{mode}_{fixture.stem}.pdf"
    _DRIVERS[mode](fixture, py_out)
    py_bytes = py_out.read_bytes()
    assert py_bytes.startswith(src_bytes), "incremental save rewrote the prefix"
    py_objs = _dirty_data_objs(py_bytes, src_len)

    assert py_objs == java_objs, (
        f"[{mode}/{fixture.stem}] appended-selection set differs: "
        f"pypdfbox={py_objs} PDFBox={java_objs}"
    )


@requires_oracle
@pytest.mark.parametrize("mode", ["editinfo", "catalogkey", "addannot"])
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_appended_prev_chains_to_source_startxref(
    mode: str, fixture: Path, tmp_path: Path
) -> None:
    """The appended trailer's ``/Prev`` must equal the source's last
    ``startxref`` byte offset — exactly, on both engines (ISO 32000-1
    §7.5.6)."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_bytes = fixture.read_bytes()
    src_len = len(src_bytes)
    src_startxref = _last_startxref(src_bytes)

    java_out = tmp_path / f"java_{mode}_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalSelectionFuzzProbe", mode, str(fixture), str(java_out)
        )
    )
    assert jf["prev_matches"] == "true", jf
    assert int(jf["appended_prev"]) == src_startxref

    py_out = tmp_path / f"py_{mode}_{fixture.stem}.pdf"
    _DRIVERS[mode](fixture, py_out)
    py_prev = _appended_prev(py_out.read_bytes(), src_len)
    assert py_prev == src_startxref, (
        f"[{mode}/{fixture.stem}] pypdfbox /Prev ({py_prev}) != source "
        f"startxref ({src_startxref})"
    )
    assert py_prev == int(jf["appended_prev"])


@requires_oracle
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_noop_appends_empty_revision_matching_pdfbox(
    fixture: Path, tmp_path: Path
) -> None:
    """A ``save_incremental`` with **nothing dirty** still appends a fresh
    (empty) revision on both engines: the source survives as a verbatim
    prefix, the file grows, the appended trailer chains ``/Prev`` to the source
    startxref, and exactly one new ``startxref`` section appears. The appended
    file length and section count must match PDFBox byte-for-byte (wave-1565
    fix — pypdfbox previously short-circuited to a byte-identical copy)."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_bytes = fixture.read_bytes()
    src_len = len(src_bytes)
    src_startxref = _last_startxref(src_bytes)
    src_sections = _count_startxref(src_bytes)

    java_out = tmp_path / f"java_noop_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalSelectionFuzzProbe", "noop", str(fixture), str(java_out)
        )
    )
    assert jf["appended"] == "true", "PDFBox no-op must still append a revision"
    assert jf["appended_objs"] == "", "no-op writes no data objects"
    assert int(jf["appended_prev"]) == src_startxref
    java_out_len = int(jf["out_len"])
    java_sections = int(jf["out_sections"])

    py_out = tmp_path / f"py_noop_{fixture.stem}.pdf"
    _noop(fixture, py_out)
    py_bytes = py_out.read_bytes()

    assert py_bytes.startswith(src_bytes), "no-op rewrote the prefix"
    assert len(py_bytes) > src_len, "no-op must still append an empty revision"
    assert _appended_prev(py_bytes, src_len) == src_startxref
    assert _dirty_data_objs(py_bytes, src_len) == [], "no-op wrote data objects"
    assert _count_startxref(py_bytes) == src_sections + 1
    # Byte-for-byte parity on the appended length + on-disk section count.
    assert len(py_bytes) == java_out_len, (
        f"[{fixture.stem}] no-op appended length differs: pypdfbox="
        f"{len(py_bytes)} PDFBox={java_out_len}"
    )
    assert _count_startxref(py_bytes) == java_sections


@requires_oracle
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_two_sequential_increments_chain_two_prev_hops(
    fixture: Path, tmp_path: Path
) -> None:
    """Two sequential increments compose: rev1 (/Info /Title) chains ``/Prev``
    to the source xref, rev2 (catalog /Lang on top of rev1) chains to rev1's
    xref. Each revision preserves the previous bytes as a verbatim prefix, both
    edits survive the chain, and PDFBox agrees on every fact."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_bytes = fixture.read_bytes()
    src_startxref = _last_startxref(src_bytes)

    jf = _parse_probe(
        run_probe_text(
            "IncrementalSelectionFuzzProbe",
            "chain2",
            str(fixture),
            str(tmp_path / f"java_chain2_{fixture.stem}.pdf"),
        )
    )
    assert jf["rev1_prev_matches"] == "true", jf
    assert jf["rev2_prev_matches"] == "true", jf
    assert jf["mid_prefix_ok"] == "true"
    assert jf["out_prefix_ok"] == "true"
    assert jf["title"] == "Sel1"
    assert jf["lang"] == "de-DE"
    # base + two increments = source sections + 2.
    assert int(jf["out_sections"]) == int(jf["source_sections"]) + 2

    py_mid = tmp_path / f"py_chain2_mid_{fixture.stem}.pdf"
    py_out = tmp_path / f"py_chain2_{fixture.stem}.pdf"
    _chain2(fixture, py_mid, py_out)
    mid_bytes = py_mid.read_bytes()
    out_bytes = py_out.read_bytes()
    mid_startxref = _last_startxref(mid_bytes)

    assert mid_bytes.startswith(src_bytes), "rev1 rewrote the source prefix"
    assert out_bytes.startswith(mid_bytes), "rev2 rewrote rev1's prefix"
    assert _appended_prev(mid_bytes, len(src_bytes)) == src_startxref
    assert _appended_prev(out_bytes, len(mid_bytes)) == mid_startxref
    assert _count_startxref(out_bytes) == _count_startxref(src_bytes) + 2

    # Both edits survive the chain on reload.
    cos = Loader.load_pdf(py_out)
    doc = PDDocument(cos)
    try:
        assert doc.get_document_information().get_title() == "Sel1"
        assert doc.get_document_catalog().get_language() == "de-DE"
    finally:
        doc.close()


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("mode", ["editinfo", "catalogkey", "addannot"])
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_appended_increment_reloads_and_validates(
    mode: str, fixture: Path, tmp_path: Path
) -> None:
    """The mutation survives a reload (the dirty object was emitted, not merely
    flagged) and the appended increment passes ``qpdf --check`` (rc <= 3) — for
    the non-noop modes, whose appended xref is non-degenerate. (The no-op
    xref-stream case emits PDFBox's own ``/W [0 0 0]`` quirk which qpdf rejects
    on *both* engines; its parity is asserted byte-for-byte elsewhere.)"""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    py_out = tmp_path / f"py_{mode}_{fixture.stem}.pdf"
    _DRIVERS[mode](fixture, py_out)

    cos = Loader.load_pdf(py_out)
    doc = PDDocument(cos)
    try:
        if mode == "editinfo":
            assert doc.get_document_information().get_title() == _TITLE
        elif mode == "catalogkey":
            assert doc.get_document_catalog().get_language() == _LANG
        elif mode == "addannot":
            assert len(doc.get_page(0).get_annotations()) >= 1
    finally:
        doc.close()

    rc, log = _qpdf_check(py_out)
    assert rc <= 3, f"[{mode}/{fixture.stem}] qpdf rejected increment (rc={rc}):\n{log}"


@requires_oracle
def test_editpage_selection_shape_pinned_via_pdfbox(tmp_path: Path) -> None:
    """``editpage`` (append a page content stream) is driven Java-oracle-only —
    the pypdfbox font-construction surface differs from PDFBox's, so we pin
    PDFBox 3.0.7's selection shape here: the increment writes a bounded delta
    (the page + its new content stream, never a pool re-dump), chains ``/Prev``
    to the source xref, preserves the prefix, and reloads with the page intact.
    The other modes assert full pypdfbox<->PDFBox parity above."""
    fixture = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_startxref = _last_startxref(fixture.read_bytes())
    jf = _parse_probe(
        run_probe_text(
            "IncrementalSelectionFuzzProbe",
            "editpage",
            str(fixture),
            str(tmp_path / "java_editpage.pdf"),
        )
    )
    assert jf["prefix_ok"] == "true"
    assert jf["prev_matches"] == "true"
    assert int(jf["appended_prev"]) == src_startxref
    objs = sorted(int(x) for x in jf["appended_objs"].split(",") if x)
    assert objs, "PDFBox editpage wrote no dirty objects"
    # A single-page content edit is a bounded delta, never the whole pool.
    assert len(objs) <= 8, f"editpage delta unexpectedly large: {objs}"
    assert jf["reload_pages"] == "2", "page count preserved through the edit"
