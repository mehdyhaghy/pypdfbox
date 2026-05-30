"""Live PDFBox differential parity pinning the two hard invariants of an
incremental save's appended cross-reference section
(``pypdfbox.pdmodel.PDDocument.save_incremental`` /
``pypdfbox.pdfwriter.cos_writer``).

Existing incremental-save oracles
(``test_save_round_trip_oracle``, ``test_incremental_chain_oracle``,
``test_incremental_add_annotation_oracle``) already pin *append-only*
(prefix preserved), *qpdf validity*, *latest-value resolution*, and *new
object minting*. What none of them pin is the **delta precision** of the
appended xref section:

1. **Only the dirty objects are written.** The appended xref section must
   list exactly the changed/added objects plus the mandatory free-list head
   (object 0) — never a re-emission of unchanged objects. A writer that
   conservatively re-dumps the whole object pool into the "incremental"
   section produces a valid-but-bloated file that qpdf still accepts, so the
   validity-only oracles can't catch it. This module counts the *used* (``n``)
   entries in the appended section's raw bytes and asserts the Java and
   pypdfbox object-number sets are identical.

2. **/Prev points at the previous startxref.** The appended trailer's
   ``/Prev`` must numerically equal the byte offset of the source file's last
   ``startxref`` (ISO 32000-1 §7.5.6). An off-by-N /Prev still leaves a file
   qpdf may recover by full scan, masking the bug — so we assert the exact
   integer equality on both sides.

The mutation is identical on both engines: set ``/Info /Title`` to
``DeltaTitle``, flag the /Info dict dirty, ``save_incremental``. The
``IncrementalXrefDeltaProbe`` performs it through Apache PDFBox 3.0.7 and
emits the parsed facts; this module reproduces them through pypdfbox and
asserts parity.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

_FIXTURES_LIST = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "pdfwriter" / "attachment.pdf",
    _FIXTURES / "multipdf" / "rot0.pdf",
]

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_TITLE = "DeltaTitle"


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
    """The last ``startxref N`` integer in ``data`` (offset of its final
    xref). Mirrors the Java probe's ``lastStartxref``."""
    last = -1
    for m in re.finditer(rb"startxref\s+(\d+)", data):
        last = int(m.group(1))
    return last


def _appended_prev(data: bytes, frm: int) -> int:
    """The ``/Prev N`` value parsed from the section appended after byte
    ``frm`` (the increment's trailer). Mirrors the Java probe."""
    last = -1
    for m in re.finditer(rb"/Prev\s+(\d+)", data[frm:]):
        last = int(m.group(1))
    return last


def _classic_used_objs(data: bytes, frm: int) -> list[int] | None:
    """Sorted object numbers carrying a used (``n``) entry in the classic
    xref *table* that opens on/after byte ``frm``. ``None`` when the
    appended increment used an xref *stream* (no classic table opener).
    Mirrors the Java probe's ``usedObjsInSection``."""
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
    """The set of *data* object numbers the appended increment wrote —
    classic-table ``n`` entries or xref-stream ``/Index`` pairs — with
    object 0 (free-list head) and the xref-stream's own object number
    dropped. Mirrors the Java probe's ``dirtyDataObjs`` so the differential
    is meaningful regardless of which engine chose which xref encoding."""
    classic = _classic_used_objs(data, frm)
    if classic:
        return sorted(set(classic) - {0})
    tail = data[frm:]
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


def _set_title_incremental_py(src: Path, out: Path) -> None:
    """Load ``src``, set ``/Info /Title`` to ``DeltaTitle``, flag the /Info
    dict dirty, ``save_incremental`` to ``out``. Always closes the document
    so the source handle is released (Windows file-lock safety)."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        info = doc.get_document_information()
        info.set_title(_TITLE)
        info.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _read_title(path: Path) -> str | None:
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        return doc.get_document_information().get_title()
    finally:
        doc.close()


# ----------------------------------------------------------- the parity tests


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_appended_xref_prev_matches_source_startxref(
    fixture: Path, tmp_path: Path
) -> None:
    """The appended trailer's ``/Prev`` must equal the source's last
    ``startxref`` byte offset — exactly, on both engines."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_bytes = fixture.read_bytes()
    src_len = len(src_bytes)
    src_startxref = _last_startxref(src_bytes)
    assert src_startxref >= 0, "fixture lacks a startxref — pick another"

    # --- Java oracle ----------------------------------------------------
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalXrefDeltaProbe", "delta", str(fixture), str(java_out)
        )
    )
    assert jf["prev_matches"] == "true", (
        f"PDFBox's own /Prev did not match source startxref: {jf}"
    )
    assert int(jf["source_startxref"]) == src_startxref

    # --- pypdfbox -------------------------------------------------------
    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    _set_title_incremental_py(fixture, py_out)
    py_bytes = py_out.read_bytes()

    assert py_bytes.startswith(src_bytes), "incremental save rewrote the prefix"
    py_prev = _appended_prev(py_bytes, src_len)
    assert py_prev == src_startxref, (
        f"pypdfbox /Prev ({py_prev}) != source startxref ({src_startxref})"
    )
    # And it agrees with the value PDFBox wrote.
    assert py_prev == int(jf["appended_prev"]), (
        f"pypdfbox /Prev ({py_prev}) != PDFBox /Prev ({jf['appended_prev']})"
    )

    rc, log = _qpdf_check(py_out)
    assert rc <= 3, f"pypdfbox incremental failed qpdf (rc={rc}):\n{log}"


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_appended_xref_contains_only_dirty_objects(
    fixture: Path, tmp_path: Path
) -> None:
    """The appended revision writes exactly the dirty data object(s) (the
    /Info dict) — never a re-dump of the unchanged pool. The Java and
    pypdfbox dirty-data-object number sets must be identical, regardless of
    whether each engine encoded the appended xref as a classic table
    (pypdfbox) or an xref stream (PDFBox); the probe normalises both to the
    application-level object set (dropping object 0 + the xref-stream's own
    bookkeeping object)."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_bytes = fixture.read_bytes()
    src_len = len(src_bytes)

    # --- Java oracle ----------------------------------------------------
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalXrefDeltaProbe", "delta", str(fixture), str(java_out)
        )
    )
    java_objs = [int(x) for x in jf["appended_used_objs"].split(",") if x]
    assert java_objs, (
        "PDFBox appended increment wrote no dirty data objects — probe could "
        f"not parse the appended xref (table or stream): {jf}"
    )
    # The dirty mutation touched exactly one object (the /Info dict). PDFBox's
    # incremental section therefore carries a small, bounded set — never the
    # whole pool. (We assert the precise parity with pypdfbox below; this is a
    # sanity bound that the increment is genuinely a delta, not a full dump.)
    assert len(java_objs) <= 5, (
        f"PDFBox appended {len(java_objs)} objects for a single-field edit — "
        f"unexpectedly large delta: {java_objs}"
    )

    # --- pypdfbox -------------------------------------------------------
    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    _set_title_incremental_py(fixture, py_out)
    py_bytes = py_out.read_bytes()
    py_objs = _dirty_data_objs(py_bytes, src_len)
    assert py_objs, (
        "pypdfbox appended xref carried no dirty data objects — the modified "
        "/Info dict was dropped from the appended revision"
    )

    # Headline differential: the exact set of object numbers pypdfbox wrote
    # into the appended section must equal the set PDFBox wrote.
    assert py_objs == java_objs, (
        f"appended-xref used-object set differs: pypdfbox={py_objs} "
        f"PDFBox={java_objs} — incremental save re-emitted the wrong objects"
    )


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_modified_title_resolves_on_reload(fixture: Path, tmp_path: Path) -> None:
    """The single modified object's new value (``/Info /Title``) must be
    recovered on reload by both engines — confirming the dirty object was
    actually emitted into the appended revision (not merely flagged)."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text(
            "IncrementalXrefDeltaProbe", "delta", str(fixture), str(java_out)
        )
    )
    assert jf["title"] == _TITLE

    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    _set_title_incremental_py(fixture, py_out)
    assert _read_title(py_out) == _TITLE
