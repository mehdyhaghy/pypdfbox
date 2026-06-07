"""Differential fuzz audit for optional-content (OCG / OCMD / OCProperties)
parsing leniency vs Apache PDFBox 3.0.7 (wave 1514, agent C).

Complements the well-formed OCG/OCMD parity suites (round-trip authoring,
inverted PDFBox-authored read-back) — none of which exercise the MALFORMED
dictionary subset this audit targets:

* ``/OCProperties``: ``/OCGs`` array missing / empty / non-array / non-dict
  members; ``/D`` default config missing / wrong-type; ``/D`` ``/ON`` ``/OFF``
  arrays (membership, unknown refs, wrong types); ``/D`` ``/BaseState``
  (``/ON``/``/OFF``/unknown); OCG ``/Name`` missing / wrong-type; ``/Intent``
  name-vs-array-vs-missing.
* ``/OCMD``: ``/OCGs`` single-vs-array-vs-missing; ``/P`` visibility policy
  (``/AnyOn``/``/AllOn``/``/AnyOff``/``/AllOff``/unknown/missing); ``/VE``
  visibility expression (nested array, malformed).

Both sides are driven on the SAME bytes: the corpus builder writes one PDF per
case. ``ocp_<name>.pdf`` carries the fuzzed ``/OCProperties`` on its catalog;
``ocmd_<name>.pdf`` carries the fuzzed OCMD as the first page's resource
``/Properties /MC1``. The Java probe
(``oracle/probes/OptionalContentFuzzProbe.java``) loads each file and projects
a stable framed line through ``PDOptionalContentProperties`` /
``PDOptionalContentMembershipDictionary`` accessors; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE ocp_<name>  groups=<names|0|null|ERR> baseState=<ON|OFF|UNCHANGED|null|ERR>
        ocgState=<n/a|states|null|ERR>
    CASE ocmd_<name> ocmd=<class|null|ERR> ocgs=<count|n/a|null|ERR>
        policy=<name|n/a|null|ERR> ve=<present|absent|n/a|null|ERR>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/graphics/optionalcontent/``; a defensible divergence is
pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------- helpers

_N = COSName.get_pdf_name


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _ocg(name: str | None = None, **extra: COSBase) -> COSDictionary:
    """A minimal /Type /OCG dictionary, optionally with a /Name."""
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    if name is not None:
        d.set_string(_N("Name"), name)
    for k, v in extra.items():
        d.set_item(_N(k), v)
    return d


# --------------------------------------------------------------------- corpus
#
# Each corpus entry is a fully-built COSDictionary:
#   - "ocp_*"  -> the /OCProperties dict to install on the catalog
#   - "ocmd_*" -> the /OCMD dict to install as page resource /Properties/MC1


def _ocp_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def add(name: str, d: COSDictionary) -> None:
        cases[f"ocp_{name}"] = d

    # --- /OCGs array shape corners ----------------------------------------
    d = COSDictionary()
    add("ocgs_missing", d)

    d = COSDictionary()
    d.set_item(_N("OCGs"), COSArray())
    add("ocgs_empty", d)

    d = COSDictionary()
    d.set_item(_N("OCGs"), COSString("not-an-array"))
    add("ocgs_not_array", d)

    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(COSString("x"), COSInteger(7), COSName.get_pdf_name("y")))
    add("ocgs_all_non_dict", d)

    d = COSDictionary()
    d.set_item(
        _N("OCGs"),
        _arr(_ocg("Alpha"), COSInteger(7), _ocg("Beta")),
    )
    add("ocgs_mixed_dict_and_scalar", d)

    # --- OCG /Name corners -------------------------------------------------
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(_ocg(None)))
    add("ocg_name_missing", d)

    d = COSDictionary()
    g = _ocg(None)
    g.set_item(_N("Name"), _N("NameIsAName"))  # /Name as a name, not a string
    d.set_item(_N("OCGs"), _arr(g))
    add("ocg_name_is_cosname", d)

    d = COSDictionary()
    g = _ocg(None)
    g.set_item(_N("Name"), COSInteger(42))  # /Name as an int
    d.set_item(_N("OCGs"), _arr(g))
    add("ocg_name_is_int", d)

    # --- OCG /Intent corners ----------------------------------------------
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(_ocg("WithIntentName", Intent=_N("View"))))
    add("ocg_intent_name", d)

    d = COSDictionary()
    d.set_item(
        _N("OCGs"),
        _arr(_ocg("WithIntentArr", Intent=_arr(_N("View"), _N("Design")))),
    )
    add("ocg_intent_array", d)

    d = COSDictionary()
    d.set_item(
        _N("OCGs"),
        _arr(_ocg("WithIntentBad", Intent=COSInteger(3))),
    )
    add("ocg_intent_wrong_type", d)

    # --- /D default config corners ----------------------------------------
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(_ocg("Solo")))
    # No /D at all.
    add("d_missing", d)

    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(_ocg("Solo")))
    d.set_item(_N("D"), COSString("not-a-dict"))
    add("d_not_dict", d)

    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(_ocg("Solo")))
    d.set_item(_N("D"), COSArray())
    add("d_is_array", d)

    # --- /D /BaseState corners --------------------------------------------
    g1 = _ocg("G1")
    g2 = _ocg("G2")
    config = COSDictionary()
    config.set_item(_N("BaseState"), _N("OFF"))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1, g2))
    d.set_item(_N("D"), config)
    add("basestate_off", d)

    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("BaseState"), _N("ON"))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("basestate_on", d)

    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("BaseState"), _N("Unchanged"))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("basestate_unchanged", d)

    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("BaseState"), _N("Bogus"))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("basestate_unknown", d)

    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("BaseState"), COSString("ON"))  # string, not name
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("basestate_string", d)

    # --- /D /ON /OFF membership corners -----------------------------------
    g1 = _ocg("OnGroup")
    g2 = _ocg("OffGroup")
    g3 = _ocg("Neutral")
    config = COSDictionary()
    config.set_item(_N("ON"), _arr(g1))
    config.set_item(_N("OFF"), _arr(g2))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1, g2, g3))
    d.set_item(_N("D"), config)
    add("on_off_membership", d)

    # /OFF lists a group not in /OCGs (unknown ref)
    g1 = _ocg("Known")
    unknown = _ocg("UnknownNotInOCGs")
    config = COSDictionary()
    config.set_item(_N("OFF"), _arr(unknown))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("off_unknown_ref", d)

    # /ON not an array
    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("ON"), COSString("nope"))
    config.set_item(_N("OFF"), COSInteger(5))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("on_off_wrong_type", d)

    # /ON array with non-dict junk entries
    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("ON"), _arr(COSInteger(1), COSString("x")))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("on_array_junk", d)

    # --- /D /Order /RBGroups /Locked malformed ----------------------------
    g1 = _ocg("G1")
    g2 = _ocg("G2")
    config = COSDictionary()
    config.set_item(_N("Order"), COSString("not-array"))
    config.set_item(_N("RBGroups"), COSInteger(9))
    config.set_item(_N("Locked"), COSString("nope"))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1, g2))
    d.set_item(_N("D"), config)
    add("d_aux_arrays_wrong_type", d)

    g1 = _ocg("G1")
    config = COSDictionary()
    config.set_item(_N("Order"), _arr(g1, _arr(COSInteger(3))))
    config.set_item(_N("RBGroups"), _arr(_arr(g1)))
    config.set_item(_N("Locked"), _arr(g1, COSInteger(2)))
    d = COSDictionary()
    d.set_item(_N("OCGs"), _arr(g1))
    d.set_item(_N("D"), config)
    add("d_aux_arrays_nested", d)

    return cases


def _ocmd_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def add(name: str, d: COSDictionary) -> None:
        cases[f"ocmd_{name}"] = d

    def _ocmd(**entries: COSBase) -> COSDictionary:
        d = COSDictionary()
        d.set_item(_N("Type"), _N("OCMD"))
        for k, v in entries.items():
            d.set_item(_N(k), v)
        return d

    # --- /OCGs single vs array vs missing ---------------------------------
    add("ocgs_missing", _ocmd())

    add("ocgs_single_dict", _ocmd(OCGs=_ocg("Single")))

    add("ocgs_array", _ocmd(OCGs=_arr(_ocg("A"), _ocg("B"))))

    add("ocgs_empty_array", _ocmd(OCGs=COSArray()))

    add("ocgs_not_dict_not_array", _ocmd(OCGs=COSString("nope")))

    add(
        "ocgs_array_with_junk",
        _ocmd(OCGs=_arr(_ocg("A"), COSInteger(3), COSString("x"))),
    )

    # /OCGs array containing a non-OCG dict (no /Type /OCG)
    plain = COSDictionary()
    plain.set_string(_N("Name"), "PlainNoType")
    add("ocgs_array_non_ocg_dict", _ocmd(OCGs=_arr(_ocg("A"), plain)))

    # --- /P visibility policy ---------------------------------------------
    add("policy_anyon", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AnyOn")))
    add("policy_allon", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AllOn")))
    add("policy_anyoff", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AnyOff")))
    add("policy_alloff", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AllOff")))
    add("policy_missing", _ocmd(OCGs=_arr(_ocg("A"))))
    add("policy_unknown", _ocmd(OCGs=_arr(_ocg("A")), P=_N("Bogus")))
    add("policy_wrong_type", _ocmd(OCGs=_arr(_ocg("A")), P=COSString("AnyOn")))

    # --- /VE visibility expression ----------------------------------------
    add("ve_absent", _ocmd(OCGs=_arr(_ocg("A"))))

    ocg_a = _ocg("A")
    ve = _arr(_N("And"), ocg_a, _arr(_N("Not"), _ocg("B")))
    add("ve_nested_and_not", _ocmd(OCGs=_arr(ocg_a), VE=ve))

    add("ve_not_array", _ocmd(OCGs=_arr(_ocg("A")), VE=COSString("nope")))

    add(
        "ve_empty_array",
        _ocmd(OCGs=_arr(_ocg("A")), VE=COSArray()),
    )

    add(
        "ve_unknown_operator",
        _ocmd(OCGs=_arr(_ocg("A")), VE=_arr(_N("Xor"), _ocg("A"))),
    )

    add(
        "ve_no_operator",
        _ocmd(OCGs=_arr(_ocg("A")), VE=_arr(_ocg("A"), _ocg("B"))),
    )

    # --- OCMD with no /Type (still routed by PDPropertyList.create?) -------
    no_type = COSDictionary()
    no_type.set_item(_N("OCGs"), _arr(_ocg("A")))
    no_type.set_item(_N("P"), _N("AllOn"))
    cases["ocmd_no_type"] = no_type

    # OCMD with /P as a real number
    add("policy_real", _ocmd(OCGs=_arr(_ocg("A")), P=COSFloat(1.5)))

    # OCMD with /OCGs single dict that is itself an OCMD (nested)
    nested = COSDictionary()
    nested.set_item(_N("Type"), _N("OCMD"))
    nested.set_item(_N("OCGs"), _arr(_ocg("Inner")))
    add("ocgs_single_is_ocmd", _ocmd(OCGs=nested))

    # /VE with a boolean leaf (malformed leaf)
    add(
        "ve_boolean_leaf",
        _ocmd(OCGs=_arr(_ocg("A")), VE=_arr(_N("Or"), COSBoolean.TRUE)),
    )

    return cases


def _build_corpus() -> dict[str, COSDictionary]:
    corpus: dict[str, COSDictionary] = {}
    corpus.update(_ocp_cases())
    corpus.update(_ocmd_cases())
    return corpus


def _write_case_pdf(path: Path, name: str, entry: COSDictionary) -> None:
    """Build a one-page PDF. ``ocp_*`` installs ``entry`` as the catalog's
    ``/OCProperties``; ``ocmd_*`` installs ``entry`` as the first page's
    resource ``/Properties /MC1``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        if name.startswith("ocmd_"):
            resources = COSDictionary()
            props = COSDictionary()
            props.set_item(_N("MC1"), entry)
            resources.set_item(_N("Properties"), props)
            page.set_resources(resources)
        else:  # ocp_*
            catalog = doc.get_document_catalog()
            catalog.get_cos_object().set_item(_N("OCProperties"), entry)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    # pypdfbox raises ValueError for the same argument-validation failures
    # Apache PDFBox signals with IllegalArgumentException (e.g. an unknown
    # /BaseState name routed through BaseState.valueOf).
    if isinstance(exc, ValueError):
        return "IllegalArgumentException"
    return type(exc).__name__


def _ocp_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"groups=ERR:{_java_exc(e)} baseState=ERR ocgState=ERR"
        )
    try:
        catalog = doc.get_document_catalog()
        ocp = catalog.get_oc_properties()
        if ocp is None:
            return prefix + "groups=null baseState=null ocgState=null"
        groups_list = None
        try:
            groups_list = ocp.get_optional_content_groups()
            names = []
            for g in groups_list:
                try:
                    n = g.get_name()
                    names.append("" if n is None else n)
                except Exception as e:  # pragma: no cover - defensive
                    names.append(f"ERR:{_java_exc(e)}")
            groups = "0" if not names else "|".join(names)
        except Exception as e:
            groups = f"ERR:{_java_exc(e)}"
        # Project through get_base_state_enum() — the upstream-faithful
        # accessor that mirrors Java getBaseState() (returns the typed enum,
        # raising on an unknown /BaseState name). The pypdfbox-spelled
        # get_base_state() string variant is intentionally lenient and is NOT
        # the parity surface here.
        try:
            base_state = ocp.get_base_state_enum().name
        except Exception as e:
            base_state = f"ERR:{_java_exc(e)}"
        try:
            if not groups_list:
                ocg_state = "n/a"
            else:
                # Upstream isGroupEnabled internally resolves the base state,
                # so it raises on the same unknown-/BaseState input. Force the
                # base-state resolution first so we mirror that propagation.
                ocp.get_base_state_enum()
                states = [
                    "1" if ocp.is_group_enabled(g) else "0"
                    for g in groups_list
                ]
                ocg_state = "|".join(states)
        except Exception as e:
            ocg_state = f"ERR:{_java_exc(e)}"
        return prefix + (
            f"groups={groups} baseState={base_state} ocgState={ocg_state}"
        )
    finally:
        doc.close()


def _ocmd_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"ocmd=ERR:{_java_exc(e)} ocgs=ERR policy=ERR ve=ERR"
        )
    try:
        page = doc.get_page(0)
        res = page.get_resources()
        prop = res.get_properties(_N("MC1"))
        if prop is None:
            return prefix + "ocmd=null ocgs=null policy=null ve=null"
        if not isinstance(prop, PDOptionalContentMembershipDictionary):
            cls = _java_class_name(prop)
            return prefix + f"ocmd={cls} ocgs=n/a policy=n/a ve=n/a"
        try:
            ocgs = str(len(prop.get_ocgs_property_list()))
        except Exception as e:
            ocgs = f"ERR:{_java_exc(e)}"
        try:
            policy = prop.get_visibility_policy_name().name
        except Exception as e:
            policy = f"ERR:{_java_exc(e)}"
        try:
            ve = "present" if prop.get_visibility_expression() is not None else "absent"
        except Exception as e:
            ve = f"ERR:{_java_exc(e)}"
        cls = _java_class_name(prop)
        return prefix + f"ocmd={cls} ocgs={ocgs} policy={policy} ve={ve}"
    finally:
        doc.close()


def _java_class_name(prop: PDPropertyList) -> str:
    """Map a pypdfbox PDPropertyList wrapper to the Java simple class name the
    probe would report."""
    if isinstance(prop, PDOptionalContentMembershipDictionary):
        return "PDOptionalContentMembershipDictionary"
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentGroup,
    )

    if isinstance(prop, PDOptionalContentGroup):
        return "PDOptionalContentGroup"
    return "PDPropertyList"


def _python_line(case_dir: Path, name: str) -> str:
    if name.startswith("ocmd_"):
        return _ocmd_line(case_dir, name)
    return _ocp_line(case_dir, name)


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_optional_content_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated OCProperties / OCMD dictionary parses (or fails to parse)
    identically on pypdfbox and Apache PDFBox 3.0.7: same group enumeration,
    same /BaseState, same per-group visibility, same OCMD class / OCG count /
    visibility policy / VE presence. Divergences are pinned explicitly in
    ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", name, entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("OptionalContentFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, "optional-content fuzz divergences:\n" + "\n".join(
        mismatches
    )
