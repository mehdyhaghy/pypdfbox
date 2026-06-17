"""Live Apache PDFBox differential parity for the *secondary* interactive-action
accessor surface — the per-subtype boolean / sub-dictionary / tri-state
accessors that :mod:`tests...oracle.test_action_oracle` deliberately leaves out
(that probe covers the salient target + ``/Next`` chain only).

Compares pypdfbox's accessor dump against Apache PDFBox's via the
``ActionAccessorProbe`` Java oracle. The surface under test:

  * the action's class simple-name (``PDActionFactory`` dispatch result):
    ``type(action).__name__`` must equal Java ``getClass().getSimpleName()``;
  * ``URI`` -> ``shouldTrackMousePosition()`` (the ``/IsMap`` boolean);
  * ``GoToR`` -> ``getOpenInNewWindow()`` (the ``OpenMode`` tri-state over
    ``/NewWindow``);
  * ``Launch`` -> ``getOpenInNewWindow()`` (``OpenMode``) plus the ``/Win``
    sub-dict params (filename / directory / operation / execute-param);
  * ``/AA`` placement: a page's additional-action ``/O`` (open) and ``/C``
    (close) actions are dispatched and dumped exactly like a link ``/A`` action,
    proving the same factory path serves both annotation ``/A`` and dict
    ``/AA``.

Canonical line grammar (must match ``oracle/probes/ActionAccessorProbe.java``)::

    <location>\t<class>\t<accessors>

where ``location`` is ``page<p>.link<i>`` for the i-th link annotation of page
p, then ``page<p>.aa.O`` / ``page<p>.aa.C`` for the page ``/AA`` actions;
``class`` is the action's class simple-name; and ``accessors`` is a
``;``-joined ``key=value`` list per class (see the probe docstring). The fixture
is built in-process by pypdfbox, saved once, and diffed against both libraries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------
# Python reproduction of ActionAccessorProbe.java
# --------------------------------------------------------------------------


def _escape(s: str | None) -> str:
    """Mirror ``ActionAccessorProbe.escape`` exactly."""
    if s is None:
        return "null"
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _win_text(s: str | None) -> str:
    return "null" if s is None else s


def _accessors(action: PDAction) -> str:
    """Mirror ``ActionAccessorProbe.accessors``."""
    if isinstance(action, PDActionURI):
        # Python ``True``/``False`` lower-cased to match Java's boolean
        # ``String.valueOf`` rendering ("true"/"false").
        return "ismap=" + ("true" if action.should_track_mouse_position() else "false")
    if isinstance(action, PDActionRemoteGoTo):
        return "newwindow=" + action.get_open_in_new_window().name
    if isinstance(action, PDActionLaunch):
        win = action.get_win_launch_params()
        return (
            "newwindow="
            + action.get_open_in_new_window_mode().name
            + ";win.file="
            + _win_text(None if win is None else win.get_filename())
            + ";win.dir="
            + _win_text(None if win is None else win.get_directory())
            + ";win.op="
            + _win_text(None if win is None else win.get_operation())
            + ";win.param="
            + _win_text(None if win is None else win.get_execute_param())
        )
    return ""


def _class_name(action: PDAction) -> str:
    """``type(action).__name__`` — the pypdfbox dispatch result.

    pypdfbox class names mirror upstream verbatim (e.g. ``PDActionURI``), so
    this equals Java ``getClass().getSimpleName()`` element-for-element.
    """
    return type(action).__name__


def _emit(lines: list[str], location: str, action: PDAction) -> None:
    lines.append(
        f"{location}\t{_escape(_class_name(action))}\t{_escape(_accessors(action))}"
    )


def _dump_accessors(doc: PDDocument) -> str:
    lines: list[str] = []
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
        aa = page.get_actions()
        if aa is not None:
            o = aa.get_o()
            if o is not None:
                _emit(lines, f"page{p}.aa.O", o)
            c = aa.get_c()
            if c is not None:
                _emit(lines, f"page{p}.aa.C", c)
    return "".join(line + "\n" for line in lines)


# --------------------------------------------------------------------------
# Built fixture
# --------------------------------------------------------------------------


def _build_accessor_pdf(out: Path) -> None:
    doc = PDDocument()
    try:
        page0 = PDPage()
        doc.add_page(page0)

        # link0: URI with /IsMap true (shouldTrackMousePosition).
        uri_map = PDActionURI()
        uri_map.set_uri("https://example.com/map")
        uri_map.set_track_mouse_position(True)
        uri_map_link = PDAnnotationLink()
        uri_map_link.set_action(uri_map)

        # link1: URI without /IsMap (default false).
        uri_plain = PDActionURI()
        uri_plain.set_uri("https://example.com/plain")
        uri_plain_link = PDAnnotationLink()
        uri_plain_link.set_action(uri_plain)

        # link2: GoToR with /NewWindow explicitly true -> OpenMode.NEW_WINDOW.
        gotor_new = PDActionRemoteGoTo()
        gotor_new.set_file("remote_new.pdf")
        gotor_new.set_open_in_new_window(OpenMode.NEW_WINDOW)
        gotor_new_link = PDAnnotationLink()
        gotor_new_link.set_action(gotor_new)

        # link3: GoToR with /NewWindow explicitly false -> OpenMode.SAME_WINDOW.
        gotor_same = PDActionRemoteGoTo()
        gotor_same.set_file("remote_same.pdf")
        gotor_same.set_open_in_new_window(OpenMode.SAME_WINDOW)
        gotor_same_link = PDAnnotationLink()
        gotor_same_link.set_action(gotor_same)

        # link4: GoToR with /NewWindow absent -> OpenMode.USER_PREFERENCE.
        gotor_pref = PDActionRemoteGoTo()
        gotor_pref.set_file("remote_pref.pdf")
        gotor_pref_link = PDAnnotationLink()
        gotor_pref_link.set_action(gotor_pref)

        # link5: Launch with /Win sub-params + /NewWindow true.
        launch = PDActionLaunch()
        launch.set_f("app.exe")
        launch.set_open_in_new_window(OpenMode.NEW_WINDOW)
        win = PDWindowsLaunchParams()
        win.set_filename("notepad.exe")
        win.set_directory("/opt/tmp")
        win.set_operation("print")
        win.set_execute_param("/silent")
        launch.set_win_launch_params(win)
        launch_link = PDAnnotationLink()
        launch_link.set_action(launch)

        # link6: Launch with NO /Win sub-dict (win.* must render "null", and
        # OpenMode falls through to USER_PREFERENCE with /NewWindow absent).
        launch_bare = PDActionLaunch()
        launch_bare.set_f("bare.exe")
        launch_bare_link = PDAnnotationLink()
        launch_bare_link.set_action(launch_bare)

        page0.set_annotations(
            [
                uri_map_link,
                uri_plain_link,
                gotor_new_link,
                gotor_same_link,
                gotor_pref_link,
                launch_link,
                launch_bare_link,
            ]
        )

        # Page /AA: O (open) = a URI action with /IsMap; C (close) = a GoToR
        # with /NewWindow false. Proves /AA dispatch == /A dispatch.
        aa = page0.get_actions()
        open_uri = PDActionURI()
        open_uri.set_uri("https://example.com/page-open")
        open_uri.set_track_mouse_position(False)
        aa.set_o(open_uri)
        close_gotor = PDActionRemoteGoTo()
        close_gotor.set_file("on_close.pdf")
        close_gotor.set_open_in_new_window(OpenMode.SAME_WINDOW)
        aa.set_c(close_gotor)

        doc.save(str(out))
    finally:
        doc.close()


@pytest.fixture(scope="module")
def accessor_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("action_accessor_oracle") / "accessors.pdf"
    _build_accessor_pdf(out)
    return out


@requires_oracle
def test_built_accessor_dump_matches_pdfbox(accessor_pdf: Path) -> None:
    """pypdfbox's secondary-accessor dump equals Apache PDFBox's, byte-for-byte,
    across URI /IsMap, GoToR + Launch OpenMode tri-state, Launch /Win params,
    and the page /AA open/close placement."""
    java = run_probe_text("ActionAccessorProbe", str(accessor_pdf))
    doc = PDDocument.load(str(accessor_pdf))
    try:
        py = _dump_accessors(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the fixture must actually exercise every accessor branch.
    assert "\tPDActionURI\tismap=true" in java
    assert "\tPDActionURI\tismap=false" in java
    assert "\tPDActionRemoteGoTo\tnewwindow=NEW_WINDOW" in java
    assert "\tPDActionRemoteGoTo\tnewwindow=SAME_WINDOW" in java
    assert "\tPDActionRemoteGoTo\tnewwindow=USER_PREFERENCE" in java
    assert (
        "\tPDActionLaunch\tnewwindow=NEW_WINDOW;win.file=notepad.exe;"
        "win.dir=/opt/tmp;win.op=print;win.param=/silent" in java
    )
    # Bare Launch: no /Win -> every win.* is "null"; /NewWindow absent ->
    # USER_PREFERENCE. Crucially win.op renders "null" (the wrapper is absent),
    # NOT the per-dict "open" default — that only applies once a /Win exists.
    assert (
        "\tPDActionLaunch\tnewwindow=USER_PREFERENCE;win.file=null;"
        "win.dir=null;win.op=null;win.param=null" in java
    )
    # /AA placement: open URI + close GoToR dispatched like /A.
    assert "page0.aa.O\tPDActionURI\tismap=false" in java
    assert "page0.aa.C\tPDActionRemoteGoTo\tnewwindow=SAME_WINDOW" in java


@requires_oracle
def test_built_accessor_round_trip(accessor_pdf: Path) -> None:
    """Reload via pypdfbox and assert the typed accessors directly, so a silent
    dispatch/accessor regression is caught at the field level even if the
    canonical-line shape happened to coincide."""
    doc = PDDocument.load(str(accessor_pdf))
    try:
        page0 = doc.get_pages().get(0)
        links = [
            a.get_action()
            for a in page0.get_annotations()
            if isinstance(a, PDAnnotationLink)
        ]

        uri_map = links[0]
        assert isinstance(uri_map, PDActionURI)
        assert uri_map.should_track_mouse_position() is True

        uri_plain = links[1]
        assert isinstance(uri_plain, PDActionURI)
        assert uri_plain.should_track_mouse_position() is False

        gotor_new = links[2]
        assert isinstance(gotor_new, PDActionRemoteGoTo)
        assert gotor_new.get_open_in_new_window() is OpenMode.NEW_WINDOW
        assert gotor_new.is_new_window() is True

        gotor_same = links[3]
        assert gotor_same.get_open_in_new_window() is OpenMode.SAME_WINDOW
        assert gotor_same.is_new_window() is False

        gotor_pref = links[4]
        assert gotor_pref.get_open_in_new_window() is OpenMode.USER_PREFERENCE

        launch = links[5]
        assert isinstance(launch, PDActionLaunch)
        assert launch.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
        win = launch.get_win_launch_params()
        assert win is not None
        assert win.get_filename() == "notepad.exe"
        assert win.get_directory() == "/opt/tmp"
        assert win.get_operation() == "print"
        assert win.get_execute_param() == "/silent"

        launch_bare = links[6]
        assert isinstance(launch_bare, PDActionLaunch)
        assert launch_bare.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE
        assert launch_bare.get_win_launch_params() is None

        aa = page0.get_actions()
        open_action = aa.get_o()
        assert isinstance(open_action, PDActionURI)
        assert open_action.get_uri() == "https://example.com/page-open"
        close_action = aa.get_c()
        assert isinstance(close_action, PDActionRemoteGoTo)
        assert close_action.get_open_in_new_window() is OpenMode.SAME_WINDOW
    finally:
        doc.close()


@requires_oracle
def test_win_operation_default_when_win_present_but_o_absent(tmp_path: Path) -> None:
    """When a ``/Win`` sub-dict exists but its ``/O`` entry is absent,
    ``getOperation()`` defaults to ``"open"`` in BOTH libraries (Table 197) —
    distinct from the bare-Launch case where the absent wrapper renders
    ``null``. Guards the ``getString(O, OPERATION_OPEN)`` default branch."""
    out = tmp_path / "win_default_op.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        launch = PDActionLaunch()
        launch.set_f("app.exe")
        # Attach an EMPTY /Win sub-dict (no /O) directly on the COS object.
        launch.get_cos_object().set_item(
            COSName.get_pdf_name("Win"), COSDictionary()
        )
        link = PDAnnotationLink()
        link.set_action(launch)
        page.set_annotations([link])
        doc.save(str(out))
    finally:
        doc.close()

    java = run_probe_text("ActionAccessorProbe", str(out))
    reloaded = PDDocument.load(str(out))
    try:
        py = _dump_accessors(reloaded)
    finally:
        reloaded.close()
    assert py == java
    # /Win present but /O absent -> "open" default (not "null").
    assert "win.op=open" in java
