"""Live PDFBox differential parity for predefined-CMap *metadata*.

The sibling oracles pin a predefined CMap's name, WMode, ``to_cid`` and the
codespace-assigned ``read_code`` length (``test_predefined_cmap_oracle.py``,
``test_predefined_cmap_type0_oracle.py``, ``test_embedded_cmap_oracle.py``).
None of them pin the CIDSystemInfo triple a CMap carries, nor the
mapping/space predicates PDFBox derives while parsing it. Those drive font
matching (a Type0 font selects a CMap whose ``Registry-Ordering`` matches the
descendant CIDFont's ``/CIDSystemInfo``) and the space-width fallback, so a
loader that dropped ``/Supplement`` or mis-flagged ``has_cid_mappings`` would
silently break glyph selection.

The oracle output is produced by ``oracle/probes/PredefCMapInfoProbe.java``,
one block per CMap::

    CMAP <name>
    REGISTRY <registry>
    ORDERING <ordering>
    SUPPLEMENT <supplement>
    WMODE <wmode>
    HASCID <true|false>
    HASUNICODE <true|false>
    SPACE <spaceMapping>

The Python side reconstructs the identical lines via
``CMapManager.get_predefined_cmap(name)``, so a divergence in any single field
surfaces as one differing line.

CMaps covered span every metadata shape in the bundled set:

* ``Identity-H`` / ``Identity-V`` — the programmatic 2-byte identity builders
  (Adobe-Identity-0; the -V case carries WMode 1 with the same CIDSystemInfo).
* ``90ms-RKSJ-H`` / ``90ms-RKSJ-V`` — Adobe-Japan1-2 via a ``usecmap`` base;
  the -V variant inherits the base codespace yet keeps WMode 1.
* ``UniGB-UCS2-H`` / ``UniGB-UCS2-V`` — Adobe-GB1-4 Unicode-input CMaps with
  CID mappings (``has_cid_mappings`` true, ``has_unicode_mappings`` false).
* ``Adobe-Japan1-UCS2`` — the inverse shape: a ``*-UCS2`` CMap with **no** CID
  mappings but Unicode (bfrange) mappings, a Supplement of 6, and a real
  ``get_space_mapping`` (the code mapped to U+0020).
* ``GB-EUC-H`` — a legacy EUC CMap whose Supplement is 0 (distinct from the
  UniGB Supplement 4) — guards against a hard-coded supplement.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap_manager import CMapManager
from tests.oracle.harness import requires_oracle, run_probe_text

_NAMES: list[str] = [
    "Identity-H",
    "Identity-V",
    "90ms-RKSJ-H",
    "90ms-RKSJ-V",
    "UniGB-UCS2-H",
    "UniGB-UCS2-V",
    "Adobe-Japan1-UCS2",
    "GB-EUC-H",
]


def _py_info_lines(name: str) -> list[str]:
    """Reconstruct one PredefCMapInfoProbe block from pypdfbox for ``name``.

    Java's ``Boolean.toString`` renders ``true``/``false`` lowercase, so the
    predicate lines lower-case the Python ``bool`` to match the probe output.
    """
    cmap = CMapManager.get_predefined_cmap(name)
    assert cmap is not None, f"bundled CMap failed to load: {name}"
    return [
        f"CMAP {cmap.get_name()}",
        f"REGISTRY {cmap.get_registry()}",
        f"ORDERING {cmap.get_ordering()}",
        f"SUPPLEMENT {cmap.get_supplement()}",
        f"WMODE {cmap.get_wmode()}",
        f"HASCID {str(cmap.has_cid_mappings()).lower()}",
        f"HASUNICODE {str(cmap.has_unicode_mappings()).lower()}",
        f"SPACE {cmap.get_space_mapping()}",
    ]


@requires_oracle
@pytest.mark.parametrize("name", _NAMES)
def test_predefined_cmap_info_matches_pdfbox(name: str) -> None:
    """pypdfbox's predefined-CMap metadata block must equal Apache PDFBox's.

    A differing ``REGISTRY``/``ORDERING``/``SUPPLEMENT`` line means the
    CIDSystemInfo triple was lost or mis-parsed; a differing ``HASCID`` /
    ``HASUNICODE`` line means the loader mis-classified the mapping content;
    a differing ``SPACE`` line means the U+0020 space-mapping was not tracked.
    """
    java = run_probe_text("PredefCMapInfoProbe", name).splitlines()
    py = _py_info_lines(name)
    assert py == java, (
        f"predefined-CMap metadata parity broken for {name}:\n"
        f"  JAVA: {java}\n"
        f"  PY:   {py}"
    )
