"""Live Apache PDFBox differential parity for the signature-field /Lock + /SV
seed-value accessor surface *not* covered by ``test_sig_field_oracle.py``.

Direction: **pypdfbox-writes → Java-reads**. pypdfbox builds an AcroForm with
a ``/FT /Sig`` :class:`PDSignatureField` and the companion ``SigFieldLockSeedProbe``
loads the PDF with Apache PDFBox 3.0.7 and reports — via the *real* typed
accessors where they exist — the slices the existing probe skips:

* ``/Lock`` ``/Action`` ``All`` and ``Exclude`` variants (the existing probe
  only exercises ``Include``), plus the ``/Lock`` ``/P`` permission level.
* ``/SV`` ``/Filter`` handler name (``PDSeedValue.getFilter()``).
* ``/SV`` ``/V`` minimum-version (``PDSeedValue.getV()`` — a primitive
  ``float``; PDFBox returns ``-1.0`` when ``/V`` is absent).
* ``/SV`` ``/MDP`` ``/P`` permission (``PDSeedValue.getMDP().getP()``).
* ``/SV`` ``/AddRevInfo`` required-flag (``PDSeedValue.isAddRevInfoRequired()``).

Upstream note: PDFBox 3.0.7's ``PDSignatureField`` has **no** ``getLock()``
accessor and ships no ``PDSignatureLock`` class, so the probe reads ``/Lock``
straight off the field's COS dictionary — the spec-defined facts pypdfbox's
typed :class:`PDSignatureLock` wrapper must reproduce. pypdfbox's
``PDSeedValue.get_v()`` deliberately returns ``None`` (not ``-1.0``) when
``/V`` is absent; here we set ``/V`` so both sides return the same real value.
"""

from __future__ import annotations

import json
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSeedValueMDP,
    PDSignatureLock,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from tests.oracle.harness import requires_oracle, run_probe_text

_EXCLUDE_FIELDS = ["sig1", "sig2"]


def _build(
    out: Path,
    *,
    lock_action: str,
    lock_fields: list[str] | None,
    lock_p: int | None,
    sv_filter: str | None,
    sv_v: float | None,
    sv_mdp_p: int | None,
    sv_add_rev_info: bool,
) -> None:
    doc = PDDocument()
    try:
        page = PDPage()
        page.set_resources(PDResources())
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        sig = PDSignatureField(form)
        sig.set_partial_name("Signature1")
        widget = sig.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 600, 250, 700))

        lock = PDSignatureLock()
        lock.set_action(lock_action)
        if lock_fields is not None:
            lock.set_fields(lock_fields)
        if lock_p is not None:
            lock.set_p(lock_p)
        sig.set_lock(lock)

        sv = PDSeedValue()
        if sv_filter is not None:
            sv.set_filter(sv_filter)
        if sv_v is not None:
            sv.set_v(sv_v)
        if sv_mdp_p is not None:
            mdp = PDSeedValueMDP()
            mdp.set_p(sv_mdp_p)
            sv.set_mdp(mdp)
        if sv_add_rev_info:
            sv.set_add_rev_info_required(True)
        sig.set_seed_value(sv)

        form.set_fields([sig])
        page.get_annotations().append(widget.get_cos_object())
        doc.save(out)
    finally:
        doc.close()


def _probe(out: Path) -> dict:
    return json.loads(run_probe_text("SigFieldLockSeedProbe", str(out)))


@requires_oracle
def test_lock_action_all_no_fields(tmp_path: Path) -> None:
    """``/Action /All`` (every field locked) — no ``/Fields`` array. PDFBox
    reads back the same action name pypdfbox holds, and confirms ``/Fields``
    is absent."""
    out = tmp_path / "lock_all.pdf"
    _build(
        out,
        lock_action=PDSignatureLock.ACTION_ALL,
        lock_fields=None,
        lock_p=None,
        sv_filter=None,
        sv_v=None,
        sv_mdp_p=None,
        sv_add_rev_info=False,
    )

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        lock = field.get_lock()
        assert lock is not None
        py_action = lock.get_action()
        py_fields = lock.get_fields()
        py_is_all = lock.is_lock_all()

    java = _probe(out)
    assert java["field_present"] is True
    assert java["lock"]["action"] == "All"
    assert "fields" not in java["lock"]
    assert py_action == java["lock"]["action"]
    assert py_action == PDSignatureLock.ACTION_ALL
    assert py_is_all is True
    assert py_fields is None


@requires_oracle
def test_lock_action_exclude_with_fields_and_p(tmp_path: Path) -> None:
    """``/Action /Exclude`` with a multi-entry ``/Fields`` array and a ``/P``
    permission level — PDFBox reads each slice exactly as pypdfbox holds it."""
    out = tmp_path / "lock_exclude.pdf"
    _build(
        out,
        lock_action=PDSignatureLock.ACTION_EXCLUDE,
        lock_fields=_EXCLUDE_FIELDS,
        lock_p=PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS,
        sv_filter=None,
        sv_v=None,
        sv_mdp_p=None,
        sv_add_rev_info=False,
    )

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        lock = field.get_lock()
        assert lock is not None
        py_action = lock.get_action()
        py_fields = lock.get_fields()
        py_p = lock.get_p()
        py_is_exclude = lock.is_lock_exclude()

    java = _probe(out)
    assert java["lock"]["action"] == "Exclude"
    assert py_action == java["lock"]["action"]
    assert py_is_exclude is True

    assert java["lock"]["fields"] == _EXCLUDE_FIELDS
    assert py_fields == _EXCLUDE_FIELDS
    assert py_fields == java["lock"]["fields"]

    assert java["lock"]["p"] == PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS
    assert py_p == java["lock"]["p"]
    assert py_p == 3


@requires_oracle
def test_seed_value_filter_v_mdp_addrevinfo(tmp_path: Path) -> None:
    """The ``/SV`` ``/Filter``, ``/V``, ``/MDP /P``, and ``/AddRevInfo`` flag
    read back through PDFBox's typed accessors exactly as pypdfbox's accessors
    report them — the slices ``SigFieldProbe`` does not exercise."""
    out = tmp_path / "sv_extra.pdf"
    _build(
        out,
        lock_action=PDSignatureLock.ACTION_INCLUDE,
        lock_fields=["f"],
        lock_p=None,
        sv_filter=PDSeedValue.FILTER_ADOBE_PPKLITE,
        sv_v=2.0,
        sv_mdp_p=PDSeedValueMDP.P_FORM_FILL_AND_SIGN,
        sv_add_rev_info=True,
    )

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        sv = field.get_seed_value()
        assert sv is not None
        py_filter = sv.get_filter()
        py_v = sv.get_v()
        py_mdp = sv.get_mdp()
        py_mdp_p = py_mdp.get_p() if py_mdp is not None else None
        py_add_rev = sv.is_add_rev_info_required()

    java = _probe(out)["sv"]

    assert java["filter"] == "Adobe.PPKLite"
    assert py_filter == java["filter"]
    assert py_filter == PDSeedValue.FILTER_ADOBE_PPKLITE

    # PDFBox emits getV() as a float; pypdfbox get_v() returns float.
    assert java["v"] == 2.0
    assert py_v == java["v"]

    assert java["mdpP"] == PDSeedValueMDP.P_FORM_FILL_AND_SIGN
    assert py_mdp_p == java["mdpP"]
    assert py_mdp_p == 2

    assert java["addRevInfoReq"] is True
    assert py_add_rev is True
    assert py_add_rev == java["addRevInfoReq"]


@requires_oracle
def test_seed_value_absent_optional_slices(tmp_path: Path) -> None:
    """When ``/Filter`` / ``/V`` / ``/MDP`` are not written, PDFBox's accessors
    report the spec-defined absent sentinels: ``getFilter()`` ``null`` (omitted
    from JSON), ``getV()`` ``-1.0``, ``getMDP()`` ``null`` (probe emits ``-1``),
    and ``isAddRevInfoRequired()`` ``false``."""
    out = tmp_path / "sv_absent.pdf"
    _build(
        out,
        lock_action=PDSignatureLock.ACTION_ALL,
        lock_fields=None,
        lock_p=None,
        sv_filter=None,
        sv_v=None,
        sv_mdp_p=None,
        sv_add_rev_info=False,
    )

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        sv = field.get_seed_value()
        assert sv is not None
        py_filter = sv.get_filter()
        py_v = sv.get_v()
        py_mdp = sv.get_mdp()
        py_add_rev = sv.is_add_rev_info_required()

    java = _probe(out)["sv"]

    # pypdfbox get_filter() returns None when /Filter is absent — matches
    # PDFBox getFilter()==null (the probe omits the key entirely).
    assert "filter" not in java
    assert py_filter is None

    # PDFBox getV() returns -1.0 when /V absent; pypdfbox get_v() diverges
    # deliberately, returning None (documented). Assert each side's contract.
    assert java["v"] == -1.0
    assert py_v is None

    # PDFBox getMDP() returns null (probe emits -1); pypdfbox get_mdp() None.
    assert java["mdpP"] == -1
    assert py_mdp is None

    assert java["addRevInfoReq"] is False
    assert py_add_rev is False
