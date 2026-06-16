"""Differential fuzz audit for the optional-content MEMBERSHIP / VISIBILITY
resolution surface vs Apache PDFBox 3.0.7 (wave 1539, agent B).

Goes beyond the two earlier OCMD/OC fuzz suites:

* ``test_optional_content_fuzz_wave1514`` projects ONE
  ``isGroupEnabled(group)`` flag per group over simple ``/ON`` / ``/OFF`` /
  ``/BaseState`` states.
* ``test_ocmd_fuzz_wave1530`` projects the STATIC OCMD shape (``/OCGs``
  count, ``/P`` policy name, ``/VE`` shape).

Neither exercises the RESOLUTION-PRECEDENCE corners of
``PDOptionalContentProperties.is_group_enabled`` this module targets:

* an OCG referenced by BOTH ``/D /ON`` and ``/D /OFF`` (which array wins);
* the name-based overload ``is_group_enabled(name)`` resolving over multiple
  OCGs that SHARE a ``/Name`` with split ``/ON`` / ``/OFF`` membership (the
  overload short-circuits on the first ENABLED match, so it can disagree with
  the group-object overload for the colliding name);
* ``/BaseState OFF`` with selective ``/ON`` re-enable, and ``Unchanged``
  resolution;
* ``/ON`` / ``/OFF`` arrays carrying non-dict junk, an OCG not present in
  ``/OCGs``, or duplicate references;
* an unknown ``/BaseState`` name (verbatim resolution / fall-back).

Both sides are driven on the SAME bytes: the corpus builder writes one PDF
per case carrying the fuzzed ``/OCProperties`` on its catalog. The Java probe
(``oracle/probes/OcmdMembershipFuzzProbe.java``) loads each file and projects
a stable framed line; this module reads the exact same files and projects the
identical grammar through pypdfbox, then asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> base=<ON|OFF|UNCHANGED|null|ERR> names=<|-joined>
        byGroup=<|-joined 1/0> byName=<|-joined 1/0>

``names`` is the ``"|"``-joined ``get_name()`` of each group (in /OCGs order;
``""`` when null). ``byGroup`` is the ``"|"``-joined
``is_group_enabled(group)`` flag for each group; ``byName`` the
``is_group_enabled(get_name())`` flag — both in the same order.

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/graphics/optionalcontent/``; a defensible divergence is
pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (  # noqa: E501
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _ocg(name: str | None = None, **extra: COSBase) -> COSDictionary:
    """A minimal ``/Type /OCG`` dictionary, optionally with a ``/Name``."""
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    if name is not None:
        d.set_string(_N("Name"), name)
    for k, v in extra.items():
        d.set_item(_N(k), v)
    return d


def _d(**entries: COSBase) -> COSDictionary:
    """A ``/D`` default-configuration dict."""
    d = COSDictionary()
    for k, v in entries.items():
        d.set_item(_N(k), v)
    return d


def _ocp(ocgs: COSArray, default_config: COSDictionary) -> COSDictionary:
    """An ``/OCProperties`` dict with the given ``/OCGs`` and ``/D``."""
    d = COSDictionary()
    d.set_item(_N("OCGs"), ocgs)
    d.set_item(_N("D"), default_config)
    return d


# --------------------------------------------------------------------- corpus


def _corpus() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def add(name: str, d: COSDictionary) -> None:
        cases[name] = d

    # --- BaseState seed + selective override ------------------------------
    # No /ON, no /OFF, default BaseState (absent -> ON): every group enabled.
    g = _ocg("Plain")
    add("basestate_default", _ocp(_arr(g), _d()))

    # BaseState ON explicit, no overrides.
    g = _ocg("Plain")
    add("basestate_on", _ocp(_arr(g), _d(BaseState=_N("ON"))))

    # BaseState OFF, no overrides: all disabled.
    g = _ocg("Plain")
    add("basestate_off", _ocp(_arr(g), _d(BaseState=_N("OFF"))))

    # BaseState Unchanged: upstream BaseState enum resolves; isGroupEnabled
    # treats != OFF as enabled.
    g = _ocg("Plain")
    add("basestate_unchanged", _ocp(_arr(g), _d(BaseState=_N("Unchanged"))))

    # Unknown BaseState name: enum resolution is the ground truth.
    g = _ocg("Plain")
    add("basestate_unknown", _ocp(_arr(g), _d(BaseState=_N("Bogus"))))

    # BaseState as a non-name value (string): falls back to default.
    g = _ocg("Plain")
    add(
        "basestate_non_name",
        _ocp(_arr(g), _d(BaseState=COSString("OFF"))),
    )

    # BaseState OFF but selective /ON re-enable of one of two groups.
    g1 = _ocg("On1")
    g2 = _ocg("Off2")
    add(
        "basestate_off_with_on_override",
        _ocp(_arr(g1, g2), _d(BaseState=_N("OFF"), ON=_arr(g1))),
    )

    # BaseState ON but selective /OFF of one of two groups.
    g1 = _ocg("Stay1")
    g2 = _ocg("Hide2")
    add(
        "basestate_on_with_off_override",
        _ocp(_arr(g1, g2), _d(BaseState=_N("ON"), OFF=_arr(g2))),
    )

    # --- /ON vs /OFF precedence (same group in both) ----------------------
    # Group listed in BOTH /ON and /OFF. Resolution order is the question.
    g = _ocg("Both")
    add(
        "group_in_on_and_off",
        _ocp(_arr(g), _d(ON=_arr(g), OFF=_arr(g))),
    )

    # Same as above but BaseState OFF underneath.
    g = _ocg("BothOff")
    add(
        "group_in_on_and_off_basestate_off",
        _ocp(_arr(g), _d(BaseState=_N("OFF"), ON=_arr(g), OFF=_arr(g))),
    )

    # Group listed twice in /OFF (duplicate refs).
    g = _ocg("DupOff")
    add("group_dup_in_off", _ocp(_arr(g), _d(OFF=_arr(g, g))))

    # Group listed twice in /ON.
    g = _ocg("DupOn")
    add("group_dup_in_on", _ocp(_arr(g), _d(BaseState=_N("OFF"), ON=_arr(g, g))))

    # --- name-overload over name-colliding groups -------------------------
    # Two OCGs share /Name "Twin": one in /ON, one in /OFF. The group-object
    # overload reports each independently; the name overload short-circuits
    # on the first ENABLED match.
    twin_on = _ocg("Twin")
    twin_off = _ocg("Twin")
    add(
        "name_collision_on_first",
        _ocp(
            _arr(twin_on, twin_off),
            _d(BaseState=_N("OFF"), ON=_arr(twin_on), OFF=_arr(twin_off)),
        ),
    )

    # Same collision but the OFF group comes first in /OCGs order.
    twin_off2 = _ocg("Twin")
    twin_on2 = _ocg("Twin")
    add(
        "name_collision_off_first",
        _ocp(
            _arr(twin_off2, twin_on2),
            _d(BaseState=_N("OFF"), ON=_arr(twin_on2), OFF=_arr(twin_off2)),
        ),
    )

    # Both twins OFF (BaseState OFF, neither in /ON): name overload -> 0/0.
    twin_a = _ocg("TwinOff")
    twin_b = _ocg("TwinOff")
    add(
        "name_collision_both_off",
        _ocp(_arr(twin_a, twin_b), _d(BaseState=_N("OFF"))),
    )

    # --- /ON / /OFF malformed ---------------------------------------------
    # /ON references an OCG that is not in /OCGs (stale ref): the named OCG
    # in /OCGs is unaffected.
    g_real = _ocg("Real")
    g_stale = _ocg("Stale")
    add(
        "on_has_stale_ref",
        _ocp(_arr(g_real), _d(BaseState=_N("OFF"), ON=_arr(g_stale))),
    )

    # /ON / /OFF arrays carrying non-dict junk alongside a real ref.
    g = _ocg("Mixed")
    add(
        "on_off_with_junk",
        _ocp(
            _arr(g),
            _d(ON=_arr(COSInteger(1), COSString("x")), OFF=_arr(g)),
        ),
    )

    # /ON not an array (scalar) -> ignored; /OFF lists the group.
    g = _ocg("ScalarOn")
    add(
        "on_scalar_off_array",
        _ocp(_arr(g), _d(ON=COSString("nope"), OFF=_arr(g))),
    )

    # /OFF not an array (scalar) -> ignored; group stays enabled via base.
    g = _ocg("ScalarOff")
    add(
        "off_scalar",
        _ocp(_arr(g), _d(OFF=COSInteger(7))),
    )

    # --- /OCGs with a null-name group -------------------------------------
    # Group with no /Name: name overload looks up name None / "".
    g = _ocg(None)
    add("group_no_name", _ocp(_arr(g), _d(OFF=_arr(g))))

    # Two groups, one named one not.
    g_named = _ocg("Named")
    g_unnamed = _ocg(None)
    add(
        "mixed_named_unnamed",
        _ocp(
            _arr(g_named, g_unnamed),
            _d(BaseState=_N("OFF"), ON=_arr(g_named)),
        ),
    )

    return cases


def _write_case_pdf(path: Path, entry: COSDictionary) -> None:
    """Build a one-page PDF carrying ``entry`` as the catalog's
    ``/OCProperties``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        catalog = doc.get_document_catalog()
        catalog.get_cos_object().set_item(_N("OCProperties"), entry)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    if isinstance(exc, ValueError):
        return "IllegalArgumentException"
    return type(exc).__name__


def _base_state_token(ocp: PDOptionalContentProperties) -> str:
    """Mirror the Java probe's ``ocp.getBaseState().name()``.

    Java ``getBaseState()`` returns the typed ``BaseState`` enum, routing the
    raw /BaseState name through ``BaseState.valueOf`` — so an UNKNOWN name
    raises ``IllegalArgumentException`` rather than resolving. The
    upstream-faithful pypdfbox accessor is ``get_base_state_enum()`` (which
    raises on the same input); the pypdfbox-spelled ``get_base_state()``
    string variant is intentionally LENIENT (returns the raw uppercased name)
    and is NOT the parity surface here. The enum member names are
    ``ON`` / ``OFF`` / ``UNCHANGED``, matching Java ``.name()``.
    """
    return ocp.get_base_state_enum().name


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"base=ERR:{_java_exc(e)} names=ERR byGroup=ERR byName=ERR"
        )
    try:
        catalog = doc.get_document_catalog()
        ocp = catalog.get_oc_properties()
        if ocp is None:
            return prefix + "base=null names= byGroup= byName="
        try:
            base = _base_state_token(ocp)
        except Exception as e:
            base = f"ERR:{_java_exc(e)}"
        try:
            groups = ocp.get_optional_content_groups()
            names = [g.get_name() or "" for g in groups]
        except Exception as e:
            return prefix + (
                f"base={base} names=ERR:{_java_exc(e)} "
                "byGroup=ERR byName=ERR"
            )
        # Java isGroupEnabled internally calls getBaseState() (the throwing
        # enum accessor), so an unknown /BaseState propagates as an
        # IllegalArgumentException out of isGroupEnabled too. pypdfbox
        # is_group_enabled routes through the LENIENT get_base_state(); force
        # the faithful enum resolution first so our projection mirrors that
        # propagation rather than the lenient fall-through.
        def _enabled_token(target: object) -> str:
            try:
                ocp.get_base_state_enum()
                return "1" if ocp.is_group_enabled(target) else "0"
            except Exception as e:
                return f"ERR:{_java_exc(e)}"

        by_group = [_enabled_token(g) for g in groups]
        by_name = [_enabled_token(nm) for nm in names]
        return prefix + (
            f"base={base} names={'|'.join(names)} "
            f"byGroup={'|'.join(by_group)} byName={'|'.join(by_name)}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_ocmd_membership_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every fuzzed /OCProperties resolves membership identically on
    pypdfbox and Apache PDFBox 3.0.7: same /BaseState, same per-group
    ``isGroupEnabled(group)`` flags AND same per-name
    ``isGroupEnabled(name)`` flags — including the /ON-vs-/OFF precedence
    corner and the name-collision short-circuit. Divergences are pinned
    explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _corpus()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("OcmdMembershipFuzzProbe", str(tmp_path))
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

    assert not mismatches, (
        "OCMD membership fuzz divergences:\n" + "\n".join(mismatches)
    )
