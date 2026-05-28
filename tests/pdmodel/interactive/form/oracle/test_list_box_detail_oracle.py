"""Live Apache PDFBox differential parity tests for LIST-BOX DETAIL semantics
(wave 1446).

Surface under test (``pypdfbox/pdmodel/interactive/form/``):

  * :class:`PDListBox` — ``get_top_index`` / ``set_top_index`` (``/TI``, the
    index of the first visible option in a scrollable list box).
  * :class:`PDChoice` (via the list box) — ``get_selected_options_index``
    (``/I``, sorted ascending), ``get_value`` (``/V``),
    ``get_options_export_values`` / ``get_options_display_values`` (the
    ``/Opt`` export/display halves), ``is_multi_select`` (the ``/Ff``
    MultiSelect bit).

PDFBox exposes no ``getSelectedExportValues`` / ``getSelectedDisplayValues`` on
``PDChoice``; the "selected export vs display" detail is *resolved* — by both
the Java ``ListBoxDetailProbe`` and the pypdfbox extractor here — from the
``/I`` indices against the export and display halves of ``/Opt``. That
resolution is the high-value differential: the selected set rendered as export
tokens and as display labels must agree, and it follows the **sorted** ``/I``
order (not the ``/V`` insertion order), so ``selExport`` can differ in order
from ``value``.

Each test emits canonical, deterministic *facts* about a list-box field two
ways — via the Java probe (compiled against the pinned pdfbox-app-3.0.7 jar)
and via pypdfbox's typed field API — and asserts the two are identical. A plain
READ (the get surface), a ``set_top_index`` round trip, and a multi-select
``/V`` + ``/I`` update round trip are all checked.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit). No upstream fixture carries a
multi-select export/display list box, so the fixtures are built at runtime via
pypdfbox, then loaded by *both* implementations — the build itself is therefore
part of the differential surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "ListBoxDetailProbe"


# --------------------------------------------------------------------------- #
# Java probe drivers
# --------------------------------------------------------------------------- #
def _java_read(path: Path, name: str) -> dict[str, str]:
    """Run the probe in READ mode; parse the named field's record into a flat
    ``{k: v}`` facts dict (each line is ``<name>\\t<k=v>\\t<k=v>...``)."""
    text = run_probe_text(_PROBE, "read", str(path), name)
    line = next(line for line in text.splitlines() if line.startswith(name + "\t"))
    parts = line.split("\t")
    facts: dict[str, str] = {}
    for col in parts[1:]:
        key, _, value = col.partition("=")
        facts[key] = value
    return facts


def _java_set(fixture: Path, out: Path, *ops: str) -> None:
    """Run the probe in SET mode (load, apply ops, save). Ops are
    ``name#ti=<int>`` (setTopIndex) or ``name=<v|v|...>`` (setValue)."""
    run_probe(_PROBE, "set", str(fixture), str(out), *ops)


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors ListBoxDetailProbe.listBoxFacts
# --------------------------------------------------------------------------- #
def _esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("|", "\\u007c")
        .replace(":", "\\u003a")
    )


def _py_facts(doc: PDDocument, name: str) -> dict[str, str]:
    field = doc.get_document_catalog().get_acro_form().get_field(name)
    assert isinstance(field, PDListBox), f"field {name!r} is not a list box"

    top_index = field.get_top_index()
    indices = field.get_selected_options_index()
    value = field.get_value()
    multi = field.is_multi_select()
    export = field.get_options_export_values()
    display = field.get_options_display_values()

    sel_export: list[str] = []
    sel_display: list[str] = []
    for j in indices:
        sel_export.append(export[j] if 0 <= j < len(export) else "<oob>")
        sel_display.append(display[j] if 0 <= j < len(display) else "<oob>")

    n = min(len(export), len(display))
    pairs = "|".join(f"{_esc(export[i])}:{_esc(display[i])}" for i in range(n))

    return {
        "topIndex": str(top_index),
        "indices": "|".join(str(i) for i in indices),
        "value": "|".join(_esc(v) for v in value),
        "multi": "1" if multi else "0",
        "export": "|".join(_esc(v) for v in export),
        "display": "|".join(_esc(v) for v in display),
        "selExport": "|".join(_esc(v) for v in sel_export),
        "selDisplay": "|".join(_esc(v) for v in sel_display),
        "pairs": pairs,
    }


def _py_read(path: Path, name: str) -> dict[str, str]:
    doc = PDDocument.load(str(path))
    try:
        return _py_facts(doc, name)
    finally:
        doc.close()


def _py_set(fixture: Path, out: Path, *ops: str) -> None:
    """Apply the same ops pypdfbox-side as the Java probe's SET dispatch."""
    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        for op in ops:
            hash_idx = op.find("#")
            if hash_idx >= 0 and op[hash_idx + 1 :].startswith("ti="):
                name = op[:hash_idx]
                ti = int(op[hash_idx + 4 :])
                field = form.get_field(name)
                assert isinstance(field, PDListBox)
                field.set_top_index(ti)
                continue
            eq = op.find("=")
            name = op[:eq]
            value = op[eq + 1 :]
            field = form.get_field(name)
            field.set_value(value.split("|") if "|" in value else value)
        doc.save(str(out))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# pypdfbox fixture builder (no upstream fixture carries this shape)
# --------------------------------------------------------------------------- #
def _build_detail_list(path: Path) -> None:
    """A multi-select :class:`PDListBox` with four export/display ``/Opt``
    pairs, ``/TI`` top index 1, and two values pre-selected out of /Opt order
    (``e3``, ``e1``) so ``/I`` must come back sorted ``0,2``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)
        lb = PDListBox(form)
        lb.set_partial_name("DetailList")
        lb.set_multi_select(True)
        lb.set_options(
            ["e1", "e2", "e3", "e4"],
            ["Display 1", "Display 2", "Display 3", "Display 4"],
        )
        widget = lb.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 500, 200, 100))
        widget.set_page(page)
        page.get_annotations().append(widget)
        form.set_fields([lb])
        lb.set_top_index(1)
        # Deliberately out of /Opt order: /V keeps insertion order, /I sorts.
        lb.set_value(["e3", "e1"])
        doc.save(str(path))
    finally:
        doc.close()


def _qpdf_ok(path: Path) -> bool:
    """``qpdf --check`` passes (warnings tolerated, hard errors not)."""
    import shutil
    import subprocess

    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# READ parity — the list-box detail GET surface
# --------------------------------------------------------------------------- #
@requires_oracle
def test_list_box_detail_read_parity(tmp_path: Path) -> None:
    """Every list-box detail fact pypdfbox reports equals what Apache PDFBox
    reports on the same fixture: ``/TI`` top index, ``/I`` (sorted ascending),
    ``/V`` selected values, ``isMultiSelect``, the full ``/Opt`` export/display
    pairs, and the selected set resolved as export tokens and display labels."""
    fixture = tmp_path / "detail.pdf"
    _build_detail_list(fixture)

    java = _java_read(fixture, "DetailList")
    py = _py_read(fixture, "DetailList")
    assert py == java

    # High-value invariants, asserted directly so a regression names itself.
    assert py["topIndex"] == "1"
    assert py["indices"] == "0|2"  # sorted ascending despite /V order e3,e1
    assert py["value"] == "e3|e1"  # /V keeps insertion order
    assert py["multi"] == "1"
    assert py["export"] == "e1|e2|e3|e4"
    assert py["display"] == "Display 1|Display 2|Display 3|Display 4"
    # Selected set follows the SORTED /I (0,2), not the /V order.
    assert py["selExport"] == "e1|e3"
    assert py["selDisplay"] == "Display 1|Display 3"
    assert _qpdf_ok(fixture)


# --------------------------------------------------------------------------- #
# set_top_index round trip — the /TI SET surface
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("ti", [0, 2, 3])
def test_set_top_index_then_read_parity(tmp_path: Path, ti: int) -> None:
    """Writing ``/TI`` via ``set_top_index`` round-trips to the identical
    top-index value under both implementations."""
    fixture = tmp_path / "detail.pdf"
    _build_detail_list(fixture)

    java_out = tmp_path / f"java_ti_{ti}.pdf"
    py_out = tmp_path / f"py_ti_{ti}.pdf"
    _java_set(fixture, java_out, f"DetailList#ti={ti}")
    _py_set(fixture, py_out, f"DetailList#ti={ti}")

    java = _java_read(java_out, "DetailList")
    py = _py_read(py_out, "DetailList")
    assert py == java
    assert py["topIndex"] == str(ti)
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# multi-select /V + /I update round trip
# --------------------------------------------------------------------------- #
@requires_oracle
def test_multi_select_value_then_read_parity(tmp_path: Path) -> None:
    """Re-selecting two options out of /Opt order round-trips to identical
    ``/V`` (insertion order) and ``/I`` (sorted ascending), and the selected
    export/display resolution matches the sorted indices under both
    implementations."""
    fixture = tmp_path / "detail.pdf"
    _build_detail_list(fixture)

    java_out = tmp_path / "java_v.pdf"
    py_out = tmp_path / "py_v.pdf"
    # e4 then e2 -> /V = e4|e2, /I sorts to 1,3 -> selExport e2|e4.
    _java_set(fixture, java_out, "DetailList=e4|e2")
    _py_set(fixture, py_out, "DetailList=e4|e2")

    java = _java_read(java_out, "DetailList")
    py = _py_read(py_out, "DetailList")
    assert py == java
    assert py["value"] == "e4|e2"
    assert py["indices"] == "1|3"  # sorted ascending regardless of /V order
    assert py["selExport"] == "e2|e4"
    assert py["selDisplay"] == "Display 2|Display 4"
    assert _qpdf_ok(py_out)
