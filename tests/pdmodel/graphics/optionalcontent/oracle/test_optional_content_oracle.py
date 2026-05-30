"""Live Apache PDFBox INVERTED differential parity for optional content
(layers / OCG) — ``pypdfbox.pdmodel.graphics.optionalcontent``.

The existing ``test_ocg_oracle.py`` differential builds the fixture *with
pypdfbox*, then parses it with both libraries. That direction can mask a
pypdfbox *reader* bug whenever pypdfbox writes an /OCProperties layout that
happens to round-trip through its own reader.

This module inverts the authoring direction: Apache PDFBox 3.0.7 itself writes
the optional-content document (``OcgAuthorProbe``), so the on-disk /OCProperties
layout — the /D config dict, the /ON and /OFF arrays, the indirect OCG
references, and the /BaseState name spelling — is exactly what upstream emits.
pypdfbox then re-reads that genuine PDFBox-produced file. The assertion is that
pypdfbox's OCG accessors (``get_optional_content_groups``, ``get_base_state``,
``is_group_enabled``) agree with PDFBox's own ``OcgProbe`` dump of the identical
bytes.

The authored fixture is deterministic (see ``OcgAuthorProbe``):

* BaseState = ON
* OCGs "Alpha", "Beta", "Gamma" (added in that order)
* "Beta" turned OFF, "Gamma" explicitly turned ON

so the expected dump is hard-coded as a second, independent pin.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

# ----------------------------------------------------------------- py dump


def _dump_py(path: Path) -> str:
    """pypdfbox's canonical OCG dump for ``path`` — identical line format to
    ``OcgProbe`` (the line format the Java oracle emits). Closes the document
    in a ``finally``."""
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


# ------------------------------------------------------------ differential test


@requires_oracle
def test_pdfbox_authored_ocg_read_by_pypdfbox(tmp_path: Path) -> None:
    """Apache PDFBox writes the OCG document; pypdfbox reads it back.

    Both the live PDFBox dump (``OcgProbe`` on the PDFBox-authored bytes) and
    pypdfbox's own dump must agree, AND both must equal the hard-coded
    expectation for the deterministic ``OcgAuthorProbe`` fixture."""
    pdf = tmp_path / "pdfbox_authored_ocg.pdf"
    # PDFBox authors and saves the fixture to disk (no stdout).
    run_probe("OcgAuthorProbe", str(pdf))
    assert pdf.is_file()

    java = run_probe_text("OcgProbe", str(pdf))
    py = _dump_py(pdf)
    assert py == java

    # Both PDFBox's and pypdfbox's no-arg PDOptionalContentProperties
    # constructor seed /D /Name = "Top" (PDF/A-3 requires a config name),
    # so the default-config name on the authored fixture is "Top".
    expected = (
        "CONFIG name=Top baseState=ON\n"
        "OCG name=Alpha enabled=true\n"
        "OCG name=Beta enabled=false\n"
        "OCG name=Gamma enabled=true\n"
    )
    assert py == expected
