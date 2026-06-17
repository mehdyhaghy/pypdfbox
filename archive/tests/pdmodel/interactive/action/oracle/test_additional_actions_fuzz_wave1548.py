"""Live Apache PDFBox differential fuzz of the ADDITIONAL-ACTIONS (/AA)
trigger-getter dispatch surface (wave 1548, agent D).

The four ``PD*AdditionalActions`` classes — annotation (E/X/D/U/Fo/Bl/PO/PC/
PV/PI), page (O/C), document-catalog (WC/WS/DS/WP/DP) and form-field (K/F/V/C)
— each resolve a trigger via ``getCOSDictionary`` + ``PDActionFactory.
createAction``. The existing /AA probes only walk the happy path:

* ``AdditionalActionsProbe`` enumerates triggers PRESENT in a real document.
* ``AaTriggerJsonProbe`` round-trips two well-formed authored triggers.
* ``ActionAccessorProbe`` drives the page /O,/C secondary accessors.

This probe fuzzes the getter DISPATCH itself over a malformed corpus: each
trigger present with an action dict whose /S is a known subtype, an UNKNOWN
subtype, missing entirely, or one of the six "extended" subtypes that PDFBox's
``createAction`` does NOT map (Rendition, Trans, GoToDp, GoTo3DView,
SetOCGState, RichMediaExecute); plus a wrong-typed value (name / int / array),
and an absent key. The projection is the resolved ``PDAction`` class
simple-name (or "null"), and whether the getter raised.

The contract under test: pypdfbox's getter dispatch == Apache PDFBox 3.0.7's.
``createAction`` returns ``null`` for an unknown /S, a missing /S, and every
extended subtype — so the typed getter yields ``None`` (not a
``PDActionUnknown`` / typed wrapper) for those. This pins the wave-1548 fix
that switched the /AA getters from ``PDAction.create`` (which wraps unknown /S
in ``PDActionUnknown`` and resolves the six extended subtypes) to
``PDActionFactory.create_action`` (the path upstream actually uses).

Strategy mirrors ``ActionSubtypeFuzzProbe``: build a deterministic corpus of
``{/CLS, /TRIG, /AA}`` descriptor dicts in a ``/FuzzAA`` COSArray off the
catalog, save one ``corpus.pdf`` + ``manifest.txt``, and have both libraries
read the identical on-disk bytes.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
    PDAnnotationAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_document_catalog_additional_actions import (
    PDDocumentCatalogAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_form_field_additional_actions import (
    PDFormFieldAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_page_additional_actions import (
    PDPageAdditionalActions,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


# --------------------------------------------------------------- COS builders


def _act(sub: str | None, **entries: COSBase) -> COSDictionary:
    """An action dictionary with optional /S subtype."""
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Action"))
    if sub is not None:
        d.set_item(_n("S"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _descriptor(cls: str, trig: str, aa_value: COSBase) -> COSDictionary:
    """One fuzz case: which AA class + trigger, over an /AA dict.

    ``aa_value`` is the dictionary wrapped by the PD*AdditionalActions; it
    holds the trigger key mapped to whatever malformed value the case probes.
    """
    d = COSDictionary()
    d.set_item(_n("CLS"), _n(cls))
    d.set_item(_n("TRIG"), _n(trig))
    d.set_item(_n("AA"), aa_value)
    return d


def _aa_with(trig: str, value: COSBase | None) -> COSDictionary:
    """An additional-actions dict carrying ``trig`` -> ``value`` (or empty)."""
    aa = COSDictionary()
    if value is not None:
        aa.set_item(_n(trig), value)
    return aa


# --------------------------------------------------------------- corpus build

# A representative trigger per AA class — enough to prove the dispatch path is
# shared, without an unwieldy cartesian product. (The four classes share one
# getter body each, parameterised only by the COSName key.)
_CLASS_TRIGGERS: dict[str, str] = {
    "page": "O",
    "annot": "E",
    "catalog": "WS",
    "field": "K",
}

# Extended subtypes that pypdfbox's PDAction.create resolves to a typed wrapper
# but PDFBox's PDActionFactory.createAction (the /AA getter path) maps to null.
_EXTENDED_SUBTYPES = (
    "Rendition",
    "Trans",
    "GoToDp",
    "GoTo3DView",
    "SetOCGState",
    "RichMediaExecute",
)


def _build_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    for cls, trig in _CLASS_TRIGGERS.items():
        # --- known subtype -> typed wrapper ---
        c[f"{cls}_known_js"] = _descriptor(
            cls, trig, _aa_with(trig, _act("JavaScript", JS=COSString("x")))
        )
        c[f"{cls}_known_goto"] = _descriptor(
            cls, trig, _aa_with(trig, _act("GoTo"))
        )
        c[f"{cls}_known_named"] = _descriptor(
            cls, trig, _aa_with(trig, _act("Named", N=_n("NextPage")))
        )
        c[f"{cls}_known_uri"] = _descriptor(
            cls, trig, _aa_with(trig, _act("URI", URI=COSString("http://x")))
        )

        # --- unknown /S -> null (createAction returns null) ---
        c[f"{cls}_unknown_s"] = _descriptor(
            cls, trig, _aa_with(trig, _act("Bogus"))
        )
        # --- missing /S -> null ---
        c[f"{cls}_missing_s"] = _descriptor(
            cls, trig, _aa_with(trig, _act(None))
        )
        # --- /S as a string, not a name -> getNameAsString null -> null ---
        c[f"{cls}_s_string"] = _descriptor(
            cls,
            trig,
            _aa_with(trig, _act(None, S=COSString("JavaScript"))),
        )

        # --- wrong-typed trigger value -> getCOSDictionary null -> null ---
        c[f"{cls}_value_name"] = _descriptor(
            cls, trig, _aa_with(trig, _n("Bogus"))
        )
        c[f"{cls}_value_int"] = _descriptor(
            cls, trig, _aa_with(trig, COSInteger.get(5))
        )
        c[f"{cls}_value_array"] = _descriptor(
            cls, trig, _aa_with(trig, _arr(COSInteger.get(1)))
        )

        # --- absent trigger key -> null ---
        c[f"{cls}_absent"] = _descriptor(cls, trig, _aa_with(trig, None))

        # --- each extended subtype -> null (NOT a typed wrapper) ---
        for ext in _EXTENDED_SUBTYPES:
            c[f"{cls}_ext_{ext}"] = _descriptor(
                cls, trig, _aa_with(trig, _act(ext))
            )

    # Exercise every annotation trigger key once (the rare two-letter ones) to
    # prove the per-key COSName wiring is correct, not just the /E representative.
    for trig in ("X", "D", "U", "Fo", "Bl", "PO", "PC", "PV", "PI"):
        c[f"annot_key_{trig}"] = _descriptor(
            "annot", trig, _aa_with(trig, _act("JavaScript", JS=COSString("k")))
        )
        c[f"annot_key_{trig}_unknown"] = _descriptor(
            "annot", trig, _aa_with(trig, _act("Bogus"))
        )

    # Same for the remaining catalog / page / field keys.
    for trig in ("WC", "DS", "WP", "DP"):
        c[f"catalog_key_{trig}"] = _descriptor(
            "catalog", trig, _aa_with(trig, _act("Named", N=_n("Print")))
        )
    c["page_key_C"] = _descriptor(
        "page", "C", _aa_with("C", _act("GoTo"))
    )
    for trig in ("F", "V", "C"):
        c[f"field_key_{trig}"] = _descriptor(
            "field", trig, _aa_with(trig, _act("JavaScript", JS=COSString("f")))
        )

    return c


# --------------------------------------------------------------- projection


def _resolve(cls: str, trig: str, aa: COSDictionary) -> object | None:
    if cls == "page":
        a = PDPageAdditionalActions(aa)
        return {"O": a.get_o, "C": a.get_c}[trig]()
    if cls == "annot":
        a = PDAnnotationAdditionalActions(aa)
        return {
            "E": a.get_e,
            "X": a.get_x,
            "D": a.get_d,
            "U": a.get_u,
            "Fo": a.get_fo,
            "Bl": a.get_bl,
            "PO": a.get_po,
            "PC": a.get_pc,
            "PV": a.get_pv,
            "PI": a.get_pi,
        }[trig]()
    if cls == "catalog":
        a = PDDocumentCatalogAdditionalActions(aa)
        return {
            "WC": a.get_wc,
            "WS": a.get_ws,
            "DS": a.get_ds,
            "WP": a.get_wp,
            "DP": a.get_dp,
        }[trig]()
    if cls == "field":
        a = PDFormFieldAdditionalActions(aa)
        return {"K": a.get_k, "F": a.get_f, "V": a.get_v, "C": a.get_c}[trig]()
    raise ValueError(f"cls {cls}")


def _project(descriptor: COSDictionary) -> str:
    cls = descriptor.get_name_as_string(_n("CLS"))
    trig = descriptor.get_name_as_string(_n("TRIG"))
    aa_base = descriptor.get_dictionary_object(_n("AA"))
    aa = aa_base if isinstance(aa_base, COSDictionary) else COSDictionary()
    action = _resolve(cls, trig, aa)
    return "null" if action is None else type(action).__name__


def _py_line(name: str, d: COSDictionary | None) -> str:
    if d is None:
        return f"CASE {name} ERR:NODICT"
    try:
        return f"CASE {name} {_project(d)}"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return f"CASE {name} ERR:{type(exc).__name__}"


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(dir_path: Path, corpus: dict[str, COSDictionary]) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        arr = COSArray()
        for d in corpus.values():
            arr.add(d)
        catalog.set_item(_n("FuzzAA"), arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    (dir_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )


_doc_keepalive: list[object] = []


def _reload_corpus(
    dir_path: Path, order: list[str]
) -> dict[str, COSDictionary | None]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    out: dict[str, COSDictionary | None] = {}
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n("FuzzAA"))
    for i, name in enumerate(order):
        entry = arr.get_object(i)
        out[name] = entry if isinstance(entry, COSDictionary) else None
    return out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java line. Empty: with the
# wave-1548 createAction fix, every getter projection matches the live oracle.
_PINNED_DIVERGENCES: dict[str, str] = {}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_additional_actions_getter_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every /AA trigger-getter dispatch projection is identical on pypdfbox and
    Apache PDFBox 3.0.7, reading the same on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("AdditionalActionsFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )

    reloaded = _reload_corpus(tmp_path, list(corpus))
    py_by_name = {name: _py_line(name, d) for name, d in reloaded.items()}

    mismatches: list[str] = []
    for jline in java_lines:
        name = jline.split(" ", 2)[1]
        pline = py_by_name[name]
        if name in _PINNED_DIVERGENCES:
            if pline != _PINNED_DIVERGENCES[name]:
                mismatches.append(
                    f"{name}: PINNED py expected {_PINNED_DIVERGENCES[name]!r} "
                    f"got {pline!r} (java {jline!r})"
                )
            continue
        if pline != jline:
            mismatches.append(f"{name}:\n  py   {pline}\n  java {jline}")

    assert not mismatches, "additional-actions getter divergence(s):\n" + "\n".join(
        mismatches
    )
