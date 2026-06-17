"""Live Apache PDFBox differential fuzz of the per-subtype accessor leniency of
the remaining PDAction subtypes (wave 1530, agent D).

The wave-1513 ``ActionFactoryFuzzProbe`` projected the *raw-COS* shape after
``PDActionFactory`` dispatch; it never drove the subtypes' own typed accessors.
This probe does: it builds malformed action dicts, saves ONE ``corpus.pdf``
both libraries reload, and projects the result of each typed accessor on the
three subtypes that carry typed accessors in PDFBox 3.0.7:

* ``PDActionHide`` — ``getT`` (polymorphic: string / annotation-dict / array)
  and ``getH`` (default ``True`` per PDF 32000-1 Table 200);
* ``PDActionThread`` — ``getD`` / ``getB`` (raw COSBase pass-through) and
  ``getFile`` (dispatches through ``PDFileSpecification.createFS``, which
  *throws* on a non-string/non-dict ``/F``);
* ``PDActionSound`` — ``getSound`` (``getCOSStream`` → null on a non-stream),
  ``getVolume`` (``getFloat`` + clamp to ``1.0`` outside ``[-1, 1]``),
  ``getSynchronous`` / ``getRepeat`` / ``getMix`` (boolean defaults ``False``).

``PDActionMovie`` exposes no public accessors in 3.0.7, and
``PDActionRendition`` / ``PDActionTransition`` do not exist in 3.0.7 at all —
those three are pypdfbox-only extensions with no oracle counterpart, so they
are covered by the hand-written ``test_pd_action_*_round_out`` suites, not here.

Java side: ``oracle/probes/ActionSubtypesFuzzProbe.java``. The Java line is
ground truth; any defensible divergence is pinned in ``_PINNED_DIVERGENCES``
with a CHANGES.md row, a real bug is fixed in production.
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
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_thread import PDActionThread
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


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


def _act(sub: str, **entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Action"))
    d.set_item(_n("S"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    # ----- Hide /T polymorphism + /H default -----
    c["hide_t_string"] = _act("Hide", T=COSString("field1"), H=COSBoolean.TRUE)
    c["hide_t_array"] = _act("Hide", T=_arr(COSString("a"), COSString("b")))
    c["hide_t_annot_dict"] = _act("Hide", T=COSDictionary())
    c["hide_t_name"] = _act("Hide", T=_n("notatarget"))
    c["hide_t_int"] = _act("Hide", T=COSInteger.get(3))
    c["hide_missing"] = _act("Hide")
    c["hide_h_false"] = _act("Hide", T=COSString("f"), H=COSBoolean.FALSE)
    # /H as the wrong COS type — getBoolean returns the default (true) when the
    # entry is not a COSBoolean.
    c["hide_h_int"] = _act("Hide", H=COSInteger.get(0))
    c["hide_h_name"] = _act("Hide", H=_n("true"))

    # ----- Thread /D + /B + /F -----
    c["thread_d_int"] = _act("Thread", D=COSInteger.get(0))
    c["thread_d_string"] = _act("Thread", D=COSString("My Thread"))
    c["thread_d_dict"] = _act("Thread", D=COSDictionary())
    c["thread_b_int"] = _act("Thread", D=COSInteger.get(1), B=COSInteger.get(2))
    c["thread_b_dict"] = _act("Thread", B=COSDictionary())
    c["thread_missing"] = _act("Thread")
    # /F polymorphism through PDFileSpecification.createFS.
    c["thread_f_string"] = _act("Thread", F=COSString("t.pdf"), D=COSInteger.get(0))
    fdict = COSDictionary()
    fdict.set_item(_n("Type"), _n("Filespec"))
    fdict.set_item(_n("F"), COSString("c.pdf"))
    c["thread_f_dict"] = _act("Thread", F=fdict)
    # /F as a name / int / array → createFS throws.
    c["thread_f_name"] = _act("Thread", F=_n("notafile"))
    c["thread_f_int"] = _act("Thread", F=COSInteger.get(5))
    c["thread_f_array"] = _act("Thread", F=_arr(COSString("a")))
    c["thread_f_stream"] = _act("Thread", F=_stream(b"%PDF-fake"))

    # ----- Sound /Sound + numeric/bool modifiers -----
    c["sound_stream"] = _act("Sound", Sound=_stream(b"\x00\x01\x02"))
    c["sound_missing"] = _act("Sound")
    c["sound_name"] = _act("Sound", Sound=_n("notsound"))
    c["sound_dict"] = _act("Sound", Sound=COSDictionary())
    c["sound_string"] = _act("Sound", Sound=COSString("notsound"))
    # /Volume in / out of [-1, 1] (clamp to 1.0 outside) + wrong type.
    c["sound_vol_half"] = _act("Sound", Sound=_stream(b"x"), Volume=COSFloat(0.5))
    c["sound_vol_neg"] = _act("Sound", Sound=_stream(b"x"), Volume=COSFloat(-1.0))
    c["sound_vol_over"] = _act("Sound", Sound=_stream(b"x"), Volume=COSFloat(2.0))
    c["sound_vol_int"] = _act("Sound", Sound=_stream(b"x"), Volume=COSInteger.get(1))
    c["sound_vol_name"] = _act("Sound", Sound=_stream(b"x"), Volume=_n("loud"))
    # bool modifiers as the wrong type → default false.
    c["sound_sync_true"] = _act("Sound", Sound=_stream(b"x"), Synchronous=COSBoolean.TRUE)
    c["sound_sync_int"] = _act("Sound", Sound=_stream(b"x"), Synchronous=COSInteger.get(1))
    c["sound_rep_true"] = _act("Sound", Sound=_stream(b"x"), Repeat=COSBoolean.TRUE)
    c["sound_mix_true"] = _act("Sound", Sound=_stream(b"x"), Mix=COSBoolean.TRUE)

    return c


# --------------------------------------------------------------- projection
#
# Mirrors ActionSubtypesFuzzProbe.java exactly.


def _hide_line(d: COSDictionary) -> str:
    a = PDActionHide(d)
    t = a.get_t()
    return f"t={_shape(t)},h={str(a.get_h()).lower()}"


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


def _thread_line(d: COSDictionary) -> str:
    a = PDActionThread(d)
    try:
        fs = a.get_file()
        file = "null" if fs is None else type(fs).__name__
    except Exception as exc:  # noqa: BLE001 - contract probe
        file = "ERR:" + _java_exc_name(exc)
    return f"d={_shape(a.get_d())},b={_shape(a.get_b())},file={file}"


def _sound_line(d: COSDictionary) -> str:
    a = PDActionSound(d)
    snd = a.get_sound()
    return (
        f"sound={'null' if snd is None else 'stream'}"
        f",vol={_java_float(a.get_volume())}"
        f",sync={str(a.get_synchronous()).lower()}"
        f",rep={str(a.get_repeat()).lower()}"
        f",mix={str(a.get_mix()).lower()}"
    )


# pypdfbox's get_file raises OSError where upstream raises IOException;
# normalise the class name to the Java side for the projection.
def _java_exc_name(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _java_float(value: float) -> str:
    """Render a float the way Java's ``String.valueOf(float)`` does for the
    integer-valued and half-step magnitudes this corpus uses (e.g. ``1.0``,
    ``0.5``, ``-1.0``). All corpus volumes are exactly representable so the
    shortest round-trip repr matches Java's output."""
    if value == int(value):
        return f"{value:.1f}"
    return repr(value)


def _py_line(name: str, d: COSDictionary | None) -> str:
    if d is None:
        proj = "NODICT"
    elif name.startswith("hide_"):
        proj = _hide_line(d)
    elif name.startswith("thread_"):
        proj = _thread_line(d)
    elif name.startswith("sound_"):
        proj = _sound_line(d)
    else:
        proj = "UNKNOWN"
    return f"CASE {name} {proj}"


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
    (dir_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")


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

_PINNED_DIVERGENCES: dict[str, str] = {}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_action_subtypes_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("ActionSubtypesFuzzProbe", str(tmp_path))
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
