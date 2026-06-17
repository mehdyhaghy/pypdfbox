"""Live Apache PDFBox differential parity for the remote / embedded GoTo and
Launch action detail surface (``pypdfbox.pdmodel.interactive.action``):

* ``PDActionRemoteGoTo`` — ``/F`` (file spec), ``/D`` (page-number int vs
  named string vs explicit array — kept RAW since the remote document is not
  opened), and ``/NewWindow`` (tri-state :class:`OpenMode`).
* ``PDActionEmbeddedGoTo`` — ``/F``, ``/D`` (resolved destination),
  ``/NewWindow``, and the chained ``/T`` :class:`PDTargetDirectory`.
* ``PDActionLaunch`` — ``/F``, ``/NewWindow``, and the ``/Win`` launch params.

Each action is reduced to one canonical line so pypdfbox and PDFBox compare
byte-for-byte without tripping over object layout. The grammar must match
``oracle/probes/RemoteGotoProbe.java``::

    page<p>.link<i>\t<subtype>\t<detail>

with ``detail`` (semicolon-joined ``key=value``) by subtype:

  * GoToR  -> ``file=<F text>;d=<canon /D>;newwindow=<OpenMode>``
  * GoToE  -> ``file=<F text>;d=<resolved dest>;newwindow=<OpenMode>;target=<canon /T>``
  * Launch -> ``file=<F text>;newwindow=<OpenMode>;win=<canon /Win>``

``canon /D`` is the RAW COS form of a GoToR ``/D`` (``int:<n>`` / ``str:<s>``
/ ``name:<n>`` / ``arr[<n>]:<e0>,<e1>,...`` / ``none``) — the high-value case,
since PDFBox keeps ``/D`` unresolved (``getD()`` returns ``COSBase``) because
the remote document is not loaded. ``canon /T`` walks the target-directory
chain hop-by-hop. ``canon /Win`` dumps the four ``/Win`` sub-dict strings.

The primary fixture is built in-process by pypdfbox: four link annotations on
page 0 — a GoToR with a page-NUMBER ``/D`` + ``/NewWindow true``, a GoToR with
a named-destination STRING ``/D``, a GoToE with a ``/T`` chain (child->parent),
and a Launch with ``/Win /F`` + ``/NewWindow``. It is saved once and diffed
against both libraries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSBase, COSInteger, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import PDTargetDirectory
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)
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

# --------------------------------------------------------------------------
# Python reproduction of RemoteGotoProbe.java
# --------------------------------------------------------------------------


def _escape(s: str | None) -> str:
    """Mirror ``RemoteGotoProbe.escape`` exactly."""
    if s is None:
        return "null"
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _null_to_empty(s: str | None) -> str:
    return "" if s is None else s


def _open_mode_name(mode: OpenMode) -> str:
    """Render an :class:`OpenMode` exactly as Java's ``OpenMode.toString()``
    (the enum constant name): ``USER_PREFERENCE`` / ``SAME_WINDOW`` /
    ``NEW_WINDOW``."""
    return {
        OpenMode.USER_PREFERENCE: "USER_PREFERENCE",
        OpenMode.SAME_WINDOW: "SAME_WINDOW",
        OpenMode.NEW_WINDOW: "NEW_WINDOW",
    }[mode]


def _file_text(fs: PDFileSpecification | None) -> str | None:
    return None if fs is None else fs.get_file()


def _canon_elem(e: COSBase | None) -> str:
    """Mirror ``RemoteGotoProbe.canonElem``."""
    if e is None:
        return "null"
    if isinstance(e, COSInteger):
        return "i" + str(e.value)
    if isinstance(e, COSName):
        return "n" + e.get_name()
    if isinstance(e, COSString):
        return "s" + e.get_string()
    return "?"


def _canon_d(d: COSBase | None) -> str:
    """Mirror ``RemoteGotoProbe.canonD``: the RAW /D COS form of a GoToR."""
    if d is None:
        return "none"
    if isinstance(d, COSInteger):
        return "int:" + str(d.value)
    if isinstance(d, COSString):
        return "str:" + d.get_string()
    if isinstance(d, COSName):
        return "name:" + d.get_name()
    if isinstance(d, COSArray):
        parts = [_canon_elem(d.get_object(i)) for i in range(d.size())]
        return f"arr[{d.size()}]:" + ",".join(parts)
    return "?"


def _resolve_dest(dest: object) -> str:
    """Mirror ``RemoteGotoProbe.resolveDest`` for the GoToE destination."""
    if dest is None:
        return "none"
    if isinstance(dest, PDNamedDestination):
        n = dest.get_named_destination()
        return "named:" + ("" if n is None else n)
    if isinstance(dest, PDPageDestination):
        return "page" + str(dest.get_page_number())
    return "none"


def _canon_target(target: PDTargetDirectory | None) -> str:
    """Mirror ``RemoteGotoProbe.canonTarget``: walk the /T -> /T chain.

    PDFBox's ``PDTargetDirectory.getPageNumber`` / ``getAnnotationIndex``
    return ``-1`` when the entry is absent (``getInt(key, -1)``); pypdfbox's
    return ``None``. Normalise pypdfbox's ``None`` to ``-1`` so the canonical
    line matches the oracle (the underlying COS dict is identical — this is
    only an accessor return-shape difference, documented in CHANGES.md).

    PDFBox's ``getNamedDestination`` returns a ``PDNamedDestination`` wrapper;
    pypdfbox's returns the bare ``str``. Both ultimately surface the same /P
    string — canonicalise to that string.
    """
    if target is None:
        return "none"
    hops: list[str] = []
    seen: set[int] = set()
    hop = 0
    while target is not None and hop < 64:
        cos = target.get_cos_object()
        if id(cos) in seen:
            break
        seen.add(id(cos))
        rel = target.get_relationship()
        # get_relationship returns COSName (upstream contract, wave 1494).
        line = "R" + ("" if rel is None else rel.get_name())
        line += "|N" + _null_to_empty(target.get_target_filename())
        named = target.get_named_destination()
        page_num = target.get_page_number()
        if named is not None:
            line += "|Pd" + named
        else:
            # None -> -1 to mirror PDFBox getInt(P, -1).
            line += "|Pp" + str(-1 if page_num is None else page_num)
        annot_name = target.get_annotation_name()
        annot_idx = target.get_annotation_number()
        if annot_name is not None:
            line += "|Aa" + annot_name
        else:
            line += "|Ai" + str(-1 if annot_idx is None else annot_idx)
        hops.append(line)
        target = target.get_target()
        hop += 1
    return ">".join(hops)


def _canon_win(win: PDWindowsLaunchParams | None) -> str:
    """Mirror ``RemoteGotoProbe.canonWin``."""
    if win is None:
        return "none"
    return (
        "f=" + _null_to_empty(win.get_filename())
        + "|d=" + _null_to_empty(win.get_directory())
        + "|o=" + _null_to_empty(win.get_operation())
        + "|p=" + _null_to_empty(win.get_execute_param())
    )


def _detail(action: PDAction) -> str:
    """Mirror ``RemoteGotoProbe.detail``."""
    if isinstance(action, PDActionRemoteGoTo):
        return (
            "file=" + _null_to_empty(_file_text(action.get_file_specification()))
            + ";d=" + _canon_d(action.get_d())
            + ";newwindow=" + _open_mode_name(action.get_open_in_new_window())
        )
    if isinstance(action, PDActionEmbeddedGoTo):
        return (
            "file=" + _null_to_empty(_file_text(action.get_file()))
            + ";d=" + _resolve_dest(action.get_destination())
            + ";newwindow="
            + _open_mode_name(action.get_open_in_new_window_mode())
            + ";target=" + _canon_target(action.get_target())
        )
    if isinstance(action, PDActionLaunch):
        return (
            "file=" + _null_to_empty(_file_text(action.get_file()))
            + ";newwindow="
            + _open_mode_name(action.get_open_in_new_window_mode())
            + ";win=" + _canon_win(action.get_win_launch_params())
        )
    return ""


def _emit(lines: list[str], location: str, action: PDAction) -> None:
    subtype = action.get_sub_type()
    lines.append(
        f"{location}\t{'null' if subtype is None else _escape(subtype)}"
        f"\t{_escape(_detail(action))}"
    )


def _dump(doc: PDDocument) -> str:
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
    return "".join(line + "\n" for line in lines)


# --------------------------------------------------------------------------
# Built fixture: GoToR(page-number /D) + GoToR(named /D) + GoToE(/T) + Launch
# --------------------------------------------------------------------------


def _build_remote_goto_pdf(out: Path) -> None:
    doc = PDDocument()
    try:
        page0 = PDPage()
        doc.add_page(page0)

        # link0: GoToR with /F complex file spec, /D as a page-NUMBER explicit
        # array ([2 /Fit] style — an integer page index since the remote doc
        # is not opened), /NewWindow true.
        gotor_num = PDActionRemoteGoTo()
        fs = PDComplexFileSpecification()
        fs.set_file("other.pdf")
        gotor_num.set_file_specification(fs)
        d_array = COSArray()
        d_array.add(COSInteger.get(2))
        d_array.add(COSName.get_pdf_name("Fit"))
        gotor_num.set_d(d_array)
        gotor_num.set_new_window(True)
        link0 = PDAnnotationLink()
        link0.set_action(gotor_num)

        # link1: GoToR with /F text-form, /D as a named-destination STRING,
        # /NewWindow absent (USER_PREFERENCE).
        gotor_named = PDActionRemoteGoTo()
        gotor_named.set_file("chapter.pdf")
        gotor_named.set_named_destination("Chapter2")
        link1 = PDAnnotationLink()
        link1.set_action(gotor_named)

        # link2: GoToE with a /T chain: child (N=attachment.pdf, P=page 3)
        # -> parent (N=root.pdf). /D as an explicit page destination (integer
        # page index 1 — page-object form is invalid for GoToE per upstream).
        gotoe = PDActionEmbeddedGoTo()
        efs = PDComplexFileSpecification()
        efs.set_file("attachment.pdf")
        gotoe.set_file(efs)
        gotoe.set_new_window(False)
        child = PDTargetDirectory()
        child.set_relationship("C")
        child.set_target_filename("attachment.pdf")
        child.set_page_number(3)
        child.set_annotation_number(0)
        parent = PDTargetDirectory()
        parent.set_relationship("P")
        parent.set_target_filename("root.pdf")
        child.set_target(parent)
        gotoe.set_target(child)
        # /D: explicit page destination — integer page-INDEX form for GoToE
        # (page-object form is invalid since the destination is in a *different*
        # document). PDPageFitDestination writes [1 /Fit].
        gotoe_dest = PDPageFitDestination()
        gotoe_dest.set_page_number(1)
        gotoe.set_destination(gotoe_dest)
        link2 = PDAnnotationLink()
        link2.set_action(gotoe)

        # link3: Launch with /F + /NewWindow true + /Win params.
        launch = PDActionLaunch()
        lfs = PDComplexFileSpecification()
        lfs.set_file("viewer.exe")
        launch.set_file(lfs)
        launch.set_open_in_new_window(True)
        win = PDWindowsLaunchParams()
        win.set_filename("notepad.exe")
        win.set_directory("workdir")
        win.set_operation(PDWindowsLaunchParams.OPERATION_PRINT)
        win.set_execute_param("/p report.txt")
        launch.set_win_launch_params(win)
        link3 = PDAnnotationLink()
        link3.set_action(launch)

        page0.set_annotations([link0, link1, link2, link3])
        doc.save(str(out))
    finally:
        doc.close()


@pytest.fixture(scope="module")
def remote_goto_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("remote_goto_oracle") / "remote_goto.pdf"
    _build_remote_goto_pdf(out)
    return out


@requires_oracle
def test_built_remote_goto_dump_matches_pdfbox(remote_goto_pdf: Path) -> None:
    """A pypdfbox-built PDF with GoToR (page-number + named /D), GoToE (/T
    chain), and Launch (/Win) actions dumps identically under pypdfbox and
    Apache PDFBox."""
    java = run_probe_text("RemoteGotoProbe", str(remote_goto_pdf))
    doc = PDDocument.load(str(remote_goto_pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java

    # Sanity: the fixture must actually exercise every high-value case.
    # GoToR with a RAW page-number /D array kept unresolved + /NewWindow true.
    assert (
        "page0.link0\tGoToR\tfile=other.pdf;d=arr[2]:i2,nFit;newwindow=NEW_WINDOW"
        in java
    )
    # GoToR with a named-destination string /D + absent /NewWindow.
    assert (
        "page0.link1\tGoToR\tfile=chapter.pdf;d=str:Chapter2;newwindow=USER_PREFERENCE"
        in java
    )
    # GoToE: page-index /D + /T child->parent chain + explicit SAME_WINDOW.
    assert "page0.link2\tGoToE\t" in java
    assert "d=page1" in java
    assert "newwindow=SAME_WINDOW" in java
    assert (
        "target=RC|Nattachment.pdf|Pp3|Ai0>RP|Nroot.pdf|Pp-1|Ai-1" in java
    )
    # Launch: /F + /NewWindow true + /Win params.
    assert (
        "page0.link3\tLaunch\tfile=viewer.exe;newwindow=NEW_WINDOW;"
        "win=f=notepad.exe|d=workdir|o=print|p=/p report.txt" in java
    )


@requires_oracle
def test_remote_goto_accessor_round_trip(remote_goto_pdf: Path) -> None:
    """Build via pypdfbox, save, reload via pypdfbox: every type-specific
    accessor returns the value written.

    PDFBox parity for the same saved bytes is proven by
    :func:`test_built_remote_goto_dump_matches_pdfbox`; this asserts the
    pypdfbox accessor surface directly so a silent accessor/dispatch
    regression is caught at the field level, not just the canonical line.
    """
    doc = PDDocument.load(str(remote_goto_pdf))
    try:
        page0 = doc.get_pages().get(0)
        links = [
            a
            for a in page0.get_annotations()
            if isinstance(a, PDAnnotationLink)
        ]
        actions = [link.get_action() for link in links]

        # link0: GoToR with raw page-number array /D + NewWindow true.
        gotor_num = actions[0]
        assert isinstance(gotor_num, PDActionRemoteGoTo)
        assert _file_text(gotor_num.get_file_specification()) == "other.pdf"
        d0 = gotor_num.get_d()
        assert isinstance(d0, COSArray)
        assert isinstance(d0.get_object(0), COSInteger)
        assert d0.get_object(0).value == 2
        assert gotor_num.is_new_window()
        assert gotor_num.get_open_in_new_window() is OpenMode.NEW_WINDOW

        # link1: GoToR with named-destination string /D + absent NewWindow.
        gotor_named = actions[1]
        assert isinstance(gotor_named, PDActionRemoteGoTo)
        assert gotor_named.get_named_destination() == "Chapter2"
        assert isinstance(gotor_named.get_d(), COSString)
        assert not gotor_named.is_new_window()
        assert (
            gotor_named.get_open_in_new_window() is OpenMode.USER_PREFERENCE
        )

        # link2: GoToE with /T child->parent chain + page-index destination.
        gotoe = actions[2]
        assert isinstance(gotoe, PDActionEmbeddedGoTo)
        assert _file_text(gotoe.get_file()) == "attachment.pdf"
        dest = gotoe.get_destination()
        assert isinstance(dest, PDPageDestination)
        assert dest.get_page_number() == 1
        assert gotoe.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
        target = gotoe.get_target()
        assert target is not None
        rel = target.get_relationship()
        assert rel is not None and rel.get_name() == "C"
        assert target.get_target_filename() == "attachment.pdf"
        assert target.get_page_number() == 3
        assert target.get_annotation_number() == 0
        nested = target.get_target()
        assert nested is not None
        nested_rel = nested.get_relationship()
        assert nested_rel is not None and nested_rel.get_name() == "P"
        assert nested.get_target_filename() == "root.pdf"
        assert nested.get_target() is None

        # link3: Launch with /F + NewWindow true + /Win params.
        launch = actions[3]
        assert isinstance(launch, PDActionLaunch)
        assert _file_text(launch.get_file()) == "viewer.exe"
        assert launch.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW
        win = launch.get_win_launch_params()
        assert win is not None
        assert win.get_filename() == "notepad.exe"
        assert win.get_operation() == PDWindowsLaunchParams.OPERATION_PRINT
        assert win.get_execute_param() == "/p report.txt"
    finally:
        doc.close()


@requires_oracle
def test_remote_goto_d_explicit_array_matches_pdfbox(tmp_path: Path) -> None:
    """A GoToR whose /D is an explicit destination array referencing an
    integer page index is kept RAW by both libraries (the remote document is
    not opened, so the page-number form survives verbatim). Guards the
    ``getD()``-returns-COSBase contract against a regression that would try to
    resolve the destination locally."""
    out = tmp_path / "gotor_array.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        action = PDActionRemoteGoTo()
        action.set_file("remote.pdf")
        # /D = [5 /XYZ 100 200 0] — explicit, with a raw integer page index.
        d = COSArray()
        d.add(COSInteger.get(5))
        d.add(COSName.get_pdf_name("XYZ"))
        d.add(COSInteger.get(100))
        d.add(COSInteger.get(200))
        d.add(COSInteger.get(0))
        action.set_d(d)
        link = PDAnnotationLink()
        link.set_action(action)
        page.set_annotations([link])
        doc.save(str(out))
    finally:
        doc.close()

    java = run_probe_text("RemoteGotoProbe", str(out))
    reloaded = PDDocument.load(str(out))
    try:
        py = _dump(reloaded)
        action = reloaded.get_pages().get(0).get_annotations()[0].get_action()
        assert isinstance(action, PDActionRemoteGoTo)
        raw = action.get_d()
        assert isinstance(raw, COSArray)
        assert raw.get_object(0).value == 5
    finally:
        reloaded.close()
    assert py == java
    assert (
        "d=arr[5]:i5,nXYZ,i100,i200,i0" in java
    )


@requires_oracle
def test_remote_goto_d_integer_page_matches_pdfbox(tmp_path: Path) -> None:
    """A GoToR whose /D is a bare integer (some producers write the remote
    page index directly as an integer rather than an array) is kept as a raw
    COSInteger by both libraries. ``PDDestination.create`` would reject a bare
    integer, so this proves the ``getD()`` raw-COSBase contract is what the
    probe and pypdfbox both rely on."""
    out = tmp_path / "gotor_int.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        action = PDActionRemoteGoTo()
        action.set_file("remote.pdf")
        action.get_cos_object().set_item(
            COSName.D, COSInteger.get(7)
        )
        link = PDAnnotationLink()
        link.set_action(action)
        page.set_annotations([link])
        doc.save(str(out))
    finally:
        doc.close()

    java = run_probe_text("RemoteGotoProbe", str(out))
    reloaded = PDDocument.load(str(out))
    try:
        py = _dump(reloaded)
        action = reloaded.get_pages().get(0).get_annotations()[0].get_action()
        assert isinstance(action, PDActionRemoteGoTo)
        assert isinstance(action.get_d(), COSInteger)
        assert action.get_d().value == 7
    finally:
        reloaded.close()
    assert py == java
    assert "d=int:7" in java
    # PDDestination.create must NOT swallow a bare integer into a page dest:
    # PDFBox throws IOException ("Error: can't convert to Destination") for a
    # bare COSInteger; pypdfbox mirrors that with OSError. The GoToR probe
    # therefore never resolves /D — it reads the raw COSBase via getD().
    with pytest.raises(OSError):
        PDDestination.create(COSInteger.get(7))
