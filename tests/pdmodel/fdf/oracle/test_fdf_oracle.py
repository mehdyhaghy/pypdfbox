"""Live Apache PDFBox differential parity for FDF / XFDF documents
(``pypdfbox.pdmodel.fdf``).

No FDF/XFDF fixtures ship with the repo, so the parity rig *builds* an FDF
through pypdfbox (a handful of fields — one with nested ``/Kids``, one
multi-select — plus a couple of annotations and a ``/F`` source reference),
saves it as both FDF and XFDF, then runs **both** libraries over the saved
artefacts and asserts they read the same field tree, values, and annotations.

The Java oracle is ``FdfProbe`` (modes ``dump`` / ``roundtrip``). It emits
canonical, line-oriented facts:

* ``F=<source PDF path or - >``
* ``FIELD <fully-qualified-name> | value=<repr> | kids=<n>`` (depth-first)
* ``ANNOT <subtype or -> | rect=<llx,lly,urx,ury or - >``

``_py_dump`` reproduces exactly that format from pypdfbox so the two sides can
be compared line-for-line.

Key behavioural facts confirmed against PDFBox 3.0.7 and baked into the
assertions here:

* A pypdfbox-saved FDF must start with an ``%FDF-`` header — PDFBox's
  ``FDFParser`` rejects a ``%PDF-`` header. (Fixed: ``COSWriter(fdf=True)``.)
* ``FDFDictionary.writeXML`` (the XFDF serialiser) does **not** emit
  ``<annots>`` — XFDF round-trips fields + ``/F`` but drops annotations. This
  is upstream behaviour, so the XFDF comparison only covers fields + ``/F``.
* A multi-select field serialised to XFDF as repeated ``<value>`` elements is
  collapsed to the *last* value on reload by **both** libraries (PDFBox's
  ``FDFField(Element)`` keeps only the last ``<value>``). Asserted as parity,
  not flagged as a bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.fdf import FDFDocument
from pypdfbox.pdmodel.fdf.fdf_annotation_square import FDFAnnotationSquare
from pypdfbox.pdmodel.fdf.fdf_annotation_text import FDFAnnotationText
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- fixture build


def _build_fdf(path_fdf: Path, path_xfdf: Path) -> None:
    """Build a representative FDF via pypdfbox and save it as both FDF and
    XFDF. Fields: a scalar, a parent with one kid, and a multi-select.
    Annotations: a Text and a Square (each with a /Rect). Plus a /F.
    """
    doc = FDFDocument()
    try:
        fdf = doc.get_catalog().get_fdf()

        fs = PDSimpleFileSpecification()
        fs.set_file("source.pdf")
        fdf.set_file(fs)

        f_name = FDFField()
        f_name.set_partial_field_name("name")
        f_name.set_value("Alice")

        f_addr = FDFField()
        f_addr.set_partial_field_name("address")
        kid_city = FDFField()
        kid_city.set_partial_field_name("city")
        kid_city.set_value("Paris")
        f_addr.set_kids([kid_city])

        f_langs = FDFField()
        f_langs.set_partial_field_name("langs")
        f_langs.set_value(["en", "fr"])

        fdf.set_fields([f_name, f_addr, f_langs])

        a_text = FDFAnnotationText()
        a_text.set_page(0)
        a_text.set_rectangle((10.0, 20.0, 30.0, 40.0))

        a_square = FDFAnnotationSquare()
        a_square.set_page(0)
        a_square.set_rectangle((1.5, 2.5, 3.5, 4.5))

        fdf.set_annotations([a_text, a_square])

        doc.save(str(path_fdf))
        doc.save_xfdf(str(path_xfdf))
    finally:
        doc.close()


# --------------------------------------------------------------- py dump helper


def _fmt_num(v: float) -> str:
    """Match the probe's float formatting: drop a trailing ``.0`` for
    integral coordinates so ``10.0`` and ``10`` compare equal."""
    if v == int(v):
        return str(int(v))
    return str(v)


def _value_repr(value: object | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return "[" + "|".join(str(item) for item in value) + "]"
    return str(value)


def _emit_field(field: FDFField, prefix: str, lines: list[str]) -> None:
    partial = field.get_partial_field_name() or ""
    fq = f"{prefix}.{partial}" if prefix and partial else (prefix or partial)
    value_repr = _value_repr(field.get_value())
    kids = field.get_kids()
    kid_count = 0 if kids is None else len(kids)
    lines.append(f"FIELD {fq} | value={value_repr} | kids={kid_count}")
    if kids is not None:
        for kid in kids:
            _emit_field(kid, fq, lines)


def _py_dump(doc: FDFDocument, *, with_annots: bool) -> list[str]:
    """Reproduce the probe's canonical ``dump`` output from pypdfbox.

    ``with_annots=False`` for the XFDF comparison, since the XFDF serialiser
    does not write ``<annots>`` (matches upstream ``FDFDictionary.writeXML``).
    """
    fdf = doc.get_catalog().get_fdf()
    lines: list[str] = []

    fs = fdf.get_file()
    f = "-" if fs is None or fs.get_file() is None else fs.get_file()
    lines.append(f"F={f}")

    fields = fdf.get_fields()
    if fields is not None:
        for field in fields:
            _emit_field(field, "", lines)

    if with_annots:
        annots = fdf.get_annotations()
        if annots is not None:
            for annot in annots:
                subtype = annot.get_subtype() or "-"
                rect = annot.get_rectangle()
                rect_repr = (
                    "-" if rect is None else ",".join(_fmt_num(c) for c in rect)
                )
                lines.append(f"ANNOT {subtype} | rect={rect_repr}")

    return lines


def _java_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln and not ln.startswith("== ")]


# --------------------------------------------------------------------- tests


@requires_oracle
def test_fdf_fields_annotations_match_pdfbox(tmp_path: Path) -> None:
    """pypdfbox and PDFBox read the same field tree, values, kids, /F, and
    annotations from a pypdfbox-saved FDF file."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    # The FDF header must be %FDF- (PDFBox's FDFParser requires it).
    assert fdf_path.read_bytes().startswith(b"%FDF-"), (
        "pypdfbox FDF save must emit an %FDF- header; PDFBox rejects %PDF-"
    )

    java = _java_lines(run_probe_text("FdfProbe", "dump", "fdf", str(fdf_path)))

    doc = Loader.load_fdf(str(fdf_path))
    try:
        py = _py_dump(doc, with_annots=True)
    finally:
        doc.close()

    assert py == java


@requires_oracle
def test_xfdf_fields_match_pdfbox(tmp_path: Path) -> None:
    """pypdfbox and PDFBox read the same field tree, values, and /F from a
    pypdfbox-saved XFDF file. Annotations are excluded — the XFDF serialiser
    does not write <annots> (upstream FDFDictionary.writeXML)."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    java = _java_lines(run_probe_text("FdfProbe", "dump", "xfdf", str(xfdf_path)))

    doc = Loader.load_xfdf(str(xfdf_path))
    try:
        py = _py_dump(doc, with_annots=False)
    finally:
        doc.close()

    assert py == java


@requires_oracle
def test_xfdf_does_not_carry_annotations(tmp_path: Path) -> None:
    """Documented divergence-free behaviour: the XFDF serialiser drops
    annotations on both sides. PDFBox's dump of the saved XFDF carries no
    ANNOT line, and so does pypdfbox's reload."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    java = run_probe_text("FdfProbe", "dump", "xfdf", str(xfdf_path))
    assert "ANNOT" not in java

    doc = Loader.load_xfdf(str(xfdf_path))
    try:
        annots = doc.get_catalog().get_fdf().get_annotations()
    finally:
        doc.close()
    # No <annots> element in the XFDF → get_annotations() returns None.
    assert annots is None


@requires_oracle
def test_fdf_round_trip_pypdfbox_save_java_reload(tmp_path: Path) -> None:
    """Round-trip contract: a pypdfbox-saved FDF, when re-saved by PDFBox as
    both FDF and XFDF and reloaded, yields the same fields PDFBox first read.

    The probe's ``roundtrip`` mode does PDFBox-side load → save(FDF) +
    saveXFDF → reload-each → dump. We assert:

    * the re-saved FDF block matches what pypdfbox reads from the *original*
      FDF (field tree + values + /F + annotations all survive a full PDFBox
      FDF round-trip);
    * the re-saved XFDF block matches what pypdfbox reads from the *XFDF*
      (fields + /F; annotations dropped by the XFDF serialiser, and the
      multi-select ``langs`` collapses to its last value — both libraries
      behave identically on the XFDF path)."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    out_fdf = tmp_path / "rt.fdf"
    out_xfdf = tmp_path / "rt.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    raw = run_probe_text(
        "FdfProbe",
        "roundtrip",
        "fdf",
        str(fdf_path),
        str(out_fdf),
        str(out_xfdf),
    )

    # Split the probe output into its two reload blocks.
    fdf_block: list[str] = []
    xfdf_block: list[str] = []
    target: list[str] | None = None
    for line in raw.splitlines():
        if line == "== fdf ==":
            target = fdf_block
        elif line == "== xfdf ==":
            target = xfdf_block
        elif line and target is not None:
            target.append(line)

    # pypdfbox's own reading of the original FDF — baseline for the FDF block.
    doc_fdf = Loader.load_fdf(str(fdf_path))
    try:
        py_full = _py_dump(doc_fdf, with_annots=True)
    finally:
        doc_fdf.close()

    # pypdfbox's own reading of the saved XFDF — baseline for the XFDF block.
    # (The XFDF serialiser drops annotations and the multi-select collapses to
    # its last value, so this is the correct parity baseline, not the FDF one.)
    doc_xfdf = Loader.load_xfdf(str(xfdf_path))
    try:
        py_xfdf = _py_dump(doc_xfdf, with_annots=False)
    finally:
        doc_xfdf.close()

    # A full PDFBox FDF round-trip preserves the whole field tree + annots.
    assert fdf_block == py_full
    # The XFDF round-trip preserves fields + /F (annotations dropped).
    assert xfdf_block == py_xfdf


@requires_oracle
def test_fdf_saved_by_pypdfbox_round_trips_through_pypdfbox(tmp_path: Path) -> None:
    """Pure-pypdfbox FDF round-trip: save → reload reproduces the field tree,
    values, kids, /F, and annotations (sanity check independent of Java)."""
    fdf_path = tmp_path / "built.fdf"
    xfdf_path = tmp_path / "built.xfdf"
    _build_fdf(fdf_path, xfdf_path)

    doc = Loader.load_fdf(str(fdf_path))
    try:
        dump = _py_dump(doc, with_annots=True)
    finally:
        doc.close()

    assert dump == [
        "F=source.pdf",
        "FIELD name | value=Alice | kids=0",
        "FIELD address | value=- | kids=1",
        "FIELD address.city | value=Paris | kids=0",
        "FIELD langs | value=[en|fr] | kids=0",
        "ANNOT Text | rect=10,20,30,40",
        "ANNOT Square | rect=1.5,2.5,3.5,4.5",
    ]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q", "--no-cov"]))
