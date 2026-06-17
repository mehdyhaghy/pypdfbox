"""Live Apache PDFBox differential fuzz of
``PDAttributeObject.create(COSDictionary)`` dispatch + the ``get_owner`` /
``is_empty`` surface and ``PDDefaultAttributeObject`` generic key/value
access (wave 1531, agent D).

The factory dispatches on ``getNameAsString(/O)`` — which resolves a ``/O``
stored as either a ``COSName`` OR a ``COSString`` — to a typed subclass
(Layout / List / PrintField / Table / ExportFormat (XML-1.00 / HTML-3.2 /
HTML-4.01 / OEB-1.00 / RTF-1.05 / CSS-1.00 / CSS-2.00) / UserProperties)
and otherwise falls back to ``PDDefaultAttributeObject``. This probe
targets the MALFORMED / edge-case subset a buggy or hostile producer can
emit:

  - ``/O`` missing / unknown / empty.
  - ``/O`` wrong type: int / array / dict / bool / real (``getNameAsString``
    returns null → default wrapper).
  - ``/O`` as a *name* vs a *string* for every known owner value (a
    string-valued ``/O`` must still route to its typed subclass — upstream
    uses ``getNameAsString``, not ``getName``).
  - empty dict (no ``/O``).
  - ``/O`` reachable through an indirect reference.
  - for the default wrapper: generic attribute access (names + value COS
    shapes) for present vs absent keys, including nested dict/array values.

Strategy mirrors the action-factory fuzz sibling: build the deterministic
corpus directly as COS, embed each dict as an entry of a non-standard
``/FuzzAttrObjs`` COSArray hung off the document catalog, save ONE
``corpus.pdf`` + a ``manifest.txt`` (one case name per line, array order).
``AttributeObjectFuzzProbe`` loads that pdf, walks the array, feeds each raw
COSDictionary to ``PDAttributeObject.create`` and projects a stable line.
Both libraries read the exact same bytes on disk, so the dispatch contract
is directly comparable.

Validation, not blind pinning: the Java line is ground truth. Each case
asserts pypdfbox produces the identical
``class=<simpleName> owner=<getOwner> empty=<bool> attrs=<proj>`` line. A
real dispatch bug is fixed in production (this wave fixed create()/get_owner
to use ``get_name_as_string`` so a string-valued ``/O`` dispatches and
resolves like upstream); any defensible divergence is pinned in
``_PINNED_DIVERGENCES`` with a matching CHANGES.md row.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_default_attribute_object import (
    PDDefaultAttributeObject,
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


def _dict(**entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _owner_name(owner: str, **entries: COSBase) -> COSDictionary:
    """Attribute dict whose ``/O`` is a COSName."""
    d = COSDictionary()
    d.set_item(_O, _n(owner))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _owner_str(owner: str, **entries: COSBase) -> COSDictionary:
    """Attribute dict whose ``/O`` is a COSString (mistyped owner)."""
    d = COSDictionary()
    d.set_item(_O, COSString(owner))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    """Deterministic, ordered attribute-dictionary corpus."""
    c: dict[str, COSDictionary] = {}

    # ----- /O dispatch: known owners as a name -----
    c["o_layout"] = _owner_name("Layout", Placement=_n("Block"))
    c["o_list"] = _owner_name("List", ListNumbering=_n("Decimal"))
    c["o_printfield"] = _owner_name("PrintField", Role=_n("rb"))
    c["o_table"] = _owner_name("Table", RowSpan=COSInteger.get(2))
    c["o_xml100"] = _owner_name("XML-1.00")
    c["o_html32"] = _owner_name("HTML-3.2")
    c["o_html401"] = _owner_name("HTML-4.01")
    c["o_oeb100"] = _owner_name("OEB-1.00")
    c["o_rtf105"] = _owner_name("RTF-1.05")
    c["o_css100"] = _owner_name("CSS-1.00")
    c["o_css200"] = _owner_name("CSS-2.00")
    c["o_userprops"] = _owner_name("UserProperties")

    # ----- /O dispatch: known owners as a *string* (still must dispatch) -----
    c["o_layout_str"] = _owner_str("Layout", Placement=_n("Block"))
    c["o_list_str"] = _owner_str("List")
    c["o_table_str"] = _owner_str("Table")
    c["o_xml100_str"] = _owner_str("XML-1.00")
    c["o_userprops_str"] = _owner_str("UserProperties")

    # ----- /O unknown / missing / empty -----
    c["o_unknown"] = _owner_name("Bogus", Foo=COSInteger.get(1))
    c["o_unknown_str"] = _owner_str("Bogus", Foo=COSInteger.get(1))
    c["o_empty_name"] = _owner_name("")
    c["o_missing"] = _dict(Foo=COSInteger.get(9))
    c["o_empty_dict"] = COSDictionary()

    # ----- /O wrong type (getNameAsString → null → default wrapper) -----
    c["o_int"] = _dict(O=COSInteger.get(5))
    c["o_real"] = _dict(O=COSFloat(1.5))
    c["o_bool"] = _dict(O=COSBoolean.TRUE)
    c["o_array"] = _dict(O=_arr(_n("Layout")))
    c["o_dict"] = _dict(O=COSDictionary())

    # ----- /O case sensitivity (owner match is case-sensitive) -----
    c["o_layout_lower"] = _owner_name("layout")
    c["o_html_typo"] = _owner_name("HTML-3.20")  # upstream is HTML-3.2

    # ----- default wrapper: generic attribute access -----
    c["dflt_only_owner"] = _owner_name("Bogus")
    c["dflt_mixed"] = _owner_name(
        "Bogus", Name=_n("v"), Str=COSString("s"), Num=COSInteger.get(3)
    )
    c["dflt_nested_dict"] = _owner_name(
        "Bogus", Inner=_dict(K=COSInteger.get(1))
    )
    c["dflt_nested_array"] = _owner_name(
        "Bogus", Cols=_arr(COSInteger.get(1), COSInteger.get(2))
    )
    c["dflt_bool_real"] = _owner_name(
        "Bogus", Flag=COSBoolean.FALSE, F=COSFloat(2.25)
    )
    # default wrapper reached via a string owner too
    c["dflt_str_owner"] = _owner_str("Bogus", Attr=COSString("x"))

    return c


# --------------------------------------------------------------- projection
#
# Mirrors AttributeObjectFuzzProbe.java exactly: same shape vocabulary, same
# dictionary-order attribute projection, same comma joining.


def _shape(b: COSBase | None) -> str:
    if b is None:
        return "null"
    if isinstance(b, COSStream):
        return "stream"
    if isinstance(b, COSDictionary):
        return "dict"
    if isinstance(b, COSArray):
        return "arr" + str(b.size())
    if isinstance(b, COSName):
        return "name"
    if isinstance(b, COSString):
        return "str"
    if isinstance(b, COSInteger):
        return "int"
    if isinstance(b, COSFloat):
        return "real"
    if isinstance(b, COSBoolean):
        return "bool"
    return "other"


def _attrs_proj(ao: PDAttributeObject) -> str:
    if not isinstance(ao, PDDefaultAttributeObject):
        return "-"
    cos = ao.get_cos_object()
    parts: list[str] = []
    for key in cos.key_set():
        if key == _O:
            continue
        parts.append(
            key.get_name() + ":" + _shape(ao.get_attribute_value(key.get_name()))
        )
    if not parts:
        return "{}"
    return ",".join(parts)


def _py_line(name: str, d: COSDictionary) -> str:
    try:
        ao = PDAttributeObject.create(d)
        cls = type(ao).__name__
        owner = ao.get_owner()
        owner_disp = owner if owner is not None else "null"
        empty = ao.is_empty()
        empty_disp = "true" if empty else "false"
        attrs = _attrs_proj(ao)
        return (
            f"CASE {name} class={cls} owner={owner_disp} "
            f"empty={empty_disp} attrs={attrs}"
        )
    except Exception as exc:  # noqa: BLE001 - contract probe; any failure counts
        return (
            f"CASE {name} class=ERR:{type(exc).__name__} "
            f"owner=ERR empty=ERR attrs=ERR"
        )


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(dir_path: Path, corpus: dict[str, COSDictionary]) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        arr = COSArray()
        for d in corpus.values():
            arr.add(d)
        catalog.set_item(_n("FuzzAttrObjs"), arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    (dir_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )


# Module-level keep-alive so a reloaded document isn't garbage-collected
# before projection reads its shapes.
_doc_keepalive: list[object] = []


def _reload_corpus(
    dir_path: Path, order: list[str]
) -> dict[str, COSDictionary]:
    """Reload corpus.pdf and pull each /FuzzAttrObjs slot as a COSDictionary,
    so both sides parse the identical on-disk bytes (not the in-memory COS)."""
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    out: dict[str, COSDictionary] = {}
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n("FuzzAttrObjs"))
    for i, name in enumerate(order):
        entry = arr.get_object(i)
        assert isinstance(entry, COSDictionary)
        out[name] = entry
    return out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java line. Empty: the live
# oracle surfaces no defensible difference after the create()/get_owner fix.
_PINNED_DIVERGENCES: dict[str, str] = {}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_attribute_object_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed / edge-case attribute dict dispatches + projects
    identically on pypdfbox ``PDAttributeObject.create`` and Apache PDFBox
    3.0.7 ``PDAttributeObject.create``, reading the same on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("AttributeObjectFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )

    reloaded = _reload_corpus(tmp_path, list(corpus))
    py_by_name = {name: _py_line(name, d) for name, d in reloaded.items()}

    mismatches: list[str] = []
    for jline in java_lines:
        name = jline.split(" ", 2)[1]
        pline = py_by_name[name]
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
        "attribute-object dispatch divergence(s):\n" + "\n".join(mismatches)
    )
