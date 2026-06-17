"""Live Apache PDFBox differential parity for the additional-actions (``/AA``)
accessor surface on ``PDPageAdditionalActions`` (page ``/O`` open + ``/C``
close) and ``PDDocumentCatalogAdditionalActions`` (catalog ``/WS`` will-save,
``/WP`` will-print, ``/WC`` will-close, ``/DS`` did-save, ``/DP`` did-print).

Unlike the pypdfbox-authored ``test_additional_actions_oracle.py`` (which
builds the file with pypdfbox and has both libraries read it), here **Apache
PDFBox AUTHORS the bytes**: ``AaTriggerJsonProbe`` builds a page ``/AA`` with
``/O`` = JavaScript and ``/C`` = GoTo plus a catalog ``/AA`` with ``/WS`` =
JavaScript and ``/DP`` = Named, saves it, reloads it, and emits — as one flat
JSON object — each trigger's presence, the dispatched action subtype, and one
salient field. pypdfbox then reads the SAME PDFBox-authored file and must
reproduce the identical JSON. A mismatch is a real bug in pypdfbox's ``/AA``
reader, its ``get_o``/``get_c``/``get_ws``/``get_dp`` getters, or the
``PDActionFactory`` dispatch driven through ``PDAction.create``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import (
    PDActionJavaScript,
)
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


def _salient(action: object | None) -> object:
    """Mirror ``AaTriggerJsonProbe.salient``: the one identifying field per
    action subtype, or ``None`` when the trigger is absent."""
    if action is None:
        return None
    if isinstance(action, PDActionJavaScript):
        return action.get_action()
    if isinstance(action, PDActionNamed):
        return action.get_n()
    if isinstance(action, PDActionGoTo):
        return action.get_destination() is not None
    return None


def _entry(action: object | None) -> dict:
    return {
        "present": action is not None,
        "subtype": None if action is None else action.get_sub_type(),  # type: ignore[attr-defined]
        "salient": _salient(action),
    }


def _py_aa_json(pdf: Path) -> dict:
    doc = PDDocument.load(str(pdf))
    try:
        catalog = doc.get_document_catalog()
        page_aa = doc.get_page(0).get_actions()
        cat_aa = catalog.get_actions()
        return {
            "page.O": _entry(None if page_aa is None else page_aa.get_o()),
            "page.C": _entry(None if page_aa is None else page_aa.get_c()),
            "catalog.WS": _entry(None if cat_aa is None else cat_aa.get_ws()),
            "catalog.WC": _entry(None if cat_aa is None else cat_aa.get_wc()),
            "catalog.WP": _entry(None if cat_aa is None else cat_aa.get_wp()),
            "catalog.DS": _entry(None if cat_aa is None else cat_aa.get_ds()),
            "catalog.DP": _entry(None if cat_aa is None else cat_aa.get_dp()),
        }
    finally:
        doc.close()


@requires_oracle
def test_aa_trigger_json_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's view of a PDFBox-authored page+catalog ``/AA`` matches
    Apache PDFBox's: present-trigger set, each present trigger's dispatched
    action subtype, and its salient field (JS source / Named name / GoTo
    destination presence) are identical."""
    pdf = tmp_path / "aa_trigger.pdf"
    # The probe authors `pdf` as a side effect, then emits the JSON view.
    java = json.loads(run_probe_text("AaTriggerJsonProbe", str(pdf)))
    py = _py_aa_json(pdf)
    assert py == java


@requires_oracle
def test_aa_trigger_json_is_non_vacuous(tmp_path: Path) -> None:
    """Guard: the PDFBox-authored file must actually carry the four triggers
    so the parity test can't pass on an empty/absent report."""
    pdf = tmp_path / "aa_trigger.pdf"
    java = json.loads(run_probe_text("AaTriggerJsonProbe", str(pdf)))
    py = _py_aa_json(pdf)
    assert py == java

    assert py["page.O"]["present"] and py["page.O"]["subtype"] == "JavaScript"
    assert py["page.C"]["present"] and py["page.C"]["subtype"] == "GoTo"
    assert py["catalog.WS"]["present"] and py["catalog.WS"]["subtype"] == "JavaScript"
    assert py["catalog.DP"]["present"] and py["catalog.DP"]["subtype"] == "Named"
    # absent triggers report cleanly as not-present on both sides
    assert not py["catalog.WC"]["present"]
    assert not py["catalog.WP"]["present"]
    assert not py["catalog.DS"]["present"]
