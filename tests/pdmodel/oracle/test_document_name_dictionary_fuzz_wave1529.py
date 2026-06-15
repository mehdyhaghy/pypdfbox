"""Differential fuzz audit for :class:`PDDocumentNameDictionary` accessor
leniency over a MALFORMED catalog ``/Names`` sub-dictionary vs Apache PDFBox
3.0.7 (wave 1529, agent E).

Apache PDFBox 3.0.7 only exposes three sub-entry accessors on this class —
``get_dests`` / ``get_embedded_files`` / ``get_javascript`` — plus
``get_cos_object``. pypdfbox additionally surfaces ``get_pages`` /
``get_templates`` / ``get_ids`` / ``get_urls`` / ``get_renditions`` / ``get_ap``
as forward-looking extensions with no upstream counterpart; those are exercised
by the value-based unit suite, not this oracle. The corpus still installs those
sub-entries at the COS level (so the ``cos`` round-trip entry count covers
them), but only the three upstream accessors are projected per-cell.

Each accessor reads its sub-entry via ``COSDictionary.get_cos_dictionary(KEY)``
semantics — returning a wrapped name-tree node when the value resolves to a
``COSDictionary``, and ``None`` otherwise (entry absent, or present as a
wrong-typed name / string / array / number). ``get_dests`` additionally falls
back to the catalog's legacy direct ``/Dests`` entry when ``/Names /Dests`` is
absent or wrong-typed, wrapping that fallback as a ``PDDestinationNameTreeNode``
(NOT the flat-dict wrapper).

This audit complements the value-based unit suite by driving BOTH stacks on the
same on-disk bytes: the corpus builder mutates the catalog ``/Names`` sub-dict
of a one-page document so the saved PDF's ``/Names`` IS the fuzzed dict (and,
for the catalog-fallback cases, a direct catalog ``/Dests``), writes one
``<case>.pdf`` per case plus a ``manifest.txt`` into a tmp dir. The Java probe
(``oracle/probes/DocumentNameDictionaryFuzzProbe.java``) loads each
``<case>.pdf`` and projects a stable framed line; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> names=<cls|null|ERR:X> dests=<cls|null|ERR:X>
        embed=<cls|null|ERR:X> js=<cls|null|ERR:X> cos=<int|null|ERR:X>

``names`` is the ``PDDocumentNameDictionary`` wrapper class (or "null" when
``/Names`` is absent / non-dict — then every other cell is "null" because no
wrapper exists). ``cos`` is the entry count of ``get_names().get_cos_object()``
(round-trip check).

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/pd_document_name_dictionary.py``; a defensible divergence is
pinned in ``_PINNED`` with a matching CHANGES.md row.
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
_NAMES = _N("Names")
_DESTS = _N("Dests")


# --------------------------------------------------------------------- corpus
#
# Each entry is a callable that, given the live one-page document's catalog COS
# dictionary, installs a fuzzed ``/Names`` sub-dict (and, for fallback cases, a
# direct catalog ``/Dests``). Using a callable lets the catalog-fallback case
# wire a real dict into the catalog alongside an absent ``/Names /Dests``.


def _names_dict(**entries: COSBase) -> COSDictionary:
    """A ``/Names`` sub-dict carrying the given key -> value entries."""
    d = COSDictionary()
    for key, value in entries.items():
        d.set_item(_N(key), value)
    return d


def _all_dict_names() -> COSDictionary:
    """A ``/Names`` sub-dict where every sub-entry is a (empty) dict —
    every accessor must wrap a node."""
    return _names_dict(
        Dests=COSDictionary(),
        EmbeddedFiles=COSDictionary(),
        JavaScript=COSDictionary(),
        Pages=COSDictionary(),
        Templates=COSDictionary(),
        IDS=COSDictionary(),
        URLS=COSDictionary(),
        Renditions=COSDictionary(),
    )


def _build_corpus() -> dict[str, object]:
    c: dict[str, object] = {}

    # ---- /Names entirely absent: getNames() is null, all cells null ----
    c["names_absent"] = lambda cat: None

    # ---- /Names present as wrong types: getNames() null (getCOSDictionary) ----
    c["names_is_name"] = lambda cat: cat.set_item(_NAMES, _N("X"))
    c["names_is_string"] = lambda cat: cat.set_item(_NAMES, COSString("x"))
    c["names_is_array"] = lambda cat: cat.set_item(_NAMES, COSArray())
    c["names_is_number"] = lambda cat: cat.set_item(_NAMES, COSInteger(7))

    # ---- empty /Names dict: wrapper exists, every accessor null ----
    c["names_empty"] = lambda cat: cat.set_item(_NAMES, COSDictionary())

    # ---- every sub-entry a dict: every accessor wraps its node ----
    c["all_dicts"] = lambda cat: cat.set_item(_NAMES, _all_dict_names())

    # ---- each sub-entry present individually as a dict ----
    for key in (
        "Dests",
        "EmbeddedFiles",
        "JavaScript",
        "Pages",
        "Templates",
        "IDS",
        "URLS",
        "Renditions",
    ):
        c[f"only_{key.lower()}_dict"] = (
            lambda cat, k=key: cat.set_item(_NAMES, _names_dict(**{k: COSDictionary()}))
        )

    # ---- each sub-entry present as a wrong type -> accessor null ----
    # name / string / array / number sweep across representative keys.
    c["embed_is_name"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(EmbeddedFiles=_N("X"))
    )
    c["embed_is_string"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(EmbeddedFiles=COSString("x"))
    )
    c["embed_is_array"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(EmbeddedFiles=COSArray())
    )
    c["embed_is_number"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(EmbeddedFiles=COSInteger(1))
    )
    c["js_is_array"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(JavaScript=COSArray())
    )
    c["js_is_string"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(JavaScript=COSString("x"))
    )
    c["pages_is_name"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(Pages=_N("X"))
    )
    c["templ_is_number"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(Templates=COSInteger(0))
    )
    c["ids_is_array"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(IDS=COSArray())
    )
    c["urls_is_string"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(URLS=COSString("x"))
    )
    c["rend_is_name"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(Renditions=_N("X"))
    )

    # ---- /Names /Dests as a name-tree (Kids array form) ----
    c["dests_nametree_kids"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(Dests=_kids_node())
    )
    # ---- /Names /EmbeddedFiles as a leaf name-tree (Names array form) ----
    c["embed_nametree_names"] = lambda cat: cat.set_item(
        _NAMES, _names_dict(EmbeddedFiles=_leaf_node())
    )

    # ---- /Dests catalog fallback: /Names present (empty), catalog /Dests dict.
    # getDests() falls back to the catalog entry and wraps it as a tree node.
    c["dests_catalog_fallback"] = _install_dests_fallback
    # ---- fallback where catalog /Dests is wrong-typed -> still null ----
    c["dests_catalog_fallback_wrongtype"] = _install_dests_fallback_wrong
    # ---- /Names /Dests dict wins over catalog /Dests (no fallback) ----
    c["dests_names_wins"] = _install_dests_names_wins

    return c


def _kids_node() -> COSDictionary:
    """A name-tree intermediate node: ``{/Kids [<leaf>]}``."""
    leaf = _leaf_node()
    node = COSDictionary()
    kids = COSArray()
    kids.add(leaf)
    node.set_item(_N("Kids"), kids)
    return node


def _leaf_node() -> COSDictionary:
    """A name-tree leaf node: ``{/Names [(a) <dest-array>]}``."""
    node = COSDictionary()
    names = COSArray()
    names.add(COSString("a"))
    names.add(COSArray())
    node.set_item(_N("Names"), names)
    return node


def _install_dests_fallback(catalog: COSDictionary) -> None:
    catalog.set_item(_NAMES, COSDictionary())
    catalog.set_item(_DESTS, COSDictionary())


def _install_dests_fallback_wrong(catalog: COSDictionary) -> None:
    catalog.set_item(_NAMES, COSDictionary())
    catalog.set_item(_DESTS, COSString("x"))


def _install_dests_names_wins(catalog: COSDictionary) -> None:
    catalog.set_item(_NAMES, _names_dict(Dests=_kids_node()))
    catalog.set_item(_DESTS, COSDictionary())


# --------------------------------------------------------------------- corpus io


def _write_case_pdf(path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        catalog = doc.get_document_catalog().get_cos_object()
        mutate(catalog)
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


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix + f"LOAD:{type(e).__name__}"
    try:
        cat = doc.get_document_catalog()
        nd = cat.get_names()
        if nd is None:
            return prefix + (
                "names=null dests=null embed=null js=null cos=null"
            )

        def _cos() -> str:
            try:
                obj = nd.get_cos_object()
                return "null" if obj is None else str(obj.size())
            except Exception as e:  # noqa: BLE001
                return _exc(e)

        return prefix + (
            f"names={_cls(nd)} "
            f"dests={_cell(nd.get_dests)} "
            f"embed={_cell(nd.get_embedded_files)} "
            f"js={_cell(nd.get_javascript)} "
            f"cos={_cos()}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_document_name_dictionary_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed ``/Names`` sub-dict resolves (or fails to resolve)
    identically on pypdfbox and Apache PDFBox 3.0.7: same getNames() presence,
    same per-accessor wrapper class, same fallback, same round-trip entry count.
    Divergences are pinned explicitly in ``_PINNED`` (with a matching CHANGES.md
    row)."""
    corpus = _build_corpus()
    for name, mutate in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", mutate)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("DocumentNameDictionaryFuzzProbe", str(tmp_path))
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
        "PDDocumentNameDictionary accessor fuzz divergences:\n"
        + "\n".join(mismatches)
    )
