"""Live PDFBox differential fuzz for binary FDF parsing (wave 1519)."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.loader import Loader
from pypdfbox.pdmodel.fdf import FDFDocument, FDFField
from tests.oracle.harness import requires_oracle, run_probe_text


def _valid_fdf(path: Path) -> bytes:
    with FDFDocument() as document:
        field = FDFField()
        field.set_partial_field_name("alpha")
        field.set_value("one")
        document.get_catalog().get_fdf().set_fields([field])
        document.save(path)
    return path.read_bytes()


def _cases(base: bytes) -> dict[str, bytes]:
    return {
        "valid": base,
        "pdf_header": base.replace(b"%FDF-", b"%PDF-", 1),
        "bad_header": base.replace(b"%FDF-", b"%XYZ-", 1),
        "bad_version": base.replace(b"%FDF-1.2", b"%FDF-x.y", 1),
        "missing_root": base.replace(b"/Root", b"/R00t", 1),
        "missing_fdf": base.replace(b"/FDF", b"/FDX", 1),
        "bad_xref": base.replace(b"xref", b"xreF", 1),
        "bad_trailer": base.replace(b"trailer", b"trailEr", 1),
        "bad_startxref": base.replace(b"startxref", b"startXref", 1),
        "bad_eof": base.replace(b"%%EOF", b"%%EOX", 1),
        "truncated": base[:-20],
        "trailing_garbage": base + b"garbage\x00\xff",
    }


def _python_line(name: str, path: Path) -> str:
    try:
        with Loader.load_fdf(path) as document:
            fields = document.get_catalog().get_fdf().get_fields()
            count = -1 if fields is None else len(fields)
            version = document.get_document().get_version()
            return f"CASE {name} OK version={version} fields={count}\n"
    except Exception:
        return f"CASE {name} ERR\n"


@requires_oracle
def test_fdf_parser_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    base = _valid_fdf(tmp_path / "seed.fdf")
    cases = _cases(base)
    for name, data in cases.items():
        (tmp_path / f"{name}.fdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text("\n".join(cases) + "\n", encoding="utf-8")

    python = "".join(_python_line(name, tmp_path / f"{name}.fdf") for name in cases)
    assert python == run_probe_text("FdfParserFuzzProbe", str(tmp_path))
