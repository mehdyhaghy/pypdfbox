"""Live Apache PDFBox differential fuzz of the typed ACCESSORS of the
less-common annotation subtypes + ``PDAnnotation.create_annotation`` factory
dispatch (wave 1554, agent E).

The existing annotation oracle suite covers dispatch-class + geometry
(``test_annotation_dispatch_fuzz_wave1515``) and appearance-stream generators
(waves 1508/1509/1536/1544). None project the per-type SCALAR accessors a buggy
or hostile producer can exercise:

  - factory: /Subtype known/unknown/missing/mistyped (a COSString instead of a
    COSName) -> concrete class create_annotation returns.
  - Link: get_highlight_mode (/H name/string/missing/bogus), get_quad_points
    arity, get_action / get_destination presence.
  - Popup: get_open (/Open bool/non-bool/missing), get_parent_markup typed cast
    (/Parent markup-dict / non-markup-dict / non-dict / fallback /P).
  - Caret: get_rect_differences (/RD missing/short/long/non-numeric/non-array).
  - RubberStamp / FileAttachment / Text: icon /Name name/string/missing/bogus.
  - Text: get_state / get_state_model (/State, /StateModel string/name/missing).

Strategy (mirrors the wave-1515 sibling): build the deterministic corpus of
annotation dictionaries directly as COS, embed them as entries of a
non-standard ``/FuzzAnnots`` COSArray hung off the document catalog, and save
ONE ``corpus.pdf`` plus a ``manifest.txt`` (one case name per line, in array
order). ``AnnotationTypeAccessorFuzzProbe`` loads that pdf, walks the array,
feeds each raw COSDictionary to ``PDAnnotation.createAnnotation`` and projects a
stable framed line. Both libraries read the exact same bytes on disk.

Validation, not blind pinning: the Java line is ground truth. Each case asserts
pypdfbox's ``PDAnnotation.create_annotation`` produces the identical
``class=... acc=...`` line. This wave FIXED four real divergences (icon/mode
accessors that read via ``getNameAsString`` upstream but only ``get_name``
[COSName-only] in pypdfbox); after the fix the Java line and pypdfbox line
agree, so there are no pinned divergences here beyond the long-standing,
already-pinned dispatch superset (which this probe does not exercise — every
subtype below dispatches identically on both sides in 3.0.7).

Caret /Sy symbol and Sound /Name icon have NO upstream accessor (they are
pypdfbox extensions), so they are NOT projected against the oracle; their
behaviour is covered by the hand-written test
``test_caret_sound_extension_accessors`` below.
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
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationCaret,
    PDAnnotationFileAttachment,
    PDAnnotationLink,
    PDAnnotationPopup,
    PDAnnotationRubberStamp,
    PDAnnotationSound,
    PDAnnotationText,
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


def _nums(*vals: float) -> COSArray:
    return _arr(
        *[
            COSInteger.get(int(v)) if float(v).is_integer() else COSFloat(float(v))
            for v in vals
        ]
    )


def _annot(sub: str | None, **entries: COSBase) -> COSDictionary:
    """An annotation dict with /Type /Annot and given /Subtype + entries.

    ``sub`` of None omits /Subtype. To set /Subtype mistyped (a COSString),
    pass ``Subtype=COSString(...)`` through ``entries`` and leave ``sub`` None.
    """
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Annot"))
    if sub is not None:
        d.set_item(_n("Subtype"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _uri_action(uri: str) -> COSDictionary:
    a = COSDictionary()
    a.set_item(_n("S"), _n("URI"))
    a.set_item(_n("URI"), COSString(uri))
    return a


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    """Deterministic, ordered annotation-dictionary corpus."""
    c: dict[str, COSDictionary] = {}

    # ----- factory dispatch (scalar-class only) -----
    c["sub_missing"] = _annot(None)
    c["sub_unknown"] = _annot("BogusAnnot")
    c["sub_link"] = _annot("Link")
    c["sub_popup"] = _annot("Popup")
    c["sub_caret"] = _annot("Caret")
    c["sub_stamp"] = _annot("Stamp")
    c["sub_fileattach"] = _annot("FileAttachment")
    c["sub_text"] = _annot("Text")
    # /Subtype mistyped as a COSString — getNameAsString still dispatches.
    ds = COSDictionary()
    ds.set_item(_n("Type"), _n("Annot"))
    ds.set_item(_n("Subtype"), COSString("Link"))
    c["sub_link_as_string"] = ds

    # ----- Link /H highlight mode -----
    c["link_h_none"] = _annot("Link", H=_n("N"))
    c["link_h_outline"] = _annot("Link", H=_n("O"))
    c["link_h_missing"] = _annot("Link")  # default I
    c["link_h_bogus"] = _annot("Link", H=_n("Z"))
    # /H stored as a COSString — upstream getNameAsString resolves it.
    c["link_h_string"] = _annot("Link", H=COSString("P"))
    c["link_h_not_name"] = _annot("Link", H=COSInteger.get(3))  # -> default I

    # ----- Link /QuadPoints + /A + /Dest -----
    c["link_qp_one"] = _annot("Link", QuadPoints=_nums(0, 0, 1, 0, 0, 1, 1, 1))
    c["link_qp_partial"] = _annot("Link", QuadPoints=_nums(0, 0, 1, 0, 0))
    c["link_qp_not_array"] = _annot("Link", QuadPoints=COSInteger.get(9))
    c["link_action"] = _annot("Link", A=_uri_action("https://example.test"))
    c["link_action_not_dict"] = _annot("Link", A=COSString("nope"))
    # /Dest as a named destination (COSName) — both sides wrap it without
    # touching the explicit-array page-ref parser, so getDestination resolves
    # non-null on both. (A bare numeric explicit-array /Dest is the
    # destination-parser's own fuzz surface and throws differently-named
    # exceptions on each side; not exercised here.)
    c["link_dest_named"] = _annot("Link", Dest=_n("intro"))
    c["link_dest_missing"] = _annot("Link")

    # ----- Popup /Open + /Parent -----
    c["popup_open_true"] = _annot("Popup", Open=COSBoolean.TRUE)
    c["popup_open_false"] = _annot("Popup", Open=COSBoolean.FALSE)
    c["popup_open_missing"] = _annot("Popup")  # default False
    c["popup_open_nonbool"] = _annot("Popup", Open=COSInteger.get(1))  # -> False
    # /Parent resolving to a markup annotation (Text) dict.
    parent_markup = _annot("Text", Contents=COSString("note"))
    c["popup_parent_markup"] = _annot("Popup", Parent=parent_markup)
    # /Parent resolving to a NON-markup annotation (Link) dict -> typed None.
    parent_link = _annot("Link")
    c["popup_parent_nonmarkup"] = _annot("Popup", Parent=parent_link)
    # /Parent not a dictionary at all.
    c["popup_parent_nondict"] = _annot("Popup", Parent=COSInteger.get(7))
    # /Parent absent but /P present (upstream fallback).
    parent_p = _annot("FreeText", Contents=COSString("ft"))
    c["popup_parent_via_p"] = _annot("Popup", P=parent_p)

    # ----- Caret /RD -----
    c["caret_rd_four"] = _annot("Caret", RD=_nums(1, 2, 3, 4))
    c["caret_rd_missing"] = _annot("Caret")  # upstream float[0]
    c["caret_rd_short"] = _annot("Caret", RD=_nums(1, 2))
    c["caret_rd_long"] = _annot("Caret", RD=_nums(1, 2, 3, 4, 5))
    c["caret_rd_nonnumeric"] = _annot(
        "Caret",
        RD=_arr(COSInteger.get(1), _n("X"), COSInteger.get(3), COSInteger.get(4)),
    )
    c["caret_rd_not_array"] = _annot("Caret", RD=COSInteger.get(5))  # -> float[0]

    # ----- RubberStamp /Name icon -----
    c["stamp_name_approved"] = _annot("Stamp", Name=_n("Approved"))
    c["stamp_name_missing"] = _annot("Stamp")  # default Draft
    c["stamp_name_bogus"] = _annot("Stamp", Name=_n("Vendor"))
    c["stamp_name_string"] = _annot("Stamp", Name=COSString("Final"))  # resolves
    c["stamp_name_not_name"] = _annot("Stamp", Name=COSInteger.get(2))  # -> Draft

    # ----- FileAttachment /Name + /FS -----
    c["fa_name_paperclip"] = _annot("FileAttachment", Name=_n("Paperclip"))
    c["fa_name_missing"] = _annot("FileAttachment")  # default PushPin
    c["fa_name_string"] = _annot("FileAttachment", Name=COSString("Tag"))  # resolves
    c["fa_name_not_name"] = _annot(
        "FileAttachment", Name=COSInteger.get(0)
    )  # -> PushPin

    # ----- Text /Name + /Open + /State + /StateModel -----
    c["text_name_help"] = _annot("Text", Name=_n("Help"))
    c["text_name_missing"] = _annot("Text")  # default Note
    c["text_name_string"] = _annot("Text", Name=COSString("Key"))  # resolves
    c["text_open_true"] = _annot("Text", Open=COSBoolean.TRUE)
    c["text_state"] = _annot(
        "Text",
        State=COSString("Accepted"),
        StateModel=COSString("Review"),
    )
    # /State as a COSName -> getString returns null (None).
    c["text_state_as_name"] = _annot("Text", State=_n("Accepted"))
    c["text_state_missing"] = _annot("Text")

    return c


# --------------------------------------------------------------- projection
#
# Mirrors AnnotationTypeAccessorFuzzProbe.java exactly.


def _bool(v: bool) -> str:
    return "true" if v else "false"


def _qp_proj(a: list[float] | None) -> str:
    if a is None:
        return "null"
    return "n" + str(len(a))


def _acc_proj(a: PDAnnotation) -> str:
    try:
        if isinstance(a, PDAnnotationLink):
            return (
                f"H={a.get_highlight_mode()} "
                f"QP={_qp_proj(a.get_quad_points())} "
                f"act={_bool(a.get_action() is not None)} "
                f"dst={_bool(a.get_destination() is not None)}"
            )
        if isinstance(a, PDAnnotationPopup):
            try:
                m = a.get_parent_markup()
                parent = "null" if m is None else type(m).__name__
            except Exception as exc:  # noqa: BLE001 - contract probe
                parent = "ERR:" + type(exc).__name__
            return f"open={_bool(a.get_open())} parent={parent}"
        if isinstance(a, PDAnnotationText):
            return (
                f"name={a.get_name()} "
                f"open={_bool(a.get_open())} "
                f"state={a.get_state() if a.get_state() is not None else 'null'} "
                f"sm={a.get_state_model() if a.get_state_model() is not None else 'null'}"
            )
        if isinstance(a, PDAnnotationFileAttachment):
            return (
                f"name={a.get_attachment_name()} "
                f"file={_bool(a.get_file() is not None)}"
            )
        if isinstance(a, PDAnnotationRubberStamp):
            return f"name={a.get_name()}"
        if a.get_subtype() == "Caret":
            rd = _caret_rd(a)
            return "rd=" + _qp_proj(rd)
        return "n/a"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return "ERR:" + type(exc).__name__


def _caret_rd(a: PDAnnotation) -> list[float] | None:
    """Mirror upstream PDAnnotationCaret.getRectDifferences: float[0] when /RD
    is absent or not a COSArray, never null."""
    if isinstance(a, PDAnnotationCaret):
        rd = a.get_rectangle_differences()
        return rd if rd is not None else []
    return None


def _py_line(name: str, d: COSDictionary | None) -> str:
    try:
        a = PDAnnotation.create_annotation(d)
        cls = type(a).__name__
        return f"CASE {name} class={cls} acc={_acc_proj(a)}"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return f"CASE {name} class=ERR:{type(exc).__name__}"


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(dir_path: Path, corpus: dict[str, COSDictionary]) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        arr = COSArray()
        for dd in corpus.values():
            arr.add(dd)
        catalog.set_item(_n("FuzzAnnots"), arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    (dir_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")


# Module-level keep-alive so a reloaded document isn't garbage-collected before
# projection reads its annotation dicts.
_doc_keepalive: list[object] = []


def _reload_corpus(
    dir_path: Path, order: list[str]
) -> dict[str, COSDictionary | None]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    out: dict[str, COSDictionary | None] = {}
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n("FuzzAnnots"))
    for i, name in enumerate(order):
        entry = arr.get_object(i)
        out[name] = entry if isinstance(entry, COSDictionary) else None
    return out


# --------------------------------------------------------------------- tests


@requires_oracle
def test_annotation_type_accessor_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed / edge-case annotation dict dispatches + projects its
    typed scalar accessors identically on pypdfbox and Apache PDFBox 3.0.7,
    reading the same on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("AnnotationTypeAccessorFuzzProbe", str(tmp_path))
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
        if pline != jline:
            mismatches.append(f"{name}:\n  py   {pline}\n  java {jline}")

    assert not mismatches, "annotation type-accessor divergence(s):\n" + "\n".join(
        mismatches
    )


def test_icon_mode_accessors_resolve_cosstring() -> None:
    """Regression pin for the wave-1554 fix: the icon/mode accessors read via
    getNameAsString upstream, so a /Name or /H stored as a COSString (malformed
    but parseable) resolves to its text rather than falling through to the
    spec default.

    Self-contained — does not require the live oracle.
    """
    link = PDAnnotationLink(_annot("Link", H=COSString("P")))
    assert link.get_highlight_mode() == "P"
    assert link.has_highlight_mode() is True
    # A non-name, non-string /H still falls through to the spec default.
    assert (
        PDAnnotationLink(_annot("Link", H=COSInteger.get(3))).get_highlight_mode()
        == PDAnnotationLink.HIGHLIGHT_MODE_INVERT
    )

    stamp = PDAnnotationRubberStamp(_annot("Stamp", Name=COSString("Final")))
    assert stamp.get_name() == "Final"

    fa = PDAnnotationFileAttachment(_annot("FileAttachment", Name=COSString("Tag")))
    assert fa.get_attachment_name() == "Tag"
    assert fa.has_attachment_name() is True

    text = PDAnnotationText(_annot("Text", Name=COSString("Key")))
    assert text.get_name() == "Key"


def test_caret_sound_extension_accessors() -> None:
    """Caret /Sy symbol and Sound /Name icon have NO upstream accessor — they
    are pypdfbox extensions, covered here rather than against the oracle.

    Self-contained.
    """
    # Caret /Sy: name resolves, default is "None", non-name falls to default.
    caret = PDAnnotationCaret(_annot("Caret", Sy=_n("P")))
    assert caret.get_symbol() == "P"
    assert caret.is_paragraph_symbol() is True
    assert PDAnnotationCaret(_annot("Caret")).get_symbol() == "None"
    assert PDAnnotationCaret(_annot("Caret")).is_no_symbol() is True
    # Caret /RD parity with upstream float[0]-when-absent contract via empty list.
    assert PDAnnotationCaret(_annot("Caret")).get_rectangle_differences() is None
    assert PDAnnotationCaret(
        _annot("Caret", RD=_nums(1, 2, 3, 4))
    ).get_rectangle_differences() == [1.0, 2.0, 3.0, 4.0]

    # Sound /Name: default Speaker, name resolves.
    sound = PDAnnotationSound(_annot("Sound", Name=_n("Mic")))
    assert sound.get_name() == "Mic"
    assert sound.is_mic_icon() is True
    assert PDAnnotationSound(_annot("Sound")).get_name() == "Speaker"
