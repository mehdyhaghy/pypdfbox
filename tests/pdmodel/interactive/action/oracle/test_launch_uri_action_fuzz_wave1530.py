"""Live Apache PDFBox differential fuzz of the ACCESSOR surface of Launch / URI
actions and the document-level URI dictionary (wave 1530, agent C).

The existing action oracle suite drives either the raw-COS shape level
(``test_action_factory_fuzz_wave1513`` → ``PDActionFactory`` dispatch) or the
canonicalised detail of real link annotations (``test_remote_goto_oracle`` →
``RemoteGotoProbe``). Neither exercises the typed *accessors* of the launch /
URI surface over MALFORMED dictionaries:

  - ``PDActionLaunch``: ``get_file`` (filespec dict vs string vs missing),
    ``get_f``/``get_d``/``get_o``/``get_p`` (string vs name vs absent),
    ``get_win_launch_params`` (missing / non-dict / dict-with-fields),
    ``get_open_in_new_window_mode`` tri-state (``true``/``false``/absent →
    ``OpenMode``).
  - ``PDWindowsLaunchParams``: ``get_filename``/``get_directory``/
    ``get_operation`` (default ``"open"``) / ``get_execute_param`` over a
    fuzzed ``/Win`` sub-dict (missing fields, wrong types).
  - ``PDActionURI``: ``get_uri`` text-decode (string / name / missing /
    UTF-8 / UTF-16-BOM bytes), ``should_track_mouse_position`` (``/IsMap``
    true/false/absent/non-bool).
  - ``PDURIDictionary``: ``get_base`` (string / name / missing / non-string).
  - ``PDWindowsLaunchParams.set_operation`` setter round-trip (upstream writes
    ``/D``, a latent bug — see ``_PINNED_DIVERGENCES``).

Strategy mirrors ``test_action_factory_fuzz_wave1513``: build the deterministic
corpus directly as COS, hang the launch / URI action dicts off a non-standard
``/FuzzActions`` COSArray and the bare URI dictionaries off a parallel
``/FuzzUriDicts`` COSArray on the catalog, save ONE ``corpus.pdf`` plus a
``manifest.txt`` (action case names, an ``@@URIDICTS`` separator, then the
URI-dict case names — in array order). The ``LaunchUriActionFuzzProbe`` loads
the same bytes and projects each case through the typed accessors. Both
libraries read the identical on-disk bytes, so the accessor contract is
directly comparable.

Validation, not blind pinning: the Java line is ground truth. Each case asserts
pypdfbox produces the identical projection; any defensible divergence is pinned
in ``_PINNED_DIVERGENCES`` with a reason + matching CHANGES.md row, and a real
bug is fixed in production.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_uri_dictionary import PDURIDictionary
from pypdfbox.pdmodel.interactive.action.pd_windows_launch_params import (
    PDWindowsLaunchParams,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


# --------------------------------------------------------------- COS builders


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _dict(**entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _act(sub: str, **entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Action"))
    d.set_item(_n("S"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _filespec(path: str) -> COSDictionary:
    """A /Filespec dictionary form (PDF 32000-1 §7.11.3)."""
    fs = COSDictionary()
    fs.set_item(_n("Type"), _n("Filespec"))
    fs.set_item(_n("F"), COSString(path))
    return fs


def _utf16be(text: str) -> COSString:
    return COSString(b"\xfe\xff" + text.encode("utf-16-be"))


def _utf8_bytes(data: bytes) -> COSString:
    return COSString(data)


# --------------------------------------------------------------- corpus build


def _build_actions() -> dict[str, COSDictionary]:
    """Deterministic, ordered Launch / URI / SetOp action-dict corpus."""
    c: dict[str, COSDictionary] = {}

    # ----- Launch /F + /Win + /NewWindow -----
    c["launch_f_string"] = _act("Launch", F=COSString("notepad.exe"))
    c["launch_f_filespec"] = _act("Launch", F=_filespec("doc.pdf"))
    c["launch_f_missing"] = _act("Launch")
    c["launch_f_name"] = _act("Launch", F=_n("named.exe"))
    c["launch_d_string"] = _act("Launch", D=COSString("/usr/bin"))
    c["launch_o_string"] = _act("Launch", O=COSString("print"))
    c["launch_p_string"] = _act("Launch", P=COSString("--flag"))
    c["launch_all_strings"] = _act(
        "Launch",
        F=COSString("app"),
        D=COSString("dir"),
        O=COSString("open"),
        P=COSString("arg"),
    )
    # /F as filespec dict but accessed via getF() (string-only path) → null.
    c["launch_f_filespec_getf"] = _act("Launch", F=_filespec("only.pdf"))

    # /NewWindow tri-state.
    c["launch_nw_true"] = _act("Launch", F=COSString("a"), NewWindow=COSBoolean.TRUE)
    c["launch_nw_false"] = _act("Launch", F=COSString("a"), NewWindow=COSBoolean.FALSE)
    c["launch_nw_absent"] = _act("Launch", F=COSString("a"))
    # /NewWindow non-boolean (int) → upstream returns USER_PREFERENCE.
    c["launch_nw_int"] = _act("Launch", F=COSString("a"), NewWindow=COSInteger.get(1))
    c["launch_nw_name"] = _act("Launch", F=COSString("a"), NewWindow=_n("true"))

    # /Win sub-dict shapes.
    win_full = _dict(
        F=COSString("win.exe"),
        D=COSString("C:\\tmp"),
        O=COSString("print"),
        P=COSString("/q"),
    )
    c["launch_win_full"] = _act("Launch", Win=win_full)
    c["launch_win_empty"] = _act("Launch", Win=COSDictionary())
    c["launch_win_missing"] = _act("Launch")
    # /Win as a non-dict → getWinLaunchParams() is null.
    c["launch_win_string"] = _act("Launch", Win=COSString("not-a-dict"))
    c["launch_win_int"] = _act("Launch", Win=COSInteger.get(3))
    # /Win with /O absent → getOperation defaults to "open".
    c["launch_win_no_o"] = _act("Launch", Win=_dict(F=COSString("x")))
    # /Win with /F as a name (not string) → getFilename() is null.
    c["launch_win_f_name"] = _act("Launch", Win=_dict(F=_n("nope")))
    # /Win with /O as a name → getOperation() folds to default "open".
    c["launch_win_o_name"] = _act("Launch", Win=_dict(O=_n("print")))

    # ----- URI -----
    c["uri_string"] = _act("URI", URI=COSString("http://good"))
    c["uri_name"] = _act("URI", URI=_n("http://name"))
    c["uri_missing"] = _act("URI")
    c["uri_empty"] = _act("URI", URI=COSString(""))
    c["uri_utf16be"] = _act("URI", URI=_utf16be("http://é.example"))
    # Non-BOM high-byte bytes → upstream decodes as UTF-8.
    c["uri_utf8_bytes"] = _act(
        "URI", URI=_utf8_bytes("café://x".encode())
    )
    c["uri_ismap_true"] = _act(
        "URI", URI=COSString("http://x"), IsMap=COSBoolean.TRUE
    )
    c["uri_ismap_false"] = _act(
        "URI", URI=COSString("http://x"), IsMap=COSBoolean.FALSE
    )
    c["uri_ismap_absent"] = _act("URI", URI=COSString("http://x"))
    # /IsMap non-boolean (int) → getBoolean default false.
    c["uri_ismap_int"] = _act(
        "URI", URI=COSString("http://x"), IsMap=COSInteger.get(1)
    )

    # ----- SetOp (setOperation round-trip on the /Win params) -----
    c["setop_win_present"] = _act("SetOp", Win=_dict(O=COSString("open")))
    c["setop_win_absent"] = _act("SetOp")

    return c


def _build_uri_dicts() -> dict[str, COSDictionary]:
    """Deterministic bare /URI (catalog-level) dictionaries for PDURIDictionary."""
    c: dict[str, COSDictionary] = {}
    c["base_string"] = _dict(Base=COSString("http://base.example/"))
    c["base_missing"] = COSDictionary()
    c["base_name"] = _dict(Base=_n("http://name-base"))
    c["base_empty"] = _dict(Base=COSString(""))
    c["base_int"] = _dict(Base=COSInteger.get(7))
    c["base_utf16be"] = _dict(Base=_utf16be("http://ü.example/"))
    # Non-BOM high-byte bytes — upstream getBase uses plain getString
    # (PDFDocEncoding), NOT the UTF-8 tolerance getURI applies.
    c["base_high_bytes"] = _dict(Base=_utf8_bytes(b"http://\xe9.example/"))
    return c


# ----------------------------------------------------------------- projection


def _exc_token(exc: BaseException) -> str:
    """Canonical exception token; folds Java ``IOException`` ↔ Python
    ``OSError`` (incl. ``PDFParseError``) per the porting table so a parity
    failure on the *same* case isn't a false positive over the label."""
    if isinstance(exc, OSError):
        return "IOERR"
    return type(exc).__name__


def _esc(s: str | None) -> str:
    if s is None:
        return "null"
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _shape(b: COSBase | None) -> str:
    from pypdfbox.cos import COSFloat, COSStream

    if b is None:
        return "null"
    if isinstance(b, COSStream):
        return "stream"
    if isinstance(b, COSDictionary):
        return "dict"
    if isinstance(b, COSArray):
        return "arr"
    if isinstance(b, COSName):
        return "name"
    if isinstance(b, COSString):
        return "str"
    if isinstance(b, COSBoolean):
        return "bool"
    if isinstance(b, COSInteger):
        return "int"
    if isinstance(b, COSFloat):
        return "real"
    return "other"


_OPEN_MODE_JAVA: dict[OpenMode, str] = {
    OpenMode.USER_PREFERENCE: "USER_PREFERENCE",
    OpenMode.SAME_WINDOW: "SAME_WINDOW",
    OpenMode.NEW_WINDOW: "NEW_WINDOW",
}


def _win_proj(win: PDWindowsLaunchParams | None) -> str:
    if win is None:
        return "none"
    return (
        "f=" + _esc(win.get_filename())
        + "|d=" + _esc(win.get_directory())
        + "|o=" + _esc(win.get_operation())
        + "|p=" + _esc(win.get_execute_param())
    )


def _launch_proj(d: COSDictionary) -> str:
    a = PDActionLaunch(d)
    fs = a.get_file()
    file = None if fs is None else fs.get_file()
    return (
        "kind=launch file=" + _esc(file)
        + " f=" + _esc(a.get_f())
        + " d=" + _esc(a.get_d())
        + " o=" + _esc(a.get_o())
        + " p=" + _esc(a.get_p())
        + " newwin=" + _OPEN_MODE_JAVA[a.get_open_in_new_window_mode()]
        + " win=" + _win_proj(a.get_win_launch_params())
    )


def _uri_proj(d: COSDictionary) -> str:
    a = PDActionURI(d)
    return (
        "kind=uri uri=" + _esc(a.get_uri())
        + " ismap=" + ("true" if a.should_track_mouse_position() else "false")
    )


def _setop_proj(d: COSDictionary) -> str:
    win_base = d.get_dictionary_object(_n("Win"))
    win_dict = win_base if isinstance(win_base, COSDictionary) else COSDictionary()
    win = PDWindowsLaunchParams(win_dict)
    win.set_operation("print")
    return (
        "kind=setop afterset_o=" + _esc(win.get_operation())
        + " raw_O=" + _shape(win_dict.get_dictionary_object(_n("O")))
        + " raw_D=" + _shape(win_dict.get_dictionary_object(_n("D")))
    )


def _uri_dict_proj(d: COSDictionary) -> str:
    return "kind=uridict base=" + _esc(PDURIDictionary(d).get_base())


def _py_action_line(name: str, d: COSDictionary | None) -> str:
    try:
        if d is None:
            return f"CASE {name} kind=nondict"
        sub = d.get_name_as_string(_n("S"))
        if sub == "Launch":
            body = _launch_proj(d)
        elif sub == "URI":
            body = _uri_proj(d)
        elif sub == "SetOp":
            body = _setop_proj(d)
        else:
            body = "kind=unknown sub=" + _esc(sub)
        return f"CASE {name} {body}"
    except Exception as exc:  # noqa: BLE001 - contract probe; any failure counts
        return f"CASE {name} ERR:{_exc_token(exc)}"


def _py_dict_line(name: str, d: COSDictionary | None) -> str:
    try:
        if d is None:
            return f"CASE {name} kind=nondict"
        return f"CASE {name} {_uri_dict_proj(d)}"
    except Exception as exc:  # noqa: BLE001 - contract probe; any failure counts
        return f"CASE {name} ERR:{_exc_token(exc)}"


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(
    dir_path: Path,
    actions: dict[str, COSDictionary],
    uri_dicts: dict[str, COSDictionary],
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        acts = COSArray()
        for d in actions.values():
            acts.add(d)
        catalog.set_item(_n("FuzzActions"), acts)
        dicts = COSArray()
        for d in uri_dicts.values():
            dicts.add(d)
        catalog.set_item(_n("FuzzUriDicts"), dicts)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    manifest = list(actions) + ["@@URIDICTS"] + list(uri_dicts)
    (dir_path / "manifest.txt").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8"
    )


_doc_keepalive: list[object] = []


def _reload(
    dir_path: Path, key: str, order: list[str]
) -> dict[str, COSDictionary | None]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n(key))
    out: dict[str, COSDictionary | None] = {}
    for i, name in enumerate(order):
        entry = arr.get_object(i)
        out[name] = entry if isinstance(entry, COSDictionary) else None
    return out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java line.
#
# setop_win_present / setop_win_absent: upstream PDWindowsLaunchParams.setOperation
# writes COSName.D (a latent bug — it should write /O), so a subsequent
# getOperation() reads /O and falls through to the "open" default, leaving the
# written value stranded on /D. pypdfbox's set_operation correctly writes /O, so
# get_operation() returns the value we set ("print"). The integer-correct
# behaviour deviates from the buggy upstream round-trip; pinned both-sides.
_PINNED_DIVERGENCES: dict[str, str] = {
    "setop_win_present": (
        "CASE setop_win_present kind=setop afterset_o=print raw_O=str raw_D=null"
    ),
    "setop_win_absent": (
        "CASE setop_win_absent kind=setop afterset_o=print raw_O=str raw_D=null"
    ),
}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_launch_uri_action_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed Launch / URI action + URI dictionary projects identically
    through the typed pypdfbox accessors and Apache PDFBox 3.0.7, reading the
    same on-disk bytes (except the pinned ``setOperation`` divergences)."""
    actions = _build_actions()
    uri_dicts = _build_uri_dicts()
    _write_corpus_pdf(tmp_path, actions, uri_dicts)

    raw = run_probe_text("LaunchUriActionFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    total = len(actions) + len(uri_dicts)
    assert len(java_lines) == total, (
        f"probe emitted {len(java_lines)} lines for {total} cases:\n{raw}"
    )

    reloaded_acts = _reload(tmp_path, "FuzzActions", list(actions))
    reloaded_dicts = _reload(tmp_path, "FuzzUriDicts", list(uri_dicts))
    py_by_name: dict[str, str] = {}
    for name, d in reloaded_acts.items():
        py_by_name[name] = _py_action_line(name, d)
    for name, d in reloaded_dicts.items():
        py_by_name[name] = _py_dict_line(name, d)

    mismatches: list[str] = []
    for jline in java_lines:
        name = jline.split(" ", 2)[1]
        pline = py_by_name[name]
        if name in _PINNED_DIVERGENCES:
            if pline != _PINNED_DIVERGENCES[name]:
                mismatches.append(
                    f"{name}: PINNED py expected {_PINNED_DIVERGENCES[name]!r} "
                    f"got {pline!r} (java {jline!r})"
                )
            continue
        if pline != jline:
            mismatches.append(f"{name}:\n  py   {pline}\n  java {jline}")

    assert not mismatches, "launch/uri accessor divergence(s):\n" + "\n".join(
        mismatches
    )
