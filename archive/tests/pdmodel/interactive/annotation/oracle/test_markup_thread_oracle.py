"""Live Apache PDFBox differential parity for MARKUP ANNOTATION THREADING +
REVIEW STATE.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation`` markup
review-workflow fields and the popup back-link —
``PDAnnotationMarkup.get_popup`` / ``PDAnnotationPopup.get_open`` +
``get_parent`` back-link, ``get_in_reply_to`` (``/IRT``), ``get_reply_type``
(``/RT``), ``PDAnnotationText.get_state`` / ``get_state_model`` (``/State`` +
``/StateModel`` review states), ``get_subject`` (``/Subj``) and
``get_creation_date`` (``/CreationDate``).

This is the threading / review-state complement to the markup *appearance*
oracle (``test_text_markup_oracle.py``, wave 1442) and the props oracle (early).
Where those compare drawn geometry, this compares the *relationship graph*: a
parent comment with an open popup, a plain reply, and an Accepted/Review state
reply, all wired with ``/Popup`` / ``/IRT`` / ``/Parent`` / ``/RT`` / ``/State``
/ ``/StateModel``.

How it works
------------
pypdfbox builds the thread, saves ONCE to ``tmp_path``, then the Java probe
``MarkupThreadProbe read`` re-reads the SAME pypdfbox bytes and emits the
canonical per-annotation fingerprint (subtype, contents, subject, raw
creation-date string, reply type, IRT target, state/state-model, popup
presence + open + parent back-link). pypdfbox's own accessors are asserted to
report the IDENTICAL facts off the same reloaded document.

The high-value cases:

* ``/IRT`` reference resolution — both replies must resolve to the *parent
  comment* annotation (identity proved writer-independently via the target's
  ``/Contents`` string, since object numbers can differ between writers).
* ``/State`` + ``/StateModel`` pair read back as ``Accepted`` / ``Review``.
* The popup ``/Parent`` back-link resolving to the parent comment, with the
  popup ``/Open`` state preserved as ``True``.

Date parsing parity (``COSDictionary.get_date`` vs PDFBox ``DateConverter``)
is asserted separately via the shared ``CosStrTextDateProbe`` so a date-parse
regression surfaces against the same oracle the cos-string tests use.

Documented (NOT a bug)
----------------------
``PDAnnotationMarkup.get_in_reply_to`` returns the raw ``COSBase`` (the
referenced annotation dictionary), whereas upstream returns a ``PDAnnotation``
built via ``createAnnotation``. Lite scope avoids the recursive factory call
during dispatch wiring; both resolve to the SAME underlying COS dictionary, so
``/IRT`` target identity (which annotation it replies to) is identical — this
test asserts exactly that.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationPopup,
    PDAnnotationText,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "MarkupThreadProbe"

# Canonical PDF date string for the parent comment's /CreationDate.
_CREATION_DATE = "D:20240115120000+00'00'"

# Unique /Contents per annotation — the writer-independent identity used to
# resolve /IRT and /Popup /Parent back-links to a specific annotation.
_PARENT_CONTENTS = "parent comment"
_REPLY_CONTENTS = "first reply"
_STATE_REPLY_CONTENTS = "accepted state"


# ---------------------------------------------------------------------------
# build — a parent Text/markup annotation with an OPEN /Popup, a plain reply
# (/IRT parent, /RT /R), and an Accepted/Review state reply (/IRT parent).
# Saved once to tmp_path. Closes the document in a try/finally.
# ---------------------------------------------------------------------------


def _build_thread(path: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 400))
        doc.add_page(page)

        parent = PDAnnotationText()
        parent.set_rectangle(PDRectangle(50, 300, 80, 320))
        parent.set_contents(_PARENT_CONTENTS)
        parent.set_subject("Review subject")
        parent.set_creation_date(_CREATION_DATE)

        popup = PDAnnotationPopup()
        popup.set_rectangle(PDRectangle(150, 250, 350, 350))
        popup.set_open(True)
        popup.set_parent(parent)
        parent.set_popup(popup)

        reply = PDAnnotationText()
        reply.set_rectangle(PDRectangle(50, 200, 80, 220))
        reply.set_contents(_REPLY_CONTENTS)
        reply.set_in_reply_to(parent)
        reply.set_reply_type(PDAnnotationText.RT_REPLY)

        state_reply = PDAnnotationText()
        state_reply.set_rectangle(PDRectangle(50, 150, 80, 170))
        state_reply.set_contents(_STATE_REPLY_CONTENTS)
        state_reply.set_in_reply_to(parent)
        state_reply.set_reply_type(PDAnnotationText.RT_REPLY)
        state_reply.set_state(PDAnnotationText.STATE_ACCEPTED)
        state_reply.set_state_model(PDAnnotationText.STATE_MODEL_REVIEW)

        page.set_annotations([parent, popup, reply, state_reply])
        doc.save(str(path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Java probe parsing
# ---------------------------------------------------------------------------


def _parse_records(text: str) -> list[dict[str, object]]:
    """Parse MarkupThreadProbe read-mode output into ordered per-annotation
    records (page /Annots order)."""
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :]}
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
        elif " " in raw:
            assert current is not None
            key, _, value = raw.partition(" ")
            current[key.lower()] = value
        else:
            # Bare-key line (none of our lines are bare today, but be tolerant).
            assert current is not None
            current[raw.lower()] = ""
    return records


def _by_contents(
    records: list[dict[str, object]], contents: str
) -> dict[str, object]:
    for rec in records:
        if rec.get("contents") == contents:
            return rec
    raise AssertionError(f"no probe record with CONTENTS {contents!r}")


# ---------------------------------------------------------------------------
# pypdfbox-side reader — resolves the same threading facts off the reloaded doc
# ---------------------------------------------------------------------------


def _contents_of(base: object) -> str | None:
    if isinstance(base, COSDictionary):
        return base.get_string("Contents")
    return None


def _read_py(path: Path) -> dict[str, dict[str, object]]:
    """Read the thread back via pypdfbox accessors, keyed by /Contents."""
    facts: dict[str, dict[str, object]] = {}
    with PDDocument.load(path) as doc:
        page = doc.get_page(0)
        for annot in page.get_annotations():
            contents = annot.get_contents()
            rec: dict[str, object] = {"subtype": annot.get_subtype()}
            if isinstance(annot, PDAnnotationText):
                rec["subject"] = annot.get_subject()
                rec["creation_date"] = annot.get_creation_date()
                rec["reply_type"] = annot.get_reply_type()
                rec["irt_contents"] = _contents_of(annot.get_in_reply_to())
                rec["state"] = annot.get_state()
                rec["state_model"] = annot.get_state_model()
                popup = annot.get_popup()
                if popup is not None:
                    rec["popup_open"] = popup.get_open()
                    rec["popup_parent_contents"] = _contents_of(popup.get_parent())
                else:
                    rec["popup_open"] = None
                    rec["popup_parent_contents"] = None
            facts[contents] = rec
    return facts


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_irt_target_resolution_matches_pdfbox(tmp_path: Path) -> None:
    """HIGH-VALUE: both replies' ``/IRT`` resolves to the parent comment, exactly
    as Apache PDFBox resolves ``getInReplyTo()`` — proven by the resolved
    target's ``/Contents`` (writer-independent identity)."""
    pdf = tmp_path / "markup_thread.pdf"
    _build_thread(pdf)

    java = _parse_records(run_probe_text(_PROBE, "read", str(pdf)))
    py = _read_py(pdf)

    # Java side: both replies point at the parent comment; parent itself has none.
    assert _by_contents(java, _PARENT_CONTENTS)["irt"] == "none"
    assert _by_contents(java, _REPLY_CONTENTS)["irt"] == _PARENT_CONTENTS
    assert _by_contents(java, _STATE_REPLY_CONTENTS)["irt"] == _PARENT_CONTENTS

    # pypdfbox side: identical IRT target resolution.
    assert py[_PARENT_CONTENTS]["irt_contents"] is None
    assert py[_REPLY_CONTENTS]["irt_contents"] == _PARENT_CONTENTS
    assert py[_STATE_REPLY_CONTENTS]["irt_contents"] == _PARENT_CONTENTS


@requires_oracle
def test_popup_open_and_parent_back_link_match_pdfbox(tmp_path: Path) -> None:
    """HIGH-VALUE: the parent's ``/Popup`` is present + open, and the popup's
    ``/Parent`` back-link resolves to the parent comment — pypdfbox reports the
    same as Apache PDFBox."""
    pdf = tmp_path / "markup_thread.pdf"
    _build_thread(pdf)

    java = _parse_records(run_probe_text(_PROBE, "read", str(pdf)))
    java_parent = _by_contents(java, _PARENT_CONTENTS)
    py_parent = _read_py(pdf)[_PARENT_CONTENTS]

    # Java oracle.
    assert java_parent["popup"] == "yes"
    assert java_parent["popupopen"] == "true"
    assert java_parent["popupparent"] == _PARENT_CONTENTS

    # pypdfbox parity.
    assert py_parent["popup_open"] is True
    assert py_parent["popup_parent_contents"] == _PARENT_CONTENTS


@requires_oracle
def test_state_and_state_model_match_pdfbox(tmp_path: Path) -> None:
    """HIGH-VALUE: the state reply reads ``/State /Accepted`` + ``/StateModel
    /Review``; the plain reply and parent carry neither — identical on both
    sides."""
    pdf = tmp_path / "markup_thread.pdf"
    _build_thread(pdf)

    java = _parse_records(run_probe_text(_PROBE, "read", str(pdf)))
    py = _read_py(pdf)

    jsr = _by_contents(java, _STATE_REPLY_CONTENTS)
    assert jsr["state"] == "Accepted"
    assert jsr["statemodel"] == "Review"
    assert _by_contents(java, _REPLY_CONTENTS)["state"] == "none"
    assert _by_contents(java, _PARENT_CONTENTS)["statemodel"] == "none"

    assert py[_STATE_REPLY_CONTENTS]["state"] == "Accepted"
    assert py[_STATE_REPLY_CONTENTS]["state_model"] == "Review"
    assert py[_REPLY_CONTENTS]["state"] is None
    assert py[_PARENT_CONTENTS]["state_model"] is None


@requires_oracle
def test_reply_type_matches_pdfbox(tmp_path: Path) -> None:
    """``/RT`` reads ``R`` (reply) for every markup annotation — both replies set
    it explicitly and the parent defaults to ``R`` (a missing ``/RT`` is a
    reply, not a group), exactly as PDFBox's ``getReplyType()`` reports."""
    pdf = tmp_path / "markup_thread.pdf"
    _build_thread(pdf)

    java = _parse_records(run_probe_text(_PROBE, "read", str(pdf)))
    py = _read_py(pdf)

    for contents in (_PARENT_CONTENTS, _REPLY_CONTENTS, _STATE_REPLY_CONTENTS):
        assert _by_contents(java, contents)["rt"] == PDAnnotationText.RT_REPLY
        assert py[contents]["reply_type"] == PDAnnotationText.RT_REPLY


@requires_oracle
def test_subject_and_creation_date_match_pdfbox(tmp_path: Path) -> None:
    """``/Subj`` + the raw ``/CreationDate`` string round-trip identically; only
    the parent carries them."""
    pdf = tmp_path / "markup_thread.pdf"
    _build_thread(pdf)

    java = _parse_records(run_probe_text(_PROBE, "read", str(pdf)))
    java_parent = _by_contents(java, _PARENT_CONTENTS)
    py = _read_py(pdf)
    py_parent = py[_PARENT_CONTENTS]

    assert java_parent["subj"] == "Review subject"
    assert java_parent["creationdate"] == _CREATION_DATE
    assert py_parent["subject"] == "Review subject"
    assert py_parent["creation_date"] == _CREATION_DATE

    # The replies carry no subject / creation date on either side.
    assert _by_contents(java, _REPLY_CONTENTS)["subj"] == "none"
    assert py[_REPLY_CONTENTS]["subject"] is None


@requires_oracle
def test_creation_date_parses_like_pdfbox_dateconverter(tmp_path: Path) -> None:
    """The parent's ``/CreationDate`` parses to the SAME instant under
    ``COSDictionary.get_date`` as Apache PDFBox's ``DateConverter`` reports for
    the identical raw string (shared ``CosStrTextDateProbe``). Guards the
    creation-date PARSE path, not just the raw-string round-trip."""
    pdf = tmp_path / "markup_thread.pdf"
    _build_thread(pdf)

    java_iso = run_probe_text("CosStrTextDateProbe", "date", _CREATION_DATE).strip()

    with PDDocument.load(pdf) as doc:
        page = doc.get_page(0)
        parent = next(
            a for a in page.get_annotations() if a.get_contents() == _PARENT_CONTENTS
        )
        parsed = parent.get_cos_object().get_date("CreationDate")

    assert parsed is not None
    base = parsed.strftime("%Y-%m-%dT%H:%M:%S")
    off = parsed.utcoffset()
    total_min = 0 if off is None else int(off.total_seconds() // 60)
    sign = "-" if total_min < 0 else "+"
    total_min = abs(total_min)
    py_iso = f"{base}{sign}{total_min // 60:02d}:{total_min % 60:02d}"

    assert py_iso == java_iso
    # Sanity: the instant matches the value we wrote (2024-01-15 12:00:00 UTC).
    assert parsed.astimezone(UTC) == datetime(
        2024, 1, 15, 12, 0, 0, tzinfo=UTC
    )
