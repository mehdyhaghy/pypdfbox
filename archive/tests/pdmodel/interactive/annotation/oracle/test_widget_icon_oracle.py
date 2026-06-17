"""Live Apache PDFBox differential parity for the push-button WIDGET ``/MK``
ICON facet (wave 1468).

Surface under test (``pypdfbox/pdmodel/interactive/annotation/``
``PDAppearanceCharacteristicsDictionary``):

  * ``/I``  normal icon    -> :meth:`get_normal_icon_form`    : ``PDFormXObject``
  * ``/RI`` rollover icon  -> :meth:`get_rollover_icon_form`  : ``PDFormXObject``
  * ``/IX`` alternate icon -> :meth:`get_alternate_icon_form` : ``PDFormXObject``

In Apache PDFBox 3.0.7 ``PDAppearanceCharacteristicsDictionary`` exposes the
three icon getters as a typed ``PDFormXObject`` (``getNormalIcon`` /
``getRolloverIcon`` / ``getAlternateIcon``) — there is NO icon setter, NO
``getTextPosition`` (``/TP``), NO ``getIconFit`` / ``/IF`` accessor, and NO
``PDIconFit`` class in 3.0.7. pypdfbox carries ``/TP`` (``get_text_position``)
and a ``PDIconFit`` (``/IF``) ahead of upstream as a forward port; those are
NOT differentiable against 3.0.7, so this oracle pins ONLY the real 3.0.7
surface: the three icon form-XObject references and the facts read off each
returned form (``/BBox``, ``/Matrix``, ``/FormType``). pypdfbox's matching
getters are the ``*_icon_form`` variants (the bare ``get_normal_icon`` returns
the raw ``COSStream`` lite-form; ``get_normal_icon_form`` returns the typed
``PDFormXObject`` that mirrors upstream's return type).

Why this is a NON-colliding surface
------------------------------------
``WidgetMkProbe`` (wave 1455) covered ``/CA`` ``/RC`` ``/AC`` captions, the
``/BC`` ``/BG`` colour-arity dispatch, and ``/R`` rotation. ``WidgetApProbe``
(wave 1434) covered ``/AS`` ``/AP`` keying + ``/BG`` ``/BC`` ``/CA`` ``/R``.
Neither read the ``/I`` ``/RI`` ``/IX`` icon form-XObject references — that is
this probe's facet.

The fixture is BUILT by Apache PDFBox (the authoritative writer) so the
differential is purely pypdfbox's READ path against what upstream wrote. The
``/I`` ``/RI`` ``/IX`` keys are installed on the raw ``/MK`` dictionary (no
upstream setter) exactly as a real form-authoring tool would.

High-value invariants
---------------------
  * present icon — the returned form's ``/BBox`` (4 canonical floats),
    ``/Matrix`` (6 canonical floats), and ``/FormType`` parse identically;
  * absent icon — a missing ``/RI`` / ``/IX`` key yields ``None`` (reported
    ``"none"``) under both;
  * non-stream value — an ``/I`` whose value is a name (not a stream) yields
    ``None`` (must not throw) under both — the graceful-degradation triage
    signal.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "WidgetIconProbe"


# --------------------------------------------------------------------------- #
# canonical float rendering — mirrors WidgetIconProbe.canonFloat (Java)
# --------------------------------------------------------------------------- #
def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


# --------------------------------------------------------------------------- #
# Java probe driver — build the fixture with Apache PDFBox, parse READ output
# --------------------------------------------------------------------------- #
def _build_fixture(path: Path) -> None:
    run_probe_text(_PROBE, "build", str(path))


def _parse_java(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        if raw.startswith("WIDGET "):
            current = {"T": raw[len("WIDGET ") :]}
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
        elif current is not None:
            key, _, value = raw.partition(" ")
            current[key] = value
    return records


def _java_records(path: Path) -> list[dict[str, str]]:
    return _parse_java(run_probe_text(_PROBE, "read", str(path)))


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors WidgetIconProbe.form() exactly
# --------------------------------------------------------------------------- #
def _form_facts(form) -> str:
    if form is None:
        return "none"
    bbox = form.get_bbox()
    if bbox is None:
        bbox_str = "none"
    else:
        bbox_str = ",".join(
            _canon_float(v)
            for v in (
                bbox.get_lower_left_x(),
                bbox.get_lower_left_y(),
                bbox.get_upper_right_x(),
                bbox.get_upper_right_y(),
            )
        )
    matrix_str = " ".join(_canon_float(v) for v in form.get_matrix())
    return f"{bbox_str} ; {matrix_str} ; {form.get_form_type()}"


def _py_widget_facts(widget: PDAnnotationWidget) -> dict[str, str]:
    cos = widget.get_cos_object()
    t = cos.get_string("T")
    mk = widget.get_appearance_characteristics()
    return {
        "T": "-" if t is None else t,
        "I": "none" if mk is None else _form_facts(mk.get_normal_icon_form()),
        "RI": "none" if mk is None else _form_facts(mk.get_rollover_icon_form()),
        "IX": "none" if mk is None else _form_facts(mk.get_alternate_icon_form()),
    }


def _py_records(path: Path) -> list[dict[str, str]]:
    doc = PDDocument.load(str(path))
    try:
        out: list[dict[str, str]] = []
        for page in doc.get_pages():
            for annot in page.get_annotations():
                if isinstance(annot, PDAnnotationWidget):
                    out.append(_py_widget_facts(annot))
        return out
    finally:
        doc.close()


def _qpdf_ok(path: Path) -> bool:
    """``qpdf --check`` passes (warnings tolerated, hard errors not)."""
    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_widget_icon_facts_match_pdfbox(tmp_path: Path) -> None:
    """Every canonical fact pypdfbox reports for the ``/I`` ``/RI`` ``/IX``
    push-button icons equals what Apache PDFBox reports on the same
    PDFBox-built fixture — present-icon ``/BBox`` + ``/Matrix`` + ``/FormType``,
    absent-icon ``None``, and non-stream-icon ``None``."""
    fixture = tmp_path / "widget_icon.pdf"
    _build_fixture(fixture)
    assert _qpdf_ok(fixture)

    java = _java_records(fixture)
    py = _py_records(fixture)

    assert len(java) == 4, f"unexpected probe annotation count: {len(java)}"
    assert len(py) == len(java)
    assert py == java


@requires_oracle
def test_all_three_icons_present_match_pdfbox(tmp_path: Path) -> None:
    """A widget carrying all three icon keys reports each form's ``/BBox``,
    ``/Matrix`` and ``/FormType`` identically to PDFBox (the fully-populated
    case)."""
    fixture = tmp_path / "widget_icon.pdf"
    _build_fixture(fixture)
    java = {r["T"]: r for r in _java_records(fixture)}
    py = {r["T"]: r for r in _py_records(fixture)}

    jr, pr = java["btnAll"], py["btnAll"]
    assert pr["I"] == jr["I"] == "0,0,20,20 ; 1 0 0 1 0 0 ; 1"
    assert pr["RI"] == jr["RI"] == "0,0,30,15 ; 2 0 0 2 5 5 ; 1"
    assert pr["IX"] == jr["IX"] == "1,2,41,22 ; 1 0 0 1 10 0 ; 1"


@requires_oracle
def test_absent_icons_report_none_match_pdfbox(tmp_path: Path) -> None:
    """A missing ``/RI`` / ``/IX`` key yields ``None`` (``"none"``) under both
    implementations; only the present ``/I`` resolves to a form."""
    fixture = tmp_path / "widget_icon.pdf"
    _build_fixture(fixture)
    java = {r["T"]: r for r in _java_records(fixture)}
    py = {r["T"]: r for r in _py_records(fixture)}

    jr, pr = java["btnNormalOnly"], py["btnNormalOnly"]
    assert pr["I"] == jr["I"] == "0,0,12,8 ; 0.5 0 0 0.5 0 0 ; 1"
    assert pr["RI"] == jr["RI"] == "none"
    assert pr["IX"] == jr["IX"] == "none"

    # /MK present but no icon keys at all -> all three None.
    jr2, pr2 = java["btnNoIcons"], py["btnNoIcons"]
    assert pr2["I"] == jr2["I"] == "none"
    assert pr2["RI"] == jr2["RI"] == "none"
    assert pr2["IX"] == jr2["IX"] == "none"


@requires_oracle
def test_non_stream_icon_reports_none_match_pdfbox(tmp_path: Path) -> None:
    """An ``/I`` whose value is a name (not a stream) yields ``None`` under
    both implementations — neither throws (graceful-degradation triage
    signal)."""
    fixture = tmp_path / "widget_icon.pdf"
    _build_fixture(fixture)
    java = {r["T"]: r for r in _java_records(fixture)}
    py = {r["T"]: r for r in _py_records(fixture)}

    jr, pr = java["btnBadIcon"], py["btnBadIcon"]
    assert pr["I"] == jr["I"] == "none"
    assert pr["RI"] == jr["RI"] == "none"
    assert pr["IX"] == jr["IX"] == "none"
