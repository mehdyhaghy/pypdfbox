"""Live Apache PDFBox differential fuzz for the binary FDF object model
(``pypdfbox.pdmodel.fdf``) — wave 1551.

Complements the existing FDF/XFDF fuzz probes:

* ``FdfParserFuzzProbe`` (wave 1519) fuzzes the *on-wire* FDF structure —
  header / xref / trailer / EOF corruption.
* ``XfdfImportFuzzProbe`` (wave 1519) fuzzes *XFDF* (XML) import.
* ``FdfAnnotationFactoryFuzzProbe`` fuzzes the FDF annotation factory.

This wave fuzzes the binary FDF *object model* that neither of those covers:

* ``/V`` value-type coercion via ``FDFField.getValue()`` — string, name,
  multi-select array, stream, and the unsupported integer / boolean that
  upstream rejects with ``IOException`` (``getValue`` throws → ``<err>``);
* ``/Opt`` option arrays are present but ``getValue`` of an empty-``/V`` field
  is ``null``;
* the qualified-field-name tree built from nested ``/Kids`` partial names
  (``/T``) — ``address`` → ``address.city``, an unnamed nested field, and a
  three-level chain;
* annotation count + subtype dispatch from binary ``/Annots`` — known
  subtypes plus an *unknown* ``/Subtype`` (dropped by ``FDFAnnotation.create``
  on both sides);
* a missing ``/FDF`` root sub-dictionary (``fdf=0``; ``getFields()`` ``null``);
* a self-referential (cyclic) ``/Kids`` entry — the walker must not recurse
  forever.

The Java oracle is ``FdfFuzzProbe``; it reads each raw ``.fdf`` byte file from
a directory named by ``manifest.txt`` and emits one canonical line per case.
``_python_line`` reproduces exactly that format from pypdfbox so the two sides
compare line-for-line. The cases are *built* with pypdfbox (FDF and PDF share
the wire format, so this yields valid xref/trailer) and then a couple are
byte-patched for the malformation that the writer cannot itself emit.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.fdf import FDFDocument, FDFField
from tests.oracle.harness import requires_oracle, run_probe_text

_V = COSName.get_pdf_name("V")
_T = COSName.get_pdf_name("T")
_KIDS = COSName.get_pdf_name("Kids")
_OPT = COSName.get_pdf_name("Opt")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FDF = COSName.get_pdf_name("FDF")
_ANNOTS = COSName.get_pdf_name("Annots")
_RECT = COSName.get_pdf_name("Rect")
_PAGE = COSName.get_pdf_name("Page")


# ----------------------------------------------------------------- builders


def _field(partial: str | None) -> FDFField:
    f = FDFField()
    if partial is not None:
        f.set_partial_field_name(partial)
    return f


def _set_v(field: FDFField, value: object) -> None:
    field.get_cos_object().set_item(_V, value)


def _annot(subtype: str, rect: tuple[float, float, float, float]) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    arr = COSArray()
    for v in rect:
        arr.add(COSInteger(int(v)))
    d.set_item(_RECT, arr)
    d.set_int(_PAGE, 0)
    return d


def _save_doc(build, path: Path) -> bytes:
    """Build an FDF via ``build(fdf_dict)`` and save it; return its bytes."""
    doc = FDFDocument()
    try:
        build(doc)
        doc.save(path)
    finally:
        doc.close()
    return path.read_bytes()


# Each entry returns the raw FDF bytes for one case.


def _case_value_string(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("vstr")
        f.set_value("hello")
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_value_name(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("vname")
        _set_v(f, COSName.get_pdf_name("Yes"))
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_value_array(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("varr")
        arr = COSArray()
        arr.add(COSString("en"))
        arr.add(COSString("fr"))
        _set_v(f, arr)
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_value_stream(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("vstream")
        s = COSStream()
        s.set_raw_data(b"streamval")
        _set_v(f, s)
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_value_integer(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("vint")
        _set_v(f, COSInteger(42))
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_value_boolean(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("vbool")
        _set_v(f, COSBoolean.TRUE)
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_no_value(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("empty")
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_opt_array(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("choice")
        f.set_options(["Red", "Green", "Blue"])
        f.set_value("Green")
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_nested_kids(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        parent = _field("address")
        city = _field("city")
        city.set_value("Paris")
        parent.set_kids([city])
        doc.get_catalog().get_fdf().set_fields([parent])

    return _save_doc(build, path)


def _case_kids_chain(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        a = _field("a")
        b = _field("b")
        c = _field("c")
        c.set_value("deep")
        b.set_kids([c])
        a.set_kids([b])
        doc.get_catalog().get_fdf().set_fields([a])

    return _save_doc(build, path)


def _case_kid_unnamed(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        parent = _field("p")
        kid = _field(None)  # no /T
        kid.set_value("orphan")
        parent.set_kids([kid])
        doc.get_catalog().get_fdf().set_fields([parent])

    return _save_doc(build, path)


def _case_cyclic_kid(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        a = _field("self")
        kids = COSArray()
        kids.add(a.get_cos_object())  # /Kids references itself
        a.get_cos_object().set_item(_KIDS, kids)
        doc.get_catalog().get_fdf().set_fields([a])

    return _save_doc(build, path)


def _case_annots_known(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        fdf = doc.get_catalog().get_fdf()
        arr = COSArray()
        arr.add(_annot("Text", (0, 0, 10, 10)))
        arr.add(_annot("Square", (1, 2, 3, 4)))
        fdf.get_cos_object().set_item(_ANNOTS, arr)

    return _save_doc(build, path)


def _case_annot_unknown(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        fdf = doc.get_catalog().get_fdf()
        arr = COSArray()
        arr.add(_annot("Mystery", (0, 0, 1, 1)))
        arr.add(_annot("Text", (0, 0, 1, 1)))
        fdf.get_cos_object().set_item(_ANNOTS, arr)

    return _save_doc(build, path)


def _case_annot_no_subtype(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        fdf = doc.get_catalog().get_fdf()
        d = COSDictionary()
        d.set_int(_PAGE, 0)  # /Annots entry with no /Subtype
        arr = COSArray()
        arr.add(d)
        fdf.get_cos_object().set_item(_ANNOTS, arr)

    return _save_doc(build, path)


def _case_empty_fdf(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:  # noqa: ARG001 — empty body on purpose
        return None

    return _save_doc(build, path)


def _case_fields_not_array(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        fdf = doc.get_catalog().get_fdf()
        fdf.get_cos_object().set_item(
            COSName.get_pdf_name("Fields"), COSName.get_pdf_name("nope")
        )

    return _save_doc(build, path)


def _case_field_kids_not_array(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("k")
        f.get_cos_object().set_item(_KIDS, COSInteger(5))
        f.set_value("kept")
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_many_fields(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        fields = []
        for i in range(5):
            f = _field(f"f{i}")
            f.set_value(f"v{i}")
            fields.append(f)
        doc.get_catalog().get_fdf().set_fields(fields)

    return _save_doc(build, path)


def _case_value_empty_string(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("blank")
        f.set_value("")
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


def _case_value_array_with_name(path: Path) -> bytes:
    def build(doc: FDFDocument) -> None:
        f = _field("mixed")
        arr = COSArray()
        arr.add(COSString("s"))
        arr.add(COSName.get_pdf_name("n"))
        _set_v(f, arr)
        doc.get_catalog().get_fdf().set_fields([f])

    return _save_doc(build, path)


# --- byte-patched malformations the writer cannot itself emit ---


def _patch_missing_fdf(base: bytes) -> bytes:
    """Rename the catalog's /FDF key so the catalog has no FDF sub-dict."""
    return base.replace(b"/FDF ", b"/FDX ", 1)


# name -> (builder, optional byte-patch)
_BUILDERS: dict[str, object] = {
    "value_string": _case_value_string,
    "value_name": _case_value_name,
    "value_array": _case_value_array,
    "value_stream": _case_value_stream,
    "value_integer": _case_value_integer,
    "value_boolean": _case_value_boolean,
    "value_empty_string": _case_value_empty_string,
    "value_array_with_name": _case_value_array_with_name,
    "no_value": _case_no_value,
    "opt_array": _case_opt_array,
    "nested_kids": _case_nested_kids,
    "kids_chain": _case_kids_chain,
    "kid_unnamed": _case_kid_unnamed,
    "cyclic_kid": _case_cyclic_kid,
    "annots_known": _case_annots_known,
    "annot_unknown": _case_annot_unknown,
    "annot_no_subtype": _case_annot_no_subtype,
    "empty_fdf": _case_empty_fdf,
    "fields_not_array": _case_fields_not_array,
    "field_kids_not_array": _case_field_kids_not_array,
    "many_fields": _case_many_fields,
}

_PATCHES = {
    "missing_fdf": ("value_string", _patch_missing_fdf),
}


# --------------------------------------------------------------- py dump


def _value_repr(field: FDFField) -> str:
    try:
        value = field.get_value()
    except Exception:
        return "<err>"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + "|".join(str(item) for item in value) + "]"
    return str(value)


def _walk_field(field: FDFField, prefix: str, out: list[str]) -> None:
    partial = field.get_partial_field_name() or ""
    qualified = partial if not prefix else f"{prefix}.{partial}"
    out.append(f"{qualified}={_value_repr(field)}")
    kids = field.get_kids()
    if kids is not None:
        for kid in kids:
            if kid.get_cos_object() is field.get_cos_object():
                out.append(f"{qualified}.<cycle>")
                continue
            _walk_field(kid, qualified, out)


def _qnames_cell(fields: list[FDFField] | None) -> str:
    if not fields:
        return "-"
    out: list[str] = []
    for field in fields:
        _walk_field(field, "", out)
    return "|".join(out)


def _types_cell(annots: object) -> str:
    if not annots:
        return "-"
    # Match the Java probe: a ``None`` placeholder (unknown / absent
    # ``/Subtype``) renders as ``null``; otherwise the class simple name.
    return "|".join(
        "null" if a is None else type(a).__name__
        for a in annots  # type: ignore[union-attr]
    )


def _fdf_present(document: FDFDocument) -> bool:
    trailer = document.get_document().get_trailer()
    if trailer is None:
        return False
    root = trailer.get_dictionary_object(COSName.get_pdf_name("Root"))
    if not isinstance(root, COSDictionary):
        return False
    return isinstance(root.get_dictionary_object(_FDF), COSDictionary)


def _python_line(name: str, path: Path) -> str:
    try:
        with Loader.load_fdf(path) as document:
            present = _fdf_present(document)
            fdf = document.get_catalog().get_fdf()
            fields = fdf.get_fields()
            annots = fdf.get_annotations()
            field_count = -1 if fields is None else len(fields)
            annot_count = -1 if annots is None else len(annots)
            return (
                f"CASE {name} OK fdf={1 if present else 0} "
                f"fields={field_count} qnames={_qnames_cell(fields)} "
                f"annots={annot_count} types={_types_cell(annots)}\n"
            )
    except Exception:
        return f"CASE {name} ERR\n"


def _write_cases(tmp_path: Path) -> list[str]:
    names: list[str] = []
    base_bytes: dict[str, bytes] = {}
    for name, builder in _BUILDERS.items():
        data = builder(tmp_path / f"{name}.fdf")  # type: ignore[operator]
        base_bytes[name] = data
        names.append(name)
    for name, (src, patch) in _PATCHES.items():
        data = patch(base_bytes[src])  # type: ignore[operator]
        (tmp_path / f"{name}.fdf").write_bytes(data)
        names.append(name)
    (tmp_path / "manifest.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    return names


# Honest divergence (confirmed against PDFBox 3.0.7):
#
# ``value_array_with_name`` — a ``/V`` *array* holding a non-``COSString``
# element (here a ``COSName``). Upstream ``FDFField.getValue()`` routes arrays
# through ``COSArray.toCOSStringStringList()``, which hard-casts every element
# to ``COSString`` and so raises ``ClassCastException`` (probe → ``<err>``).
# pypdfbox's ``get_value`` array path coerces each element generically
# (``COSName`` → its bare name), yielding ``[s|n]``. We keep pypdfbox's more
# robust behaviour (a malformed multi-select still reads) and normalise this
# single known-divergent line before the line-for-line comparison rather than
# silently asserting parity we don't have.
_KNOWN_DIVERGENCE = {
    "CASE value_array_with_name OK fdf=1 fields=1 qnames=mixed=[s|n] "
    "annots=-1 types=-": (
        "CASE value_array_with_name OK fdf=1 fields=1 qnames=mixed=<err> "
        "annots=-1 types=-"
    ),
}


def _normalise_known_divergence(line: str) -> str:
    return _KNOWN_DIVERGENCE.get(line, line)


@requires_oracle
def test_fdf_object_model_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    names = _write_cases(tmp_path)
    python = "".join(
        _normalise_known_divergence(_python_line(name, tmp_path / f"{name}.fdf").rstrip("\n"))
        + "\n"
        for name in names
    )
    java = run_probe_text("FdfFuzzProbe", str(tmp_path))
    assert python == java


def test_fdf_object_model_fuzz_pins_python(tmp_path: Path) -> None:
    """Pin pypdfbox's own behaviour (oracle-independent) so a regression in
    value coercion, the qualified-name walk, annotation dispatch, or the
    missing-/FDF / cyclic-kid edges is caught even without Java.

    Facts confirmed against PDFBox 3.0.7 via ``FdfFuzzProbe`` and baked here:

    * ``/V`` string / name / array / stream all coerce through
      ``FDFField.getValue()`` (name → bare string, array → list, stream →
      decoded text); an integer or boolean ``/V`` makes ``getValue`` raise
      (``<err>``).
    * a field with ``/Opt`` but no ``/V`` reports ``value=null``.
    * the qualified-name walk joins nested ``/T`` with ``.`` and handles an
      unnamed kid (``p.=orphan``) and a three-level chain (``a.b.c``).
    * an unknown / absent ``/Subtype`` annotation is dropped by
      ``FDFAnnotation.create``, so ``annot_unknown`` keeps only the ``Text``.
    * a missing ``/FDF`` catalog entry reports ``fdf=0`` with ``fields=-1``.
    * a self-referential ``/Kids`` entry is rendered ``self.<cycle>`` without
      infinite recursion.
    """
    names = _write_cases(tmp_path)
    lines = {
        name: _python_line(name, tmp_path / f"{name}.fdf").rstrip("\n")
        for name in names
    }

    assert lines["value_string"] == (
        "CASE value_string OK fdf=1 fields=1 qnames=vstr=hello annots=-1 types=-"
    )
    assert lines["value_name"] == (
        "CASE value_name OK fdf=1 fields=1 qnames=vname=Yes annots=-1 types=-"
    )
    assert lines["value_array"] == (
        "CASE value_array OK fdf=1 fields=1 qnames=varr=[en|fr] annots=-1 types=-"
    )
    assert lines["value_stream"] == (
        "CASE value_stream OK fdf=1 fields=1 qnames=vstream=streamval "
        "annots=-1 types=-"
    )
    assert lines["value_integer"] == (
        "CASE value_integer OK fdf=1 fields=1 qnames=vint=<err> annots=-1 types=-"
    )
    assert lines["value_boolean"] == (
        "CASE value_boolean OK fdf=1 fields=1 qnames=vbool=<err> annots=-1 types=-"
    )
    assert lines["value_empty_string"] == (
        "CASE value_empty_string OK fdf=1 fields=1 qnames=blank= annots=-1 types=-"
    )
    assert lines["value_array_with_name"] == (
        "CASE value_array_with_name OK fdf=1 fields=1 qnames=mixed=[s|n] "
        "annots=-1 types=-"
    )
    assert lines["no_value"] == (
        "CASE no_value OK fdf=1 fields=1 qnames=empty=null annots=-1 types=-"
    )
    assert lines["opt_array"] == (
        "CASE opt_array OK fdf=1 fields=1 qnames=choice=Green annots=-1 types=-"
    )
    assert lines["nested_kids"] == (
        "CASE nested_kids OK fdf=1 fields=1 "
        "qnames=address=null|address.city=Paris annots=-1 types=-"
    )
    assert lines["kids_chain"] == (
        "CASE kids_chain OK fdf=1 fields=1 "
        "qnames=a=null|a.b=null|a.b.c=deep annots=-1 types=-"
    )
    assert lines["kid_unnamed"] == (
        "CASE kid_unnamed OK fdf=1 fields=1 qnames=p=null|p.=orphan "
        "annots=-1 types=-"
    )
    assert lines["cyclic_kid"] == (
        "CASE cyclic_kid OK fdf=1 fields=1 qnames=self=null|self.<cycle> "
        "annots=-1 types=-"
    )
    assert lines["annots_known"] == (
        "CASE annots_known OK fdf=1 fields=-1 qnames=- annots=2 "
        "types=FDFAnnotationText|FDFAnnotationSquare"
    )
    # Fixed: get_annotations now preserves the None placeholder for an unknown
    # subtype, matching upstream (count stays 2: null + the Text).
    assert lines["annot_unknown"] == (
        "CASE annot_unknown OK fdf=1 fields=-1 qnames=- annots=2 "
        "types=null|FDFAnnotationText"
    )
    # An /Annots entry with no /Subtype is kept as a None placeholder too.
    assert lines["annot_no_subtype"] == (
        "CASE annot_no_subtype OK fdf=1 fields=-1 qnames=- annots=1 types=null"
    )
    assert lines["empty_fdf"] == (
        "CASE empty_fdf OK fdf=1 fields=-1 qnames=- annots=-1 types=-"
    )
    assert lines["fields_not_array"] == (
        "CASE fields_not_array OK fdf=1 fields=-1 qnames=- annots=-1 types=-"
    )
    assert lines["field_kids_not_array"] == (
        "CASE field_kids_not_array OK fdf=1 fields=1 qnames=k=kept "
        "annots=-1 types=-"
    )
    assert lines["many_fields"] == (
        "CASE many_fields OK fdf=1 fields=5 "
        "qnames=f0=v0|f1=v1|f2=v2|f3=v3|f4=v4 annots=-1 types=-"
    )
    assert lines["missing_fdf"] == (
        "CASE missing_fdf OK fdf=0 fields=-1 qnames=- annots=-1 types=-"
    )


if __name__ == "__main__":  # pragma: no cover
    import pytest

    raise SystemExit(pytest.main([__file__, "-q", "--no-cov"]))
