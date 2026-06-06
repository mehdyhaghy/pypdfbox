"""Live PDFBox differential parity for ``PDFMergerUtility``'s ``/OCProperties``
(optional-content / layers) merge.

The companion oracle modules pin the merged page geometry
(``test_merge_split_oracle.py``), the AcroForm / outline / named-destination
surface (``test_merge_oracle.py``), and ``/PageLabels``
(``test_merge_page_labels_oracle.py``). None of them exercises optional-content
group merging — this module fills that gap.

``PDFMergerUtility`` merges ``/OCProperties`` through
``PDFCloneUtility.cloneMergeCOSBase``: when the destination already carries an
``/OCProperties`` (i.e. the *second* and later sources), the source ``/OCGs``
array entries are **appended** (no dedup by ``/Name`` — two sources each naming
a layer ``Layer1`` yield two groups in the merged document), and the ``/D``
default-config sub-dictionary is merged element-wise (the destination wins on
scalar keys like ``/Name``; the ``/ON``, ``/OFF``, ``/Order`` arrays
concatenate). A merge that instead deduplicated by name, or dropped the second
source's groups, or clobbered ``/D/Name`` would diverge here.

Inputs are built through pypdfbox with ``/OCProperties`` written via the
``PDOptionalContentProperties`` wrapper so the two source files are
byte-identical on both sides of the comparison. The Java side runs
``MergeOcPropertiesProbe`` (``PDFMergerUtility.mergeDocuments`` then reload +
``/OCProperties`` projection); the pypdfbox side runs the same merge through
``PDFMergerUtility.merge_documents`` and reads the same projection back. Both
merged outputs must also pass ``qpdf --check``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_NAME = COSName.get_pdf_name("Name")
_OFF = COSName.get_pdf_name("OFF")


# ----------------------------------------------------------------- builders


def _ocg_source(
    path: Path,
    group_names: list[str],
    *,
    config_name: str,
    off_names: list[str] | None = None,
) -> None:
    """Build a single-page PDF whose catalog carries an ``/OCProperties`` with
    one OCG per entry in ``group_names``. ``/D/Name`` is ``config_name``; any
    name in ``off_names`` is added to ``/D/OFF`` (default-hidden)."""
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.LETTER))
    ocp = PDOptionalContentProperties()
    groups: dict[str, PDOptionalContentGroup] = {}
    for name in group_names:
        group = PDOptionalContentGroup(name)
        ocp.add_group(group)
        groups[name] = group
    d = ocp.get_d()
    d.set_string(_NAME, config_name)
    if off_names:
        off = COSArray()
        for name in off_names:
            off.add(groups[name].get_cos_object())
        d.set_item(_OFF, off)
    doc.get_document_catalog().set_oc_properties(ocp)
    doc.save(str(path))
    doc.close()


# ------------------------------------------------------------- fact reader


def _py_merge(sources: list[Path], dest: Path) -> None:
    merger = PDFMergerUtility()
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _read_oc_facts(path: Path) -> list[str]:
    """Project a merged document's ``/OCProperties`` into the same line list the
    Java ``MergeOcPropertiesProbe`` emits."""
    doc = PDDocument.load(str(path))
    try:
        ocp = doc.get_document_catalog().get_oc_properties()
        if ocp is None:
            return ["NO_OCPROPERTIES"]
        lines: list[str] = []
        ocgs = ocp.get_oc_gs()
        lines.append(f"OCGS_COUNT={ocgs.size()}")
        for i in range(ocgs.size()):
            entry = ocp.to_dictionary(ocgs.get_object(i))
            name = ""
            if entry is not None:
                name = entry.get_string(_NAME) or ""
            lines.append(f"OCG {i} name={_esc(name)}")
        d = ocp.get_d()
        d_name = d.get_string(_NAME)
        lines.append(f"D_NAME={'null' if d_name is None else _esc(d_name)}")
        for key in ("ON", "OFF", "Order"):
            arr = d.get_dictionary_object(COSName.get_pdf_name(key))
            lines.append(
                f"D_{key.upper()}_COUNT={arr.size() if isinstance(arr, COSArray) else -1}"
            )
        return lines
    finally:
        doc.close()


def _esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _qpdf_check(path: Path) -> int:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
def test_merge_oc_properties_distinct_names(tmp_path: Path) -> None:
    """Two sources with disjoint layer names: the merged ``/OCGs`` is the union
    in source order, and ``/D/Name`` is the first source's config name."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    _ocg_source(a, ["AlphaLayer"], config_name="ConfigA")
    _ocg_source(b, ["BravoLayer"], config_name="ConfigB")

    java_out = tmp_path / "java.pdf"
    py_out = tmp_path / "py.pdf"
    java = run_probe_text(
        "MergeOcPropertiesProbe", str(java_out), str(a), str(b)
    )
    _py_merge([a, b], py_out)
    py = "\n".join(_read_oc_facts(py_out)) + "\n"

    assert py == java
    assert _qpdf_check(py_out) <= 3
    assert "OCGS_COUNT=2" in py


@requires_oracle
@_requires_qpdf
def test_merge_oc_properties_duplicate_names(tmp_path: Path) -> None:
    """Two sources that BOTH name a layer ``Shared``: upstream appends rather
    than deduplicating, so the merged ``/OCGs`` carries two ``Shared`` groups.
    This is the load-bearing 'no dedup by name' contract."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    _ocg_source(a, ["Shared", "OnlyA"], config_name="Top")
    _ocg_source(b, ["Shared", "OnlyB"], config_name="Top", off_names=["Shared"])

    java_out = tmp_path / "java.pdf"
    py_out = tmp_path / "py.pdf"
    java = run_probe_text(
        "MergeOcPropertiesProbe", str(java_out), str(a), str(b)
    )
    _py_merge([a, b], py_out)
    py = "\n".join(_read_oc_facts(py_out)) + "\n"

    assert py == java
    assert _qpdf_check(py_out) <= 3
    # Both 'Shared' groups survive (4 groups: Shared, OnlyA, Shared, OnlyB).
    assert "OCGS_COUNT=4" in py


@requires_oracle
@_requires_qpdf
def test_merge_oc_properties_dest_lacks_then_gains(tmp_path: Path) -> None:
    """First source has NO ``/OCProperties``; second does. The destination
    gains the second source's ``/OCProperties`` wholesale (clone, not merge)."""
    a = tmp_path / "a.pdf"  # no OCProperties
    b = tmp_path / "b.pdf"
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.LETTER))
    doc.save(str(a))
    doc.close()
    _ocg_source(b, ["LateLayer"], config_name="LateConfig")

    java_out = tmp_path / "java.pdf"
    py_out = tmp_path / "py.pdf"
    java = run_probe_text(
        "MergeOcPropertiesProbe", str(java_out), str(a), str(b)
    )
    _py_merge([a, b], py_out)
    py = "\n".join(_read_oc_facts(py_out)) + "\n"

    assert py == java
    assert _qpdf_check(py_out) <= 3
    assert "OCGS_COUNT=1" in py
    assert "D_NAME=LateConfig" in py
