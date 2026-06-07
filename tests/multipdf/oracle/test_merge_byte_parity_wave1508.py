"""Live PDFBox differential parity for ``PDFMergerUtility`` *merged page-dict
byte shape* (``pypdfbox.multipdf.pdf_merger_utility``).

Wave 1506 (``test_merge_byte_geometry_oracle.py``) proved the merged object
*graph* — numbering, ``/Type`` roles, page-tree shape, header version — is
byte-identical to PDFBox under a matched (uncompressed) save strategy. This
module goes one level finer, into the **page dictionaries themselves**, and pins
the things that determine whether a merged page serializes byte-for-byte the way
PDFBox serializes it:

* the page dict's **key insertion order**,
* the presence + value of a **materialized ``/CropBox``** (PDFBox's
  ``appendDocument`` page loop runs ``setCropBox``/``setMediaBox``/
  ``setRotation``/``setResources`` unconditionally, so a source page that only
  *inherited* a crop box gains an explicit ``/CropBox`` key in the merged
  output),
* the **``/Parent`` key position** (upstream does NOT strip + re-append
  ``/Parent`` — ``PDPageTree.add`` overwrites it in place, so it keeps its
  source slot rather than landing last),
* the **trailing ``/Annots``** a struct-tree merge materializes (upstream's
  struct-tree branch finishes with ``newPage.setAnnotations(annotations)``,
  which writes an ``/Annots`` array — empty when the source had none).

Fixtures cover every shape the wave-1508 production fixes target:

* ``rot0`` / ``rot90`` — own ``/Resources``, own ``/Rotate``, inherited-only
  crop, no struct tree (the clean numbering pair).
* ``PDFBOX-6018-…-OrphanPopups`` — **no own ``/Resources``** AND inherited-only
  crop AND no own ``/Rotate``: exercises every unconditional setter appending a
  fresh key.
* ``AcroFormForMerge`` — page carries its **own ``/CropBox``** (setCropBox is an
  in-place value update, key keeps its source slot).
* ``PDFA3A`` — a **struct-tree** source (materializes the trailing ``/Annots``).

The full merged bytes are byte-identical to PDFBox *modulo* the
content+time-derived ``/ID`` hash (non-deterministic by design) for the clean
page-concatenation pair AND, since wave 1509, for the complex AcroForm /
struct-tree fixtures too. The two wave-1508 writer-level residuals (form-XObject
``/Resources`` written indirect vs PDFBox's inline-direct; struct-tree
ParentTree number-tree node lacking ``/Limits``) are CLOSED — see ``CHANGES.md``
wave 1509. ``test_complex_fixture_merge_is_byte_identical_modulo_id`` now pins
the whole merged byte stream for every complex fixture.
"""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path

import pytest

from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"

_PROBE = "MergePageDictOrderProbe"


# --------------------------------------------------------------- helpers


def _have(*names: str) -> list[Path]:
    paths = [_FIXTURES / n for n in names]
    for p in paths:
        if not p.is_file():
            pytest.skip(f"fixture missing: {p}")
    return paths


def _parse_probe(text: str) -> list[dict[str, object]]:
    """Parse ``MergePageDictOrderProbe`` stdout into a per-page record list."""
    pages: dict[int, dict[str, object]] = {}
    for line in text.splitlines():
        if not line or not line.startswith("page "):
            continue
        _, idx_s, field, *rest = line.split(" ", 3)
        idx = int(idx_s)
        rec = pages.setdefault(idx, {})
        if field == "keys":
            rec["keys"] = rest[0].split(",") if rest and rest[0] else []
        elif field == "crop":
            rec["crop"] = "none" if rest[0] == "none" else tuple(rest[0].split(" "))
        elif field == "parent_index":
            rec["parent_index"] = int(rest[0])
    return [pages[i] for i in sorted(pages)]


def _merge_py_pages(sources: list[Path]) -> list[dict[str, object]]:
    """Reproduce the merger's append pipeline and emit the same per-page record
    shape as the Java probe, reading the page dicts back from the live model.

    The Java probe reloads the *saved* file; here we read the in-memory model
    after append. The serialized key order equals the COSDictionary key order
    (the writer emits keys in insertion order), so this is the faithful Python
    side of the differential.
    """
    merger = PDFMergerUtility()
    dest = PDDocument()
    try:
        for src in sources:
            sd = PDDocument.load(src)
            try:
                merger.append_document(dest, sd)
            finally:
                sd.close()
        records: list[dict[str, object]] = []
        for i in range(dest.get_number_of_pages()):
            page = dest.get_page(i)
            pc = page.get_cos_object()
            keys = [str(k).lstrip("/") for k in pc.key_set()]
            parent_index = keys.index("Parent") if "Parent" in keys else -1
            crop_rect = page.get_crop_box()
            if crop_rect is None:
                crop: object = "none"
            else:
                crop = tuple(
                    _float_bits(v)
                    for v in (
                        crop_rect.get_lower_left_x(),
                        crop_rect.get_lower_left_y(),
                        crop_rect.get_upper_right_x(),
                        crop_rect.get_upper_right_y(),
                    )
                )
            records.append(
                {"keys": keys, "parent_index": parent_index, "crop": crop}
            )
        return records
    finally:
        dest.close()


def _float_bits(value: float) -> str:
    """IEEE-754 single-precision bit pattern as lowercase hex (matches the Java
    probe's ``Integer.toHexString(Float.floatToIntBits(f))``)."""
    import struct

    bits = struct.unpack(">I", struct.pack(">f", float(value)))[0]
    return format(bits, "x")


def _run_probe_pages(sources: list[Path]) -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as td:
        out = str(Path(td) / "java.pdf")
        text = run_probe_text(_PROBE, out, *[str(s) for s in sources])
    return _parse_probe(text)


def _merge_py_uncompressed_bytes(sources: list[Path]) -> bytes:
    merger = PDFMergerUtility()
    dest = PDDocument()
    try:
        for src in sources:
            sd = PDDocument.load(src)
            try:
                merger.append_document(dest, sd)
            finally:
                sd.close()
        buf = io.BytesIO()
        with COSWriter(buf) as writer:
            writer.write(dest)
        return buf.getvalue()
    finally:
        dest.close()


def _strip_id(data: bytes) -> bytes:
    """Blank the non-deterministic ``/ID`` so byte comparison is meaningful."""
    return re.sub(
        rb"/ID \[<[0-9A-Fa-f]+> <[0-9A-Fa-f]+>\]", b"/ID [<ID> <ID>]", data
    )


# ------------------------------------------------------------------ scenarios

# (label, source-fixture-names) — each row is a merge pair the page-dict pins
# run against. Chosen to cover: own-Resources+own-Rotate+inherited-crop;
# no-Resources+no-Rotate+inherited-crop; own-CropBox; struct-tree source.
_SCENARIOS = [
    ("rot0_rot90", ("rot0.pdf", "rot90.pdf")),
    (
        "no_resources_inherited_crop",
        ("PDFBOX-6018-099267-p9-OrphanPopups.pdf", "rot0.pdf"),
    ),
    ("own_cropbox", ("AcroFormForMerge.pdf", "rot0.pdf")),
    ("struct_tree", ("PDFA3A.pdf", "rot0.pdf")),
]


# ------------------------------------------------------------------ tests


@requires_oracle
@pytest.mark.parametrize(
    "names", [s[1] for s in _SCENARIOS], ids=[s[0] for s in _SCENARIOS]
)
def test_merged_page_dict_shape_matches_pdfbox(names: tuple[str, ...]) -> None:
    """Per merged page: key insertion order, materialized ``/CropBox`` value,
    ``/Parent`` key position, and (for struct-tree sources) the trailing
    ``/Annots`` are byte-faithful to PDFBox.

    This is the load-bearing wave-1508 pin. A regression in any of the
    appendDocument geometry setters (order, conditional vs unconditional, or the
    struct-tree ``setAnnotations`` write-back) shifts a page's key list or crop
    value immediately.
    """
    sources = _have(*names)
    java = _run_probe_pages(sources)
    py = _merge_py_pages(sources)

    assert len(py) == len(java), (
        f"merged page count diverged: pypdfbox {len(py)} vs PDFBox {len(java)}"
    )
    for i, (jp, pp) in enumerate(zip(java, py, strict=True)):
        assert pp["keys"] == jp["keys"], (
            f"page {i} key order diverged:\n"
            f"  pypdfbox: {pp['keys']}\n  PDFBox:   {jp['keys']}"
        )
        assert pp["crop"] == jp["crop"], (
            f"page {i} /CropBox diverged: "
            f"pypdfbox {pp['crop']} vs PDFBox {jp['crop']}"
        )
        assert pp["parent_index"] == jp["parent_index"], (
            f"page {i} /Parent key position diverged: "
            f"pypdfbox {pp['parent_index']} vs PDFBox {jp['parent_index']}"
        )


@requires_oracle
def test_merged_cropbox_materialized_for_inherited_only_source() -> None:
    """A source page that only *inherited* its crop box gains an explicit
    ``/CropBox`` key in the merged output — present, non-``none``, and
    positioned exactly as PDFBox positions it.
    """
    sources = _have("PDFBOX-6018-099267-p9-OrphanPopups.pdf", "rot0.pdf")
    java = _run_probe_pages(sources)
    py = _merge_py_pages(sources)
    for i, (jp, pp) in enumerate(zip(java, py, strict=True)):
        assert "CropBox" in pp["keys"], f"page {i} missing materialized /CropBox"
        assert pp["crop"] != "none"
        assert pp["keys"].index("CropBox") == jp["keys"].index("CropBox")


@requires_oracle
def test_merged_struct_tree_page_materializes_trailing_annots() -> None:
    """Upstream's struct-tree merge branch finishes with
    ``newPage.setAnnotations(...)``, which materializes a trailing ``/Annots``
    array even when the source page had none. pypdfbox mirrors that, so a merged
    struct-tree page ends with ``/Annots``.
    """
    sources = _have("PDFA3A.pdf", "rot0.pdf")
    java = _run_probe_pages(sources)
    py = _merge_py_pages(sources)
    # Page 0 is the struct-tree source page.
    assert java[0]["keys"][-1] == "Annots"
    assert py[0]["keys"][-1] == "Annots"
    assert py[0]["keys"] == java[0]["keys"]


@requires_oracle
def test_plain_concatenation_merge_is_byte_identical_modulo_id() -> None:
    """For a clean page-concatenation pair (no AcroForm / struct tree to merge),
    the full uncompressed merged bytes are byte-identical to PDFBox apart from
    the content+time-derived ``/ID`` hash — the strongest possible parity pin.
    """
    sources = _have("rot0.pdf", "rot90.pdf")
    with tempfile.TemporaryDirectory() as td:
        java_out = Path(td) / "java.pdf"
        # MergePageDictOrderProbe already saved the merged file to java_out via
        # its first arg; reuse MergeObjectGeometryProbe's writer would also do,
        # but here we run the dict-order probe purely for its side-effect file.
        run_probe_text(_PROBE, str(java_out), *[str(s) for s in sources])
        java_bytes = java_out.read_bytes()

    py_bytes = _merge_py_uncompressed_bytes(sources)
    assert _strip_id(py_bytes) == _strip_id(java_bytes), (
        "plain-concatenation merge diverged beyond /ID; "
        f"sizes pypdfbox={len(py_bytes)} PDFBox={len(java_bytes)}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "names",
    [
        ("AcroFormForMerge.pdf", "rot0.pdf"),
        ("PDFBOX-6018-099267-p9-OrphanPopups.pdf", "rot0.pdf"),
        ("PDFA3A.pdf", "rot0.pdf"),
    ],
    ids=["own_cropbox_formxobject", "orphan_no_resources", "struct_tree"],
)
def test_complex_fixture_merge_is_byte_identical_modulo_id(
    names: tuple[str, ...],
) -> None:
    """The complex AcroForm / struct-tree merge fixtures are now byte-identical
    to PDFBox 3.0.7 (modulo the time-derived ``/ID``) — the two wave-1508
    writer-level residuals are CLOSED in wave 1509.

    History (wave 1508, see CHANGES.md / DEFERRED.md): these pairs previously
    diverged below the page-dict layer by exactly two writer-level markers and
    were only pinned structurally (this test formerly asserted the divergence
    *was* those two markers, so a page-dict regression could not hide behind
    them). Wave 1509 root-caused and fixed both upstream-faithfully:

      * a form-XObject's ``/Resources`` (and any nested ``/XObject``)
        sub-dictionary is now written INLINE (direct) — pypdfbox's
        ``COSWriter.visit_from_dictionary`` mirrors upstream's PDFBOX-3684
        ``setDirect(true)`` block for non-incremental saves;
      * the merged struct-tree ParentTree single-leaf number-tree node now
        carries ``/Limits [lower upper]`` (``[0 0]`` for the single-leaf case),
        emitted ahead of ``/Nums`` exactly as upstream ``setNumbers`` does.

    With both fixed, the whole merged byte stream matches PDFBox for every
    complex fixture — the strongest possible parity pin.
    """
    sources = _have(*names)
    with tempfile.TemporaryDirectory() as td:
        java_out = Path(td) / "java.pdf"
        run_probe_text(_PROBE, str(java_out), *[str(s) for s in sources])
        java_bytes = java_out.read_bytes()
    py_bytes = _merge_py_uncompressed_bytes(sources)

    assert _strip_id(py_bytes) == _strip_id(java_bytes), (
        "complex merge diverged beyond /ID; "
        f"sizes pypdfbox={len(py_bytes)} PDFBox={len(java_bytes)}"
    )


@requires_oracle
def test_struct_tree_parent_tree_limits_emitted_before_nums() -> None:
    """The wave-1509 ParentTree-``/Limits`` fix specifically: the merged
    struct-tree single-leaf number-tree node carries ``/Limits [0 0]`` AND
    serializes it ahead of ``/Nums`` (upstream ``setNumbers`` materializes
    ``/Limits`` via ``setUpper/LowerLimit`` before ``setItem(NUMS, ...)``).
    """
    sources = _have("PDFA3A.pdf", "rot0.pdf")
    with tempfile.TemporaryDirectory() as td:
        java_out = Path(td) / "java.pdf"
        run_probe_text(_PROBE, str(java_out), *[str(s) for s in sources])
        java_bytes = java_out.read_bytes()
    py_bytes = _merge_py_uncompressed_bytes(sources)

    for blob in (java_bytes, py_bytes):
        assert b"/Limits [0 0]" in blob
        # /Limits precedes /Nums inside the ParentTree leaf object.
        limits_at = blob.index(b"/Limits [0 0]")
        nums_at = blob.index(b"/Nums [0 ", limits_at - 80)
        assert limits_at < nums_at
