"""Live Apache PDFBox differential parity for optional content membership
dictionaries (OCMD) — ``PDOptionalContentMembershipDictionary`` write paths.

The companion ``test_ocg_oracle.py`` pins the catalog ``/OCProperties`` round
trip; this module pins the *OCMD* round trip. pypdfbox BUILDS a one-page
document, attaches an OCMD to the first page's ``/Resources /Properties`` under
a known resource name, sets ``/P`` (visibility policy) and ``/OCGs``, saves it
ONCE, and then both libraries parse the identical bytes:

* pypdfbox reads ``page.get_resources().get_properties(name)`` back.
* the Java ``OcmdProbe`` reads ``page.getResources().getProperties(name)`` back
  via ``PDPropertyList.create`` and dumps ``/P`` + the referenced OCG names.

The differential is genuine: the file is produced once by pypdfbox and parsed
independently by each library. The canonical dump (per :func:`_dump_py` /
``OcmdProbe``) is, in order:

* ``POLICY=<AllOn|AnyOn|AnyOff|AllOff>``
* one ``OCG name=<name>`` line per OCG in ``/OCGs``, sorted by name.

The non-oracle tests pin the same dump from pypdfbox alone so the suite passes
without Java; the ``@requires_oracle`` tests add the cross-library assertion.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentMembershipDictionary,
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_RESOURCE_NAME = "MC0"


# --------------------------------------------------------------- fixture build


def _build_ocmd_pdf(
    out: Path,
    *,
    group_names: list[str],
    member_names: list[str],
    policy: str,
) -> None:
    """Build a one-page PDF whose first page carries an OCMD in
    ``/Resources /Properties`` under :data:`_RESOURCE_NAME`. ``member_names``
    selects which of the registered OCGs the OCMD references (by /Name).
    Closes the document in a ``finally``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        props = PDOptionalContentProperties()
        wrappers: dict[str, PDOptionalContentGroup] = {}
        for name in group_names:
            g = PDOptionalContentGroup(name)
            props.add_group(g)
            wrappers[name] = g
        doc.get_document_catalog().set_oc_properties(props)

        ocmd = PDOptionalContentMembershipDictionary()
        ocmd.set_ocgs([wrappers[n] for n in member_names])
        ocmd.set_visibility_policy(policy)

        res = PDResources()
        res.put(COSName.get_pdf_name(_RESOURCE_NAME), ocmd)
        page.set_resources(res)

        doc.save(str(out))
    finally:
        doc.close()


# ----------------------------------------------------------------- py dump


def _dump_py(path: Path) -> str:
    """pypdfbox's canonical OCMD dump for ``path`` — identical line format to
    ``OcmdProbe``. Closes the document in a ``finally``."""
    doc = PDDocument.load(path)
    try:
        page = doc.get_page(0)
        res = page.get_resources()
        pl = (
            None
            if res is None
            else res.get_properties(COSName.get_pdf_name(_RESOURCE_NAME))
        )
        if not isinstance(pl, PDOptionalContentMembershipDictionary):
            return "NOT_OCMD\n"
        lines = [f"POLICY={pl.get_visibility_policy()}"]
        ocg_lines = [f"OCG name={g.get_name() or ''}" for g in pl.get_ocgs()]
        ocg_lines.sort()
        lines.extend(ocg_lines)
        return "\n".join(lines) + "\n"
    finally:
        doc.close()


# ------------------------------------------------------------ non-oracle pins


def test_ocmd_anyoff_round_trips_in_pypdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "ocmd_anyoff.pdf"
    _build_ocmd_pdf(
        pdf,
        group_names=["Layer A", "Layer B"],
        member_names=["Layer A", "Layer B"],
        policy="AnyOff",
    )
    assert _dump_py(pdf) == "POLICY=AnyOff\nOCG name=Layer A\nOCG name=Layer B\n"


def test_ocmd_default_policy_is_anyon(tmp_path: Path) -> None:
    """No explicit /P written when the policy is left at the spec default —
    the read-back still resolves to AnyOn."""
    doc = PDDocument()
    pdf = tmp_path / "ocmd_default.pdf"
    try:
        page = PDPage()
        doc.add_page(page)
        props = PDOptionalContentProperties()
        a = PDOptionalContentGroup("Solo")
        props.add_group(a)
        doc.get_document_catalog().set_oc_properties(props)
        ocmd = PDOptionalContentMembershipDictionary()
        ocmd.set_ocgs([a])
        # Deliberately do NOT set /P.
        res = PDResources()
        res.put(COSName.get_pdf_name(_RESOURCE_NAME), ocmd)
        page.set_resources(res)
        doc.save(str(pdf))
    finally:
        doc.close()
    assert _dump_py(pdf) == "POLICY=AnyOn\nOCG name=Solo\n"


def test_ocmd_alloff_single_member(tmp_path: Path) -> None:
    pdf = tmp_path / "ocmd_alloff.pdf"
    _build_ocmd_pdf(
        pdf,
        group_names=["X", "Y", "Z"],
        member_names=["Y"],
        policy="AllOff",
    )
    assert _dump_py(pdf) == "POLICY=AllOff\nOCG name=Y\n"


# ------------------------------------------------------------ differential


@requires_oracle
def test_ocmd_anyoff_matches_pdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "ocmd_anyoff.pdf"
    _build_ocmd_pdf(
        pdf,
        group_names=["Layer A", "Layer B"],
        member_names=["Layer A", "Layer B"],
        policy="AnyOff",
    )
    java = run_probe_text("OcmdProbe", str(pdf), _RESOURCE_NAME)
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_ocmd_allon_matches_pdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "ocmd_allon.pdf"
    _build_ocmd_pdf(
        pdf,
        group_names=["Alpha", "Beta", "Gamma"],
        member_names=["Alpha", "Gamma"],
        policy="AllOn",
    )
    java = run_probe_text("OcmdProbe", str(pdf), _RESOURCE_NAME)
    py = _dump_py(pdf)
    assert py == java


@requires_oracle
def test_ocmd_default_policy_matches_pdfbox(tmp_path: Path) -> None:
    """No /P written: both libraries resolve the spec default AnyOn."""
    doc = PDDocument()
    pdf = tmp_path / "ocmd_default.pdf"
    try:
        page = PDPage()
        doc.add_page(page)
        props = PDOptionalContentProperties()
        a = PDOptionalContentGroup("Solo")
        props.add_group(a)
        doc.get_document_catalog().set_oc_properties(props)
        ocmd = PDOptionalContentMembershipDictionary()
        ocmd.set_ocgs([a])
        res = PDResources()
        res.put(COSName.get_pdf_name(_RESOURCE_NAME), ocmd)
        page.set_resources(res)
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OcmdProbe", str(pdf), _RESOURCE_NAME)
    py = _dump_py(pdf)
    assert py == java
    assert py == "POLICY=AnyOn\nOCG name=Solo\n"
