"""Live Apache PDFBox differential parity for the interactive-action surface
(``pypdfbox.pdmodel.interactive.action`` + the link-annotation ``/A`` accessor).

Compares pypdfbox's canonical action dump against Apache PDFBox's, via the
``ActionProbe`` Java oracle. Every action found at the catalog ``/OpenAction``
and on each page's link-annotation ``/A`` is reduced to one canonical line so
the two languages compare byte-for-byte without tripping over object layout or
float rendering.

Canonical line grammar (must match ``oracle/probes/ActionProbe.java``)::

    <location>\t<subtype>\t<salient>\t<next>

where ``location`` is ``openaction`` for the catalog action, then
``page<p>.link<i>`` for the i-th link annotation of page p (links counted in
``/Annots`` order, non-link annotations skipped); ``subtype`` is the action's
``/S`` name; ``salient`` is the target-identifying field per subtype; and
``next`` carries the ``/Next`` action chain:

  * URI        -> ``uri=<URI string>``
  * GoTo       -> ``dest=<resolved destination>``
  * GoToR      -> ``file=<F text>;dest=<resolved destination>``
  * Launch     -> ``file=<F file-spec text>;dest=<D launch command>``
  * Named      -> ``name=<N>``
  * JavaScript -> ``js=<JS source, decoded from string OR stream>``
  * SubmitForm -> ``url=<F text>;flags=<Flags>;fields=<Fields count>``
  * ResetForm  -> ``flags=<Flags>;fields=<Fields count>``
  * other      -> ``""``

A destination resolves to ``page<index>`` (0-based, via ``retrievePageNumber``),
``named:<name>``, or ``none``. The ``next`` column is ``next=<len>`` for an
empty/absent ``/Next`` and ``next=<len>:<sub0>,<sub1>,...`` when present
(``PDAction.get_next`` normalises the single-dict and array forms).

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

from pypdfbox.cos import COSArray, COSBase, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import (
    PDActionJavaScript,
)
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_reset_form import (
    PDActionResetForm,
)
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
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


def _array_size(array: object) -> int:
    """Mirror ``ActionProbe.arraySize``: element count, or ``-1`` when absent.

    pypdfbox's ``get_cos_fields`` / ``get_fields`` return the raw ``COSArray``
    (or ``None``) — the upstream ``getFields()`` shape — so ``.size()`` lines
    up with the Java ``COSArray.size()`` the probe calls.
    """
    return -1 if array is None else array.size()  # type: ignore[attr-defined]


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
    if isinstance(action, PDActionJavaScript):
        js = action.get_action()
        return "js=" + ("" if js is None else js)
    if isinstance(action, PDActionSubmitForm):
        return (
            "url="
            + _null_to_empty(_file_text(action.get_file()))
            + ";flags="
            + str(action.get_flags())
            + ";fields="
            + str(_array_size(action.get_cos_fields()))
        )
    if isinstance(action, PDActionResetForm):
        return (
            "flags="
            + str(action.get_flags())
            + ";fields="
            + str(_array_size(action.get_fields()))
        )
    return ""


def _next_chain(action: PDAction) -> str:
    """Mirror ``ActionProbe.nextChain``: ``next=<len>[:<sub0>,<sub1>,...]``."""
    nxt = action.get_next()
    if not nxt:
        return "next=0"
    subs = ",".join(
        "null" if a.get_sub_type() is None else a.get_sub_type() for a in nxt
    )
    return f"next={len(nxt)}:{subs}"


def _emit(lines: list[str], location: str, action: PDAction) -> None:
    subtype = action.get_sub_type()
    lines.append(
        f"{location}\t{'null' if subtype is None else _escape(subtype)}"
        f"\t{_escape(_salient(action))}"
        f"\t{_escape(_next_chain(action))}"
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

        # page0.link4: JavaScript action (string-form /JS).
        js_action = PDActionJavaScript("app.alert('hi');")
        js_link = PDAnnotationLink()
        js_link.set_action(js_action)

        # page0.link5: SubmitForm action — URL + flags + two named fields.
        submit_action = PDActionSubmitForm()
        submit_action.set_url("https://example.com/submit")
        submit_action.set_flags(PDActionSubmitForm.FLAG_EXPORT_FORMAT)
        submit_fields = COSArray()
        submit_fields.add(COSString("field.a"))
        submit_fields.add(COSString("field.b"))
        submit_action.set_fields(submit_fields)
        submit_link = PDAnnotationLink()
        submit_link.set_action(submit_action)

        # page0.link6: ResetForm action — flags + one named field.
        reset_action = PDActionResetForm()
        reset_action.set_flags(PDActionResetForm.FLAG_INCLUDE_EXCLUDE)
        reset_fields = COSArray()
        reset_fields.add(COSString("field.a"))
        reset_action.set_fields(reset_fields)
        reset_link = PDAnnotationLink()
        reset_link.set_action(reset_action)

        # page0.link7: a URI action carrying a /Next chain of two actions
        # (a Named action followed by a ResetForm action). PDAction.get_next
        # must walk both, normalising the single-or-array /Next form.
        chained_action = PDActionURI()
        chained_action.set_uri("https://example.com/chained")
        next_named = PDActionNamed()
        next_named.set_n(PDActionNamed.NAMED_ACTION_FIRST_PAGE)
        next_reset = PDActionResetForm()
        chained_action.set_next([next_named, next_reset])
        chained_link = PDAnnotationLink()
        chained_link.set_action(chained_action)

        page0.set_annotations(
            [
                uri_link,
                goto_link,
                named_link,
                gotor_link,
                js_link,
                submit_link,
                reset_link,
                chained_link,
            ]
        )

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
    # Sanity: the fixture must actually exercise every action subtype, the
    # type-specific salient fields, AND the /Next chain column.
    assert "\tURI\turi=https://example.com/path?q=1\tnext=0" in java
    assert "openaction\tGoTo\tdest=page1\tnext=0" in java
    assert "\tNamed\tname=NextPage\tnext=0" in java
    assert "\tGoToR\tfile=other.pdf;dest=named:Chapter2\tnext=0" in java
    assert "\tGoTo\tdest=page0\tnext=0" in java
    # JavaScript: string-form /JS round-trips its source.
    assert "\tJavaScript\tjs=app.alert('hi');\tnext=0" in java
    # SubmitForm: /F URL + /Flags + /Fields element count.
    submit_flag = PDActionSubmitForm.FLAG_EXPORT_FORMAT
    assert (
        f"\tSubmitForm\turl=https://example.com/submit;flags={submit_flag};fields=2\tnext=0"
        in java
    )
    # ResetForm: /Flags + /Fields element count.
    reset_flag = PDActionResetForm.FLAG_INCLUDE_EXCLUDE
    assert f"\tResetForm\tflags={reset_flag};fields=1\tnext=0" in java
    # /Next chain: a URI action followed by Named + ResetForm.
    assert (
        "\tURI\turi=https://example.com/chained\tnext=2:Named,ResetForm" in java
    )


def _collect_link_actions(doc: PDDocument) -> dict[str, PDAction]:
    """Index page-0 link actions by their ``/S`` subtype for round-trip checks.

    The chained URI is keyed ``URI.next`` so it doesn't collide with the plain
    URI action; everything else is keyed by bare subtype.
    """
    by_subtype: dict[str, PDAction] = {}
    page0 = doc.get_pages().get(0)
    for annot in page0.get_annotations():
        if not isinstance(annot, PDAnnotationLink):
            continue
        action = annot.get_action()
        if action is None:
            continue
        key = action.get_sub_type() or "null"
        if key == "URI" and action.get_next():
            key = "URI.next"
        by_subtype[key] = action
    return by_subtype


@requires_oracle
def test_built_action_accessor_round_trip(action_pdf: Path) -> None:
    """Build via pypdfbox, save once, reload via pypdfbox: every type-specific
    accessor returns the value that was written, and the /Next chain is walked.

    PDFBox parity for the same saved bytes is proven by
    :func:`test_built_action_dump_matches_pdfbox`; this asserts the pypdfbox
    accessor surface directly so a silent dispatch/accessor regression is
    caught at the field level, not just the canonical-line level.
    """
    doc = PDDocument.load(str(action_pdf))
    try:
        actions = _collect_link_actions(doc)

        uri = actions["URI"]
        assert isinstance(uri, PDActionURI)
        assert uri.get_uri() == "https://example.com/path?q=1"

        named = actions["Named"]
        assert isinstance(named, PDActionNamed)
        assert named.get_n() == PDActionNamed.NAMED_ACTION_NEXT_PAGE

        js = actions["JavaScript"]
        assert isinstance(js, PDActionJavaScript)
        assert js.get_action() == "app.alert('hi');"
        assert js.is_string_payload()

        submit = actions["SubmitForm"]
        assert isinstance(submit, PDActionSubmitForm)
        assert submit.get_url() == "https://example.com/submit"
        assert submit.get_flags() == PDActionSubmitForm.FLAG_EXPORT_FORMAT
        assert submit.is_export_format()
        submit_fields = submit.get_cos_fields()
        assert submit_fields is not None
        assert submit_fields.size() == 2

        reset = actions["ResetForm"]
        assert isinstance(reset, PDActionResetForm)
        assert reset.get_flags() == PDActionResetForm.FLAG_INCLUDE_EXCLUDE
        assert reset.is_exclude()
        reset_fields = reset.get_fields()
        assert reset_fields is not None
        assert reset_fields.size() == 1

        # /Next chain: URI -> [Named(FirstPage), ResetForm].
        chained = actions["URI.next"]
        assert chained.get_uri() == "https://example.com/chained"
        chain = chained.get_next()
        assert chain is not None
        assert [a.get_sub_type() for a in chain] == ["Named", "ResetForm"]
        head = chain[0]
        assert isinstance(head, PDActionNamed)
        assert head.get_n() == PDActionNamed.NAMED_ACTION_FIRST_PAGE
        assert isinstance(chain[1], PDActionResetForm)
    finally:
        doc.close()


@requires_oracle
def test_javascript_stream_payload_matches_pdfbox(tmp_path: Path) -> None:
    """``/JS`` stored as a ``COSStream`` (not a ``COSString``) must decode to
    the same source under pypdfbox and PDFBox. PDF 32000-1 §12.6.4.16 permits
    both forms; large scripts are usually streams. Guards the stream-vs-string
    branch in ``PDActionJavaScript.get_action`` against silent divergence."""
    out = tmp_path / "js_stream.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        js = PDActionJavaScript()
        stream = doc.get_document().create_cos_stream()
        body = stream.create_output_stream()
        body.write(b'app.alert("streamed");')
        body.close()
        js.get_cos_object().set_item(COSName.get_pdf_name("JS"), stream)
        link = PDAnnotationLink()
        link.set_action(js)
        page.set_annotations([link])
        doc.save(str(out))
    finally:
        doc.close()

    java = run_probe_text("ActionProbe", str(out))
    reloaded = PDDocument.load(str(out))
    try:
        py = _dump_actions(reloaded)
        action = reloaded.get_pages().get(0).get_annotations()[0].get_action()
        assert isinstance(action, PDActionJavaScript)
        assert action.is_stream_payload()
        assert action.get_action() == 'app.alert("streamed");'
    finally:
        reloaded.close()
    assert py == java
    assert '\tJavaScript\tjs=app.alert("streamed");\tnext=0' in java


@requires_oracle
def test_single_next_dict_walked_as_chain(tmp_path: Path) -> None:
    """A ``/Next`` stored as a single action dictionary (not an array) must be
    walked by both libraries as a length-1 chain. PDFBox normalises the
    single-dict and array forms; pypdfbox's ``get_next`` must agree.

    This builds the single-dict form directly on the COS dictionary so the
    saved bytes carry ``/Next`` as a dictionary, then diffs the canonical dump.
    """
    out = tmp_path / "single_next.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        uri = PDActionURI()
        uri.set_uri("https://example.com/single")
        nxt = PDActionNamed()
        nxt.set_n(PDActionNamed.NAMED_ACTION_LAST_PAGE)
        # Store /Next as a single dictionary, not an array.
        uri.get_cos_object().set_item(
            COSName.get_pdf_name("Next"), nxt.get_cos_object()
        )
        link = PDAnnotationLink()
        link.set_action(uri)
        page.set_annotations([link])
        doc.save(str(out))
    finally:
        doc.close()

    java = run_probe_text("ActionProbe", str(out))
    reloaded = PDDocument.load(str(out))
    try:
        py = _dump_actions(reloaded)
    finally:
        reloaded.close()
    assert py == java
    assert "\tURI\turi=https://example.com/single\tnext=1:Named" in java


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
