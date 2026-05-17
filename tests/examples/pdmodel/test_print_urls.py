"""Coverage-boost tests for ``pypdfbox.examples.pdmodel.print_urls``.

Drives ``PrintURLs.main()`` against in-memory PDFs that carry
``PDAnnotationLink`` + ``PDActionURI`` pairs, exercising:

* the rotation==0 (page-coordinate flip) branch
* the rotation!=0 (no-op) branch
* the annotation without rectangle / without action skip branches
* ``get_action_uri()`` dispatch (URI action, missing action, non-URI
  action, AttributeError, raise-from-get_action)
* ``usage()`` writes to stderr
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdfbox.examples.pdmodel.print_urls import PrintURLs
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _make_link(uri: str, rect: PDRectangle | None) -> PDAnnotationLink:
    link = PDAnnotationLink()
    if rect is not None:
        link.set_rectangle(rect)
    action = PDActionURI()
    action.set_uri(uri)
    link.set_action(action)
    return link


def _save_doc_with_links(
    path: Path,
    annots: list[Any],
    rotation: int = 0,
) -> None:
    doc = PDDocument()
    page = PDPage()
    if rotation:
        page.set_rotation(rotation)
    doc.add_page(page)
    if annots:
        page.set_annotations(annots)
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# Constructor + module surface
# ---------------------------------------------------------------------------


def test_constructor_is_a_no_op() -> None:
    obj = PrintURLs()
    assert obj is not None


def test_usage_writes_to_stderr(capsys) -> None:
    PrintURLs.usage()
    err = capsys.readouterr().err
    assert "PrintURLs" in err
    assert "input-file" in err


# ---------------------------------------------------------------------------
# main() — usage branch
# ---------------------------------------------------------------------------


def test_main_usage_no_args(capsys) -> None:
    PrintURLs.main([])
    err = capsys.readouterr().err
    assert "PrintURLs" in err


def test_main_usage_none_argv(capsys) -> None:
    PrintURLs.main(None)
    err = capsys.readouterr().err
    assert "PrintURLs" in err


def test_main_usage_too_many_args(capsys) -> None:
    PrintURLs.main(["a", "b"])
    err = capsys.readouterr().err
    assert "PrintURLs" in err


# ---------------------------------------------------------------------------
# main() — URI annotations on a page with rotation == 0
# ---------------------------------------------------------------------------


def test_main_prints_uri_for_simple_link(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "urls.pdf"
    link = _make_link("http://example.com/", PDRectangle(50, 700, 100, 20))
    _save_doc_with_links(pdf, [link])

    PrintURLs.main([str(pdf)])
    out = capsys.readouterr().out
    assert "http://example.com/" in out
    assert "Page 1:" in out


def test_main_handles_multiple_links(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "multi.pdf"
    annots = [
        _make_link("https://one.test/", PDRectangle(10, 700, 50, 20)),
        _make_link("https://two.test/", PDRectangle(10, 650, 50, 20)),
    ]
    _save_doc_with_links(pdf, annots)
    PrintURLs.main([str(pdf)])
    out = capsys.readouterr().out
    assert "https://one.test/" in out
    assert "https://two.test/" in out


def test_main_handles_rotated_page(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "rotated.pdf"
    link = _make_link("http://rot.test/", PDRectangle(50, 700, 100, 20))
    _save_doc_with_links(pdf, [link], rotation=90)
    PrintURLs.main([str(pdf)])
    out = capsys.readouterr().out
    # The rotation != 0 branch is taken — coordinate flip is skipped.
    assert "http://rot.test/" in out


# ---------------------------------------------------------------------------
# main() — skip branches: no rectangle, no URI action
# ---------------------------------------------------------------------------


def test_main_skips_region_registration_when_no_rectangle(
    tmp_path: Path, capsys,
) -> None:
    pdf = tmp_path / "no_rect.pdf"
    # Build a link that lacks /Rect — the ``rect is None`` continue
    # branch in main() short-circuits region registration but the
    # second loop still emits the URI with an empty text region.
    link = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("http://norect.test/")
    link.set_action(action)
    _save_doc_with_links(pdf, [link])
    PrintURLs.main([str(pdf)])
    out = capsys.readouterr().out
    # The URI surfaces with an empty text region (no rectangle ->
    # ``get_text_for_region`` returns "").
    assert "http://norect.test/" in out
    assert "Page 1:''" in out


def test_main_skips_annotation_without_action(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "no_action.pdf"
    # PDAnnotationLink without /A — get_action() returns None.
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(50, 700, 100, 20))
    _save_doc_with_links(pdf, [link])
    PrintURLs.main([str(pdf)])
    out = capsys.readouterr().out
    # No URI was attached -> nothing printed.
    assert out == ""


def test_main_with_blank_page_produces_no_output(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "blank.pdf"
    _save_doc_with_links(pdf, [])
    PrintURLs.main([str(pdf)])
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# get_action_uri — dispatch matrix
# ---------------------------------------------------------------------------


def test_get_action_uri_returns_uri_for_action_uri() -> None:
    uri = PDActionURI()
    uri.set_uri("http://x.test/")

    class FakeAnnot:
        def get_action(self) -> Any:
            return uri

    result = PrintURLs.get_action_uri(FakeAnnot())
    assert isinstance(result, PDActionURI)
    assert result.get_uri() == "http://x.test/"


def test_get_action_uri_returns_none_when_action_is_none() -> None:
    class FakeAnnot:
        def get_action(self) -> Any:
            return None

    assert PrintURLs.get_action_uri(FakeAnnot()) is None


def test_get_action_uri_returns_none_for_non_uri_action() -> None:
    class FakeAnnot:
        def get_action(self) -> Any:
            return object()  # not a PDActionURI

    assert PrintURLs.get_action_uri(FakeAnnot()) is None


def test_get_action_uri_returns_none_when_no_get_action_method() -> None:
    class NoAction:
        pass

    assert PrintURLs.get_action_uri(NoAction()) is None


def test_get_action_uri_swallows_get_action_exceptions() -> None:
    class FakeAnnot:
        def get_action(self) -> Any:
            raise ValueError("boom")

    assert PrintURLs.get_action_uri(FakeAnnot()) is None


def test_get_action_uri_handles_runtime_error() -> None:
    class FakeAnnot:
        def get_action(self) -> Any:
            raise RuntimeError("Java-style broad catch parity")

    assert PrintURLs.get_action_uri(FakeAnnot()) is None
