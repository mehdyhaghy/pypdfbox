"""Differential fuzz audit for the catalog ``/Names`` subtree wrappers vs Apache
PDFBox 3.0.7 (wave 1555, agent B).

Complements the wave-1529 ``PDDocumentNameDictionary`` accessor-leniency oracle
(which drives a malformed ``/Names`` sub-dict via on-disk PDFs) by attacking two
surfaces that probe does NOT touch:

1. **Per-name destination resolution** on the legacy flat
   :class:`PDDocumentNameDestinationDictionary`
   (``get_destination(name)``) over a ~17-case matrix of malformed / edge entry
   values — bare explicit-destination arrays, ``{/D <array>}`` /
   ``{/D <string>}`` / ``{/D <name>}`` / ``{/D <dict>}`` / ``{/D <shortarr>}``
   dict forms, dicts without ``/D``, bare wrong-typed values, and malformed bare
   arrays (too short / empty / bad item[1] / unknown fit type). This is the
   "named-destination resolution returning a page destination vs ``None`` vs
   exception" surface, exercised directly against the wrapper.

2. **Sub-entry accessor presence/class** on :class:`PDDocumentNameDictionary`
   built directly over an in-memory ``/Names`` dict whose every upstream-exposed
   sub-entry (``/Dests`` / ``/EmbeddedFiles`` / ``/JavaScript``) is present-as-
   dict vs present-as-non-dict vs missing, plus a sample
   ``get_dests().get_value("home")`` chained through the name-tree wrapper.

Both stacks construct byte-identical COS shapes (no file round-trip needed — the
wrappers accept a raw ``COSDictionary``) and project the identical grammar. The
Java probe is ``oracle/probes/NameDictionaryFuzzProbe.java``; this module mirrors
it line-for-line and asserts parity when the live oracle is present, falling back
to PDFBox-3.0.7-derived expected values otherwise.

``IOException`` maps to pypdfbox ``OSError`` per the harness convention.

REAL DIVERGENCE PINNED (``_PINNED_NAMEDICT``): when a
:class:`PDDocumentNameDictionary` is built with a ``None`` catalog AND
``/Names /Dests`` is absent or wrong-typed, upstream ``getDests()`` throws
``NullPointerException`` because its catalog-fallback path dereferences
``catalog.getCOSObject()`` without a null check — a latent upstream bug. pypdfbox
guards the fallback with ``if self._catalog is not None`` and returns ``None``,
so it is strictly more robust. This divergence is defensible and recorded in
CHANGES.md; it surfaces only via the programmatic ``(None, names)`` constructor
path (real PDF loading always supplies a catalog, where both stacks agree).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _xyz() -> COSArray:
    a = COSArray()
    a.add(COSInteger.get(0))
    a.add(_N("XYZ"))
    a.add(COSInteger.get(1))
    a.add(COSInteger.get(2))
    a.add(COSInteger.get(3))
    return a


def _fit() -> COSArray:
    a = COSArray()
    a.add(COSInteger.get(0))
    a.add(_N("Fit"))
    return a


def _wrap_d(d: COSBase) -> COSDictionary:
    dict_ = COSDictionary()
    dict_.set_item(_N("D"), d)
    return dict_


def _cls(o: object) -> str:
    return "null" if o is None else type(o).__name__


# --------------------------------------------------------- section 1 corpus


def _build_dest_dict() -> PDDocumentNameDestinationDictionary:
    d = COSDictionary()
    d.set_item(_N("arr_xyz"), _xyz())
    d.set_item(_N("arr_fit"), _fit())
    d.set_item(_N("dictD_xyz"), _wrap_d(_xyz()))
    d.set_item(_N("dictD_fit"), _wrap_d(_fit()))
    d.set_item(_N("dictD_str"), _wrap_d(COSString("target")))
    d.set_item(_N("dictD_name"), _wrap_d(_N("target")))
    d.set_item(_N("dictD_dict"), _wrap_d(COSDictionary()))
    _short = COSArray()
    _short.add(COSInteger.get(0))
    d.set_item(_N("dictD_shortarr"), _wrap_d(_short))
    _no_d = COSDictionary()
    _no_d.set_item(_N("Type"), _N("X"))
    d.set_item(_N("dict_noD"), _no_d)
    d.set_item(_N("bare_name"), _N("foo"))
    d.set_item(_N("bare_string"), COSString("foo"))
    d.set_item(_N("bare_number"), COSInteger.get(5))
    _short2 = COSArray()
    _short2.add(COSInteger.get(0))
    d.set_item(_N("arr_short"), _short2)
    d.set_item(_N("arr_empty"), COSArray())
    _bad1 = COSArray()
    _bad1.add(COSInteger.get(0))
    _bad1.add(COSInteger.get(9))
    d.set_item(_N("arr_baditem1"), _bad1)
    _unk = COSArray()
    _unk.add(COSInteger.get(0))
    _unk.add(_N("BOGUS"))
    d.set_item(_N("arr_unknownfit"), _unk)
    return PDDocumentNameDestinationDictionary(d)


_DEST_CASES: tuple[str, ...] = (
    "arr_xyz",
    "arr_fit",
    "dictD_xyz",
    "dictD_fit",
    "dictD_str",
    "dictD_name",
    "dictD_dict",
    "dictD_shortarr",
    "dict_noD",
    "bare_name",
    "bare_string",
    "bare_number",
    "arr_short",
    "arr_empty",
    "arr_baditem1",
    "arr_unknownfit",
    "absent",
)

# Expected GETDEST lines, captured from the live Apache PDFBox 3.0.7 oracle
# (NameDictionaryFuzzProbe). IOException -> OSError. pypdfbox matches every cell.
_DEST_EXPECTED: dict[str, str] = {
    "arr_xyz": "PDPageXYZDestination",
    "arr_fit": "PDPageFitDestination",
    "dictD_xyz": "PDPageXYZDestination",
    "dictD_fit": "PDPageFitDestination",
    "dictD_str": "PDNamedDestination",
    "dictD_name": "PDNamedDestination",
    "dictD_dict": "ERR:OSError",
    "dictD_shortarr": "ERR:OSError",
    "dict_noD": "null",
    "bare_name": "null",
    "bare_string": "null",
    "bare_number": "null",
    "arr_short": "ERR:OSError",
    "arr_empty": "ERR:OSError",
    "arr_baditem1": "ERR:OSError",
    "arr_unknownfit": "ERR:OSError",
    "absent": "null",
}


def _py_get_dest(dd: PDDocumentNameDestinationDictionary, name: str) -> str:
    try:
        return _cls(dd.get_destination(name))
    except Exception as exc:  # noqa: BLE001 — projecting the exception class
        return "ERR:" + type(exc).__name__


# --------------------------------------------------------- section 2 corpus


def _names_all_dicts() -> COSDictionary:
    d = COSDictionary()
    for key in ("Dests", "EmbeddedFiles", "JavaScript"):
        d.set_item(_N(key), COSDictionary())
    return d


def _names_all_nondict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Dests"), _N("x"))
    d.set_item(_N("EmbeddedFiles"), COSArray())
    d.set_item(_N("JavaScript"), COSString("x"))
    return d


def _names_dest_tree_home() -> COSDictionary:
    dest_tree = COSDictionary()
    names_arr = COSArray()
    names_arr.add(COSString("home"))
    names_arr.add(_xyz())
    dest_tree.set_item(_N("Names"), names_arr)
    d = COSDictionary()
    d.set_item(_N("Dests"), dest_tree)
    return d


def _names_only(key: str, value: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N(key), value)
    return d


def _namedict_cases() -> list[tuple[str, COSDictionary]]:
    return [
        ("empty", COSDictionary()),
        ("all_dicts", _names_all_dicts()),
        ("all_nondict", _names_all_nondict()),
        ("dests_only_dict", _names_only("Dests", COSDictionary())),
        ("dests_only_nondict", _names_only("Dests", COSInteger.get(3))),
        ("dests_nametree_home", _names_dest_tree_home()),
    ]


# Expected NAMEDICT lines from the live oracle, BUT with the catalog-null
# divergence corrected to pypdfbox's hardened behaviour (see module docstring /
# _PINNED_NAMEDICT). For the three cases where /Dests is absent-or-non-dict AND
# catalog is None, upstream throws NPE on the null-catalog fallback; pypdfbox
# returns null. The pinned set below is what pypdfbox produces.
_NAMEDICT_PY_EXPECTED: dict[str, str] = {
    "empty": "dests=null embed=null js=null deslookup=null",
    "all_dicts": (
        "dests=PDDestinationNameTreeNode embed=PDEmbeddedFilesNameTreeNode "
        "js=PDJavascriptNameTreeNode deslookup=null"
    ),
    "all_nondict": "dests=null embed=null js=null deslookup=null",
    "dests_only_dict": (
        "dests=PDDestinationNameTreeNode embed=null js=null deslookup=null"
    ),
    "dests_only_nondict": "dests=null embed=null js=null deslookup=null",
    "dests_nametree_home": (
        "dests=PDDestinationNameTreeNode embed=null js=null "
        "deslookup=PDPageXYZDestination"
    ),
}

# The raw Java oracle lines (NPE where pypdfbox returns null). Used to assert the
# divergence is real and lives exactly where the docstring claims, and that every
# OTHER cell agrees with pypdfbox.
_NAMEDICT_JAVA_EXPECTED: dict[str, str] = {
    **_NAMEDICT_PY_EXPECTED,
    "empty": (
        "dests=ERR:NullPointerException embed=null js=null "
        "deslookup=ERR:NullPointerException"
    ),
    "all_nondict": (
        "dests=ERR:NullPointerException embed=null js=null "
        "deslookup=ERR:NullPointerException"
    ),
    "dests_only_nondict": (
        "dests=ERR:NullPointerException embed=null js=null "
        "deslookup=ERR:NullPointerException"
    ),
}

# Cells where pypdfbox intentionally diverges from upstream (hardened null-catalog
# fallback). Everything not listed here must agree byte-for-byte.
_PINNED_NAMEDICT: frozenset[str] = frozenset(
    {"empty", "all_nondict", "dests_only_nondict"}
)


def _py_dests(nd: PDDocumentNameDictionary) -> str:
    try:
        return _cls(nd.get_dests())
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + type(exc).__name__


def _py_embed(nd: PDDocumentNameDictionary) -> str:
    try:
        return _cls(nd.get_embedded_files())
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + type(exc).__name__


def _py_js(nd: PDDocumentNameDictionary) -> str:
    try:
        return _cls(nd.get_javascript())
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + type(exc).__name__


def _py_deslookup(nd: PDDocumentNameDictionary) -> str:
    try:
        tree = nd.get_dests()
        if tree is None:
            return "null"
        return _cls(tree.get_value("home"))
    except Exception as exc:  # noqa: BLE001
        return "ERR:" + type(exc).__name__


def _py_namedict_line(label: str, names: COSDictionary) -> str:
    nd = PDDocumentNameDictionary(None, names)
    return (
        f"dests={_py_dests(nd)} embed={_py_embed(nd)} "
        f"js={_py_js(nd)} deslookup={_py_deslookup(nd)}"
    )


# --------------------------------------------------------- value-based tests


def test_get_destination_matrix_matches_pdfbox_values() -> None:
    """pypdfbox ``get_destination`` matches the PDFBox-3.0.7 resolution matrix."""
    dd = _build_dest_dict()
    for case in _DEST_CASES:
        assert _py_get_dest(dd, case) == _DEST_EXPECTED[case], case


def test_namedict_accessors_match_pinned_values() -> None:
    """pypdfbox ``/Names`` accessors match the pinned (hardened) expectation."""
    for label, names in _namedict_cases():
        assert _py_namedict_line(label, names) == _NAMEDICT_PY_EXPECTED[label], label


def test_null_catalog_dests_fallback_returns_none_not_npe() -> None:
    """Pin the hardening: a null-catalog wrapper with absent/wrong-typed /Dests
    returns ``None`` (where upstream throws NPE)."""
    for label in _PINNED_NAMEDICT:
        names = dict(_namedict_cases())[label]
        nd = PDDocumentNameDictionary(None, names)
        assert nd.get_dests() is None, label


# --------------------------------------------------------- live oracle tests


@requires_oracle
def test_oracle_get_destination_parity() -> None:
    raw = run_probe_text("NameDictionaryFuzzProbe")
    java: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.startswith("GETDEST "):
            continue
        body = line[len("GETDEST ") :]
        case, _, val = body.partition(" = ")
        # IOException -> OSError to compare against pypdfbox's exception surface.
        java[case.strip()] = val.strip().replace("IOException", "OSError")
    dd = _build_dest_dict()
    for case in _DEST_CASES:
        assert _py_get_dest(dd, case) == java[case], case
        assert java[case] == _DEST_EXPECTED[case], case


@requires_oracle
def test_oracle_namedict_parity_with_pinned_divergence() -> None:
    raw = run_probe_text("NameDictionaryFuzzProbe")
    java: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.startswith("NAMEDICT "):
            continue
        body = line[len("NAMEDICT ") :]
        label, _, rest = body.partition(" ")
        java[label.strip()] = rest.strip()
    for label, names in _namedict_cases():
        py = _py_namedict_line(label, names)
        # The live Java oracle line must match our recorded snapshot.
        assert java[label] == _NAMEDICT_JAVA_EXPECTED[label], label
        if label in _PINNED_NAMEDICT:
            # Intentional, documented divergence: pypdfbox hardens the null
            # catalog fallback. Java NPEs, pypdfbox returns null.
            assert "NullPointerException" in java[label], label
            assert "NullPointerException" not in py, label
            assert py == _NAMEDICT_PY_EXPECTED[label], label
        else:
            assert py == java[label], label
