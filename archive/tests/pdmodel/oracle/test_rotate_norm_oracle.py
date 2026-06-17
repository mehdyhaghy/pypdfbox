"""Live PDFBox differential parity for out-of-spec ``/Rotate`` value normalisation.

PDF 32000-1 §14.8.4 says ``/Rotate`` "shall be a multiple of 90" in
``{0, 90, 180, 270}``. Real PDFs in the wild violate that — negative angles
(``-90``, ``-180``), values ``>= 360`` (``450``, ``720``) and odd non-multiples
(``45``) all show up. ``PDPage.getRotation()`` is therefore expected to
*normalise* the wild value into ``[0, 360)`` (PDFBox does this via
``((v % 360) + 360) % 360`` once it has confirmed ``v % 90 == 0``).

Sister test ``test_page_inheritance_oracle.py`` already covers a *single*
``/Rotate -90`` case as one field in a multi-attribute walk. This module is
the dedicated, page-per-case parity pin for that normalisation logic and
sweeps every interesting bucket:

* ``-90`` — negative-mod (the classic Python-vs-Java sign-of-mod trap).
* ``450`` — value above 360.
* ``720`` — exact multiple of 360 (should collapse to 0).
* ``45``  — non-multiple-of-90 (PDFBox returns ``0`` per the upstream
  ``rotationAngle % 90 == 0`` gate; pypdfbox must match).
* ``-180`` — negative whose ``% 360`` in C/Java would already be ``-180``,
  exercising the ``+360`` arm of the normalisation.

Each page is built as a hand-authored ``/Page`` dictionary so the parser sees
the raw out-of-spec integer; no constructor-side coercion is involved. The
probe (``oracle/probes/RotateNormProbe.java``) calls
``PDPage.getRotation()`` per page; pypdfbox's :meth:`PDPage.get_rotation` is
asserted equal field-for-field.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_COUNT = COSName.COUNT  # type: ignore[attr-defined]
_PAGES = COSName.PAGES  # type: ignore[attr-defined]
_PAGE = COSName.PAGE  # type: ignore[attr-defined]
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_MEDIA_BOX = COSName.MEDIA_BOX  # type: ignore[attr-defined]
_ROTATE = COSName.get_pdf_name("Rotate")


# Out-of-spec /Rotate values, in page order. Test IDs (see PARITY_CASES) keep
# the canonical mapping readable when a failure points at a row.
_RAW_ROTATIONS: tuple[int, ...] = (-90, 450, 720, 45, -180)


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    arr = COSArray()
    for v in (llx, lly, urx, ury):
        arr.add(COSInteger.get(int(v)))
    return arr


def _build_rotate_pdf(path: Path) -> None:
    """Hand-craft a flat page tree whose pages each carry one of the
    malformed ``/Rotate`` values in :data:`_RAW_ROTATIONS`."""
    doc = PDDocument()
    try:
        cos_doc = doc.get_document()
        catalog = cos_doc.get_trailer().get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]

        root = COSDictionary()
        root.set_item(_TYPE, _PAGES)
        # Root MediaBox so the malformed pages still have a resolvable box.
        root.set_item(_MEDIA_BOX, _rect(0, 0, 612, 792))

        kids = COSArray()
        for raw in _RAW_ROTATIONS:
            page = COSDictionary()
            page.set_item(_TYPE, _PAGE)
            page.set_item(_PARENT, root)
            page.set_item(_ROTATE, COSInteger.get(int(raw)))
            kids.add(page)
        root.set_item(_KIDS, kids)
        root.set_int(_COUNT, len(_RAW_ROTATIONS))

        catalog.set_item(_PAGES, root)
        doc.save(path)
    finally:
        doc.close()


def _py_report(path: Path) -> str:
    """Rebuild the canonical report ``RotateNormProbe`` emits, field-for-field."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        count = doc.get_number_of_pages()
        lines.append(f"count {count}")
        for i, page in enumerate(doc.get_pages()):
            lines.append(f"page {i} rotate {page.get_rotation()}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_rotate_normalisation_matches_pdfbox(tmp_path: Path) -> None:
    """``PDPage.get_rotation()`` must match Apache PDFBox for every malformed
    ``/Rotate`` value (negative, ``>= 360``, exact multiple of 360, and
    non-multiple-of-90). Mismatch on any row is a real parity bug — the
    negative-mod-360 wraparound and the non-multiple-of-90 reject-to-zero are
    the high-value cases."""
    pdf = tmp_path / "rotate_norm.pdf"
    _build_rotate_pdf(pdf)

    java = run_probe_text("RotateNormProbe", str(pdf))
    py = _py_report(pdf)

    assert py == java, (
        "page /Rotate normalisation diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_rotate_normalisation_per_case(tmp_path: Path) -> None:
    """Stronger per-case assertion. The bulk equality in
    :func:`test_rotate_normalisation_matches_pdfbox` already pins parity, but a
    failure there only points at the diffed line. This variant decomposes the
    probe output into per-page rotations and asserts each one matches the
    expected normalised value, so a regression names the exact malformed input
    that broke (e.g. "pypdfbox returned 90 for raw 450, expected 90")."""
    pdf = tmp_path / "rotate_norm_cases.pdf"
    _build_rotate_pdf(pdf)

    java_lines = run_probe_text("RotateNormProbe", str(pdf)).splitlines()
    # Drop the "count N" header; remainder is one "page i rotate <v>" per page.
    java_rot = [int(line.rsplit(" ", 1)[-1]) for line in java_lines[1:]]

    doc = PDDocument.load(pdf)
    try:
        py_rot = [page.get_rotation() for page in doc.get_pages()]
    finally:
        doc.close()

    for raw, py_val, java_val in zip(_RAW_ROTATIONS, py_rot, java_rot, strict=True):
        assert py_val == java_val, (
            f"raw /Rotate {raw}: pypdfbox={py_val} pdfbox={java_val}"
        )
