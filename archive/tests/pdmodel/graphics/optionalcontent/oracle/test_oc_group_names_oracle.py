"""Live Apache PDFBox differential parity for the *name-keyed* optional-content
accessor surface of ``PDOptionalContentProperties``
(``pypdfbox.pdmodel.graphics.optionalcontent``).

Where ``test_ocg_oracle.py`` / ``test_oc_config_oracle.py`` iterate
``getOptionalContentGroups()`` (and sort the dump), this module pins the
accessors that address groups by their ``/Name`` *string* and that PRESERVE
the ``/OCGs`` array order:

* ``getGroupNames()`` — the ordered ``/OCGs`` name array (insertion order, not
  sorted; ``""`` for entries that don't resolve to a dictionary),
* ``hasGroup(name)`` — name membership (present + absent names),
* ``isGroupEnabled(name)`` — the *String* overload (resolves by ``/Name``
  through ``/OCGs``, "at least one group with this name enabled"),
* ``getGroup(name)`` round-trip — the name-keyed lookup.

No bundled fixture carries an ``/OCProperties`` dictionary, so each test BUILDS
a document programmatically via pypdfbox, saves it ONCE to a temp file, then
runs BOTH libraries on the identical bytes: pypdfbox's name-keyed accessors vs.
the Java oracle (``OcGroupNamesProbe``). The differential is genuine: the
assertion is that pypdfbox's name-accessor dump equals Apache PDFBox 3.0.7's
dump of the same saved file.

The fixtures deliberately use names whose *insertion* order differs from their
*sorted* order so the order-preservation of ``getGroupNames()`` is actually
exercised (a sorted dump would pass even if order were wrong).

The canonical dump (per :func:`_dump_py` / ``OcGroupNamesProbe``) is, in order:

* ``NAMES=<n0>|<n1>|...``                 (pipe-joined, /OCGs array order)
* one ``HAS name=<n> present=<true|false>`` per name, array order,
* one ``ENABLED name=<n> enabled=<true|false>`` per name, array order,
* one ``LOOKUP name=<n> found=<true|false> roundtrip=<name|null>`` per name,
* one trailing ``ABSENT name=__no_such_layer__ present=false enabled=false
  found=false`` probing the not-found path of every accessor.
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

_ABSENT = "__no_such_layer__"


# ----------------------------------------------------------------- py dump


def _dump_py(path: Path) -> str:
    """pypdfbox's canonical name-accessor dump — identical line format to
    ``OcGroupNamesProbe``. Closes the document in a ``finally``."""
    doc = PDDocument.load(path)
    try:
        props = doc.get_document_catalog().get_oc_properties()
        if props is None:
            return "NO_OCPROPERTIES\n"

        names = props.get_group_names()
        lines = ["NAMES=" + "|".join(names)]

        for name in names:
            present = "true" if props.has_group(name) else "false"
            lines.append(f"HAS name={name} present={present}")
        for name in names:
            enabled = "true" if props.is_group_enabled(name) else "false"
            lines.append(f"ENABLED name={name} enabled={enabled}")
        for name in names:
            group = props.get_group(name)
            found = "true" if group is not None else "false"
            roundtrip = "null" if group is None else group.get_name() or ""
            lines.append(f"LOOKUP name={name} found={found} roundtrip={roundtrip}")

        absent_present = "true" if props.has_group(_ABSENT) else "false"
        absent_enabled = "true" if props.is_group_enabled(_ABSENT) else "false"
        absent_found = "true" if props.get_group(_ABSENT) is not None else "false"
        lines.append(
            f"ABSENT name={_ABSENT} present={absent_present}"
            f" enabled={absent_enabled} found={absent_found}"
        )

        return "\n".join(lines) + "\n"
    finally:
        doc.close()


# ------------------------------------------------------------ differential tests


@requires_oracle
def test_group_names_order_and_lookup_matches_pdfbox(tmp_path: Path) -> None:
    """Insertion order != sorted order: groups added "Zulu", "Alpha", "Mike"
    must dump in that /OCGs array order, not sorted. Every name-keyed accessor
    (hasGroup / isGroupEnabled(name) / getGroup) plus the absent-name path must
    agree with Apache PDFBox 3.0.7 on the identical saved file."""
    pdf = tmp_path / "oc_group_names.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        # Insertion order chosen so it differs from sorted order.
        zulu = PDOptionalContentGroup("Zulu")
        alpha = PDOptionalContentGroup("Alpha")
        mike = PDOptionalContentGroup("Mike")
        for g in (zulu, alpha, mike):
            props.add_group(g)
        # Mixed enabled state via the default config: Alpha OFF, others on the
        # BaseState=ON seed.
        props.set_group_enabled(alpha, False)
        props.get_default_configuration().set_name("Cfg")
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcGroupNamesProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_group_names_basestate_off_matches_pdfbox(tmp_path: Path) -> None:
    """BaseState=OFF so the name-keyed isGroupEnabled(name) defaults to false
    for un-listed names; one group pinned ON and one pinned OFF on top. The
    String overload's "at least one enabled" resolution must agree."""
    pdf = tmp_path / "oc_group_names_off.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        on_g = PDOptionalContentGroup("Foreground")
        off_g = PDOptionalContentGroup("Background")
        bare_g = PDOptionalContentGroup("Watermark")
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
    java = run_probe_text("OcGroupNamesProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_duplicate_name_at_least_one_enabled_matches_pdfbox(tmp_path: Path) -> None:
    """Two OCGs share the /Name "Shared": one enabled, one disabled.
    isGroupEnabled(name) is documented as "at least one enabled", so it must
    return true; getGroupNames lists the name twice (array order). Confirms
    pypdfbox's name resolution matches PDFBox's duplicate-name handling."""
    pdf = tmp_path / "oc_dup_names.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        props = PDOptionalContentProperties()
        shared_on = PDOptionalContentGroup("Shared")
        shared_off = PDOptionalContentGroup("Shared")
        unique = PDOptionalContentGroup("Unique")
        for g in (shared_on, shared_off, unique):
            props.add_group(g)
        props.set_base_state("OFF")
        props.set_group_enabled(shared_on, True)
        props.set_group_enabled(shared_off, False)
        props.get_default_configuration().set_name("Cfg")
        doc.get_document_catalog().set_oc_properties(props)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcGroupNamesProbe", str(pdf))
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
    java = run_probe_text("OcGroupNamesProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java
    assert py == "NO_OCPROPERTIES\n"
