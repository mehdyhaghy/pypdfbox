"""Live PDFBox differential fuzz for FDFAnnotation.create (wave 1519)."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSNull, COSString
from pypdfbox.pdmodel.fdf import FDFAnnotation
from tests.oracle.harness import requires_oracle, run_probe_text

_NAMES = [
    "Text",
    "FreeText",
    "FileAttachment",
    "Square",
    "Circle",
    "Line",
    "Polygon",
    "PolyLine",
    "Polyline",
    "Ink",
    "Stamp",
    "Caret",
    "Highlight",
    "Underline",
    "StrikeOut",
    "Squiggly",
    "Link",
    "Sound",
    "UnknownSubtype",
]


def _dictionary(subtype: object | None) -> COSDictionary:
    dictionary = COSDictionary()
    if subtype is not None:
        dictionary.set_item(COSName.SUBTYPE, subtype)  # type: ignore[arg-type]
    return dictionary


def _py_dump() -> str:
    cases = [(name, _dictionary(COSName.get_pdf_name(name))) for name in _NAMES]
    cases.extend(
        [
            ("missing", _dictionary(None)),
            ("string", _dictionary(COSString("Text"))),
            ("integer", _dictionary(COSInteger.ONE)),
            ("null_value", _dictionary(COSNull.NULL)),
        ]
    )
    lines: list[str] = []
    for name, dictionary in cases:
        try:
            annotation = FDFAnnotation.create(dictionary)
            result = "null" if annotation is None else type(annotation).__name__
        except Exception as exc:
            result = f"ERR:{type(exc).__name__}"
        lines.append(f"CASE {name} {result}\n")
    return "".join(lines)


@requires_oracle
def test_fdf_annotation_factory_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("FdfAnnotationFactoryFuzzProbe")
