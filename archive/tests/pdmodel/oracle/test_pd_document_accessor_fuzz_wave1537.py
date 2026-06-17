"""Differential fuzz audit for the :class:`PDDocument` top-level read-accessor
surface over MALFORMED / EDGE document state vs Apache PDFBox 3.0.7
(wave 1537, agent D).

Complements the catalog / doc-info / doc-nav fuzz probes (which drive the
sub-dictionaries directly) by driving the ``PDDocument`` facade itself —
``get_number_of_pages``, ``get_page(int)``, ``get_document_catalog``,
``get_document_information``, ``get_version``, ``is_encrypted`` — over documents
whose ``/Root`` is missing or mistyped, whose ``/Pages`` is missing or carries a
``/Count`` that lies, whose header / catalog versions disagree, and whose
``/Encrypt`` is present or absent.

Both sides are driven on the SAME bytes: the corpus builder mutates a freshly
constructed document, saves one ``<case>.pdf`` per case plus a ``manifest.txt``
into a tmp dir. The Java probe (``oracle/probes/PdDocumentAccessorFuzzProbe.java``)
loads each ``<case>.pdf`` and projects a stable framed line; this module reads
the exact same files and projects the identical grammar through pypdfbox, then
asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> numpages=<int|ERR:X> page0=<ok|ERR:X> pageN=<ok|ERR:X>
        version=<float|ERR:X> encrypted=<bool|ERR:X>
        hascatalog=<bool|ERR:X> hasinfo=<bool|ERR:X>

``pageN`` probes ``get_page(numpages)`` (one past the last valid index) to
surface the out-of-range exception class. Java is ground truth: a real
divergence is a production fix in ``pypdfbox/pdmodel/pd_document.py``; a
defensible divergence is pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_ROOT = _N("Root")
_PAGES = _N("Pages")
_COUNT = _N("Count")
_TYPE = _N("Type")
_VERSION = _N("Version")
_INFO = _N("Info")
_ENCRYPT = _N("Encrypt")


def _catalog(doc: PDDocument) -> COSDictionary:
    return doc.get_document_catalog().get_cos_object()


def _pages_dict(doc: PDDocument) -> COSDictionary:
    return _catalog(doc).get_dictionary_object(_PAGES)


def _trailer(doc: PDDocument) -> COSDictionary:
    return doc.get_document().get_trailer()


# --------------------------------------------------------------------- corpus
#
# Each entry is a callable mutating an already-page-populated document just
# before save. ``npages`` controls how many pages are added first.


def _build_corpus() -> dict[str, tuple[int, Callable[[PDDocument], None]]]:
    c: dict[str, tuple[int, Callable[[PDDocument], None]]] = {}

    # ---- well-formed baselines ----
    c["empty_doc"] = (0, lambda d: None)
    c["one_page"] = (1, lambda d: None)
    c["three_pages"] = (3, lambda d: None)

    # ---- /Count that lies (over- and under-count) ----
    c["count_overstates"] = (1, lambda d: _pages_dict(d).set_int(_COUNT, 5))
    c["count_understates"] = (3, lambda d: _pages_dict(d).set_int(_COUNT, 1))
    c["count_zero_with_pages"] = (2, lambda d: _pages_dict(d).set_int(_COUNT, 0))
    c["count_negative"] = (1, lambda d: _pages_dict(d).set_int(_COUNT, -2))
    c["count_missing"] = (1, lambda d: _pages_dict(d).remove_item(_COUNT))
    c["count_is_string"] = (
        1,
        lambda d: _pages_dict(d).set_item(_COUNT, COSString("2")),
    )
    c["count_is_name"] = (
        1,
        lambda d: _pages_dict(d).set_item(_COUNT, _N("2")),
    )

    # ---- /Pages malformed ----
    c["pages_missing"] = (1, lambda d: _catalog(d).remove_item(_PAGES))
    c["pages_is_array"] = (
        1,
        lambda d: _catalog(d).set_item(_PAGES, COSArray()),
    )
    c["pages_is_string"] = (
        1,
        lambda d: _catalog(d).set_item(_PAGES, COSString("nope")),
    )
    c["pages_empty_kids"] = (1, _pages_empty_kids)

    # ---- /Root missing / mistyped ----
    c["root_missing"] = (1, lambda d: _trailer(d).remove_item(_ROOT))
    c["root_is_array"] = (
        1,
        lambda d: _trailer(d).set_item(_ROOT, COSArray()),
    )
    c["root_is_string"] = (
        1,
        lambda d: _trailer(d).set_item(_ROOT, COSString("nope")),
    )
    c["root_no_type"] = (1, lambda d: _catalog(d).remove_item(_TYPE))
    c["root_wrong_type"] = (
        1,
        lambda d: _catalog(d).set_item(_TYPE, _N("NotCatalog")),
    )

    # ---- version: header vs catalog /Version (max wins per upstream) ----
    c["version_catalog_higher"] = (
        1,
        lambda d: _catalog(d).set_item(_VERSION, _N("1.7")),
    )
    c["version_catalog_lower"] = (
        1,
        lambda d: _catalog(d).set_item(_VERSION, _N("1.2")),
    )
    c["version_catalog_malformed"] = (
        1,
        lambda d: _catalog(d).set_item(_VERSION, _N("garbage")),
    )
    c["version_catalog_as_string"] = (
        1,
        lambda d: _catalog(d).set_item(_VERSION, COSString("1.6")),
    )
    c["version_catalog_empty"] = (
        1,
        lambda d: _catalog(d).set_item(_VERSION, _N("")),
    )

    # ---- /Info presence / mistype ----
    c["info_absent"] = (1, lambda d: _drop_info(d))
    c["info_is_array"] = (
        1,
        lambda d: _trailer(d).set_item(_INFO, COSArray()),
    )

    # ---- /Encrypt malformed-but-present (key presence drives is_encrypted) ----
    c["encrypt_empty_dict"] = (
        1,
        lambda d: _trailer(d).set_item(_ENCRYPT, COSDictionary()),
    )

    return c


def _pages_empty_kids(d: PDDocument) -> None:
    pages = _pages_dict(d)
    pages.set_item(_N("Kids"), COSArray())
    pages.set_int(_COUNT, 0)


def _drop_info(d: PDDocument) -> None:
    trailer = _trailer(d)
    if trailer is not None:
        trailer.remove_item(_INFO)


# --------------------------------------------------------------------- corpus io


def _write_case_pdf(
    path: Path, npages: int, mutate: Callable[[PDDocument], None]
) -> None:
    doc = PDDocument()
    try:
        for _ in range(npages):
            doc.add_page(PDPage())
        # Force an /Info dict to exist so the default-presence cases have a
        # consistent baseline (matches upstream's lazy-create on first access).
        doc.get_document_information()
        mutate(doc)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _err(e: BaseException) -> str:
    if isinstance(e, IndexError):
        return "ERR:IndexOutOfBoundsException"
    if isinstance(e, OSError):
        return "ERR:IOException"
    return f"ERR:{type(e).__name__}"


def _num_pages_cell(doc: PDDocument) -> str:
    try:
        return str(doc.get_number_of_pages())
    except Exception as e:  # noqa: BLE001 — mirror the probe catch-all
        return _err(e)


def _page_cell(doc: PDDocument, index: int) -> str:
    try:
        return "ok" if doc.get_page(index) is not None else "null"
    except Exception as e:  # noqa: BLE001
        return _err(e)


def _page_past_end_cell(doc: PDDocument) -> str:
    try:
        n = doc.get_number_of_pages()
    except Exception as e:  # noqa: BLE001
        return _err(e)
    return _page_cell(doc, n)


def _version_cell(doc: PDDocument) -> str:
    try:
        # Java prints a float via Float.toString — reproduce its 1-decimal
        # shape for the common case (e.g. 1.4 -> "1.4").
        return _format_float(doc.get_version())
    except Exception as e:  # noqa: BLE001
        return _err(e)


def _format_float(v: float) -> str:
    # Float.toString(1.4f) == "1.4"; Python str(1.4) == "1.4". For values that
    # came through float() of "1.7" etc. both stacks agree to one decimal.
    text = repr(float(v))
    return text


def _bool_cell(fn: Callable[[], object]) -> str:
    try:
        return "true" if fn() else "false"
    except Exception as e:  # noqa: BLE001
        return _err(e)


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix.rstrip() + f" LOAD:{type(e).__name__}"
    try:
        return prefix + (
            f"numpages={_num_pages_cell(doc)} "
            f"page0={_page_cell(doc, 0)} "
            f"pageN={_page_past_end_cell(doc)} "
            f"version={_version_cell(doc)} "
            f"encrypted={_bool_cell(doc.is_encrypted)} "
            f"hascatalog={_bool_cell(lambda: doc.get_document_catalog() is not None)} "
            f"hasinfo={_bool_cell(lambda: doc.get_document_information() is not None)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

def _lenient_load_line(name: str) -> str:
    """The line pypdfbox emits for a malformed-trailer case where Apache
    PDFBox refuses to load the file but pypdfbox loads it leniently and reaches
    a synthesised catalog / empty page tree."""
    return (
        f"CASE {name} numpages=0 page0=ERR:IndexOutOfBoundsException "
        f"pageN=ERR:IndexOutOfBoundsException version=1.4 encrypted=false "
        f"hascatalog=true hasinfo=true"
    )


# name -> (python_line_override, java_line_override, reason).
#
# Loader-strictness divergences, NOT accessor divergences: Apache PDFBox's
# ``Loader.loadPDF`` performs a strict trailer sanity pass and throws an
# ``IOException`` when ``/Root`` or ``/Pages`` is missing / mistyped, or when
# ``/Encrypt`` is present but unusable. pypdfbox's loader is more lenient: it
# loads the file and synthesises a minimal catalog / empty page tree (or, for
# the empty-/Encrypt case, surfaces the key presence through ``is_encrypted``).
# Reconciling this lives in the parser/loader cluster, not in the PDDocument
# accessor zone this wave audits, so we pin both sides here and record the
# divergence in CHANGES.md (Wave 1537) for a future loader-strictness wave.
_PINNED: dict[str, tuple[str, str, str]] = {
    name: (
        _lenient_load_line(name),
        f"CASE {name} LOAD:IOException",
        "loader leniency: PDFBox rejects this malformed trailer at load time; "
        "pypdfbox loads it and synthesises a minimal catalog/page tree",
    )
    for name in (
        "root_missing",
        "root_is_array",
        "root_is_string",
        "pages_missing",
        "pages_is_array",
        "pages_is_string",
    )
}
_PINNED["encrypt_empty_dict"] = (
    "CASE encrypt_empty_dict numpages=1 page0=ok pageN=ERR:IndexOutOfBoundsException "
    "version=1.4 encrypted=true hascatalog=true hasinfo=true",
    "CASE encrypt_empty_dict LOAD:IOException",
    "loader leniency: PDFBox rejects a present-but-unusable /Encrypt at load "
    "time; pypdfbox loads it and reports is_encrypted()==True from key presence",
)


# --------------------------------------------------------------------- test


@requires_oracle
def test_pd_document_accessor_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed/edge document resolves (or fails to resolve) identically
    on pypdfbox and Apache PDFBox 3.0.7 across the PDDocument read-accessor
    surface: same page count, same out-of-range exception class, same merged
    header/catalog version, same encryption / catalog / info presence.
    Divergences are pinned explicitly in ``_PINNED`` (with a CHANGES.md row)."""
    corpus = _build_corpus()
    for name, (npages, mutate) in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", npages, mutate)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("PdDocumentAccessorFuzzProbe", str(tmp_path))
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
        "PDDocument accessor fuzz divergences:\n" + "\n".join(mismatches)
    )
