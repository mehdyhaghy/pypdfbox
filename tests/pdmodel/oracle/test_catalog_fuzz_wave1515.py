"""Differential fuzz audit for :class:`PDDocumentCatalog` accessor / enum
leniency over a MALFORMED catalog (root) dictionary vs Apache PDFBox 3.0.7
(wave 1515, agent D).

Complements the well-formed catalog oracle suite (``test_catalog_oracle``,
``test_catalog_meta_oracle``, ``test_catalog_page_enum_oracle``,
``test_catalog_version_oracle``, ``test_viewer_prefs_oracle``) — none of which
exercise the malformed / mistyped catalog subset this audit targets:

* ``/Version`` as a name vs string vs number vs missing (``get_version``
  delegates to ``COSDictionary.get_name_as_string``, accepting a COSName or a
  COSString and returning ``None`` otherwise);
* ``/PageLayout`` enum sweep (SinglePage / OneColumn / TwoColumnLeft /
  TwoColumnRight / TwoPageLeft / TwoPageRight / unknown / wrong-type / missing)
  — the upstream-compatible default-applying read
  (``get_page_layout_or_default``) folds absent / unknown / wrong-type to
  SinglePage;
* ``/PageMode`` enum sweep (UseNone / UseOutlines / UseThumbs / FullScreen /
  UseOC / UseAttachments / unknown / wrong-type / missing) —
  ``get_page_mode_or_default`` folds absent / unknown / wrong-type to UseNone;
* ``/OpenAction`` as an action dict (recognised /S, unknown /S, /D-only
  shorthand), a destination array, and a wrong-type value;
* ``/Lang`` string vs wrong-type vs missing;
* ``/MarkInfo`` dict vs wrong-type (and the /Marked flag inside);
* presence / wrong-type of ``/PageLabels`` ``/ViewerPreferences`` ``/Names``
  ``/Dests`` ``/Outlines`` ``/StructTreeRoot`` ``/AcroForm`` ``/URI``.

Both sides are driven on the SAME bytes: the corpus builder mutates the catalog
(root) dictionary of a one-page document so that the saved PDF's catalog IS the
fuzzed dict, writes one ``<case>.pdf`` per case plus a ``manifest.txt`` into a
tmp dir. The Java probe (``oracle/probes/CatalogFuzzProbe.java``) loads each
``<case>.pdf`` and projects a stable framed line; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

The enum cells compare upstream's DEFAULT-applying ``getPageLayout()`` /
``getPageMode()`` (never null) against pypdfbox's
``get_page_layout_or_default()`` / ``get_page_mode_or_default()`` (the
upstream-compatible default-applying reads). The nullable
``get_page_layout()`` / ``get_page_mode()`` are pypdfbox's deliberate
"explicit vs default" extension and are exercised by the value-based unit suite.

Line grammar (one per case, manifest order)::

    CASE <name> version=<str|null|ERR:X> layout=<enum|ERR:X>
        mode=<enum|ERR:X> openaction=<cls|null|ERR:X> lang=<str|null|ERR:X>
        markinfo=<cls|null|ERR:X> marked=<0|1|ERR:X> labels=<cls|null|ERR:X>
        vprefs=<cls|null|ERR:X> names=<cls|null|ERR:X> dests=<cls|null|ERR:X>
        outline=<cls|null|ERR:X> struct=<cls|null|ERR:X> acro=<cls|null|ERR:X>
        uri=<cls|null|ERR:X>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/pd_document_catalog.py``; a defensible divergence is pinned
in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
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


def _uri_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_string(_N("Base"), "http://example.com/")
    return d


# --------------------------------------------------------------------- corpus
#
# Each entry is a callable that, given the live one-page document, mutates the
# catalog (root) dictionary in place. Using a callable (rather than a static
# COSDictionary) lets the /OpenAction destination-array case reference the
# document's real first page object, so the saved bytes round-trip to a valid
# page destination on both stacks.


def _set(catalog: COSDictionary, key: str, value: COSBase) -> None:
    catalog.set_item(_N(key), value)


def _build_corpus() -> dict[str, object]:
    c: dict[str, object] = {}

    # ---- bare catalog: every probed entry absent (default-applying enums) ----
    c["bare_catalog"] = lambda cat, page: None

    # ---- /Version: name (spec form) / string (lenient) / number / missing ----
    c["version_name_17"] = lambda cat, page: _set(cat, "Version", _N("1.7"))
    c["version_string_15"] = lambda cat, page: _set(
        cat, "Version", COSString("1.5")
    )
    c["version_is_number"] = lambda cat, page: _set(
        cat, "Version", COSInteger(2)
    )
    c["version_is_array"] = lambda cat, page: _set(
        cat, "Version", COSArray()
    )

    # ---- /PageLayout enum sweep (default-applying) ----
    for layout in (
        "SinglePage",
        "OneColumn",
        "TwoColumnLeft",
        "TwoColumnRight",
        "TwoPageLeft",
        "TwoPageRight",
    ):
        c[f"layout_{layout}"] = (
            lambda cat, page, lay=layout: _set(cat, "PageLayout", _N(lay))
        )
    c["layout_unknown"] = lambda cat, page: _set(
        cat, "PageLayout", _N("Sideways")
    )
    c["layout_is_string"] = lambda cat, page: _set(
        cat, "PageLayout", COSString("OneColumn")
    )
    c["layout_is_number"] = lambda cat, page: _set(
        cat, "PageLayout", COSInteger(3)
    )
    c["layout_is_array"] = lambda cat, page: _set(
        cat, "PageLayout", COSArray()
    )

    # ---- /PageMode enum sweep (default-applying) ----
    for mode in (
        "UseNone",
        "UseOutlines",
        "UseThumbs",
        "FullScreen",
        "UseOC",
        "UseAttachments",
    ):
        c[f"mode_{mode}"] = (
            lambda cat, page, m=mode: _set(cat, "PageMode", _N(m))
        )
    c["mode_unknown"] = lambda cat, page: _set(cat, "PageMode", _N("UseXfa"))
    c["mode_is_string"] = lambda cat, page: _set(
        cat, "PageMode", COSString("UseThumbs")
    )
    c["mode_is_number"] = lambda cat, page: _set(
        cat, "PageMode", COSInteger(1)
    )

    # ---- /OpenAction: action dict (known/unknown/D-only), dest array, wrong ----
    c["openaction_goto"] = lambda cat, page: _set(
        cat, "OpenAction", _action("GoTo")
    )
    c["openaction_uri_action"] = lambda cat, page: _set(
        cat, "OpenAction", _action("URI")
    )
    c["openaction_unknown_s"] = lambda cat, page: _set(
        cat, "OpenAction", _action("Bogus")
    )
    c["openaction_d_only"] = lambda cat, page: _set(
        cat, "OpenAction", _action(None)
    )
    c["openaction_dest_array"] = _install_dest_array
    c["openaction_is_name"] = lambda cat, page: _set(
        cat, "OpenAction", _N("Foo")
    )
    c["openaction_is_string"] = lambda cat, page: _set(
        cat, "OpenAction", COSString("Foo")
    )

    # ---- /Lang: string / wrong-type / missing ----
    c["lang_string"] = lambda cat, page: _set(
        cat, "Lang", COSString("en-US")
    )
    c["lang_is_name"] = lambda cat, page: _set(cat, "Lang", _N("en-US"))
    c["lang_is_number"] = lambda cat, page: _set(cat, "Lang", COSInteger(1))

    # ---- /MarkInfo dict (marked true/false) vs wrong-type ----
    c["markinfo_marked"] = lambda cat, page: _set(
        cat, "MarkInfo", _mark_info(True)
    )
    c["markinfo_unmarked"] = lambda cat, page: _set(
        cat, "MarkInfo", _mark_info(False)
    )
    c["markinfo_is_array"] = lambda cat, page: _set(
        cat, "MarkInfo", COSArray()
    )
    c["markinfo_is_name"] = lambda cat, page: _set(
        cat, "MarkInfo", _N("Marked")
    )

    # ---- presence / wrong-type of the remaining wrapper accessors ----
    c["pagelabels_dict"] = lambda cat, page: _set(
        cat, "PageLabels", COSDictionary()
    )
    c["pagelabels_is_array"] = lambda cat, page: _set(
        cat, "PageLabels", COSArray()
    )
    c["vprefs_dict"] = lambda cat, page: _set(
        cat, "ViewerPreferences", COSDictionary()
    )
    c["vprefs_is_name"] = lambda cat, page: _set(
        cat, "ViewerPreferences", _N("X")
    )
    c["names_dict"] = lambda cat, page: _set(cat, "Names", COSDictionary())
    c["names_is_array"] = lambda cat, page: _set(cat, "Names", COSArray())
    c["dests_dict"] = lambda cat, page: _set(cat, "Dests", COSDictionary())
    c["dests_is_string"] = lambda cat, page: _set(
        cat, "Dests", COSString("x")
    )
    c["outline_dict"] = lambda cat, page: _set(
        cat, "Outlines", COSDictionary()
    )
    c["outline_is_number"] = lambda cat, page: _set(
        cat, "Outlines", COSInteger(0)
    )
    c["struct_dict"] = lambda cat, page: _set(
        cat, "StructTreeRoot", COSDictionary()
    )
    c["struct_is_array"] = lambda cat, page: _set(
        cat, "StructTreeRoot", COSArray()
    )
    c["acro_dict"] = lambda cat, page: _set(cat, "AcroForm", _acro_form())
    c["acro_is_name"] = lambda cat, page: _set(cat, "AcroForm", _N("Form"))
    c["uri_dict"] = lambda cat, page: _set(cat, "URI", _uri_dict())
    c["uri_is_string"] = lambda cat, page: _set(
        cat, "URI", COSString("http://x/")
    )

    return c


def _install_dest_array(catalog: COSDictionary, page: PDPage) -> None:
    """``/OpenAction`` as a page-backed explicit destination array
    ``[<page> /Fit]`` — resolves to a ``PDPageFitDestination`` on both
    stacks."""
    arr = COSArray()
    arr.add(page.get_cos_object())
    arr.add(_N("Fit"))
    catalog.set_item(_N("OpenAction"), arr)


# --------------------------------------------------------------------- corpus io


def _write_case_pdf(path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        catalog = doc.get_document_catalog().get_cos_object()
        mutate(catalog, page)
        doc.save(str(path))
    finally:
        doc.close()


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


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix + f"LOAD:{type(e).__name__}"
    try:
        cat = doc.get_document_catalog()

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

        return prefix + (
            f"version={_str_cell(cat.get_version)} "
            f"layout={_layout()} "
            f"mode={_mode()} "
            f"openaction={_cell(cat.get_open_action)} "
            f"lang={_str_cell(cat.get_language)} "
            f"markinfo={_cell(cat.get_mark_info)} "
            f"marked={_marked()} "
            f"labels={_cell(cat.get_page_labels)} "
            f"vprefs={_cell(cat.get_viewer_preferences)} "
            f"names={_cell(cat.get_names)} "
            f"dests={_cell(cat.get_dests)} "
            f"outline={_cell(cat.get_document_outline)} "
            f"struct={_cell(cat.get_structure_tree_root)} "
            f"acro={_cell(lambda: cat.get_acro_form(None))} "
            f"uri={_cell(cat.get_uri)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_catalog_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed catalog dict resolves (or fails to resolve) identically
    on pypdfbox and Apache PDFBox 3.0.7: same per-accessor cell, same
    default-applied enum, same wrapper class. Divergences are pinned explicitly
    in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, mutate in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", mutate)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("CatalogFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, (
        "PDDocumentCatalog accessor/enum fuzz divergences:\n"
        + "\n".join(mismatches)
    )
