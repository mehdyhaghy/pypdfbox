"""Live Apache PDFBox differential fuzz of the TYPED-ACCESSOR VALUES on the
standard attribute-object subclasses (Layout / List / Table / PrintField)
plus ``PDMarkedContent`` (wave 1548, agent E).

The wave-1531 sibling
(``tests/.../logicalstructure/oracle/test_attribute_object_fuzz_wave1531.py``)
fuzzed ``PDAttributeObject.create`` *dispatch* + ``get_owner`` / ``is_empty``
+ the generic ``PDDefaultAttributeObject`` key/value shape. This wave instead
feeds well-/mis-typed VALUES to each subclass's typed getters and pins what
they return on absent / wrong-type / out-of-range input:

  - Layout: ``get_placement`` / ``get_writing_mode`` (name defaults) +
    ``get_background_color`` (a colour value — Java ``PDGamma``) +
    ``get_border_style`` (a single name or a per-side name list).
  - List: ``get_list_numbering`` (default ``None``) on absent / name /
    string / wrong-type.
  - Table: ``get_row_span`` / ``get_col_span`` (default 1) / ``get_headers``
    / ``get_scope`` / ``get_summary`` on absent / wrong-type / mixed array.
  - PrintField: ``get_role`` / ``get_checked_state`` (default ``off``) on
    absent / name / string.
  - ``PDMarkedContent``: ``get_tag`` / ``get_mcid`` (default -1) /
    ``get_language`` / ``get_actual_text`` / ``get_alternate_description`` /
    ``get_expanded_form`` on a null tag, null properties, and properties
    with present / absent / wrong-type entries, plus the ``/Artifact``
    dispatch to ``PDArtifactMarkedContent``.

Strategy mirrors the wave-1531 sibling: build a deterministic corpus directly
as COS, embed attribute dicts in a ``/FuzzAttr`` COSArray and marked-content
cases in a ``/FuzzMC`` COSArray (each ``{Tag, Props}``) hung off the catalog,
save ONE ``corpus.pdf`` + a ``manifest.txt`` (``A:<name>`` / ``M:<name>``
lines, array order). ``AttributeAccessorFuzzProbe`` loads that pdf and
replays both arrays. Both libraries read the identical on-disk bytes.

Validation, not blind pinning: the Java line is ground truth. Each case
asserts pypdfbox produces the identical projected line; any defensible
divergence is pinned in ``_PINNED_DIVERGENCES`` with a matching CHANGES.md
row.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_layout_attribute_object import (
    PDLayoutAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_list_attribute_object import (
    PDListAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_print_field_attribute_object import (
    PDPrintFieldAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_table_attribute_object import (
    PDTableAttributeObject,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_O = COSName.get_pdf_name("O")


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _owner(owner: str, **entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_O, _n(owner))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _props(**entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _mc(tag: str | None, props: COSDictionary | None) -> COSDictionary:
    """A {Tag, Props} envelope slot for one PDMarkedContent case."""
    slot = COSDictionary()
    if tag is not None:
        slot.set_item(_n("Tag"), _n(tag))
    if props is not None:
        slot.set_item(_n("Props"), props)
    return slot


# --------------------------------------------------------------- corpus build


def _build_attr_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    # ---- Layout ----
    c["layout_empty"] = _owner("Layout")
    c["layout_placement"] = _owner("Layout", Placement=_n("Block"))
    c["layout_wmode"] = _owner("Layout", WritingMode=_n("RlTb"))
    c["layout_placement_wrongtype"] = _owner(
        "Layout", Placement=COSInteger.get(7)
    )
    c["layout_bg_rgb"] = _owner(
        "Layout",
        BackgroundColor=_arr(COSFloat(0.25), COSFloat(0.5), COSFloat(0.75)),
    )
    c["layout_bg_int"] = _owner(
        "Layout",
        BackgroundColor=_arr(
            COSInteger.get(0), COSInteger.get(1), COSInteger.get(0)
        ),
    )
    c["layout_bg_absent"] = _owner("Layout", Placement=_n("Block"))
    c["layout_borderstyle_name"] = _owner("Layout", BorderStyle=_n("Solid"))
    c["layout_borderstyle_arr"] = _owner(
        "Layout",
        BorderStyle=_arr(
            _n("Solid"), _n("Dashed"), _n("Solid"), _n("Dashed")
        ),
    )
    c["layout_borderstyle_absent"] = _owner("Layout")

    # ---- List ----
    c["list_empty"] = _owner("List")
    c["list_numbering"] = _owner("List", ListNumbering=_n("Decimal"))
    c["list_numbering_wrongtype"] = _owner(
        "List", ListNumbering=COSInteger.get(3)
    )
    c["list_numbering_string"] = _owner(
        "List", ListNumbering=COSString("Disc")
    )

    # ---- Table ----
    c["table_empty"] = _owner("Table")
    c["table_spans"] = _owner(
        "Table", RowSpan=COSInteger.get(3), ColSpan=COSInteger.get(2)
    )
    c["table_span_wrongtype"] = _owner("Table", RowSpan=_n("two"))
    c["table_headers"] = _owner(
        "Table", Headers=_arr(COSString("h1"), COSString("h2"))
    )
    c["table_headers_mixed"] = _owner(
        "Table",
        Headers=_arr(COSString("h1"), COSInteger.get(5), COSString("h3")),
    )
    c["table_headers_wrongtype"] = _owner("Table", Headers=COSString("nope"))
    c["table_scope"] = _owner("Table", Scope=_n("Row"))
    c["table_summary"] = _owner("Table", Summary=COSString("a table"))
    c["table_summary_wrongtype"] = _owner("Table", Summary=COSInteger.get(1))

    # ---- PrintField ----
    c["printfield_empty"] = _owner("PrintField")
    c["printfield_role_name"] = _owner("PrintField", Role=_n("rb"))
    c["printfield_role_string"] = _owner("PrintField", Role=COSString("cb"))
    c["printfield_checked_name"] = _owner(
        "PrintField", checked=_n("on")
    )
    c["printfield_checked_string"] = _owner(
        "PrintField", checked=COSString("neutral")
    )
    c["printfield_checked_wrongtype"] = _owner(
        "PrintField", checked=COSInteger.get(1)
    )

    return c


def _build_mc_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    c["mc_null_tag_null_props"] = _mc(None, None)
    c["mc_tag_no_props"] = _mc("P", None)
    c["mc_tag_empty_props"] = _mc("Span", _props())
    c["mc_mcid"] = _mc("P", _props(MCID=COSInteger.get(4)))
    c["mc_mcid_wrongtype"] = _mc("P", _props(MCID=_n("four")))
    c["mc_lang_name"] = _mc("P", _props(Lang=_n("en-US")))
    c["mc_lang_string"] = _mc("P", _props(Lang=COSString("de-DE")))
    c["mc_actual"] = _mc("P", _props(ActualText=COSString("hello")))
    c["mc_actual_wrongtype"] = _mc("P", _props(ActualText=_n("nope")))
    c["mc_alt"] = _mc("Figure", _props(Alt=COSString("a figure")))
    c["mc_expanded"] = _mc("Span", _props(E=COSString("Doctor")))
    c["mc_all"] = _mc(
        "P",
        _props(
            MCID=COSInteger.get(2),
            Lang=_n("fr"),
            ActualText=COSString("act"),
            Alt=COSString("alt"),
            E=COSString("exp"),
        ),
    )
    c["mc_artifact"] = _mc("Artifact", _props(MCID=COSInteger.get(9)))
    c["mc_artifact_null_props"] = _mc("Artifact", None)

    return c


# --------------------------------------------------------------- projection
#
# Mirrors AttributeAccessorFuzzProbe.java exactly: same field order, same
# null spelling, same float / array formatting.


def _java_float(value: float) -> str:
    """Render a float the way Java's ``Float.toString`` / string concat does
    for the finite values this corpus uses (``0.25`` -> ``"0.25"``,
    ``1.0`` -> ``"1.0"``)."""
    if value == int(value):
        return f"{int(value)}.0"
    return str(value)


def _gamma(rgb: object) -> str:
    if rgb is None:
        return "null"
    # pypdfbox get_background_color() returns a tuple of components; Java
    # returns a PDGamma whose getR/getG/getB are the first three floats.
    seq = list(rgb)  # type: ignore[arg-type]
    r, g, b = seq[0], seq[1], seq[2]
    return f"rgb({_java_float(r)},{_java_float(g)},{_java_float(b)})"


def _border_style(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return "S:" + value
    if isinstance(value, list):
        return "A:[" + ", ".join(str(v) for v in value) + "]"
    return "?:" + type(value).__name__


def _headers(values: list[str]) -> str:
    # Java getHeaders() returns String[]; absent -> the probe maps null.
    # pypdfbox returns [] for absent. We normalise: empty list -> "null" to
    # match the Java side's null-on-absent, non-empty -> Arrays.toString form.
    if not values:
        return "null"
    return "[" + ", ".join(values) + "]"


def _attr_proj(ao: PDAttributeObject) -> str:
    if isinstance(ao, PDLayoutAttributeObject) and not isinstance(
        ao, (PDListAttributeObject, PDTableAttributeObject)
    ):
        # PDExportFormat subclasses PDLayout, but this corpus never produces
        # one; the plain Layout cases land here.
        placement = ao.get_placement()
        wmode = ao.get_writing_mode()
        bg = ao.get_background_color()
        border = ao.get_border_style()
        return (
            f"placement={placement if placement is not None else 'null'}"
            f" writingMode={wmode if wmode is not None else 'null'}"
            f" bg={_gamma(bg)}"
            f" borderStyle={_border_style(border)}"
        )
    if isinstance(ao, PDListAttributeObject):
        ln = ao.get_list_numbering()
        return f"listNumbering={ln if ln is not None else 'null'}"
    if isinstance(ao, PDTableAttributeObject):
        scope = ao.get_scope()
        summary = ao.get_summary()
        return (
            f"rowSpan={ao.get_row_span()}"
            f" colSpan={ao.get_col_span()}"
            f" headers={_headers(ao.get_headers())}"
            f" scope={scope if scope is not None else 'null'}"
            f" summary={summary if summary is not None else 'null'}"
        )
    if isinstance(ao, PDPrintFieldAttributeObject):
        role = ao.get_role()
        checked = ao.get_checked_state()
        return (
            f"role={role if role is not None else 'null'}"
            f" checked={checked if checked is not None else 'null'}"
        )
    return f"cls={type(ao).__name__}"


def _py_attr_line(name: str, d: COSDictionary) -> str:
    try:
        ao = PDAttributeObject.create(d)
        return f"ATTR {name} cls={type(ao).__name__} {_attr_proj(ao)}"
    except Exception as exc:  # noqa: BLE001 - contract probe; any failure counts
        return f"ATTR {name} ERR:{type(exc).__name__}"


def _py_mc_line(name: str, slot: COSDictionary) -> str:
    tag_base = slot.get_dictionary_object(_n("Tag"))
    tag = tag_base if isinstance(tag_base, COSName) else None
    props_base = slot.get_dictionary_object(_n("Props"))
    props = props_base if isinstance(props_base, COSDictionary) else None
    try:
        mc = PDMarkedContent.create(tag, props)
        tag_v = mc.get_tag()
        lang = mc.get_language()
        actual = mc.get_actual_text()
        alt = mc.get_alternate_description()
        exp = mc.get_expanded_form()
        return (
            f"MC {name} cls={type(mc).__name__}"
            f" tag={tag_v if tag_v is not None else 'null'}"
            f" mcid={mc.get_mcid()}"
            f" lang={lang if lang is not None else 'null'}"
            f" actual={actual if actual is not None else 'null'}"
            f" alt={alt if alt is not None else 'null'}"
            f" exp={exp if exp is not None else 'null'}"
        )
    except Exception as exc:  # noqa: BLE001 - contract probe; any failure counts
        return f"MC {name} ERR:{type(exc).__name__}"


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(
    dir_path: Path,
    attr: dict[str, COSDictionary],
    mc: dict[str, COSDictionary],
) -> list[str]:
    """Write corpus.pdf + manifest.txt, returning the manifest order."""
    doc = PDDocument()
    manifest: list[str] = []
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        attr_arr = COSArray()
        for d in attr.values():
            attr_arr.add(d)
        catalog.set_item(_n("FuzzAttr"), attr_arr)
        mc_arr = COSArray()
        for slot in mc.values():
            mc_arr.add(slot)
        catalog.set_item(_n("FuzzMC"), mc_arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    for name in attr:
        manifest.append(f"A:{name}")
    for name in mc:
        manifest.append(f"M:{name}")
    (dir_path / "manifest.txt").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8"
    )
    return manifest


# Module-level keep-alive so a reloaded document isn't garbage-collected
# before projection reads its shapes.
_doc_keepalive: list[object] = []


def _reload_corpus(
    dir_path: Path, attr_order: list[str], mc_order: list[str]
) -> tuple[dict[str, COSDictionary], dict[str, COSDictionary]]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    catalog = doc.get_document_catalog().get_cos_object()
    attr_arr = catalog.get_dictionary_object(_n("FuzzAttr"))
    mc_arr = catalog.get_dictionary_object(_n("FuzzMC"))
    attr_out: dict[str, COSDictionary] = {}
    for i, name in enumerate(attr_order):
        entry = attr_arr.get_object(i)
        assert isinstance(entry, COSDictionary)
        attr_out[name] = entry
    mc_out: dict[str, COSDictionary] = {}
    for i, name in enumerate(mc_order):
        entry = mc_arr.get_object(i)
        assert isinstance(entry, COSDictionary)
        mc_out[name] = entry
    return attr_out, mc_out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java line.
#
# table_headers / table_headers_mixed: upstream PDFBox 3.0.7 has a
# round-trip-broken /Headers accessor — setHeaders() writes COSString
# elements (PDStandardAttributeObject.setArrayOfString), but getHeaders()
# reads them back via getArrayOfString which unconditionally casts every
# element to COSName. A COSString-valued /Headers array (the only kind the
# matching setter can produce) therefore throws ClassCastException on EVERY
# read. pypdfbox.get_headers tolerantly decodes COSString entries (and
# silently drops non-string junk), so a round-tripped /Headers reads back
# cleanly. We pin the divergence rather than reproduce a guaranteed-crash
# getter: matching the Java exception would make pypdfbox strictly worse and
# break its own setter/getter round trip. See CHANGES.md (wave 1548).
_PINNED_DIVERGENCES: dict[str, str] = {
    "table_headers": (
        "ATTR table_headers cls=PDTableAttributeObject "
        "rowSpan=1 colSpan=1 headers=[h1, h2] scope=null summary=null"
    ),
    "table_headers_mixed": (
        "ATTR table_headers_mixed cls=PDTableAttributeObject "
        "rowSpan=1 colSpan=1 headers=[h1, h3] scope=null summary=null"
    ),
}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_attribute_accessor_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every typed-accessor / marked-content case projects identically on
    pypdfbox and Apache PDFBox 3.0.7, reading the same on-disk bytes."""
    attr = _build_attr_corpus()
    mc = _build_mc_corpus()
    _write_corpus_pdf(tmp_path, attr, mc)

    raw = run_probe_text("AttributeAccessorFuzzProbe", str(tmp_path))
    java_lines = [
        ln for ln in raw.splitlines() if ln.startswith(("ATTR ", "MC "))
    ]
    total = len(attr) + len(mc)
    assert len(java_lines) == total, (
        f"probe emitted {len(java_lines)} lines for {total} cases:\n{raw}"
    )

    attr_reloaded, mc_reloaded = _reload_corpus(
        tmp_path, list(attr), list(mc)
    )
    py_by_name: dict[str, str] = {}
    for name, d in attr_reloaded.items():
        py_by_name[f"ATTR {name}"] = _py_attr_line(name, d)
    for name, slot in mc_reloaded.items():
        py_by_name[f"MC {name}"] = _py_mc_line(name, slot)

    mismatches: list[str] = []
    for jline in java_lines:
        kind, name, _ = jline.split(" ", 2)
        key = f"{kind} {name}"
        pline = py_by_name[key]
        if name in _PINNED_DIVERGENCES:
            if pline != _PINNED_DIVERGENCES[name]:
                mismatches.append(
                    f"{name}: PINNED py expected "
                    f"{_PINNED_DIVERGENCES[name]!r} got {pline!r} "
                    f"(java {jline!r})"
                )
            continue
        if pline != jline:
            mismatches.append(f"{name}:\n  py   {pline}\n  java {jline}")

    assert not mismatches, (
        "attribute-accessor / marked-content divergence(s):\n"
        + "\n".join(mismatches)
    )
