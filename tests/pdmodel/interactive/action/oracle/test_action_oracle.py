"""Live Apache PDFBox differential parity for the interactive-action surface
(``pypdfbox.pdmodel.interactive.action`` + the link-annotation ``/A`` accessor).

Compares pypdfbox's canonical action dump against Apache PDFBox's, via the
``ActionProbe`` Java oracle. Every action found at the catalog ``/OpenAction``
and on each page's link-annotation ``/A`` is reduced to one canonical line so
the two languages compare byte-for-byte without tripping over object layout or
float rendering.

Canonical line grammar (must match ``oracle/probes/ActionProbe.java``)::

    <location>\t<subtype>\t<salient>

where ``location`` is ``openaction`` for the catalog action, then
``page<p>.link<i>`` for the i-th link annotation of page p (links counted in
``/Annots`` order, non-link annotations skipped); ``subtype`` is the action's
``/S`` name; and ``salient`` is the target-identifying field per subtype:

  * URI    -> ``uri=<URI string>``
  * GoTo   -> ``dest=<resolved destination>``
  * GoToR  -> ``file=<F text>;dest=<resolved destination>``
  * Launch -> ``file=<F file-spec text>;dest=<D launch command>``
  * Named  -> ``name=<N>``
  * other  -> ``""``

A destination resolves to ``page<index>`` (0-based, via ``retrievePageNumber``),
``named:<name>``, or ``none``.

No fixture PDF in ``tests/fixtures`` carries uncompressed action dictionaries
the harness can find by grep, so the primary fixture is built in-process by
pypdfbox: a URI link, a GoTo link (explicit page destination), a Named link, a
GoToR link (remote file + named destination), plus a catalog ``/OpenAction``
GoTo. It is saved once and diffed against both libraries. Any fixture PDFs that
do happen to carry actions are also swept.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSBase
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"


# --------------------------------------------------------------------------
# Python reproduction of ActionProbe.java
# --------------------------------------------------------------------------


def _escape(s: str | None) -> str:
    """Mirror ``ActionProbe.escape`` exactly."""
    if s is None:
        return "null"
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _resolve_dest(dest: object) -> str:
    """Mirror ``ActionProbe.resolveDest``.

    ``dest`` may be a :class:`PDDestination` (named or explicit page), a bare
    ``str`` (pypdfbox's ``PDActionGoTo.get_destination`` returns the raw name
    for the string/name form rather than a :class:`PDNamedDestination` wrapper
    — re-wrap so the named arm fires, matching upstream Java), or ``None``.
    """
    if isinstance(dest, str):
        dest = PDNamedDestination(dest)
    if dest is None:
        return "none"
    if isinstance(dest, PDNamedDestination):
        n = dest.get_named_destination()
        return "named:" + ("" if n is None else n)
    if isinstance(dest, PDPageDestination):
        return "page" + str(dest.retrieve_page_number())
    return "none"


def _file_text(fs: PDFileSpecification | None) -> str | None:
    return None if fs is None else fs.get_file()


def _null_to_empty(s: str | None) -> str:
    return "" if s is None else s


def _salient(action: PDAction) -> str:
    """Mirror ``ActionProbe.salient``."""
    if isinstance(action, PDActionURI):
        uri = action.get_uri()
        return "uri=" + ("" if uri is None else uri)
    if isinstance(action, PDActionGoTo):
        return "dest=" + _resolve_dest(action.get_destination())
    if isinstance(action, PDActionRemoteGoTo):
        d: COSBase | None = action.get_d()
        return (
            "file="
            + _null_to_empty(_file_text(action.get_file_specification()))
            + ";dest="
            + _resolve_dest(PDDestination.create(d))
        )
    if isinstance(action, PDActionLaunch):
        return (
            "file="
            + _null_to_empty(_file_text(action.get_file()))
            + ";dest="
            + _null_to_empty(action.get_d())
        )
    if isinstance(action, PDActionNamed):
        n = action.get_n()
        return "name=" + ("" if n is None else n)
    return ""


def _emit(lines: list[str], location: str, action: PDAction) -> None:
    subtype = action.get_sub_type()
    lines.append(
        f"{location}\t{'null' if subtype is None else _escape(subtype)}"
        f"\t{_escape(_salient(action))}"
    )


def _dump_actions(doc: PDDocument) -> str:
    catalog = doc.get_document_catalog()
    lines: list[str] = []

    open_action = catalog.get_open_action()
    if isinstance(open_action, PDAction):
        _emit(lines, "openaction", open_action)

    pages = doc.get_pages()
    for p in range(pages.get_count()):
        page = pages.get(p)
        link_index = 0
        for annot in page.get_annotations():
            if not isinstance(annot, PDAnnotationLink):
                continue
            action = annot.get_action()
            if action is not None:
                _emit(lines, f"page{p}.link{link_index}", action)
            link_index += 1

    # ActionProbe terminates every line with '\n'.
    return "".join(line + "\n" for line in lines)


# --------------------------------------------------------------------------
# Built fixture: URI + GoTo + Named + GoToR links + OpenAction GoTo
# --------------------------------------------------------------------------


def _build_action_pdf(out: Path) -> None:
    doc = PDDocument()
    try:
        page0 = PDPage()
        page1 = PDPage()
        doc.add_page(page0)
        doc.add_page(page1)

        # Catalog /OpenAction: a GoTo to page 1 (Fit).
        open_dest = PDPageFitDestination()
        open_dest.set_page(page1)
        open_go = PDActionGoTo()
        open_go.set_destination(open_dest)
        doc.get_document_catalog().set_open_action(open_go)

        # page0.link0: URI action.
        uri_link = PDAnnotationLink()
        uri_action = PDActionURI()
        uri_action.set_uri("https://example.com/path?q=1")
        uri_link.set_action(uri_action)

        # page0.link1: GoTo action to page 1 (explicit page destination).
        goto_dest = PDPageFitDestination()
        goto_dest.set_page(page1)
        goto_action = PDActionGoTo()
        goto_action.set_destination(goto_dest)
        goto_link = PDAnnotationLink()
        goto_link.set_action(goto_action)

        # page0.link2: Named action.
        named_action = PDActionNamed()
        named_action.set_n(PDActionNamed.NAMED_ACTION_NEXT_PAGE)
        named_link = PDAnnotationLink()
        named_link.set_action(named_action)

        # page0.link3: GoToR action (remote file + named destination).
        gotor_action = PDActionRemoteGoTo()
        gotor_action.set_file("other.pdf")
        gotor_action.set_named_destination("Chapter2")
        gotor_link = PDAnnotationLink()
        gotor_link.set_action(gotor_action)

        page0.set_annotations([uri_link, goto_link, named_link, gotor_link])

        # page1.link0: GoTo back to page 0.
        back_dest = PDPageFitDestination()
        back_dest.set_page(page0)
        back_action = PDActionGoTo()
        back_action.set_destination(back_dest)
        back_link = PDAnnotationLink()
        back_link.set_action(back_action)
        page1.set_annotations([back_link])

        doc.save(str(out))
    finally:
        doc.close()


@pytest.fixture(scope="module")
def action_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("action_oracle") / "actions.pdf"
    _build_action_pdf(out)
    return out


@requires_oracle
def test_built_action_dump_matches_pdfbox(action_pdf: Path) -> None:
    """A pypdfbox-built PDF with URI/GoTo/Named/GoToR links + OpenAction
    dumps identically under pypdfbox and Apache PDFBox."""
    java = run_probe_text("ActionProbe", str(action_pdf))
    doc = PDDocument.load(str(action_pdf))
    try:
        py = _dump_actions(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the fixture must actually exercise the five action subtypes.
    assert "\tURI\turi=https://example.com/path?q=1" in java
    assert "openaction\tGoTo\tdest=page1" in java
    assert "\tNamed\tname=NextPage" in java
    assert "\tGoToR\tfile=other.pdf;dest=named:Chapter2" in java
    assert "\tGoTo\tdest=page0" in java


# --------------------------------------------------------------------------
# Sweep any fixture PDFs that happen to carry actions.
# --------------------------------------------------------------------------


def _has_actions(pdf: Path) -> bool:
    try:
        doc = PDDocument.load(str(pdf))
    except Exception:
        return False
    try:
        return bool(_dump_actions(doc))
    except Exception:
        return False
    finally:
        doc.close()


def _discover_action_fixtures() -> list[Path]:
    pdfs = sorted(_FIXTURES.rglob("*.pdf"))
    return [p for p in pdfs if _has_actions(p)]


_ACTION_FIXTURES = _discover_action_fixtures()
_FIXTURE_IDS = [str(p.relative_to(_FIXTURES)) for p in _ACTION_FIXTURES]


@requires_oracle
@pytest.mark.parametrize("fixture", _ACTION_FIXTURES, ids=_FIXTURE_IDS)
def test_fixture_action_dump_matches_pdfbox(fixture: Path) -> None:
    """pypdfbox's action dump equals PDFBox's across fixtures with actions."""
    java = run_probe_text("ActionProbe", str(fixture))
    doc = PDDocument.load(str(fixture))
    try:
        py = _dump_actions(doc)
    finally:
        doc.close()
    assert py == java
