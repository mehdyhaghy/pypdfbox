"""Live Apache PDFBox differential parity for optional content (layers / OCG)
— ``pypdfbox.pdmodel.graphics.optionalcontent``.

No bundled fixture in ``tests/fixtures`` carries an ``/OCProperties`` dictionary
(``grep -rl OCProperties tests/fixtures`` → none), so each test BUILDS a small
optional-content document programmatically via pypdfbox, saves it ONCE to a temp
file, and then runs BOTH libraries (pypdfbox and the Java oracle via
``OcgProbe``) on that same saved bytes. The differential is genuine: the file is
produced once and independently parsed by each library; the assertion is that
pypdfbox's OCG dump equals Apache PDFBox 3.0.7's dump of the identical file.

The canonical dump (per :func:`_dump_py` / ``OcgProbe``) is, in order:

* ``CONFIG name=<default config /D /Name> baseState=<ON|OFF|UNCHANGED>``
* one ``OCG name=<name> enabled=<true|false>`` line per OCG, sorted by name,
  where ``enabled`` is the OCG's visibility under the default configuration
  (``isGroupEnabled`` / :meth:`is_group_enabled`).

PDFBox's ``BaseState.name()`` is upper-cased (``UNCHANGED``); pypdfbox's
:meth:`get_base_state` returns the spec spelling (``Unchanged``). The dump
upper-cases the Python side so the canonical line matches across libraries — a
representation detail, not a behavioural divergence (both resolve identical
per-OCG visibility, which is what the ``OCG`` lines assert).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- fixture build


def _build_ocg_pdf(
    out: Path,
    *,
    config_name: str,
    base_state: str,
    groups: list[str],
    off_groups: tuple[str, ...] = (),
    on_groups: tuple[str, ...] = (),
) -> None:
    """Build a one-page PDF with the given OCGs and default-config state and
    save it to ``out``. ``off_groups`` / ``on_groups`` are explicitly listed in
    ``/D /OFF`` / ``/D /ON``. Closes the document in a ``finally``."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        wrappers = {}
        for name in groups:
            g = PDOptionalContentGroup(name)
            props.add_group(g)
            wrappers[name] = g
        props.set_base_state(base_state)
        for name in off_groups:
            props.set_group_enabled(wrappers[name], False)
        for name in on_groups:
            props.set_group_enabled(wrappers[name], True)
        props.get_default_configuration().set_name(config_name)
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(out))
    finally:
        doc.close()


# ----------------------------------------------------------------- py dump


def _dump_py(path: Path) -> str:
    """pypdfbox's canonical OCG dump for ``path`` — identical line format to
    ``OcgProbe``. Closes the document in a ``finally``."""
    doc = PDDocument.load(path)
    try:
        props = doc.get_document_catalog().get_oc_properties()
        if props is None:
            return "NO_OCPROPERTIES\n"
        cfg = props.get_default_configuration()
        config_name = cfg.get_name() or ""
        base_state = props.get_base_state().upper()
        lines = [f"CONFIG name={config_name} baseState={base_state}"]
        ocg_lines = []
        for group in props.get_optional_content_groups():
            name = group.get_name() or ""
            enabled = "true" if props.is_group_enabled(group) else "false"
            ocg_lines.append(f"OCG name={name} enabled={enabled}")
        ocg_lines.sort()
        lines.extend(ocg_lines)
        return "\n".join(lines) + "\n"
    finally:
        doc.close()


# ------------------------------------------------------------ differential tests


@requires_oracle
def test_two_ocgs_one_off_matches_pdfbox(tmp_path: Path) -> None:
    """Two OCGs, base state ON, the second turned OFF by default."""
    pdf = tmp_path / "ocg_two_one_off.pdf"
    _build_ocg_pdf(
        pdf,
        config_name="Default",
        base_state="ON",
        groups=["Layer One", "Layer Two"],
        off_groups=("Layer Two",),
    )
    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_base_state_off_with_one_explicit_on_matches_pdfbox(tmp_path: Path) -> None:
    """Base state OFF (all hidden) with one OCG explicitly listed in /D /ON."""
    pdf = tmp_path / "ocg_base_off.pdf"
    _build_ocg_pdf(
        pdf,
        config_name="Cfg",
        base_state="OFF",
        groups=["Alpha", "Beta"],
        on_groups=("Alpha",),
    )
    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_base_state_unchanged_matches_pdfbox(tmp_path: Path) -> None:
    """Base state Unchanged — exercises the BaseState name casing
    (``Unchanged`` vs PDFBox ``UNCHANGED``) and the ``!= OFF`` enabled rule."""
    pdf = tmp_path / "ocg_unchanged.pdf"
    _build_ocg_pdf(
        pdf,
        config_name="Cfg",
        base_state="Unchanged",
        groups=["Alpha", "Beta"],
        on_groups=("Alpha",),
    )
    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_many_ocgs_sorted_dump_matches_pdfbox(tmp_path: Path) -> None:
    """Several OCGs with a mix of ON/OFF — confirms the sorted, canonical dump
    agrees across the whole set, not just a 2-group toy case."""
    pdf = tmp_path / "ocg_many.pdf"
    _build_ocg_pdf(
        pdf,
        config_name="Mixed Config",
        base_state="ON",
        groups=["Zulu", "Mike", "Alpha", "Tango"],
        off_groups=("Mike", "Tango"),
    )
    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_two_same_named_groups_both_off_matches_pdfbox(tmp_path: Path) -> None:
    """Two *distinct* OCGs sharing the /Name "Dup", both turned OFF by a
    single ``set_group_enabled("Dup", False)`` call. Upstream
    ``setGroupEnabled(String, boolean)`` loops over EVERY matching OCG, so
    both dictionaries land in /D /OFF — and ``isGroupEnabled("Dup")`` is then
    false for the whole name. The dump (sorted, one line per OCG) must agree
    across libraries: two ``OCG name=Dup enabled=false`` lines plus the solo
    group."""
    pdf = tmp_path / "ocg_same_named.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        # Two distinct OCG objects, identical /Name.
        for _ in range(2):
            props.add_group(PDOptionalContentGroup("Dup"))
        props.add_group(PDOptionalContentGroup("Solo"))
        props.set_base_state("ON")
        # Name-based toggle must hit BOTH "Dup" groups.
        result = props.set_group_enabled("Dup", False)
        # Neither had a prior on/off setting → upstream returns False.
        assert result is False
        props.get_default_configuration().set_name("Cfg")
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java
    assert py == (
        "CONFIG name=Cfg baseState=ON\n"
        "OCG name=Dup enabled=false\n"
        "OCG name=Dup enabled=false\n"
        "OCG name=Solo enabled=true\n"
    )


@requires_oracle
def test_no_ocproperties_matches_pdfbox(tmp_path: Path) -> None:
    """A plain document with no /OCProperties: both libraries report the
    sentinel line, confirming the catalog->OCProperties lookup agrees on the
    absent case too."""
    pdf = tmp_path / "no_ocg.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java
    assert py == "NO_OCPROPERTIES\n"
