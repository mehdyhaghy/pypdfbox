"""Live Apache PDFBox differential fuzz of ``PDActionFactory.create_action``
dispatch + per-subtype action-dictionary parsing leniency (wave 1513, agent C).

The well-formed action oracle suite (``test_action_oracle``,
``test_action_accessor_oracle``, ``test_action_dest_type_oracle``,
``test_action_hide_target_oracle``, ``test_remote_goto_oracle``) only exercises
syntactically valid action dicts. This probe targets the MALFORMED / edge-case
subset a buggy or hostile producer can emit:

  - ``/S`` missing / unknown / mistyped (a *string* instead of a *name*).
  - per-subtype payloads with the wrong COS type or absent:
    URI ``/URI`` as name/string/missing; GoTo ``/D`` as array/name/string/dict;
    GoToR & Launch ``/F`` as string/dict/missing; JavaScript ``/JS`` as
    string/stream/missing; Named ``/N`` standard + non-standard; Launch ``/Win``
    dict; Submit/Reset/Hide ``/Fields`` as array/single/missing; Hide ``/T`` as
    string/array/dict.
  - ``/Next`` chains: single dict, array, nested, with unknown / non-dict members.

Strategy: build the deterministic corpus of action dictionaries directly as COS,
embed them as entries of a non-standard ``/FuzzActions`` COSArray hung off the
document catalog, and save ONE ``corpus.pdf`` plus a ``manifest.txt`` (one case
name per line, in array order) into a tmp dir. The ``ActionFactoryFuzzProbe``
loads that single pdf, walks the array, feeds each raw COSDictionary to
``PDActionFactory.createAction`` and projects a stable line. Both libraries read
the exact same bytes on disk, so the parse contract is directly comparable.

Validation, not blind pinning: the Java line is ground truth. Each case asserts
pypdfbox's ``PDActionFactory.create_action`` produces the identical
``class=<simpleName|null> sub=<S-value> payload=<shape-projection>`` line. Any
defensible divergence is pinned in ``_PINNED_DIVERGENCES`` with a reason and a
matching CHANGES.md row; a real dispatch / parse bug is fixed in production.

The payload projection works at the raw-COS level (identical
``get_dictionary_object`` semantics on both libraries) rather than through
accessor methods, whose text-decoding details (e.g. ``get_uri``'s UTF-8/UTF-16
tolerance vs upstream ``getString``) are a separate accessor-level concern out
of scope for a factory-dispatch + parse-leniency fuzz.
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
from pypdfbox.pdmodel.interactive.action.pd_action_factory import PDActionFactory
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


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


def _act(sub: str | None, **entries: COSBase) -> COSDictionary:
    """An action dict with ``/Type /Action`` and the given ``/S`` + entries.

    A ``sub`` of ``None`` omits ``/S`` entirely. To set ``/S`` as a *string*
    (mistyped) pass it through ``entries`` (``S=COSString(...)``) and leave
    ``sub`` None.
    """
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Action"))
    if sub is not None:
        d.set_item(_n("S"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    """Deterministic, ordered action-dictionary corpus."""
    c: dict[str, COSDictionary] = {}

    # ----- /S dispatch edge cases -----
    c["s_missing"] = _act(None, URI=COSString("http://a"))
    c["s_unknown"] = _act("BogusAct", URI=COSString("http://a"))
    c["s_empty_name"] = _act("")
    # /S as a COSString instead of a COSName — getNameAsString returns null.
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Action"))
    d.set_item(_n("S"), COSString("URI"))
    d.set_item(_n("URI"), COSString("http://str-s"))
    c["s_as_string"] = d
    c["s_lowercase_uri"] = _act("uri", URI=COSString("http://lc"))

    # ----- URI -----
    c["uri_good"] = _act("URI", URI=COSString("http://good"), IsMap=COSBoolean.TRUE)
    c["uri_as_name"] = _act("URI", URI=_n("http://name"))
    c["uri_missing"] = _act("URI")
    c["uri_ismap_int"] = _act("URI", URI=COSString("http://x"), IsMap=COSInteger.get(1))
    c["uri_empty"] = _act("URI", URI=COSString(""))

    # ----- GoTo -----
    c["goto_d_array"] = _act("GoTo", D=_arr(COSInteger.get(0), _n("Fit")))
    c["goto_d_name"] = _act("GoTo", D=_n("MyDest"))
    c["goto_d_string"] = _act("GoTo", D=COSString("named-dest"))
    c["goto_d_dict"] = _act("GoTo", D=COSDictionary())
    c["goto_d_missing"] = _act("GoTo")
    c["goto_d_int"] = _act("GoTo", D=COSInteger.get(7))

    # ----- GoToR -----
    c["gotor_f_string"] = _act(
        "GoToR", F=COSString("other.pdf"), D=_arr(COSInteger.get(0), _n("Fit"))
    )
    c["gotor_f_dict"] = _act(
        "GoToR", F=COSDictionary(), D=COSString("dest"), NewWindow=COSBoolean.TRUE
    )
    c["gotor_f_missing"] = _act("GoToR", D=_n("D"))
    c["gotor_newwindow_int"] = _act(
        "GoToR", F=COSString("o.pdf"), NewWindow=COSInteger.get(0)
    )

    # ----- GoToE -----
    c["gotoe_t_dict"] = _act("GoToE", F=COSString("e.pdf"), T=COSDictionary())
    c["gotoe_minimal"] = _act("GoToE")

    # ----- Launch -----
    win = COSDictionary()
    win.set_item(_n("F"), COSString("app.exe"))
    c["launch_win_dict"] = _act("Launch", Win=win, NewWindow=COSBoolean.TRUE)
    c["launch_f_string"] = _act("Launch", F=COSString("file.exe"))
    c["launch_f_dict"] = _act("Launch", F=COSDictionary())
    c["launch_missing"] = _act("Launch")
    c["launch_win_string"] = _act("Launch", Win=COSString("notdict"))

    # ----- Named -----
    c["named_nexttpage"] = _act("Named", N=_n("NextPage"))
    c["named_nonstandard"] = _act("Named", N=_n("CustomVendorAction"))
    c["named_n_string"] = _act("Named", N=COSString("NextPage"))
    c["named_n_missing"] = _act("Named")

    # ----- JavaScript -----
    c["js_string"] = _act("JavaScript", JS=COSString("app.alert(1);"))
    c["js_stream"] = _act("JavaScript", JS=_stream(b"app.alert(2);"))
    c["js_missing"] = _act("JavaScript")
    c["js_name"] = _act("JavaScript", JS=_n("notjs"))

    # ----- SubmitForm -----
    c["submit_fields_array"] = _act(
        "SubmitForm",
        F=COSString("http://submit"),
        Fields=_arr(COSString("f1"), COSString("f2")),
        Flags=COSInteger.get(4),
    )
    c["submit_fields_single"] = _act("SubmitForm", Fields=COSString("f1"))
    c["submit_missing"] = _act("SubmitForm")
    c["submit_f_dict"] = _act("SubmitForm", F=COSDictionary())

    # ----- ResetForm -----
    c["reset_fields_array"] = _act(
        "ResetForm", Fields=_arr(COSString("f1")), Flags=COSInteger.get(1)
    )
    c["reset_missing"] = _act("ResetForm")
    c["reset_fields_name"] = _act("ResetForm", Fields=_n("f1"))

    # ----- Hide -----
    c["hide_t_string"] = _act("Hide", T=COSString("field1"), H=COSBoolean.TRUE)
    c["hide_t_array"] = _act("Hide", T=_arr(COSString("a"), COSString("b")))
    c["hide_t_dict"] = _act("Hide", T=COSDictionary())
    c["hide_missing"] = _act("Hide")
    c["hide_h_false"] = _act("Hide", T=COSString("f"), H=COSBoolean.FALSE)

    # ----- Thread -----
    c["thread_d_int"] = _act("Thread", F=COSString("t.pdf"), D=COSInteger.get(0))
    c["thread_b_dict"] = _act("Thread", D=COSInteger.get(1), B=COSDictionary())
    c["thread_missing"] = _act("Thread")

    # ----- Sound -----
    c["sound_stream"] = _act("Sound", Sound=_stream(b"\x00\x01"))
    c["sound_missing"] = _act("Sound")
    c["sound_name"] = _act("Sound", Sound=_n("notsound"))

    # ----- Movie -----
    c["movie_op_name"] = _act("Movie", T=COSString("title"), Operation=_n("Play"))
    c["movie_missing"] = _act("Movie")

    # ----- ImportData -----
    c["import_f_string"] = _act("ImportData", F=COSString("data.fdf"))
    c["import_missing"] = _act("ImportData")

    # ----- SetOCGState (no dedicated factory case in upstream) -----
    c["setocg_state_array"] = _act(
        "SetOCGState", State=_arr(_n("ON")), PreserveRB=COSBoolean.TRUE
    )
    c["setocg_missing"] = _act("SetOCGState")

    # ----- /Next chains -----
    nxt_uri = _act("URI", URI=COSString("http://next"))
    c["next_single_dict"] = _act("URI", URI=COSString("http://a"), Next=nxt_uri)
    c["next_array"] = _act(
        "GoTo",
        D=_n("d"),
        Next=_arr(_act("URI", URI=COSString("http://n1")), _act("Named", N=_n("Quit"))),
    )
    nested = _act("URI", URI=COSString("http://inner"), Next=_act("Named", N=_n("Quit")))
    c["next_nested"] = _act("GoTo", D=_n("d"), Next=nested)
    c["next_unknown_member"] = _act(
        "GoTo", D=_n("d"), Next=_arr(_act("Bogus"), _act("URI", URI=COSString("http://k")))
    )
    c["next_nondict_member"] = _act(
        "GoTo", D=_n("d"), Next=_arr(COSInteger.get(5), _act("URI", URI=COSString("http://k")))
    )
    c["next_as_string"] = _act("GoTo", D=_n("d"), Next=COSString("notdict"))

    return c


# --------------------------------------------------------------- projection
#
# Mirrors ActionFactoryFuzzProbe.java exactly: same shape vocabulary, same
# per-subtype key order, same comma joining, same /Next suffix.


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


def _key(d: COSDictionary, name: str) -> str:
    return name + ":" + _shape(d.get_dictionary_object(_n(name)))


def _next_proj(d: COSDictionary) -> str:
    return "Next:" + _shape(d.get_dictionary_object(_n("Next")))


_PER_SUBTYPE: dict[str, tuple[str, ...]] = {
    "URI": ("URI", "IsMap"),
    "GoTo": ("D",),
    "GoToR": ("F", "D", "NewWindow"),
    "GoToE": ("F", "D", "T"),
    "Launch": ("F", "Win", "NewWindow"),
    "Named": ("N",),
    "JavaScript": ("JS",),
    "SubmitForm": ("F", "Fields", "Flags"),
    "ResetForm": ("Fields", "Flags"),
    "Hide": ("T", "H"),
    "Thread": ("F", "D", "B"),
    "Sound": ("Sound",),
    "Movie": ("T", "Operation"),
    "ImportData": ("F",),
    "SetOCGState": ("State", "PreserveRB"),
}


def _project_payload(action: object, d: COSDictionary, sub: str | None) -> str:
    if action is None:
        return "-"
    keys = _PER_SUBTYPE.get(sub or "")
    body = (
        ",".join(_key(d, k) for k in keys)
        if keys is not None
        else "entries:" + str(d.size())
    )
    return body + "," + _next_proj(d)


def _py_line(name: str, d: COSDictionary | None) -> str:
    try:
        action = PDActionFactory.create_action(d)
        cls = "null" if action is None else type(action).__name__
        sub = None if d is None else d.get_name_as_string(_n("S"))
        sub_disp = sub if sub is not None else "null"
        payload = _project_payload(action, d, sub if d is not None else None)
        return f"CASE {name} class={cls} sub={sub_disp} payload={payload}"
    except Exception as exc:  # noqa: BLE001 - contract probe; any failure counts
        return f"CASE {name} class=ERR sub=ERR payload=ERR:{type(exc).__name__}"


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


# Module-level keep-alive so a reloaded document (and its lazily-backed
# COSStream entries) isn't garbage-collected before projection reads its shapes.
_doc_keepalive: list[object] = []


def _reload_corpus(dir_path: Path, order: list[str]) -> dict[str, COSDictionary | None]:
    """Reload corpus.pdf and pull each /FuzzActions slot as a COSDictionary,
    so both sides parse the identical on-disk bytes (not the in-memory COS)."""
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

# Intentional, documented divergences from the Java line. Empty unless the live
# oracle surfaces a defensible difference; populated during the run.
_PINNED_DIVERGENCES: dict[str, str] = {}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_action_factory_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed / edge-case action dict dispatches + projects identically
    on pypdfbox ``PDActionFactory.create_action`` and Apache PDFBox 3.0.7
    ``PDActionFactory.createAction``, reading the same on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("ActionFactoryFuzzProbe", str(tmp_path))
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

    assert not mismatches, "action-factory parse divergence(s):\n" + "\n".join(
        mismatches
    )
