"""Live Apache PDFBox differential parity for the annotation model factory.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation.PDAnnotation``

* ``create_annotation`` / ``create`` dispatch — including a /Subtype stored as
  a COSString (upstream reads it via ``getNameAsString``, so it still resolves
  the typed subclass) and a missing /Subtype (-> PDAnnotationUnknown).
* per-subtype no-arg constructor dict shape — every constructor seeds
  /Type /Annot + /Subtype, plus Line's /L=[0,0,0,0] and the four text-markup
  types' empty /QuadPoints.

The Java probe ``AnnotFactoryProbe`` prints a canonical block; pypdfbox builds
the identical block and the two are compared exactly.

Documented divergence (NOT exercised here): pypdfbox's factory dispatches a
richer set of subtypes than upstream's truncated switch (Movie, Screen,
PrinterMark, TrapNet, Watermark, 3D, Redact -> typed subclasses, where upstream
3.0.7 falls back to PDAnnotationUnknown). That superset is intentional and
pinned by the value-based tests in ``test_pd_annotation.py``; this oracle test
only covers subtypes upstream itself dispatches.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationCaret,
    PDAnnotationCircle,
    PDAnnotationFileAttachment,
    PDAnnotationFreeText,
    PDAnnotationHighlight,
    PDAnnotationInk,
    PDAnnotationLine,
    PDAnnotationLink,
    PDAnnotationPolygon,
    PDAnnotationPolyline,
    PDAnnotationPopup,
    PDAnnotationRubberStamp,
    PDAnnotationSound,
    PDAnnotationSquare,
    PDAnnotationSquiggly,
    PDAnnotationStrikeout,
    PDAnnotationText,
    PDAnnotationUnderline,
    PDAnnotationWidget,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_CTOR_CLASSES = {
    "Text": PDAnnotationText,
    "Link": PDAnnotationLink,
    "FreeText": PDAnnotationFreeText,
    "Line": PDAnnotationLine,
    "Square": PDAnnotationSquare,
    "Circle": PDAnnotationCircle,
    "Polygon": PDAnnotationPolygon,
    "PolyLine": PDAnnotationPolyline,
    "Highlight": PDAnnotationHighlight,
    "Underline": PDAnnotationUnderline,
    "Squiggly": PDAnnotationSquiggly,
    "StrikeOut": PDAnnotationStrikeout,
    "Stamp": PDAnnotationRubberStamp,
    "Caret": PDAnnotationCaret,
    "Ink": PDAnnotationInk,
    "Popup": PDAnnotationPopup,
    "FileAttachment": PDAnnotationFileAttachment,
    "Sound": PDAnnotationSound,
    "Widget": PDAnnotationWidget,
}


def _py_shape(ann: PDAnnotation) -> str:
    d = ann.get_cos_object()
    parts: dict[str, str] = {}
    for k in d.key_set():
        name = k.get_name()
        v = d.get_item(k)
        if name in ("Type", "Subtype"):
            parts[name] = v.name  # type: ignore[attr-defined]
        elif isinstance(v, COSArray):
            parts[name] = f"array[{v.size()}]"
        else:
            parts[name] = type(v).__name__ if v is not None else "null"
    return ",".join(f"{k}={parts[k]}" for k in sorted(parts))


def _py_ctor_block() -> str:
    lines = []
    for subtype, cls in _CTOR_CLASSES.items():
        lines.append(f"{subtype}|{_py_shape(cls())}")
    return "\n".join(lines) + "\n"


@requires_oracle
def test_constructor_dict_shape_matches_pdfbox() -> None:
    java = run_probe_text("AnnotFactoryProbe", "ctor")
    assert _py_ctor_block() == java


@requires_oracle
def test_factory_dispatch_matches_pdfbox() -> None:
    java = run_probe_text("AnnotFactoryProbe", "dispatch")

    cos_name = COSDictionary()
    cos_name.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Link"))  # type: ignore[attr-defined]
    cos_str = COSDictionary()
    cos_str.set_item(COSName.SUBTYPE, COSString("Link"))  # type: ignore[attr-defined]
    cos_str_ann = PDAnnotation.create_annotation(cos_str)

    py = (
        f"cosname={type(PDAnnotation.create_annotation(cos_name)).__name__}\n"
        f"cosstring={type(cos_str_ann).__name__}\n"
        f"cosstring_subtype={cos_str_ann.get_subtype()}\n"
        f"missing={type(PDAnnotation.create_annotation(COSDictionary())).__name__}\n"
    )
    assert py == java
