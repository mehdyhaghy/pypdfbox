"""Fuzz / parity battery for the popup + markup-reply wiring surface.

Wave 1598, agent A. Pins pypdfbox against the observed behaviour of Apache
PDFBox 3.0.7, captured live from ``PopupReplyWiringProbe`` (see
``archive/oracle/probes/PopupReplyWiringProbe.java``) on 2026-07-05:

* ``PDAnnotationPopup.getOpen`` / ``setOpen`` — COSBoolean-only reads with a
  ``false`` default; strings / ints / names in ``/Open`` are ignored.
* ``PDAnnotationPopup.getParent`` — ``/Parent``-then-``/P`` resolution plus
  the markup-only downcast: a parent resolving to a non-markup annotation
  (Link, Widget), an unknown subtype, a subtype-less dict, or a non-dict
  value all yield ``null`` upstream.
* ``PDAnnotationMarkup`` review-workflow entries — ``/RT`` (name AND string
  coercion via ``getNameAsString``, wrong types fall back to ``R``), ``/CA``
  (numeric-only, 1.0 default, negatives passed through), ``/Subj`` and ``/T``
  (COSString-only via ``getString``), ``/IT`` (name-or-string), ``/RC``
  (COSString or COSStream body incl. PDFDocEncoding and UTF-16BE BOM
  decoding), ``/Popup`` (dict-only), ``/IRT`` (createAnnotation dispatch),
  ``/ExData`` (typed PDExternalDataDictionary wrapper, dict-only).
* Full popup <-> markup <-> reply pointer wiring across a save + reload
  round trip (dict identity of ``/Popup``, ``/Parent`` and ``/IRT`` targets).

Every case computes a Java-comparable projection string (``null``, ``true``,
class simple names, plain values) so the sibling oracle test
(``oracle/test_popup_reply_wiring_fuzz_wave1598_oracle.py``) can diff the
identical projection against the live probe output.

Deviation notes (docstring-documented "lite" shapes, exercised here through
upstream-equivalent projections):

* ``PDAnnotationMarkup.get_in_reply_to`` returns the raw resolved COS value
  where upstream ``getInReplyTo`` runs ``PDAnnotation.createAnnotation`` on
  it; the projection below applies ``PDAnnotation.create`` to the raw value,
  which is the identical dispatch.
* ``PDAnnotationPopup.get_parent`` returns the raw COS value; the typed
  upstream-equivalent accessor is ``get_parent_markup`` and that is what the
  parent cases project.
"""

from __future__ import annotations

import io
from functools import lru_cache

import pytest

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
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- Java-style projection helpers ----------


def _j(value: object) -> str:
    """Render a projection value the way the Java probe prints it."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _annot_dict(subtype: str | None) -> COSDictionary:
    d = COSDictionary()
    if subtype is not None:
        d.set_name("Subtype", subtype)
    return d


def _popup_open(open_value: COSBase | None) -> str:
    d = COSDictionary()
    if open_value is not None:
        d.set_item("Open", open_value)
    return _j(PDAnnotationPopup(d).get_open())


def _popup_parent(
    parent_value: COSBase | None = None, p_value: COSBase | None = None
) -> str:
    d = COSDictionary()
    if parent_value is not None:
        d.set_item("Parent", parent_value)
    if p_value is not None:
        d.set_item("P", p_value)
    markup = PDAnnotationPopup(d).get_parent_markup()
    return _j(None if markup is None else type(markup).__name__)


def _irt_projection(irt_value: COSBase | None) -> str:
    """Upstream getInReplyTo == createAnnotation(resolved /IRT) when it is a
    dictionary, else null; pypdfbox returns the raw COS, so the projection
    applies the same PDAnnotation.create dispatch on top."""
    ann = PDAnnotationText()
    if irt_value is not None:
        ann.get_cos_object().set_item("IRT", irt_value)
    value = ann.get_in_reply_to()
    if isinstance(value, COSDictionary):
        return type(PDAnnotation.create(value)).__name__
    return "null"


def _rc_stream(body: bytes) -> str:
    ann = PDAnnotationText()
    st = COSStream()
    with st.create_output_stream() as out:
        out.write(body)
    ann.get_cos_object().set_item("RC", st)
    return _j(ann.get_rich_contents())


def _popup_get(popup_value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if popup_value is not None:
        ann.get_cos_object().set_item("Popup", popup_value)
    popup = ann.get_popup()
    return _j(None if popup is None else type(popup).__name__)


# ---------- individual case projections ----------


def _case_popup_fresh_subtype() -> str:
    fresh = PDAnnotationPopup()
    return _j(fresh.get_cos_object().get_name_as_string("Subtype"))


def _case_popup_setopen_raw() -> str:
    fresh = PDAnnotationPopup()
    fresh.set_open(True)
    raw = fresh.get_cos_object().get_item("Open")
    return f"{type(raw).__name__}:{_j(raw.value)}"


def _case_popup_setparent_key_parent() -> str:
    popup = PDAnnotationPopup()
    markup = PDAnnotationText()
    popup.set_parent(markup)
    return _j(popup.get_cos_object().get_item("Parent") is markup.get_cos_object())


def _case_popup_setparent_key_p() -> str:
    popup = PDAnnotationPopup()
    popup.set_parent(PDAnnotationText())
    value = popup.get_cos_object().get_item("P")
    return _j(None if value is None else type(value).__name__)


def _rt_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("RT", value)
    return _j(ann.get_reply_type())


def _case_rt_set_raw() -> str:
    ann = PDAnnotationText()
    ann.set_reply_type("Group")
    raw = ann.get_cos_object().get_item("RT")
    return f"{type(raw).__name__}:{raw.name}"


def _ca_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("CA", value)
    return _j(ann.get_constant_opacity())


def _case_ca_set_raw() -> str:
    ann = PDAnnotationText()
    ann.set_constant_opacity(0.5)
    raw = ann.get_cos_object().get_item("CA")
    return f"{type(raw).__name__}:{_j(ann.get_constant_opacity())}"


def _subj_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("Subj", value)
    return _j(ann.get_subject())


def _it_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("IT", value)
    return _j(ann.get_intent())


def _title_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("T", value)
    return _j(ann.get_title_popup())


def _rc_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("RC", value)
    return _j(ann.get_rich_contents())


def _case_rc_set_raw() -> str:
    ann = PDAnnotationText()
    ann.set_rich_contents("<body>rich</body>")
    raw = ann.get_cos_object().get_item("RC")
    return f"{type(raw).__name__}:{_j(ann.get_rich_contents())}"


def _case_popup_set_wire() -> str:
    ann = PDAnnotationText()
    popup = PDAnnotationPopup()
    ann.set_popup(popup)
    return _j(ann.get_cos_object().get_item("Popup") is popup.get_cos_object())


def _case_irt_set_wire() -> str:
    target = PDAnnotationText()
    replier = PDAnnotationText()
    replier.set_in_reply_to(target)
    return _j(replier.get_cos_object().get_item("IRT") is target.get_cos_object())


def _exdata_with(value: COSBase | None) -> str:
    ann = PDAnnotationText()
    if value is not None:
        ann.get_cos_object().set_item("ExData", value)
    wrapped = ann.get_external_data()
    return _j(None if wrapped is None else type(wrapped).__name__)


def _case_exdata_dict() -> str:
    ann = PDAnnotationText()
    exd = COSDictionary()
    exd.set_name("Type", "ExData")
    exd.set_name("Subtype", "Markup3D")
    ann.get_cos_object().set_item("ExData", exd)
    wrapped = ann.get_external_data()
    return f"{type(wrapped).__name__}:{_j(wrapped.get_subtype())}"


# ---------- save/reload wiring round trip ----------


@lru_cache(maxsize=1)
def _wire_cases() -> dict[str, str]:
    """Mirror the probe's document: markup + wired popup + reply, saved and
    reloaded, projecting pointer identity and dispatch after the round trip."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)

        markup = PDAnnotationText()
        markup.set_rectangle(PDRectangle(100, 700, 120, 720))
        markup.set_contents("note body")
        markup.set_title_popup("Reviewer")

        popup = PDAnnotationPopup()
        popup.set_rectangle(PDRectangle(120, 640, 320, 700))
        popup.set_open(True)
        popup.set_parent(markup)
        markup.set_popup(popup)

        reply = PDAnnotationText()
        reply.set_rectangle(PDRectangle(100, 600, 120, 620))
        reply.set_contents("reply body")
        reply.set_in_reply_to(markup)
        reply.set_reply_type("R")

        page.set_annotations([markup, popup, reply])
        buf = io.BytesIO()
        doc.save(buf)

    doc2 = PDDocument.load(buf.getvalue())
    try:
        annots = doc2.get_page(0).get_annotations()
        m2, p2, r2 = annots
        parent2 = p2.get_parent_markup()
        return {
            "WIRE_COUNT": str(len(annots)),
            "WIRE_CLASSES": ",".join(type(a).__name__ for a in annots),
            "WIRE_POPUP_CLASS": _j(type(m2.get_popup()).__name__),
            "WIRE_POPUP_SAME_DICT": _j(
                m2.get_popup().get_cos_object() is p2.get_cos_object()
            ),
            "WIRE_PARENT_SAME_DICT": _j(
                parent2 is not None
                and parent2.get_cos_object() is m2.get_cos_object()
            ),
            "WIRE_IRT_SAME_DICT": _j(r2.get_in_reply_to() is m2.get_cos_object()),
            "WIRE_REPLYTYPE": _j(r2.get_reply_type()),
            "WIRE_POPUP_OPEN": _j(p2.get_open()),
            "WIRE_TITLE": _j(m2.get_title_popup()),
            "WIRE_PARENT_TITLE": _j(
                None if parent2 is None else parent2.get_title_popup()
            ),
        }
    finally:
        doc2.close()


# ---------- the full case table ----------


def build_python_cases() -> dict[str, str]:
    """Compute every projection from pypdfbox — same names, same grammar as
    the Java probe's ``CASE <name> <value>`` lines."""
    cases: dict[str, str] = {
        # PDAnnotationPopup /Open
        "POPUP_FRESH_SUBTYPE": _case_popup_fresh_subtype(),
        "POPUP_OPEN_DEFAULT": _popup_open(None),
        "POPUP_OPEN_TRUE": _popup_open(COSBoolean.get(True)),
        "POPUP_OPEN_FALSE": _popup_open(COSBoolean.get(False)),
        "POPUP_OPEN_STRING": _popup_open(COSString("true")),
        "POPUP_OPEN_INT": _popup_open(COSInteger.get(1)),
        "POPUP_OPEN_NAME": _popup_open(COSName.get_pdf_name("true")),
        "POPUP_SETOPEN_RAW": _case_popup_setopen_raw(),
        # PDAnnotationPopup /Parent vs /P
        "POPUP_PARENT_ABSENT": _popup_parent(),
        "POPUP_PARENT_TEXT": _popup_parent(_annot_dict("Text")),
        "POPUP_PARENT_P_FALLBACK": _popup_parent(None, _annot_dict("Text")),
        "POPUP_PARENT_PRECEDENCE": _popup_parent(
            _annot_dict("Square"), _annot_dict("Text")
        ),
        "POPUP_PARENT_LINK": _popup_parent(_annot_dict("Link")),
        "POPUP_PARENT_WIDGET": _popup_parent(_annot_dict("Widget")),
        "POPUP_PARENT_FILEATTACHMENT": _popup_parent(_annot_dict("FileAttachment")),
        "POPUP_PARENT_UNKNOWN_SUBTYPE": _popup_parent(_annot_dict("FooBar77")),
        "POPUP_PARENT_NO_SUBTYPE": _popup_parent(_annot_dict(None)),
        "POPUP_PARENT_ARRAY": _popup_parent(COSArray()),
        "POPUP_PARENT_NAME": _popup_parent(COSName.get_pdf_name("NotADict")),
        "POPUP_SETPARENT_KEY_PARENT": _case_popup_setparent_key_parent(),
        "POPUP_SETPARENT_KEY_P": _case_popup_setparent_key_p(),
        # /RT reply type
        "RT_DEFAULT": _rt_with(None),
        "RT_NAME_GROUP": _rt_with(COSName.get_pdf_name("Group")),
        "RT_STRING_GROUP": _rt_with(COSString("Group")),
        "RT_INT": _rt_with(COSInteger.get(5)),
        "RT_SET_RAW": _case_rt_set_raw(),
        # /CA constant opacity
        "CA_DEFAULT": _ca_with(None),
        "CA_INT_ZERO": _ca_with(COSInteger.get(0)),
        "CA_FLOAT_QUARTER": _ca_with(COSFloat(0.25)),
        "CA_STRING": _ca_with(COSString("0.5")),
        "CA_NEGATIVE": _ca_with(COSFloat(-0.5)),
        "CA_SET_RAW": _case_ca_set_raw(),
        # /Subj, /IT, /T
        "SUBJ_DEFAULT": _subj_with(None),
        "SUBJ_STRING": _subj_with(COSString("a subject")),
        "SUBJ_NAME": _subj_with(COSName.get_pdf_name("NameSubject")),
        "IT_DEFAULT": _it_with(None),
        "IT_NAME": _it_with(COSName.get_pdf_name("FreeTextCallout")),
        "IT_STRING": _it_with(COSString("FreeTextCallout")),
        "IT_INT": _it_with(COSInteger.get(3)),
        "TITLE_DEFAULT": _title_with(None),
        "TITLE_STRING": _title_with(COSString("Reviewer")),
        "TITLE_NAME": _title_with(COSName.get_pdf_name("Reviewer")),
        # /RC rich contents
        "RC_ABSENT": _rc_with(None),
        "RC_SET_RAW": _case_rc_set_raw(),
        "RC_STREAM_ASCII": _rc_stream(b"<body>stream rich</body>"),
        "RC_STREAM_PDFDOC": _rc_stream(b"caf\xe9"),
        "RC_STREAM_UTF16BOM": _rc_stream(b"\xfe\xff\x00h\x00i"),
        "RC_NAME": _rc_with(COSName.get_pdf_name("NotRich")),
        "RC_INT": _rc_with(COSInteger.get(7)),
        # /Popup accessor
        "POPUP_GET_ABSENT": _popup_get(None),
        "POPUP_GET_DICT": _popup_get(_annot_dict("Popup")),
        "POPUP_GET_ARRAY": _popup_get(COSArray()),
        "POPUP_GET_NAME": _popup_get(COSName.get_pdf_name("NotAPopup")),
        "POPUP_SET_WIRE": _case_popup_set_wire(),
        # /IRT in-reply-to dispatch
        "IRT_ABSENT": _irt_projection(None),
        "IRT_TEXT": _irt_projection(_annot_dict("Text")),
        "IRT_HIGHLIGHT": _irt_projection(_annot_dict("Highlight")),
        "IRT_UNKNOWN_SUBTYPE": _irt_projection(_annot_dict("ZapZap99")),
        "IRT_STRING": _irt_projection(COSString("nope")),
        "IRT_INT": _irt_projection(COSInteger.get(4)),
        "IRT_SET_WIRE": _case_irt_set_wire(),
        # /ExData
        "EXDATA_ABSENT": _exdata_with(None),
        "EXDATA_DICT": _case_exdata_dict(),
        "EXDATA_ARRAY": _exdata_with(COSArray()),
    }
    cases.update(_wire_cases())
    return cases


# Pinned PDFBox 3.0.7 probe output (PopupReplyWiringProbe, 2026-07-05).
EXPECTED: dict[str, str] = {
    "POPUP_FRESH_SUBTYPE": "Popup",
    "POPUP_OPEN_DEFAULT": "false",
    "POPUP_OPEN_TRUE": "true",
    "POPUP_OPEN_FALSE": "false",
    "POPUP_OPEN_STRING": "false",
    "POPUP_OPEN_INT": "false",
    "POPUP_OPEN_NAME": "false",
    "POPUP_SETOPEN_RAW": "COSBoolean:true",
    "POPUP_PARENT_ABSENT": "null",
    "POPUP_PARENT_TEXT": "PDAnnotationText",
    "POPUP_PARENT_P_FALLBACK": "PDAnnotationText",
    "POPUP_PARENT_PRECEDENCE": "PDAnnotationSquare",
    "POPUP_PARENT_LINK": "null",
    "POPUP_PARENT_WIDGET": "null",
    "POPUP_PARENT_FILEATTACHMENT": "PDAnnotationFileAttachment",
    "POPUP_PARENT_UNKNOWN_SUBTYPE": "null",
    "POPUP_PARENT_NO_SUBTYPE": "null",
    "POPUP_PARENT_ARRAY": "null",
    "POPUP_PARENT_NAME": "null",
    "POPUP_SETPARENT_KEY_PARENT": "true",
    "POPUP_SETPARENT_KEY_P": "null",
    "RT_DEFAULT": "R",
    "RT_NAME_GROUP": "Group",
    "RT_STRING_GROUP": "Group",
    "RT_INT": "R",
    "RT_SET_RAW": "COSName:Group",
    "CA_DEFAULT": "1.0",
    "CA_INT_ZERO": "0.0",
    "CA_FLOAT_QUARTER": "0.25",
    "CA_STRING": "1.0",
    "CA_NEGATIVE": "-0.5",
    "CA_SET_RAW": "COSFloat:0.5",
    "SUBJ_DEFAULT": "null",
    "SUBJ_STRING": "a subject",
    "SUBJ_NAME": "null",
    "IT_DEFAULT": "null",
    "IT_NAME": "FreeTextCallout",
    "IT_STRING": "FreeTextCallout",
    "IT_INT": "null",
    "TITLE_DEFAULT": "null",
    "TITLE_STRING": "Reviewer",
    "TITLE_NAME": "null",
    "RC_ABSENT": "null",
    "RC_SET_RAW": "COSString:<body>rich</body>",
    "RC_STREAM_ASCII": "<body>stream rich</body>",
    "RC_STREAM_PDFDOC": "café",
    "RC_STREAM_UTF16BOM": "hi",
    "RC_NAME": "null",
    "RC_INT": "null",
    "POPUP_GET_ABSENT": "null",
    "POPUP_GET_DICT": "PDAnnotationPopup",
    "POPUP_GET_ARRAY": "null",
    "POPUP_GET_NAME": "null",
    "POPUP_SET_WIRE": "true",
    "IRT_ABSENT": "null",
    "IRT_TEXT": "PDAnnotationText",
    "IRT_HIGHLIGHT": "PDAnnotationHighlight",
    "IRT_UNKNOWN_SUBTYPE": "PDAnnotationUnknown",
    "IRT_STRING": "null",
    "IRT_INT": "null",
    "IRT_SET_WIRE": "true",
    "EXDATA_ABSENT": "null",
    "EXDATA_DICT": "PDExternalDataDictionary:Markup3D",
    "EXDATA_ARRAY": "null",
    "WIRE_COUNT": "3",
    "WIRE_CLASSES": "PDAnnotationText,PDAnnotationPopup,PDAnnotationText",
    "WIRE_POPUP_CLASS": "PDAnnotationPopup",
    "WIRE_POPUP_SAME_DICT": "true",
    "WIRE_PARENT_SAME_DICT": "true",
    "WIRE_IRT_SAME_DICT": "true",
    "WIRE_REPLYTYPE": "R",
    "WIRE_POPUP_OPEN": "true",
    "WIRE_TITLE": "Reviewer",
    "WIRE_PARENT_TITLE": "Reviewer",
}


@pytest.fixture(scope="module")
def python_cases() -> dict[str, str]:
    return build_python_cases()


@pytest.mark.parametrize("name", sorted(EXPECTED), ids=sorted(EXPECTED))
def test_popup_reply_wiring_matches_pinned_pdfbox(
    name: str, python_cases: dict[str, str]
) -> None:
    assert python_cases[name] == EXPECTED[name]


def test_case_tables_cover_the_same_surface(python_cases: dict[str, str]) -> None:
    assert set(python_cases) == set(EXPECTED)
