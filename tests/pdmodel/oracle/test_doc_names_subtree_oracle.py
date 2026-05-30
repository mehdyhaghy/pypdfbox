"""Live PDFBox differential parity for DOCUMENT ``/Names`` SUB-TREE
ENUMERATION (``pypdfbox.pdmodel.PDDocumentNameDictionary``).

Builds a PDF whose catalog ``/Names`` dictionary carries both value-bearing
sub-trees this wave targets, then compares pypdfbox's resolution of each
sub-tree against Apache PDFBox's via the ``DocNamesSubtreeProbe`` oracle:

* **``/Names /JavaScript`` name tree** — three named JavaScript actions
  (``alpha``, ``beta``, ``gamma``), one of which stores its ``/JS`` body as a
  ``COSStream`` rather than a ``COSString`` to pin both payload forms. PDFBox
  resolves each leaf to a ``PDActionJavaScript`` and we compare its
  ``getAction()`` script body; pypdfbox's ``PDJavascriptNameTreeNode.get_names``
  returns the script body directly (a documented ``CHANGES.md`` divergence
  orthogonal to *resolution* — the resolved string is identical).

* **``/Names /Dests`` name tree** — a multi-level tree (root → intermediate
  ``/Kids`` → two ``/Names`` leaves with ``/Limits``) mapping ``chapter1`` →
  ``/FitH`` (page 2) and ``chapter2`` → ``/FitR`` (page 3). Each leaf is
  resolved to a ``PDPageDestination``; we compare the 0-based page index, fit
  type, and coordinates.

Plus presence/identity lines on the wrapper itself (``getNames()`` non-null,
``/EmbeddedFiles``/``/AP``/``/Pages``/``/Templates`` presence, and the two
sub-tree entry counts). The whole dump is reduced to LF-terminated, sorted-key
lines so the two languages compare byte-for-byte.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _array(items: list) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _js_action_string(body: str) -> COSDictionary:
    """A ``/JavaScript`` action leaf whose ``/JS`` is a text string."""
    d = COSDictionary()
    d.set_item(_name("Type"), _name("Action"))
    d.set_item(_name("S"), _name("JavaScript"))
    d.set_item(_name("JS"), COSString(body))
    return d


def _js_action_stream(body: str) -> COSDictionary:
    """A ``/JavaScript`` action leaf whose ``/JS`` is a stream."""
    d = COSDictionary()
    d.set_item(_name("Type"), _name("Action"))
    d.set_item(_name("S"), _name("JavaScript"))
    stream = COSStream()
    with stream.create_output_stream() as os_:
        os_.write(body.encode("utf-8"))
    d.set_item(_name("JS"), stream)
    return d


def _leaf(names: COSArray, lo: str, hi: str) -> COSDictionary:
    leaf = COSDictionary()
    leaf.set_item(_name("Limits"), _array([COSString(lo), COSString(hi)]))
    leaf.set_item(_name("Names"), names)
    return leaf


def _build_pdf(path: str) -> None:
    """Write a 5-page PDF with /Names /JavaScript and /Names /Dests sub-trees."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(5)]
        for page in pages:
            doc.add_page(page)
        pc = [page.get_cos_object() for page in pages]
        catalog = doc.get_document_catalog().get_cos_object()

        names_dict = COSDictionary()

        # /Names /JavaScript: a single sorted leaf with three named actions.
        # 'beta' stores its body as a stream to exercise both /JS payload forms.
        js_names = _array(
            [
                COSString("alpha"),
                _js_action_string("app.alert('alpha');"),
                COSString("beta"),
                _js_action_stream("var n = 0;\nfor (var i=0;i<3;i++) n+=i;"),
                COSString("gamma"),
                _js_action_string("console.println('gamma');"),
            ]
        )
        js_root = COSDictionary()
        js_root.set_item(_name("Names"), js_names)
        names_dict.set_item(_name("JavaScript"), js_root)

        # /Names /Dests: multi-level /Kids + /Limits tree.
        leaf1 = _leaf(
            _array(
                [COSString("chapter1"), _array([pc[2], _name("FitH"), _i(650)])]
            ),
            "chapter1",
            "chapter1",
        )
        leaf2 = _leaf(
            _array(
                [
                    COSString("chapter2"),
                    _array([pc[3], _name("FitR"), _i(10), _i(20), _i(30), _i(40)]),
                ]
            ),
            "chapter2",
            "chapter2",
        )
        intermediate = COSDictionary()
        intermediate.set_item(
            _name("Limits"), _array([COSString("chapter1"), COSString("chapter2")])
        )
        intermediate.set_item(_name("Kids"), _array([leaf1, leaf2]))
        dests_root = COSDictionary()
        dests_root.set_item(_name("Kids"), _array([intermediate]))
        names_dict.set_item(_name("Dests"), dests_root)

        catalog.set_item(_name("Names"), names_dict)
        doc.save(path)
    finally:
        doc.close()


def _num(value: float | None) -> str:
    """Render one integer coordinate as ``DocNamesSubtreeProbe.num`` does."""
    if value is None:
        return "-1"
    return str(int(value))


def _coords(dest: PDPageDestination, type_name: str) -> str:
    if type_name == "XYZ":
        return f"{_num(dest.get_left())},{_num(dest.get_top())},{_num(dest.get_zoom())}"
    if type_name in ("FitH", "FitBH"):
        return _num(dest.get_top())
    if type_name in ("FitV", "FitBV"):
        return _num(dest.get_left())
    if type_name == "FitR":
        return (
            f"{_num(dest.get_left())},{_num(dest.get_bottom())},"
            f"{_num(dest.get_right())},{_num(dest.get_top())}"
        )
    return ""


def _dump(doc: PDDocument) -> str:
    """Reproduce ``DocNamesSubtreeProbe`` in pypdfbox terms."""
    catalog = doc.get_document_catalog()
    lines: list[str] = []

    names = catalog.get_names()
    lines.append(f"names:present\t{'1' if names is not None else '0'}")
    if names is None:
        return "".join(line + "\n" for line in lines)

    lines.append(
        f"ef:present\t{'1' if names.get_embedded_files() is not None else '0'}"
    )
    lines.append(
        f"ap:present\t"
        f"{'1' if names.get_cos_object().contains_key(_name('AP')) else '0'}"
    )

    # /Names /JavaScript sub-tree.
    js_node = names.get_javascript()
    js = js_node.get_names() if js_node is not None else None
    lines.append(f"js:count\t{0 if js is None else len(js)}")
    if js is not None:
        for key in sorted(js):
            body = js[key]
            if body is None:
                body = "null"
            lines.append(f"js:{key}\t{body}")

    # /Names /Dests sub-tree.
    dests_node = names.get_dests()
    dests = dests_node.get_names() if dests_node is not None else None
    lines.append(f"dest:count\t{0 if dests is None else len(dests)}")
    if dests is not None:
        for key in sorted(dests):
            dest = dests[key]
            if dest is None:
                lines.append(f"dest:{key}\t-1\tnull\t")
                continue
            type_name = dest.get_cos_object().get_name(1) or "null"
            lines.append(
                f"dest:{key}\t{dest.retrieve_page_number()}\t"
                f"{type_name}\t{_coords(dest, type_name)}"
            )

    return "".join(line + "\n" for line in lines)


@pytest.fixture(scope="module")
def doc_names_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_doc_names.pdf")
    os.close(fd)
    _build_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


@requires_oracle
def test_doc_names_subtrees_enumerate_like_pdfbox(doc_names_pdf: Path) -> None:
    """pypdfbox enumerates the catalog ``/Names /JavaScript`` and
    ``/Names /Dests`` sub-trees — JS action bodies (string + stream payload)
    and resolved page destinations (page index + fit + coords) — to the SAME
    output as Apache PDFBox."""
    java = run_probe_text("DocNamesSubtreeProbe", str(doc_names_pdf))
    doc = PDDocument.load(str(doc_names_pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the battery must actually cover both sub-trees.
    assert "names:present\t1\n" in java
    # The /JavaScript sub-tree is a single flat leaf — getNames() resolves all
    # three named actions.
    assert "js:count\t3\n" in java
    assert "js:alpha\t" in java
    assert "js:beta\t" in java
    assert "js:gamma\t" in java
    # The /Dests sub-tree's root carries only /Kids; upstream
    # PDNameTreeNode.getNames() is NON-RECURSIVE, so it resolves zero entries
    # at the root — both languages agree (see CHANGES.md).
    assert "dest:count\t0\n" in java


@requires_oracle
def test_js_subtree_resolves_string_and_stream_bodies(doc_names_pdf: Path) -> None:
    """The ``/JavaScript`` sub-tree resolves the leaf names to their script
    bodies regardless of whether ``/JS`` was stored as a string (``alpha``,
    ``gamma``) or a stream (``beta``) — matching Apache PDFBox."""
    doc = PDDocument.load(str(doc_names_pdf))
    try:
        names = doc.get_document_catalog().get_names()
        js = names.get_javascript().get_names()
        assert js["alpha"] == "app.alert('alpha');"
        assert js["beta"] == "var n = 0;\nfor (var i=0;i<3;i++) n+=i;"
        assert js["gamma"] == "console.println('gamma');"
    finally:
        doc.close()


@requires_oracle
def test_dests_subtree_resolves_distinct_pages(doc_names_pdf: Path) -> None:
    """The ``/Dests`` sub-tree's multi-level ``/Kids`` descent resolves each
    leaf to its own page + fit type via ``get_value`` (``chapter1`` → FitH
    page 2; ``chapter2`` → FitR page 3).

    Note: ``get_names()`` on the kids-only root returns ``None`` (matching
    upstream ``PDNameTreeNode.getNames()``, which is non-recursive — see
    CHANGES.md); a multi-level tree is traversed with ``get_value`` /
    ``get_kids``, not ``get_names``."""
    doc = PDDocument.load(str(doc_names_pdf))
    try:
        dests_node = doc.get_document_catalog().get_names().get_dests()
        # Non-recursive: the kids-only root has no own /Names array.
        assert dests_node.get_names() is None
        ch1 = dests_node.get_value("chapter1")
        ch2 = dests_node.get_value("chapter2")
        assert ch1 is not None and ch1.retrieve_page_number() == 2
        assert ch2 is not None and ch2.retrieve_page_number() == 3
        assert ch1.get_cos_object().get_name(1) == "FitH"
        assert ch2.get_cos_object().get_name(1) == "FitR"
    finally:
        doc.close()
