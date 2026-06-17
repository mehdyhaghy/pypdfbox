"""Live Apache PDFBox differential parity for optional-content *configuration
metadata* — the ``/OCProperties /D`` default-configuration dictionary
(``pypdfbox.pdmodel.graphics.optionalcontent``).

Where ``test_ocg_oracle.py`` covers the basic OCG name + BaseState-derived
ON/OFF dump, this module exercises the richer **config dictionary** surface
that PDFBox 3.0 exposes only off the raw COS dictionary:

* ``/BaseState`` interacting with explicit ``/D /ON`` + ``/D /OFF`` lists
  (PDFBox ``isGroupEnabled`` resolution: ON wins, then OFF, else the
  ``BaseState != OFF`` seed),
* the per-OCG ``/Usage`` ``View``/``Print`` render state
  (``PDOptionalContentGroup.getRenderState`` / :meth:`get_render_state`),
* the ``/Order`` UI tree flattened with nesting markers (``[`` ``]``) and
  label strings (``LABEL:<text>``),
* ``/RBGroups`` radio-button group membership,
* ``/Locked`` groups.

No bundled fixture carries an ``/OCProperties`` dictionary, so each test
BUILDS a document programmatically via pypdfbox, saves it ONCE to a temp
file, then runs BOTH libraries on the identical bytes: pypdfbox's typed
accessors (:class:`PDOptionalContentConfiguration`,
:class:`PDOptionalContentProperties`,
:class:`PDOptionalContentGroup`) vs. the Java oracle (``OcConfigProbe``,
reading ``/Order`` / ``/RBGroups`` / ``/Locked`` off the COS dict exactly as
PDFBox callers must, since 3.0 ships no public getter for them). The
differential is genuine: the assertion is that pypdfbox's config-metadata
dump equals Apache PDFBox 3.0.7's dump of the same saved file.

The canonical dump (per :func:`_dump_py` / ``OcConfigProbe``) is, in order:

* ``BASESTATE=<ON|OFF|UNCHANGED>``
* one ``OCG name=<n> enabled=<true|false> view=<ON|OFF|none> print=<...>``
  line per OCG, sorted by name,
* one ``ORDER <tokens>`` line (space-joined flattened tokens),
* one ``RBGROUP <name>|<name>|...`` line per radio-button group, sorted,
* one ``LOCKED <name>`` line per locked OCG, sorted.

PDFBox's ``BaseState.name()`` is upper-cased (``UNCHANGED``); pypdfbox's
:meth:`get_base_state` returns the spec spelling (``Unchanged``). The dump
upper-cases the Python side so the canonical line matches — a representation
detail, not a behavioural divergence.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_NAME: COSName = COSName.get_pdf_name("Name")


# ----------------------------------------------------------------- py dump


def _flatten_order(props: PDOptionalContentProperties, arr: COSArray) -> list[str]:
    """Flatten a /Order array into canonical tokens — identical shape to
    ``OcConfigProbe.flattenOrder``: ``LABEL:<text>`` for a label string, a
    nested sub-array wrapped in ``[`` ``]``, an OCG reference as its /Name."""
    tokens: list[str] = []
    for index in range(arr.size()):
        raw = arr.get_object(index)
        if isinstance(raw, COSString):
            tokens.append("LABEL:" + raw.get_string())
            continue
        if isinstance(raw, COSArray):
            tokens.append("[")
            tokens.extend(_flatten_order(props, raw))
            tokens.append("]")
            continue
        ocg = props.to_dictionary(raw)
        tokens.append((ocg.get_string(_NAME) if ocg is not None else "?") or "")
    return tokens


def _dump_py(path: Path) -> str:
    """pypdfbox's canonical config-metadata dump — identical line format to
    ``OcConfigProbe``. Closes the document in a ``finally``."""
    doc = PDDocument.load(path)
    try:
        props = doc.get_document_catalog().get_oc_properties()
        if props is None:
            return "NO_OCPROPERTIES\n"
        cfg = props.get_default_configuration()
        lines = [f"BASESTATE={props.get_base_state().upper()}"]

        ocg_lines: list[str] = []
        for group in props.get_optional_content_groups():
            name = group.get_name() or ""
            enabled = "true" if props.is_group_enabled(group) else "false"
            view = group.get_render_state("View") or "none"
            prints = group.get_render_state("Print") or "none"
            ocg_lines.append(
                f"OCG name={name} enabled={enabled} view={view} print={prints}"
            )
        ocg_lines.sort()
        lines.extend(ocg_lines)

        order = cfg.get_order()
        tokens = _flatten_order(props, order) if order is not None else []
        lines.append("ORDER " + " ".join(tokens))

        rb_lines: list[str] = []
        for radio_group in cfg.get_rbgroups():
            members = sorted((g.get_name() or "") for g in radio_group)
            rb_lines.append("RBGROUP " + "|".join(members))
        rb_lines.sort()
        lines.extend(rb_lines)

        lock_lines = sorted(
            "LOCKED " + (g.get_name() or "") for g in cfg.get_locked()
        )
        lines.extend(lock_lines)

        return "\n".join(lines) + "\n"
    finally:
        doc.close()


# --------------------------------------------------------------- fixture build


def _build_full_config_pdf(out: Path) -> None:
    """Build a one-page PDF whose /OCProperties /D config carries the full
    metadata surface: 3 OCGs (one with /Usage /View /ViewState OFF +
    /Print ON), BaseState OFF with explicit /ON + /OFF, a nested /Order
    (label + sub-array grouping two OCGs), an /RBGroups making two OCGs
    mutually exclusive, and a /Locked list. Closes the document in a
    ``finally``."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        g1 = PDOptionalContentGroup("Layer Alpha")
        g2 = PDOptionalContentGroup("Layer Beta")
        g3 = PDOptionalContentGroup("Layer Gamma")
        for g in (g1, g2, g3):
            props.add_group(g)

        # g1: /Usage /View /ViewState OFF and /Print /PrintState ON.
        g1.set_usage_view_state("OFF")
        g1.set_usage_print_state("ON")

        # BaseState OFF (all hidden by default), g2 explicitly ON, g3 OFF.
        props.set_base_state("OFF")
        props.set_group_enabled(g2, True)
        props.set_group_enabled(g3, False)

        cfg = props.get_default_configuration()
        cfg.set_name("DefaultCfg")

        # Nested /Order: a label string, a sub-array grouping g1 + g2, g3.
        order = COSArray()
        order.add(COSString("Tree Root"))
        sub = COSArray()
        sub.add(g1.get_cos_object())
        sub.add(g2.get_cos_object())
        order.add(sub)
        order.add(g3.get_cos_object())
        cfg.set_order(order)

        # /RBGroups: g1 and g3 mutually exclusive.
        cfg.add_rbgroup([g1, g3])
        # /Locked: g2.
        cfg.set_locked([g2])

        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(out))
    finally:
        doc.close()


# ------------------------------------------------------------ differential tests


@requires_oracle
def test_full_config_metadata_matches_pdfbox(tmp_path: Path) -> None:
    """The complete config surface: BaseState OFF + /ON + /OFF resolution,
    per-OCG /Usage View/Print, nested /Order, /RBGroups, /Locked — all of it
    must agree with Apache PDFBox 3.0.7 on the identical saved file."""
    pdf = tmp_path / "oc_full_config.pdf"
    _build_full_config_pdf(pdf)
    java = run_probe_text("OcConfigProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_basestate_off_on_off_interplay_matches_pdfbox(tmp_path: Path) -> None:
    """Isolated BaseState=OFF resolution: a group in /ON resolves enabled, a
    group in /OFF resolves disabled, and an un-listed group falls back to the
    BaseState seed (disabled when OFF). ON is checked before OFF in PDFBox's
    ``isGroupEnabled`` — assert pypdfbox agrees on each."""
    pdf = tmp_path / "oc_basestate.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        on_g = PDOptionalContentGroup("Explicit On")
        off_g = PDOptionalContentGroup("Explicit Off")
        bare_g = PDOptionalContentGroup("Bare")
        for g in (on_g, off_g, bare_g):
            props.add_group(g)
        props.set_base_state("OFF")
        props.set_group_enabled(on_g, True)
        props.set_group_enabled(off_g, False)
        props.get_default_configuration().set_name("Cfg")
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcConfigProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_basestate_unchanged_matches_pdfbox(tmp_path: Path) -> None:
    """BaseState=Unchanged — exercises the PDFBox ``UNCHANGED`` casing vs.
    pypdfbox spec spelling and the ``!= OFF`` enabled seed, with one group
    pinned ON and one pinned OFF on top."""
    pdf = tmp_path / "oc_unchanged.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        a = PDOptionalContentGroup("Aye")
        b = PDOptionalContentGroup("Bee")
        c = PDOptionalContentGroup("Cee")
        for g in (a, b, c):
            props.add_group(g)
        props.set_base_state("Unchanged")
        props.set_group_enabled(b, False)
        props.get_default_configuration().set_name("Cfg")
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcConfigProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_nested_order_deeper_matches_pdfbox(tmp_path: Path) -> None:
    """A two-level nested /Order: a label, a sub-array that itself nests a
    label + sub-array, then a top-level OCG. Confirms the flattening agrees
    on arbitrary nesting depth, not just one level."""
    pdf = tmp_path / "oc_nested_order.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        g1 = PDOptionalContentGroup("One")
        g2 = PDOptionalContentGroup("Two")
        g3 = PDOptionalContentGroup("Three")
        g4 = PDOptionalContentGroup("Four")
        for g in (g1, g2, g3, g4):
            props.add_group(g)
        cfg = props.get_default_configuration()
        cfg.set_name("Cfg")
        order = COSArray()
        order.add(COSString("Outer"))
        inner = COSArray()
        inner.add(COSString("Inner"))
        deepest = COSArray()
        deepest.add(g1.get_cos_object())
        deepest.add(g2.get_cos_object())
        inner.add(deepest)
        inner.add(g3.get_cos_object())
        order.add(inner)
        order.add(g4.get_cos_object())
        cfg.set_order(order)
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcConfigProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_multiple_rbgroups_and_locked_matches_pdfbox(tmp_path: Path) -> None:
    """Two distinct /RBGroups radio-button groups plus multiple /Locked
    entries — confirms membership and locked lists agree across the whole
    set, not just a single group."""
    pdf = tmp_path / "oc_rb_locked.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        groups = [
            PDOptionalContentGroup(n)
            for n in ("Red", "Green", "Blue", "Solid", "Dashed")
        ]
        for g in groups:
            props.add_group(g)
        cfg = props.get_default_configuration()
        cfg.set_name("Cfg")
        # Two radio-button groups: colour set and line-style set.
        cfg.add_rbgroup([groups[0], groups[1], groups[2]])
        cfg.add_rbgroup([groups[3], groups[4]])
        cfg.set_locked([groups[0], groups[3]])
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcConfigProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_no_ocproperties_matches_pdfbox(tmp_path: Path) -> None:
    """A plain document with no /OCProperties: both libraries emit the
    sentinel line, confirming the absent case agrees too."""
    pdf = tmp_path / "no_oc.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcConfigProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java
    assert py == "NO_OCPROPERTIES\n"
