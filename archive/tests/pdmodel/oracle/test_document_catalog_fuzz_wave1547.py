"""In-memory differential fuzz audit for :class:`PDDocumentCatalog` accessors
vs Apache PDFBox 3.0.7 (wave 1547, agent B).

Distinct from the file-driven ``test_catalog_fuzz_wave1515`` audit: that one
round-trips every fuzzed catalog through ``save`` + ``PDDocument.load``, so the
parser / writer can normalise or strip a malformed value before the accessor
ever sees it. This module instead constructs :class:`PDDocumentCatalog`
DIRECTLY over a hand-built (and often malformed) root :class:`COSDictionary`
— ``PDDocumentCatalog(doc, dict)`` — so each accessor's own leniency is what is
observed, with no round-trip in the way. The Java sibling
(``oracle/probes/DocumentCatalogFuzzProbe.java``) reflects the protected
``PDDocumentCatalog(PDDocument, COSDictionary)`` constructor to build the
byte-identical in-memory dict on the upstream side.

It also extends the audited accessor surface beyond wave 1515 with
``get_metadata`` (stream vs wrong-type), ``get_oc_properties`` (dict vs
wrong-type), and ``get_output_intents`` (clean array / array-with-bad-entry /
wrong-type) — the last of which is a real, pinned divergence: upstream's
``getOutputIntents`` casts each array entry to ``COSDictionary``
unconditionally, so a non-dict entry throws ``ClassCastException`` and the whole
call fails; pypdfbox's :meth:`get_output_intents` skips the non-dict entry
defensively and returns the surviving wrappers.

Both stacks build the SAME in-memory corpus (hard-coded on each side, no
external bytes). The Java probe emits one framed line per case; this module
reconstructs the identical dict, projects the identical grammar through
pypdfbox, and asserts line-for-line parity.

Line grammar (one per case)::

    CASE <name> version=<str|null|ERR:X> layout=<enum|ERR:X> mode=<enum|ERR:X>
        openaction=<cls|null|ERR:X> lang=<str|null|ERR:X>
        markinfo=<cls|null|ERR:X> marked=<0|1|ERR:X>
        metadata=<cls|null|ERR:X> ocprops=<cls|null|ERR:X> oi=<int|ERR:X>
        struct=<cls|null|ERR:X> names=<cls|null|ERR:X> dests=<cls|null|ERR:X>
        outline=<cls|null|ERR:X> acro=<cls|null|ERR:X>

``layout`` / ``mode`` compare upstream's DEFAULT-applying ``getPageLayout()`` /
``getPageMode()`` (never null) against pypdfbox's
``get_page_layout_or_default()`` / ``get_page_mode_or_default()``. ``oi`` is the
SIZE of the output-intent list. Java is ground truth: a real divergence is a
production fix; a defensible divergence is pinned in ``_PINNED`` with a matching
CHANGES.md row.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_catalog import PDDocumentCatalog
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _action(sub_type: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("Action"))
    if sub_type is not None:
        d.set_item(_N("S"), _N(sub_type))
    d.set_item(_N("D"), COSArray())
    return d


def _mark_info(marked: bool) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("MarkInfo"))
    d.set_boolean(_N("Marked"), marked)
    return d


def _acro_form() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Fields"), COSArray())
    return d


def _dest_array() -> COSArray:
    arr = COSArray()
    page = COSDictionary()
    page.set_item(_N("Type"), _N("Page"))
    arr.add(page)
    arr.add(_N("Fit"))
    return arr


def _output_intent_arr(with_bad_entry: bool) -> COSArray:
    arr = COSArray()
    oi = COSDictionary()
    oi.set_item(_N("Type"), _N("OutputIntent"))
    oi.set_item(_N("S"), _N("GTS_PDFA1"))
    arr.add(oi)
    if with_bad_entry:
        arr.add(_N("NotADict"))
    return arr


def _metadata_stream() -> COSBase:
    from pypdfbox.cos import COSStream

    s = COSStream()
    s.set_item(_N("Type"), _N("Metadata"))
    return s


# --------------------------------------------------------------------- corpus
#
# Each entry is a callable returning the fuzzed root dict, mirroring the Java
# probe's ``root(key, value)`` / hand-built dicts case for case, in order. The
# corpus is intentionally hard-coded on both stacks so no bytes cross the wire.


def _root(key: str, value: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N(key), value)
    return d


def _build_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    c["bare"] = COSDictionary()

    c["version_name_17"] = _root("Version", _N("1.7"))
    c["version_string_15"] = _root("Version", COSString("1.5"))
    c["version_float"] = _root("Version", COSFloat(2.0))
    c["version_int"] = _root("Version", COSInteger.get(2))
    c["version_array"] = _root("Version", COSArray())

    for lay in (
        "SinglePage",
        "OneColumn",
        "TwoColumnLeft",
        "TwoColumnRight",
        "TwoPageLeft",
        "TwoPageRight",
    ):
        c[f"layout_{lay}"] = _root("PageLayout", _N(lay))
    c["layout_unknown"] = _root("PageLayout", _N("Sideways"))
    c["layout_string"] = _root("PageLayout", COSString("OneColumn"))
    c["layout_int"] = _root("PageLayout", COSInteger.get(1))

    for m in (
        "UseNone",
        "UseOutlines",
        "UseThumbs",
        "FullScreen",
        "UseOC",
        "UseAttachments",
    ):
        c[f"mode_{m}"] = _root("PageMode", _N(m))
    c["mode_unknown"] = _root("PageMode", _N("UseXfa"))
    c["mode_string"] = _root("PageMode", COSString("UseThumbs"))

    c["openaction_goto"] = _root("OpenAction", _action("GoTo"))
    c["openaction_uri"] = _root("OpenAction", _action("URI"))
    c["openaction_unknown_s"] = _root("OpenAction", _action("Bogus"))
    c["openaction_d_only"] = _root("OpenAction", _action(None))
    c["openaction_dest"] = _root("OpenAction", _dest_array())
    c["openaction_name"] = _root("OpenAction", _N("Foo"))
    c["openaction_string"] = _root("OpenAction", COSString("Foo"))

    c["lang_string"] = _root("Lang", COSString("en-US"))
    c["lang_name"] = _root("Lang", _N("en-US"))
    c["lang_int"] = _root("Lang", COSInteger.get(1))

    c["markinfo_marked"] = _root("MarkInfo", _mark_info(True))
    c["markinfo_unmarked"] = _root("MarkInfo", _mark_info(False))
    c["markinfo_array"] = _root("MarkInfo", COSArray())

    c["metadata_stream"] = _root("Metadata", _metadata_stream())
    c["metadata_dict"] = _root("Metadata", COSDictionary())
    c["metadata_name"] = _root("Metadata", _N("X"))

    c["ocprops_dict"] = _root("OCProperties", COSDictionary())
    c["ocprops_array"] = _root("OCProperties", COSArray())

    c["oi_clean"] = _root("OutputIntents", _output_intent_arr(False))
    c["oi_bad_entry"] = _root("OutputIntents", _output_intent_arr(True))
    c["oi_dict"] = _root("OutputIntents", COSDictionary())

    c["struct_dict"] = _root("StructTreeRoot", COSDictionary())
    c["struct_array"] = _root("StructTreeRoot", COSArray())
    c["names_dict"] = _root("Names", COSDictionary())
    c["names_array"] = _root("Names", COSArray())
    c["dests_dict"] = _root("Dests", COSDictionary())
    c["dests_string"] = _root("Dests", COSString("x"))
    c["outline_dict"] = _root("Outlines", COSDictionary())
    c["outline_int"] = _root("Outlines", COSInteger.get(0))
    c["acro_dict"] = _root("AcroForm", _acro_form())
    c["acro_name"] = _root("AcroForm", _N("Form"))

    return c


# ----------------------------------------------------- Python-side projection


def _exc(e: Exception) -> str:
    if isinstance(e, OSError):
        return "ERR:IOException"
    return f"ERR:{type(e).__name__}"


def _cls(obj: object) -> str:
    return "null" if obj is None else type(obj).__name__


def _cell(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return _cls(fn())
    except Exception as e:  # noqa: BLE001 — mirror the probe's catch-all
        return _exc(e)


def _str_cell(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        v = fn()
        return "null" if v is None else v
    except Exception as e:  # noqa: BLE001
        return _exc(e)


def _python_line(doc: PDDocument, name: str, root: COSDictionary) -> str:
    prefix = f"CASE {name} "
    if not isinstance(root.get_dictionary_object(_N("Type")), COSName):
        root.set_item(_N("Type"), _N("Catalog"))
    cat = PDDocumentCatalog(doc, root)

    def _layout() -> str:
        try:
            return cat.get_page_layout_or_default().string_value()
        except Exception as e:  # noqa: BLE001
            return _exc(e)

    def _mode() -> str:
        try:
            return cat.get_page_mode_or_default().string_value()
        except Exception as e:  # noqa: BLE001
            return _exc(e)

    def _marked() -> str:
        try:
            return "1" if cat.is_document_marked() else "0"
        except Exception as e:  # noqa: BLE001
            return _exc(e)

    def _oi() -> str:
        try:
            return str(len(cat.get_output_intents()))
        except Exception as e:  # noqa: BLE001
            return _exc(e)

    return prefix + (
        f"version={_str_cell(cat.get_version)} "
        f"layout={_layout()} "
        f"mode={_mode()} "
        f"openaction={_cell(cat.get_open_action)} "
        f"lang={_str_cell(cat.get_language)} "
        f"markinfo={_cell(cat.get_mark_info)} "
        f"marked={_marked()} "
        f"metadata={_cell(cat.get_metadata)} "
        f"ocprops={_cell(cat.get_oc_properties)} "
        f"oi={_oi()} "
        f"struct={_cell(cat.get_structure_tree_root)} "
        f"names={_cell(cat.get_names)} "
        f"dests={_cell(cat.get_dests)} "
        f"outline={_cell(cat.get_document_outline)} "
        f"acro={_cell(lambda: cat.get_acro_form(None))}"
    )


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
#
# /OutputIntents with a non-dictionary array element: upstream's
# getOutputIntents() casts every entry to COSDictionary unconditionally, so the
# stray COSName throws ClassCastException and the whole call fails (oi=ERR).
# pypdfbox's get_output_intents() skips non-dictionary entries defensively and
# returns the one valid wrapper (oi=1). pypdfbox is strictly more robust here;
# pinned with a CHANGES.md row.
_PINNED: dict[str, tuple[str, str, str]] = {
    "oi_bad_entry": (
        "CASE oi_bad_entry version=null layout=SinglePage mode=UseNone "
        "openaction=null lang=null markinfo=null marked=0 metadata=null "
        "ocprops=null oi=1 struct=null names=null dests=null outline=null "
        "acro=null",
        "CASE oi_bad_entry version=null layout=SinglePage mode=UseNone "
        "openaction=null lang=null markinfo=null marked=0 metadata=null "
        "ocprops=null oi=ERR:ClassCastException struct=null names=null "
        "dests=null outline=null acro=null",
        "get_output_intents skips non-dict array entries; upstream casts "
        "unconditionally and throws ClassCastException",
    ),
}


# --------------------------------------------------------------------- test


@requires_oracle
def test_document_catalog_fuzz_matches_pdfbox() -> None:
    """Every malformed catalog dict resolves identically when the catalog is
    built in-memory directly over the dict on pypdfbox and Apache PDFBox 3.0.7:
    same per-accessor cell, same default-applied enum, same wrapper class.
    Divergences are pinned in ``_PINNED`` with a matching CHANGES.md row."""
    raw = run_probe_text("DocumentCatalogFuzzProbe")
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    doc = PDDocument()
    try:
        corpus = _build_corpus()
        assert len(java_lines) == len(corpus), (
            f"probe emitted {len(java_lines)} lines for "
            f"{len(corpus)} cases:\n{raw}"
        )

        mismatches: list[str] = []
        for name, root in corpus.items():
            java = java_by_name.get(name, "<MISSING>")
            py = _python_line(doc, name, root)
            if name in _PINNED:
                py_exp, java_exp, _reason = _PINNED[name]
                if py == py_exp and java == java_exp:
                    continue
            if py != java:
                mismatches.append(
                    f"  {name}\n    java: {java}\n    py  : {py}"
                )

        assert not mismatches, (
            "PDDocumentCatalog in-memory accessor fuzz divergences:\n"
            + "\n".join(mismatches)
        )
    finally:
        doc.close()
