"""Live PDFBox differential fuzz for XFDF import (wave 1519)."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.loader import Loader
from pypdfbox.pdmodel.fdf import FDFField
from tests.oracle.harness import requires_oracle, run_probe_text

_OPEN = '<xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve">'

_CASES = {
    "empty": f"{_OPEN}</xfdf>",
    "wrong_root": "<notxfdf/>",
    "prefixed_root": '<x:xfdf xmlns:x="http://ns.adobe.com/xfdf/"/>',
    "malformed": f"{_OPEN}<fields></xfdf>",
    "field_simple": f'{_OPEN}<fields><field name="a"><value>one</value></field></fields></xfdf>',
    "field_nested": (
        f'{_OPEN}<fields><field name="a"><field name="b"><value>two</value>'
        "</field></field></fields></xfdf>"
    ),
    "field_missing_name": f'{_OPEN}<fields><field><value>blank</value></field></fields></xfdf>',
    "field_rich": (
        f'{_OPEN}<fields><field name="r"><value-richtext>rich</value-richtext>'
        "</field></fields></xfdf>"
    ),
    "file_ids": f'{_OPEN}<f href="forms.pdf"/><ids original="0011" modified="aabb"/></xfdf>',
    "ids_bad": f'{_OPEN}<ids original="xyz" modified="01"/></xfdf>',
    "annots_known": (
        f'{_OPEN}<annots><text page="1" rect="0,0,10,10" color="#ff0000">'
        '<contents>Hi</contents></text><square page="0" rect="1,2,3,4"/>'
        "</annots></xfdf>"
    ),
    "annots_unknown": (
        f'{_OPEN}<annots><mystery page="0"/>'
        '<text page="0" rect="0,0,1,1"/></annots></xfdf>'
    ),
    "annot_bad_page": f'{_OPEN}<annots><text page="bogus" rect="0,0,1,1"/></annots></xfdf>',
    "annot_bad_rect": f'{_OPEN}<annots><text page="0" rect="0,1,2"/></annots></xfdf>',
    "annot_bad_color": (
        f'{_OPEN}<annots><text page="0" rect="0,0,1,1" color="#zzzzzz"/>'
        "</annots></xfdf>"
    ),
}


def _field_cell(field: FDFField) -> str:
    kids = field.get_kids()
    value = field.get_value()
    return (
        f"{field.get_partial_field_name()}="
        f"{'null' if value is None else value}/{0 if kids is None else len(kids)}"
    )


def _fields_cell(fields: list[FDFField] | None) -> str:
    if not fields:
        return "-"
    values: list[str] = []
    for field in fields:
        values.append(_field_cell(field))
        for kid in field.get_kids() or []:
            values.append(">" + _field_cell(kid))
    return "|".join(values)


def _python_line(name: str, path: Path) -> str:
    try:
        with Loader.load_xfdf(path) as document:
            fdf = document.get_catalog().get_fdf()
            annotations = fdf.get_annotations()
            annotation_cell = (
                "-"
                if not annotations
                else "|".join(type(annotation).__name__ for annotation in annotations)
            )
            ids = fdf.get_id()
            return (
                f"CASE {name} OK fields={_fields_cell(fdf.get_fields())} "
                f"annots={annotation_cell} "
                f"file={'null' if fdf.get_file_path() is None else fdf.get_file_path()} "
                f"ids={0 if ids is None else ids.size()}\n"
            )
    except Exception:
        return f"CASE {name} ERR\n"


@requires_oracle
def test_xfdf_import_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    for name, xml in _CASES.items():
        (tmp_path / f"{name}.xfdf").write_text(xml, encoding="utf-8")
    (tmp_path / "manifest.txt").write_text("\n".join(_CASES) + "\n", encoding="utf-8")

    python = "".join(_python_line(name, tmp_path / f"{name}.xfdf") for name in _CASES)
    assert python == run_probe_text("XfdfImportFuzzProbe", str(tmp_path))
