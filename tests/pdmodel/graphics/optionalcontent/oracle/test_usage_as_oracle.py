"""Live Apache PDFBox differential parity for /OCProperties /D /AS Usage
Application arrays (PDF 32000-1 §8.11.4.4 Table 102).

The /AS array sits inside an optional-content configuration dictionary
(``/D`` or an alternate ``/Configs`` entry). Each entry is a Usage
Application dictionary specifying an /Event ("View"/"Print"/"Export"), one
or more /Category names (View/Print/Export/Language/Zoom/...) and a list of
/OCGs that the application should auto-apply state to from those category
slots in the OCG's own /Usage dict.

Apache PDFBox 3.0 ships **no** public accessor for /AS — callers walk the
COS dict directly. Likewise, ``PDOptionalContentProperties.isGroupEnabled``
in PDFBox 3.0 does not factor /AS into the answer (it only consults the
``/D /ON`` + ``/D /OFF`` lists against /BaseState). The probe
``oracle/probes/UsageAsProbe.java`` mirrors that surface so the differential
asserts pypdfbox agrees on:

* the /AS array length,
* each entry's /Event + /Category + /OCGs count,
* per-OCG ``/Usage /View /ViewState`` content,
* PDFBox's ``isGroupEnabled`` (pre-/AS) resolution.

The PDF-spec category-driven override of /BaseState is then asserted by an
extra Python-side check via :meth:`PDOptionalContentProperties.compute_visible_ocgs`
(the View pass) — this is pypdfbox's value-add over PDFBox 3.0 (Apache
PDFBox 3.0 simply does not surface /AS to its public API; see
``OcConfigProbe`` for the basic /D resolution).

The canonical dump (per :func:`_dump_py` / ``UsageAsProbe``) is, in order:

* ``AS_LEN=<n>``
* one ``AS entry=<i> event=<E> categories=<C1|C2|...> ocgs=<n>`` line per
  /AS entry (in array order; categories sorted lexicographically),
* one ``OCG name=<n> enabled=<true|false> view=<ON|OFF|none>`` line per OCG,
  sorted by name.

When the catalog has no /OCProperties: the single sentinel line
``NO_OCPROPERTIES``.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_NAME: COSName = COSName.get_pdf_name("Name")
_EVENT: COSName = COSName.get_pdf_name("Event")
_CATEGORY: COSName = COSName.get_pdf_name("Category")
_OCGS: COSName = COSName.get_pdf_name("OCGs")


# ----------------------------------------------------------------- py dump


def _dump_py(path: Path) -> str:
    """pypdfbox's canonical /AS dump — identical line format to
    ``UsageAsProbe``. Closes the document in a ``finally``."""
    doc = PDDocument.load(path)
    try:
        props = doc.get_document_catalog().get_oc_properties()
        if props is None:
            return "NO_OCPROPERTIES\n"
        cfg = props.get_default_configuration()
        as_arr = cfg.get_as_array()
        lines: list[str] = []
        as_len = as_arr.size() if as_arr is not None else 0
        lines.append(f"AS_LEN={as_len}")

        if as_arr is not None:
            for i in range(as_arr.size()):
                entry = props.to_dictionary(as_arr.get_object(i))
                if entry is None:
                    lines.append(f"AS entry={i} event= categories= ocgs=0")
                    continue
                event_obj = entry.get_dictionary_object(_EVENT)
                event = event_obj.name if isinstance(event_obj, COSName) else ""
                cats_obj = entry.get_dictionary_object(_CATEGORY)
                cats: list[str] = []
                if isinstance(cats_obj, COSName):
                    cats = [cats_obj.name]
                elif isinstance(cats_obj, COSArray):
                    cats = [c.name for c in cats_obj if isinstance(c, COSName)]
                cats.sort()
                ocgs_obj = entry.get_dictionary_object(_OCGS)
                ocgs_count = 0
                if isinstance(ocgs_obj, COSArray):
                    for raw in ocgs_obj:
                        if props.to_dictionary(raw) is not None:
                            ocgs_count += 1
                lines.append(
                    f"AS entry={i} event={event} "
                    f"categories={'|'.join(cats)} ocgs={ocgs_count}"
                )

        ocg_lines: list[str] = []
        for group in props.get_optional_content_groups():
            name = group.get_name() or ""
            enabled = "true" if props.is_group_enabled(group) else "false"
            view = group.get_render_state("View") or "none"
            ocg_lines.append(
                f"OCG name={name} enabled={enabled} view={view}"
            )
        ocg_lines.sort()
        lines.extend(ocg_lines)
        return "\n".join(lines) + "\n"
    finally:
        doc.close()


# --------------------------------------------------------------- fixture builders


def _build_basic_as_pdf(out: Path) -> None:
    """Build a PDF whose /D /AS contains one View-event entry flipping a
    single OCG /Usage /View /ViewState — the canonical example from PDF
    32000-1 §8.11.4.4."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        g_view_off = PDOptionalContentGroup("Off For View")
        g_plain = PDOptionalContentGroup("Plain")
        props.add_group(g_view_off)
        props.add_group(g_plain)
        # The OCG with usage /View /ViewState OFF — /AS should auto-apply this.
        g_view_off.set_usage_view_state("OFF")
        # Default config + one /AS entry targeting the View category.
        cfg = props.get_default_configuration()
        cfg.set_name("DefaultCfg")
        cfg.add_as_entry("View", ["View"], [g_view_off])
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(out))
    finally:
        doc.close()


def _build_multi_category_as_pdf(out: Path) -> None:
    """Two /AS entries: one for the View event covering two OCGs, and one
    for the Print event covering one OCG. The View entry lists *two*
    categories (View + Language) so the probe's category flattening is
    exercised on the array-of-names shape."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        g_a = PDOptionalContentGroup("Alpha")
        g_b = PDOptionalContentGroup("Bravo")
        g_c = PDOptionalContentGroup("Charlie")
        for g in (g_a, g_b, g_c):
            props.add_group(g)
        g_a.set_usage_view_state("OFF")
        g_b.set_usage_view_state("ON")
        g_c.set_usage_print_state("OFF")
        cfg = props.get_default_configuration()
        cfg.set_name("DefaultCfg")
        # View entry: two categories, two OCGs.
        cfg.add_as_entry("View", ["View", "Language"], [g_a, g_b])
        # Print entry: one category, one OCG.
        cfg.add_as_entry("Print", ["Print"], [g_c])
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(out))
    finally:
        doc.close()


def _build_basestate_override_pdf(out: Path) -> None:
    """BaseState ON globally, but the /AS View entry should override one
    OCG OFF based on its /Usage /View /ViewState=OFF. This is the
    high-value case from the task brief: category-driven override of
    /BaseState."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        flipped = PDOptionalContentGroup("Flipped")
        stable = PDOptionalContentGroup("Stable")
        for g in (flipped, stable):
            props.add_group(g)
        # BaseState ON: both groups visible by default.
        props.set_base_state("ON")
        # /Usage /View /ViewState OFF on "Flipped".
        flipped.set_usage_view_state("OFF")
        # /AS View entry: when application category=View, auto-apply OFF
        # to "Flipped" from its /Usage /View /ViewState.
        cfg = props.get_default_configuration()
        cfg.set_name("DefaultCfg")
        cfg.add_as_entry("View", ["View"], [flipped])
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(out))
    finally:
        doc.close()


def _build_empty_as_pdf(out: Path) -> None:
    """An /OCProperties dict with no /AS array — exercises the AS_LEN=0
    sentinel path on both probes."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        g = PDOptionalContentGroup("Solo")
        props.add_group(g)
        props.get_default_configuration().set_name("DefaultCfg")
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(out))
    finally:
        doc.close()


# ------------------------------------------------------------ differential tests


@requires_oracle
def test_basic_as_entry_matches_pdfbox(tmp_path: Path) -> None:
    """A single /AS View entry: array length, /Event, /Category, /OCGs
    count, plus per-OCG /Usage /View /ViewState and isGroupEnabled — must
    all agree with Apache PDFBox 3.0.7 on the identical saved file."""
    pdf = tmp_path / "as_basic.pdf"
    _build_basic_as_pdf(pdf)
    java = run_probe_text("UsageAsProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_multi_category_as_matches_pdfbox(tmp_path: Path) -> None:
    """Two /AS entries — one with two categories and two OCGs, another
    with one category and one OCG — confirms the multi-entry / multi-cat
    flattening agrees on both probes."""
    pdf = tmp_path / "as_multi.pdf"
    _build_multi_category_as_pdf(pdf)
    java = run_probe_text("UsageAsProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_basestate_override_matches_pdfbox(tmp_path: Path) -> None:
    """BaseState ON with a /AS View entry whose target OCG has /Usage
    /View /ViewState OFF — PDFBox's public ``isGroupEnabled`` still
    reports ``true`` for that OCG (it ignores /AS), and pypdfbox's
    :meth:`is_group_enabled` must match that. The /AS-aware resolution
    (via :meth:`compute_visible_ocgs`) is asserted separately below."""
    pdf = tmp_path / "as_override.pdf"
    _build_basestate_override_pdf(pdf)
    java = run_probe_text("UsageAsProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_empty_as_matches_pdfbox(tmp_path: Path) -> None:
    """An /OCProperties dict with no /AS array: ``AS_LEN=0`` and no entry
    lines on both probes."""
    pdf = tmp_path / "as_empty.pdf"
    _build_empty_as_pdf(pdf)
    java = run_probe_text("UsageAsProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_no_ocproperties_matches_pdfbox(tmp_path: Path) -> None:
    """A plain document with no /OCProperties: both probes emit the
    ``NO_OCPROPERTIES`` sentinel."""
    pdf = tmp_path / "no_oc.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("UsageAsProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java
    assert py == "NO_OCPROPERTIES\n"


# ------------------------------------------------------ pypdfbox /AS resolution


def test_compute_visible_ocgs_applies_as_override(tmp_path: Path) -> None:
    """pypdfbox value-add over PDFBox 3.0: when a /AS View entry lists an
    OCG whose /Usage /View /ViewState is OFF, :meth:`compute_visible_ocgs`
    called with ``destination="View"`` excludes that OCG from the visible
    set even though /BaseState is ON. The other OCG remains visible.

    This is the category-driven override of /BaseState (PDF 32000-1
    §8.11.4.4 Table 102) — the high-value case from the task brief."""
    pdf = tmp_path / "as_override.pdf"
    _build_basestate_override_pdf(pdf)
    doc = PDDocument.load(pdf)
    try:
        props = doc.get_document_catalog().get_oc_properties()
        groups = {g.get_name(): g for g in props.get_optional_content_groups()}
        flipped = groups["Flipped"]
        stable = groups["Stable"]

        # Without the /AS pass, both OCGs are visible (BaseState=ON).
        no_as = props.compute_visible_ocgs(destination=None)
        assert id(flipped.get_cos_object()) in no_as
        assert id(stable.get_cos_object()) in no_as

        # With destination="View", /AS auto-applies the Usage /ViewState=OFF
        # for "Flipped"; "Stable" stays visible.
        view = props.compute_visible_ocgs(destination="View")
        assert id(flipped.get_cos_object()) not in view
        assert id(stable.get_cos_object()) in view

        # destination="Print" does NOT match the /AS entry (its /Event is
        # "View"), so "Flipped" remains visible from the BaseState seed.
        print_set = props.compute_visible_ocgs(destination="Print")
        assert id(flipped.get_cos_object()) in print_set
        assert id(stable.get_cos_object()) in print_set
    finally:
        doc.close()


def test_compute_visible_ocgs_singular_category_name(tmp_path: Path) -> None:
    """The spec allows /Category to be either a single name OR an array of
    names (Table 102). Build an /AS entry with a *singular* COSName
    /Category (not an array) and confirm
    :meth:`compute_visible_ocgs` still applies the override — the
    ``_apply_auto_state`` helper accepts both shapes."""
    pdf = tmp_path / "as_singular.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        target = PDOptionalContentGroup("Target")
        props.add_group(target)
        target.set_usage_view_state("OFF")
        props.set_base_state("ON")

        # Build a hand-rolled /AS entry with /Category as a singular COSName.
        cfg = props.get_default_configuration()
        cfg.set_name("DefaultCfg")
        as_arr = COSArray()
        entry = COSDictionary()
        entry.set_item(_EVENT, COSName.get_pdf_name("View"))
        entry.set_item(_CATEGORY, COSName.get_pdf_name("View"))
        ocgs = COSArray()
        ocgs.add(target.get_cos_object())
        entry.set_item(_OCGS, ocgs)
        as_arr.add(entry)
        cfg.get_cos_object().set_item(COSName.get_pdf_name("AS"), as_arr)

        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()

    doc = PDDocument.load(pdf)
    try:
        props = doc.get_document_catalog().get_oc_properties()
        target = props.get_optional_content_groups()[0]
        # Override applies — "Target" removed from visible set.
        view = props.compute_visible_ocgs(destination="View")
        assert id(target.get_cos_object()) not in view
    finally:
        doc.close()
