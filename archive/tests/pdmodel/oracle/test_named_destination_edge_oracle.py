"""Live PDFBox differential parity for NAMED-DESTINATION RESOLUTION EDGE CASES
(``pypdfbox.pdmodel`` catalog / name-tree / legacy-dict dispatch).

Complements ``test_named_destination_oracle.py`` (happy-path resolution
surfaces) by pinning the trickier dispatch / precedence / fall-through
behaviours of ``PDDocumentCatalog.find_named_destination_page``:

* **precedence** — a name registered in BOTH the modern ``/Names /Dests`` name
  tree AND the legacy catalog ``/Dests`` dict. Upstream tries the name tree
  first (``findNamedDestinationPage`` body: ``getNames().getDests().getValue``
  before the legacy ``getDests().getDestination`` fallback), so the tree
  **shadows** the legacy dict — the tree's page/fit wins.
* **legacyonly** — a name present ONLY in the legacy dict; proves the fallback
  arm is reached when the tree misses.
* **dictD** — a legacy ``/Dests`` entry whose value is a ``{/D <array>}`` dict
  rather than a bare array. Upstream ``PDDocumentNameDestinationDictionary
  .getDestination`` dereferences ``/D`` (PDF spec: value is "either an array
  ... or a dictionary with a D entry"); both forms resolve.
* **barearray** — a legacy ``/Dests`` entry whose value is a bare array.
* **chaintree** — a name-tree leaf whose value is itself a named *string*
  (``string -> string`` chain). PDFBOX-5975: ``convertCOSToPD`` builds a
  ``PDNamedDestination`` which is not a ``PDPageDestination``, so it returns
  ``null`` — the chain is NOT followed recursively (one hop, then null).
* **chainlegacy** — a legacy ``/Dests`` entry whose value is a bare
  ``COSString``. ``getDestination`` only accepts an array or a dict-with-``/D``;
  a bare string yields ``null`` (again, no recursion).
* **missing** — a name registered nowhere; resolves to ``None``.

Each case is reduced to ``<label>\\t<pageIndex>\\t<typeName>\\t`` so pypdfbox
and Apache PDFBox compare byte-for-byte via the ``NamedDestEdgeProbe`` oracle.
The hard-literal assertions pass WITHOUT the oracle; the ``@requires_oracle``
test pins the differential.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

# Labels in the exact order both the probe and the Python resolver emit them.
_LABELS = [
    "precedence",
    "legacyonly",
    "dictD",
    "barearray",
    "chaintree",
    "chainlegacy",
    "missing",
]

# Oracle-confirmed literals (PDFBox 3.0.7). "<pageIndex>\t<typeName>".
_EXPECTED = {
    "precedence": (1, "XYZ"),  # name tree (page 1) shadows legacy (page 4)
    "legacyonly": (2, "XYZ"),  # legacy fallback reached
    "dictD": (3, "FitH"),  # legacy {/D <array>} dict accepted
    "barearray": (1, "FitV"),  # legacy bare array accepted
    "chaintree": (None, "null"),  # string->string in tree -> null (no recursion)
    "chainlegacy": (None, "null"),  # string->string in legacy -> null
    "missing": (None, "null"),  # unregistered name -> None
}


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _array(items: list) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _build_pdf(path: str) -> None:
    """Write a 5-page PDF wiring named destinations through every edge case."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(5)]
        for page in pages:
            doc.add_page(page)
        pc = [page.get_cos_object() for page in pages]
        catalog = doc.get_document_catalog().get_cos_object()

        # Legacy catalog /Dests flat dict.
        dests = COSDictionary()
        # precedence: legacy -> page 4 /Fit (must be SHADOWED by the tree).
        dests.set_item(_name("precedence"), _array([pc[4], _name("Fit")]))
        # legacyonly: only in legacy -> page 2 /XYZ.
        dests.set_item(
            _name("legacyonly"), _array([pc[2], _name("XYZ"), _i(50), _i(60), _i(2)])
        )
        # dictD: legacy value is a {/D <array>} dict -> page 3 /FitH.
        d_dict = COSDictionary()
        d_dict.set_item(_name("D"), _array([pc[3], _name("FitH"), _i(700)]))
        dests.set_item(_name("dictD"), d_dict)
        # barearray: legacy bare array -> page 1 /FitV.
        dests.set_item(_name("barearray"), _array([pc[1], _name("FitV"), _i(33)]))
        # chainlegacy: legacy value is a bare COSString (string -> string chain).
        dests.set_item(_name("chainlegacy"), COSString("legacyonly"))
        catalog.set_item(_name("Dests"), dests)

        # Modern /Names /Dests name tree (single flat leaf; entries lexical).
        leaf = COSDictionary()
        leaf.set_item(
            _name("Names"),
            _array(
                [
                    # chaintree (< "precedence"): leaf value is a named string.
                    COSString("chaintree"),
                    COSString("legacyonly"),
                    # precedence: tree -> page 1 /XYZ (wins over legacy /Fit).
                    COSString("precedence"),
                    _array([pc[1], _name("XYZ"), _i(10), _i(20), _i(1)]),
                ]
            ),
        )
        names_dict = COSDictionary()
        names_dict.set_item(_name("Dests"), leaf)
        catalog.set_item(_name("Names"), names_dict)

        doc.save(path)
    finally:
        doc.close()


def _resolve(catalog, name: str) -> str:
    """Reduce a resolved named destination to ``<pageIndex>\\t<typeName>\\t``."""
    dest = catalog.find_named_destination_page(PDNamedDestination(name))
    if dest is None:
        return "-1\tnull\t"
    cos = dest.get_cos_object()
    type_name = "null"
    if isinstance(cos, COSArray):
        t = cos.get_name(1)
        if t is not None:
            type_name = t
    return f"{dest.retrieve_page_number()}\t{type_name}\t"


@pytest.fixture(scope="module")
def edge_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_named_dest_edge.pdf")
    os.close(fd)
    _build_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


def test_edge_cases_resolve_to_pinned_literals(edge_pdf: Path) -> None:
    """Hard-literal regression (no oracle): every edge case resolves to its
    oracle-confirmed page index + fit type — name tree shadows legacy
    ``/Dests``, ``{/D <array>}`` and bare-array legacy entries both resolve,
    and ``string -> string`` chains return ``None`` (one hop, no recursion)."""
    doc = PDDocument.load(str(edge_pdf))
    try:
        catalog = doc.get_document_catalog()
        for label in _LABELS:
            page, type_name = _EXPECTED[label]
            dest = catalog.find_named_destination_page(PDNamedDestination(label))
            if page is None:
                assert dest is None, f"{label}: expected unresolved, got {dest!r}"
                continue
            assert dest is not None, f"{label}: expected page {page}, got None"
            assert dest.retrieve_page_number() == page, f"{label}: wrong page"
            assert dest.get_cos_object().get_name(1) == type_name, f"{label}: wrong fit"
    finally:
        doc.close()


def test_name_tree_shadows_legacy_dests(edge_pdf: Path) -> None:
    """When the same name lives in BOTH the modern name tree and the legacy
    ``/Dests`` dict, the name tree wins (upstream tries it first)."""
    doc = PDDocument.load(str(edge_pdf))
    try:
        catalog = doc.get_document_catalog()
        dest = catalog.find_named_destination_page(PDNamedDestination("precedence"))
        # Tree entry: page 1 /XYZ. Legacy entry would have been page 4 /Fit.
        assert dest is not None
        assert dest.retrieve_page_number() == 1
        assert dest.get_cos_object().get_name(1) == "XYZ"
    finally:
        doc.close()


def test_chained_named_destination_is_not_followed(edge_pdf: Path) -> None:
    """A named destination whose value is itself a named string resolves to
    ``None`` — upstream follows exactly one hop (PDFBOX-5975), never chasing
    the chain, whether the chain lives in the name tree or the legacy dict."""
    doc = PDDocument.load(str(edge_pdf))
    try:
        catalog = doc.get_document_catalog()
        assert (
            catalog.find_named_destination_page(PDNamedDestination("chaintree"))
            is None
        )
        assert (
            catalog.find_named_destination_page(PDNamedDestination("chainlegacy"))
            is None
        )
    finally:
        doc.close()


@requires_oracle
def test_edge_cases_match_pdfbox(edge_pdf: Path) -> None:
    """pypdfbox resolves every edge case — name-tree-over-legacy precedence,
    ``{/D <array>}`` vs bare-array legacy dispatch, and ``string -> string``
    non-recursion — to the SAME page index + fit type as Apache PDFBox."""
    java = run_probe_text("NamedDestEdgeProbe", str(edge_pdf))
    doc = PDDocument.load(str(edge_pdf))
    try:
        catalog = doc.get_document_catalog()
        py = "".join(f"{label}\t{_resolve(catalog, label)}\n" for label in _LABELS)
    finally:
        doc.close()
    assert py == java
    # Sanity: the oracle must actually exercise the precedence + chain arms.
    assert "precedence\t1\tXYZ\t" in java
    assert "dictD\t3\tFitH\t" in java
    assert "chaintree\t-1\tnull\t" in java
    assert "chainlegacy\t-1\tnull\t" in java
