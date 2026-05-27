"""Live PDFBox differential parity for additional-actions (``/AA``) trigger
dictionaries across all four owner contexts:

* annotation ``/AA`` — ``PDAnnotationAdditionalActions`` (E/X/D/U/Fo/Bl/PO/PC/PV/PI)
* form-field ``/AA`` — ``PDFormFieldAdditionalActions`` (K/F/V/C)
* page ``/AA`` — ``PDPageAdditionalActions`` (O/C)
* catalog ``/AA`` — ``PDDocumentCatalogAdditionalActions`` (WC/WS/DS/WP/DP)

We build one PDF with pypdfbox carrying triggers on every container (covering
the full trigger-name matrix), save it once, then compare:

* ``AdditionalActionsProbe`` — Apache PDFBox loads the file and emits, per
  ``/AA`` container, one canonical line per present trigger with the trigger's
  action subtype (and JS source / URI where applicable):
  ``<container> <trigger> <subtype> [js=<code>] [uri=<uri>]`` — sorted.
* the pypdfbox reproduction (``_py_additional_actions``) — same wrappers,
  same trigger getters (``get_e``/``get_k``/``get_o``/``get_wc`` ...), same
  canonical render.

Exact-match: the present-trigger set, each trigger's dispatched action
subtype, and the JS/URI payload must be identical to PDFBox's. A mismatch is a
real bug in a trigger getter, the AA-key dispatch, or the action factory.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import (
    PDActionJavaScript,
)
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
    PDAnnotationAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_document_catalog_additional_actions import (  # noqa: E501
    PDDocumentCatalogAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_form_field_additional_actions import (
    PDFormFieldAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_page_additional_actions import (
    PDPageAdditionalActions,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared canonical render (must match AdditionalActionsProbe) ----------


def _esc(value: str | None) -> str:
    if value is None:
        return "none"
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _describe(container: str, trigger: str, action: object | None) -> str | None:
    if action is None:
        return None
    sub = action.get_sub_type()  # type: ignore[attr-defined]
    line = f"{container} {trigger} {sub if sub is not None else 'none'}"
    if isinstance(action, PDActionJavaScript):
        line += f" js={_esc(action.get_action())}"
    elif isinstance(action, PDActionURI):
        line += f" uri={_esc(action.get_uri())}"
    return line


# ---------- PDF builder ----------


def _build_pdf(path: Path) -> None:
    """Build a PDF carrying ``/AA`` triggers on a widget annotation, a form
    field, a page, and the document catalog. Save once to ``path``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        # ---- annotation /AA on a widget: E (URI), X (JS), U (Named) ----
        widget = PDAnnotationWidget()
        annot_aa = PDAnnotationAdditionalActions()
        enter = PDActionURI()
        enter.set_uri("https://example.com/enter")
        annot_aa.set_e(enter)
        exit_action = PDActionJavaScript("app.alert('exit');")
        annot_aa.set_x(exit_action)
        up = PDActionNamed()
        up.set_sub_type("Named")
        annot_aa.set_u(up)
        widget.set_actions(annot_aa)
        page.add_annotation(widget)

        # ---- field /AA: K, F, V, C all JavaScript ----
        acro_form = PDAcroForm(doc)
        field = PDTextField(acro_form)
        field.set_partial_name("trigField")
        field_aa = PDFormFieldAdditionalActions()
        field_aa.set_k(PDActionJavaScript("AFNumber_Keystroke(2,0,0,0,'',true);"))
        field_aa.set_f(PDActionJavaScript("AFNumber_Format(2,0,0,0,'',true);"))
        field_aa.set_v(PDActionJavaScript("event.rc = (event.value >= 0);"))
        field_aa.set_c(PDActionJavaScript("AFSimple_Calculate('SUM', ['a','b']);"))
        field.set_actions(field_aa)
        fields = acro_form.get_fields()
        fields.append(field)
        acro_form.set_fields(fields)
        doc.get_document_catalog().set_acro_form(acro_form)

        # ---- page /AA: O (JS), C (GoTo) ----
        page_aa = PDPageAdditionalActions()
        page_aa.set_o(PDActionJavaScript("app.alert('page open');"))
        close_goto = PDActionGoTo()
        close_goto.set_sub_type("GoTo")
        page_aa.set_c(close_goto)
        page.set_actions(page_aa)

        # ---- catalog /AA: WC (JS), DS (JS) ----
        cat_aa = PDDocumentCatalogAdditionalActions()
        cat_aa.set_wc(PDActionJavaScript("app.alert('will close');"))
        cat_aa.set_ds(PDActionJavaScript("app.alert('did save');"))
        doc.get_document_catalog().set_actions(cat_aa)

        doc.save(str(path))
    finally:
        doc.close()


# ---------- pypdfbox reproduction (mirrors AdditionalActionsProbe) ----------

_ANNOT_TRIGGERS = (
    ("E", "get_e"),
    ("X", "get_x"),
    ("D", "get_d"),
    ("U", "get_u"),
    ("Fo", "get_fo"),
    ("Bl", "get_bl"),
    ("PO", "get_po"),
    ("PC", "get_pc"),
    ("PV", "get_pv"),
    ("PI", "get_pi"),
)
_FIELD_TRIGGERS = (("K", "get_k"), ("F", "get_f"), ("V", "get_v"), ("C", "get_c"))
_PAGE_TRIGGERS = (("O", "get_o"), ("C", "get_c"))
_CATALOG_TRIGGERS = (
    ("WC", "get_wc"),
    ("WS", "get_ws"),
    ("DS", "get_ds"),
    ("WP", "get_wp"),
    ("DP", "get_dp"),
)


def _emit(lines: list[str], container: str, aa: object, triggers: tuple) -> None:
    for trigger, getter in triggers:
        action = getattr(aa, getter)()
        line = _describe(container, trigger, action)
        if line is not None:
            lines.append(line)


def _py_additional_actions(path: Path) -> str:
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        catalog = doc.get_document_catalog()

        # catalog /AA
        cat_aa = catalog.get_actions()
        if cat_aa is not None and not cat_aa.is_empty():
            _emit(lines, "catalog", cat_aa, _CATALOG_TRIGGERS)

        # page /AA + annotation /AA
        for page in doc.get_pages():
            page_aa = page.get_actions()
            if page_aa is not None and not page_aa.is_empty():
                _emit(lines, "page", page_aa, _PAGE_TRIGGERS)
            for annot in page.get_annotations():
                if not isinstance(annot, PDAnnotationWidget):
                    continue
                annot_aa = annot.get_actions()
                if annot_aa is None or annot_aa.is_empty():
                    continue
                _emit(lines, "annot", annot_aa, _ANNOT_TRIGGERS)

        # field /AA
        form = catalog.get_acro_form()
        if form is not None:
            for field in form.get_field_tree():
                getter = getattr(field, "get_actions", None)
                if getter is None:
                    continue
                field_aa = getter()
                if field_aa is None or field_aa.is_empty():
                    continue
                _emit(lines, "field", field_aa, _FIELD_TRIGGERS)
    finally:
        doc.close()
    lines.sort()
    return "\n".join(lines) + ("\n" if lines else "")


# ---------- differential tests ----------


@requires_oracle
def test_additional_actions_match_pdfbox(tmp_path: Path) -> None:
    """Full /AA trigger matrix across annotation/field/page/catalog matches
    Apache PDFBox: present-trigger set + each trigger's action subtype +
    JS/URI payload."""
    pdf = tmp_path / "additional_actions.pdf"
    _build_pdf(pdf)
    java = run_probe_text("AdditionalActionsProbe", str(pdf))
    py = _py_additional_actions(pdf)
    assert py == java


@requires_oracle
def test_additional_actions_report_is_non_empty(tmp_path: Path) -> None:
    """Guard: the built PDF must actually carry triggers so the parity test
    can't pass vacuously on an empty report."""
    pdf = tmp_path / "additional_actions.pdf"
    _build_pdf(pdf)
    report = _py_additional_actions(pdf)
    # every container present
    assert "annot E URI" in report
    assert "field K JavaScript" in report
    assert "page O JavaScript" in report
    assert "catalog WC JavaScript" in report
