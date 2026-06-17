"""Live Apache PDFBox differential fuzz of the TYPED ACCESSOR surface of the
file-/URI-/script-carrying ``PDAction`` subtypes (wave 1541, agent A).

The three existing action fuzz probes leave the accessor-level decode / dispatch
of the *non*-Hide/Thread/Sound subtypes uncovered:

* ``test_action_factory_fuzz_wave1513`` projects the raw-COS *shape* after
  ``PDActionFactory.create_action`` dispatch — never the accessor methods.
* ``test_action_subtypes_fuzz_wave1530`` drives only Hide / Thread / Sound
  accessors.
* ``test_launch_uri_action_fuzz_wave1530`` targets a narrower Launch/URI slice.

This probe drives the public typed getters that *decode* (JavaScript
``get_action`` string-vs-stream-body; URI ``get_uri``) or *dispatch*
(``PDFileSpecification.create_fs`` via ``get_file`` / ``get_file_specification``;
``get_open_in_new_window``/``..._mode`` → :class:`OpenMode` tri-state) a
malformed payload, for JavaScript / URI / Named / Launch / GoToR / GoToE /
ImportData / SubmitForm / ResetForm.

Strategy mirrors ``ActionFactoryFuzzProbe``: build a deterministic corpus of
action dicts, embed them in a ``/FuzzActions`` COSArray off the catalog, save one
``corpus.pdf`` + ``manifest.txt``, and have both libraries read the identical
on-disk bytes. Each case asserts pypdfbox's accessor projection equals Apache
PDFBox 3.0.7's. Defensible divergences are pinned in ``_PINNED_DIVERGENCES`` with
a reason; a real bug is fixed in production.

Accessor mapping (pypdfbox → upstream getter the Java probe drives):

* JavaScript ``get_action`` → ``getAction``.
* URI ``get_uri`` → ``getURI`` (upstream ``getString``);
  ``should_track_mouse_position`` → ``shouldTrackMousePosition``.
* Named ``get_n`` → ``getN`` (``getNameAsString`` tolerance).
* Launch ``get_file`` → ``getFile`` (``createFS``); ``get_f/get_d/get_o/get_p``;
  ``get_win_launch_params`` presence; ``get_open_in_new_window_mode`` →
  ``getOpenInNewWindow`` (OpenMode).
* GoToR ``get_file_specification`` → ``getFile`` (NOT ``get_file``, which is the
  legacy string ``getF`` form); ``get_d`` shape; ``get_open_in_new_window`` →
  ``getOpenInNewWindow`` (OpenMode).
* GoToE ``get_file`` → ``getFile``; ``get_open_in_new_window_mode`` →
  ``getOpenInNewWindow``.
* ImportData ``get_file`` → ``getFile``.
* SubmitForm ``get_cos_fields`` → ``getFields`` (raw COSArray);
  ``get_file`` → ``getFile``; ``get_flags`` → ``getFlags``.
* ResetForm ``get_fields`` → ``getFields``; ``get_flags`` → ``getFlags``.

``get_file`` / ``get_file_specification`` can raise (upstream IOException,
pypdfbox OSError) for a wrong-typed ``/F``; the probe normalises both to the
token ``ERR`` so the contract under test is "both raise on the same input",
not the exception class name.
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
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import (
    PDActionImportData,
)
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
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_F = COSName.get_pdf_name("F")


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


# --------------------------------------------------------------- COS builders


def _stream(payload: bytes) -> COSStream:
    st = COSStream()
    out = st.create_output_stream()
    out.write(payload)
    out.close()
    return st


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _fs_dict(name: str) -> COSDictionary:
    """A minimal complex file specification (``/Type /Filespec /F name``)."""
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Filespec"))
    d.set_string(_F, name)
    return d


def _act(sub: str | None, **entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Action"))
    if sub is not None:
        d.set_item(_n("S"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    # ----- JavaScript: get_action string vs stream-body vs name vs missing -----
    c["js_string"] = _act("JavaScript", JS=COSString("app.alert(1);"))
    c["js_stream"] = _act("JavaScript", JS=_stream(b"app.alert(2);"))
    c["js_empty_string"] = _act("JavaScript", JS=COSString(""))
    c["js_name"] = _act("JavaScript", JS=_n("notjs"))
    c["js_missing"] = _act("JavaScript")
    c["js_int"] = _act("JavaScript", JS=COSInteger.get(7))

    # ----- URI: get_uri (ASCII, matches getString) + IsMap default -----
    c["uri_ascii"] = _act("URI", URI=COSString("http://good"), IsMap=COSBoolean.TRUE)
    c["uri_no_ismap"] = _act("URI", URI=COSString("http://no-map"))
    c["uri_empty"] = _act("URI", URI=COSString(""))
    c["uri_as_name"] = _act("URI", URI=_n("http://name"))
    c["uri_missing"] = _act("URI")
    c["uri_ismap_int"] = _act("URI", URI=COSString("http://x"), IsMap=COSInteger.get(1))

    # ----- Named: get_n name vs string vs missing vs int -----
    c["named_name"] = _act("Named", N=_n("NextPage"))
    c["named_string"] = _act("Named", N=COSString("FromString"))
    c["named_missing"] = _act("Named")
    c["named_int"] = _act("Named", N=COSInteger.get(3))

    # ----- Launch: get_file dispatch + getF/D/O/P + win + OpenMode -----
    win = COSDictionary()
    win.set_item(_F, COSString("app.exe"))
    c["launch_f_string"] = _act(
        "Launch", F=COSString("file.exe"), NewWindow=COSBoolean.TRUE
    )
    c["launch_f_complex"] = _act("Launch", F=_fs_dict("complex.exe"))
    c["launch_f_name"] = _act("Launch", F=_n("badtype"))  # createFS -> ERR
    c["launch_f_int"] = _act("Launch", F=COSInteger.get(1))  # createFS -> ERR
    c["launch_missing"] = _act("Launch")
    c["launch_win_dict"] = _act(
        "Launch", Win=win, NewWindow=COSBoolean.FALSE
    )
    c["launch_win_string"] = _act("Launch", Win=COSString("notdict"))
    c["launch_dop"] = _act(
        "Launch",
        F=COSString("x"),
        D=COSString("solaris-cmd"),
        O=COSString("open"),
        P=COSString("params"),
    )
    c["launch_nw_int"] = _act("Launch", F=COSString("x"), NewWindow=COSInteger.get(1))

    # ----- GoToR: get_file_specification dispatch + getD shape + OpenMode -----
    c["gotor_f_string"] = _act(
        "GoToR", F=COSString("other.pdf"), D=_arr(COSInteger.get(0), _n("Fit"))
    )
    c["gotor_f_complex"] = _act(
        "GoToR", F=_fs_dict("o.pdf"), D=COSString("dest"), NewWindow=COSBoolean.TRUE
    )
    c["gotor_f_name"] = _act("GoToR", F=_n("badtype"), D=_n("D"))  # createFS -> ERR
    c["gotor_missing"] = _act("GoToR")
    c["gotor_nw_false"] = _act(
        "GoToR", F=COSString("o.pdf"), NewWindow=COSBoolean.FALSE
    )
    c["gotor_nw_int"] = _act("GoToR", F=COSString("o.pdf"), NewWindow=COSInteger.get(0))

    # ----- GoToE: get_file dispatch + OpenMode -----
    c["gotoe_f_string"] = _act("GoToE", F=COSString("e.pdf"), NewWindow=COSBoolean.TRUE)
    c["gotoe_f_complex"] = _act("GoToE", F=_fs_dict("e.pdf"))
    c["gotoe_f_int"] = _act("GoToE", F=COSInteger.get(2))  # createFS -> ERR
    c["gotoe_missing"] = _act("GoToE")

    # ----- ImportData: get_file dispatch -----
    c["import_f_string"] = _act("ImportData", F=COSString("data.fdf"))
    c["import_f_complex"] = _act("ImportData", F=_fs_dict("data.fdf"))
    c["import_f_name"] = _act("ImportData", F=_n("badtype"))  # createFS -> ERR
    c["import_missing"] = _act("ImportData")

    # ----- SubmitForm: get_cos_fields + get_file + get_flags -----
    c["submit_fields_array"] = _act(
        "SubmitForm",
        F=COSString("http://submit"),
        Fields=_arr(COSString("f1"), COSString("f2")),
        Flags=COSInteger.get(4),
    )
    c["submit_fields_single"] = _act("SubmitForm", Fields=COSString("f1"))
    c["submit_f_complex"] = _act("SubmitForm", F=_fs_dict("submit"))
    c["submit_f_name"] = _act("SubmitForm", F=_n("badtype"))  # createFS -> ERR
    c["submit_missing"] = _act("SubmitForm")
    c["submit_flags_real"] = _act(
        "SubmitForm", Fields=_arr(), Flags=COSFloat(8.0)
    )

    # ----- ResetForm: get_fields + get_flags -----
    c["reset_fields_array"] = _act(
        "ResetForm", Fields=_arr(COSString("f1")), Flags=COSInteger.get(1)
    )
    c["reset_fields_name"] = _act("ResetForm", Fields=_n("f1"))
    c["reset_missing"] = _act("ResetForm")
    c["reset_flags_only"] = _act("ResetForm", Flags=COSInteger.get(1))

    return c


# --------------------------------------------------------------- projection


def _shape(b: COSBase | None) -> str:
    if b is None:
        return "null"
    if isinstance(b, COSStream):
        return "stream"
    if isinstance(b, COSDictionary):
        return "dict"
    if isinstance(b, COSArray):
        return "arr" + str(b.size())
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


def _str(s: str | None) -> str:
    return "null" if s is None else s


def _file_class(d: COSDictionary, key: COSName) -> str:
    try:
        fs = PDFileSpecification.create_fs(d.get_dictionary_object(key))
        return "null" if fs is None else type(fs).__name__
    except Exception:  # noqa: BLE001 - normalise OSError/IOError to ERR
        return "ERR"


def _open_mode_name(mode: object) -> str:
    # pypdfbox OpenMode.name == upstream OpenMode.name(): USER_PREFERENCE /
    # SAME_WINDOW / NEW_WINDOW.
    return getattr(mode, "name", str(mode))


def _js_line(d: COSDictionary) -> str:
    return "js=" + _str(PDActionJavaScript(d).get_action())


def _uri_line(d: COSDictionary) -> str:
    a = PDActionURI(d)
    return "uri=" + _str(a.get_uri()) + ",map=" + _java_bool(
        a.should_track_mouse_position()
    )


def _named_line(d: COSDictionary) -> str:
    return "n=" + _str(PDActionNamed(d).get_n())


def _java_bool(b: bool) -> str:
    return "true" if b else "false"


def _launch_line(d: COSDictionary) -> str:
    a = PDActionLaunch(d)
    return (
        "file=" + _file_class(d, _F)
        + ",f=" + _str(a.get_f())
        + ",d=" + _str(a.get_d())
        + ",o=" + _str(a.get_o())
        + ",p=" + _str(a.get_p())
        + ",win=" + _java_bool(a.get_win_launch_params() is not None)
        + ",nw=" + _open_mode_name(a.get_open_in_new_window_mode())
    )


def _gotor_line(d: COSDictionary) -> str:
    a = PDActionRemoteGoTo(d)
    # get_file_specification mirrors upstream getFile() (createFS); a bad /F
    # type raises (OSError) and we normalise to ERR like the Java probe does
    # for its IOException — both raising on the same input is the contract.
    try:
        fs = a.get_file_specification()
        file_tok = "null" if fs is None else type(fs).__name__
    except Exception:  # noqa: BLE001
        file_tok = "ERR"
    return (
        "file=" + file_tok
        + ",d=" + _shape(a.get_d())
        + ",nw=" + _open_mode_name(a.get_open_in_new_window())
    )


def _gotoe_line(d: COSDictionary) -> str:
    a = PDActionEmbeddedGoTo(d)
    try:
        fs = a.get_file()
        file_tok = "null" if fs is None else type(fs).__name__
    except Exception:  # noqa: BLE001
        file_tok = "ERR"
    return "file=" + file_tok + ",nw=" + _open_mode_name(
        a.get_open_in_new_window_mode()
    )


def _import_line(d: COSDictionary) -> str:
    a = PDActionImportData(d)
    try:
        fs = a.get_file()
        return "file=" + ("null" if fs is None else type(fs).__name__)
    except Exception:  # noqa: BLE001
        return "file=ERR"


def _submit_line(d: COSDictionary) -> str:
    a = PDActionSubmitForm(d)
    fields = a.get_cos_fields()
    fields_tok = "null" if fields is None else "arr" + str(fields.size())
    return (
        "file=" + _file_class(d, _F)
        + ",fields=" + fields_tok
        + ",flags=" + str(a.get_flags())
    )


def _reset_line(d: COSDictionary) -> str:
    a = PDActionResetForm(d)
    fields = a.get_fields()
    fields_tok = "null" if fields is None else "arr" + str(fields.size())
    return "fields=" + fields_tok + ",flags=" + str(a.get_flags())


_DISPATCH = {
    "js_": _js_line,
    "uri_": _uri_line,
    "named_": _named_line,
    "launch_": _launch_line,
    "gotor_": _gotor_line,
    "gotoe_": _gotoe_line,
    "import_": _import_line,
    "submit_": _submit_line,
    "reset_": _reset_line,
}


def _project(name: str, d: COSDictionary | None) -> str:
    if d is None:
        return "NODICT"
    for prefix, fn in _DISPATCH.items():
        if name.startswith(prefix):
            return fn(d)
    return "UNKNOWN"


def _py_line(name: str, d: COSDictionary | None) -> str:
    try:
        return f"CASE {name} {_project(name, d)}"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return f"CASE {name} ERR:{type(exc).__name__}"


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(dir_path: Path, corpus: dict[str, COSDictionary]) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        arr = COSArray()
        for d in corpus.values():
            arr.add(d)
        catalog.set_item(_n("FuzzActions"), arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    (dir_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )


_doc_keepalive: list[object] = []


def _reload_corpus(
    dir_path: Path, order: list[str]
) -> dict[str, COSDictionary | None]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    out: dict[str, COSDictionary | None] = {}
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n("FuzzActions"))
    for i, name in enumerate(order):
        entry = arr.get_object(i)
        out[name] = entry if isinstance(entry, COSDictionary) else None
    return out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java line. Empty: the live oracle
# surfaced none for the cases above (all use ASCII / spec-shaped payloads chosen
# so upstream getString and pypdfbox's tolerant decode agree).
_PINNED_DIVERGENCES: dict[str, str] = {}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_action_subtype_accessor_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every typed-accessor projection of the file-/URI-/script-carrying action
    subtypes is identical on pypdfbox and Apache PDFBox 3.0.7, reading the same
    on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("ActionSubtypeFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )

    reloaded = _reload_corpus(tmp_path, list(corpus))
    py_by_name = {name: _py_line(name, d) for name, d in reloaded.items()}

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

    assert not mismatches, "action-subtype accessor divergence(s):\n" + "\n".join(
        mismatches
    )
