"""Differential fuzz audit for optional-content CONFIGURATION metadata vs
Apache PDFBox 3.0.7 (wave 1559, agent E).

Complements the well-formed config read-back (``OcConfigProbe`` /
``test_oc_config_oracle.py``) and the malformed-parse-leniency audit
(``OptionalContentFuzzProbe`` / ``test_optional_content_fuzz_wave1514.py``,
which projected groups / baseState / per-group enabled). Neither exercises the
CONFIGURATION-dict edge subset this audit targets:

* ``/D`` default config: missing / non-dict; ``/Order`` nested arrays, label
  strings, non-OCG refs; ``/RBGroups`` malformed / nested; ``/Locked``;
  ``/BaseState`` ON/OFF/Unchanged/unknown; ``/ListMode``.
* ``/Configs`` alternate configurations: present / absent / non-array; per-entry
  ``/Name`` listing.
* OCG ``/Usage`` ``/View`` ``/Print`` ``/Export`` sub-dicts present / absent /
  wrong-type; ``getRenderState`` for VIEW / PRINT / EXPORT including the Export
  fallback.
* ``getGroupNames`` ordering (incl. addGroup append + name collisions).

Both sides read the SAME bytes: the corpus builder writes one ``<name>.pdf`` per
case with the fuzzed ``/OCProperties`` installed on the catalog. The Java probe
(``oracle/probes/OcConfigFuzzProbe.java``) projects a stable framed line per
case; this module reads the identical files and projects the same grammar
through pypdfbox, then asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> names=<a|b|0|ERR> base=<ON|OFF|UNCHANGED|ERR>
        order=<tokens|none|empty|ERR> rb=<g|g;...|none|ERR>
        locked=<n,...|none|ERR> listmode=<v|absent> configs=<n,...|0|none>
        render=<name:V/P/E|none|ERR>

Java is ground truth: a real divergence is a production fix; a defensible
divergence is pinned in ``_PINNED`` with a matching CHANGES.md row.
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
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (  # noqa: E501
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _ocg(name: str | None = None, **extra: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    if name is not None:
        d.set_string(_N("Name"), name)
    for k, v in extra.items():
        d.set_item(_N(k), v)
    return d


def _usage(**subs: COSDictionary) -> COSDictionary:
    """Build a /Usage dict with View/Print/Export sub-dicts."""
    u = COSDictionary()
    for k, v in subs.items():
        u.set_item(_N(k), v)
    return u


def _state_sub(state_key: str, value: COSBase) -> COSDictionary:
    sub = COSDictionary()
    sub.set_item(_N(state_key), value)
    return sub


def _config(name: str | None = None, **entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    if name is not None:
        d.set_string(_N("Name"), name)
    for k, v in entries.items():
        d.set_item(_N(k), v)
    return d


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def add(name: str, ocgs: COSArray | None, d: COSDictionary | None) -> None:
        ocp = COSDictionary()
        if ocgs is not None:
            ocp.set_item(_N("OCGs"), ocgs)
        if d is not None:
            ocp.set_item(_N("D"), d)
        cases[name] = ocp

    # ---- /D corners ------------------------------------------------------
    add("d_missing", _arr(_ocg("Solo")), None)

    add("d_not_dict_string", _arr(_ocg("Solo")), None)
    cases["d_not_dict_string"].set_item(_N("D"), COSString("nope"))

    add("d_is_array", _arr(_ocg("Solo")), None)
    cases["d_is_array"].set_item(_N("D"), COSArray())

    add("d_empty", _arr(_ocg("Solo")), _config())

    # ---- /BaseState corners ---------------------------------------------
    add("base_on", _arr(_ocg("A")), _config(BaseState=_N("ON")))
    add("base_off", _arr(_ocg("A")), _config(BaseState=_N("OFF")))
    add("base_unchanged", _arr(_ocg("A")), _config(BaseState=_N("Unchanged")))
    add("base_unknown", _arr(_ocg("A")), _config(BaseState=_N("Bogus")))

    # ---- /Order corners --------------------------------------------------
    g1, g2, g3 = _ocg("G1"), _ocg("G2"), _ocg("G3")
    add(
        "order_flat",
        _arr(g1, g2, g3),
        _config(Order=_arr(g1, g2, g3)),
    )

    g1, g2 = _ocg("L1"), _ocg("L2")
    add(
        "order_labeled_nested",
        _arr(g1, g2),
        _config(
            Order=_arr(
                COSString("Group A"),
                _arr(g1, _arr(COSString("Sub"), g2)),
            )
        ),
    )

    g1 = _ocg("OnlyG")
    add(
        "order_with_non_ocg",
        _arr(g1),
        _config(Order=_arr(g1, COSInteger(7), COSName.get_pdf_name("loose"))),
    )

    g1 = _ocg("OG")
    add("order_not_array", _arr(g1), _config(Order=COSString("nope")))

    g1 = _ocg("EG")
    add("order_empty", _arr(g1), _config(Order=COSArray()))

    # ---- /RBGroups corners ----------------------------------------------
    g1, g2, g3 = _ocg("R1"), _ocg("R2"), _ocg("R3")
    add(
        "rb_two_members",
        _arr(g1, g2, g3),
        _config(RBGroups=_arr(_arr(g1, g2))),
    )

    g1, g2, g3, g4 = _ocg("R1"), _ocg("R2"), _ocg("R3"), _ocg("R4")
    add(
        "rb_two_groups",
        _arr(g1, g2, g3, g4),
        _config(RBGroups=_arr(_arr(g1, g2), _arr(g3, g4))),
    )

    g1 = _ocg("RJ")
    add(
        "rb_junk_entries",
        _arr(g1),
        _config(RBGroups=_arr(COSInteger(3), _arr(g1), COSString("x"))),
    )

    g1 = _ocg("RN")
    add("rb_not_array", _arr(g1), _config(RBGroups=COSInteger(9)))

    g1 = _ocg("RM")
    add(
        "rb_member_non_ocg",
        _arr(g1),
        _config(RBGroups=_arr(_arr(g1, COSInteger(2)))),
    )

    # ---- /Locked corners -------------------------------------------------
    g1, g2 = _ocg("LK1"), _ocg("LK2")
    add(
        "locked_two",
        _arr(g1, g2),
        _config(Locked=_arr(g1, g2)),
    )

    g1 = _ocg("LK1")
    add(
        "locked_junk",
        _arr(g1),
        _config(Locked=_arr(g1, COSInteger(5))),
    )

    g1 = _ocg("LK1")
    add("locked_not_array", _arr(g1), _config(Locked=COSString("nope")))

    # ---- /ListMode corners ----------------------------------------------
    g1 = _ocg("LM1")
    add("listmode_allpages", _arr(g1), _config(ListMode=_N("AllPages")))
    g1 = _ocg("LM2")
    add("listmode_visible", _arr(g1), _config(ListMode=_N("VisiblePages")))
    g1 = _ocg("LM3")
    add("listmode_bogus", _arr(g1), _config(ListMode=_N("Weird")))
    g1 = _ocg("LM4")
    add("listmode_absent", _arr(g1), _config())

    # ---- /Configs alternate configs -------------------------------------
    g1 = _ocg("CG")
    add(
        "configs_one",
        _arr(g1),
        _config(BaseState=_N("ON")),
    )
    cases["configs_one"].set_item(
        _N("Configs"), _arr(_config("AltConfig", BaseState=_N("OFF")))
    )

    g1 = _ocg("CG2")
    add("configs_two", _arr(g1), _config())
    cases["configs_two"].set_item(
        _N("Configs"),
        _arr(_config("Beta"), _config("Alpha")),
    )

    g1 = _ocg("CG3")
    add("configs_unnamed", _arr(g1), _config())
    cases["configs_unnamed"].set_item(
        _N("Configs"), _arr(_config(None, BaseState=_N("OFF")))
    )

    g1 = _ocg("CG4")
    add("configs_not_array", _arr(g1), _config())
    cases["configs_not_array"].set_item(_N("Configs"), COSString("nope"))

    g1 = _ocg("CG5")
    add("configs_junk", _arr(g1), _config())
    cases["configs_junk"].set_item(
        _N("Configs"), _arr(COSInteger(1), _config("Gamma"))
    )

    # ---- OCG /Usage render-state corners --------------------------------
    g = _ocg(
        "UViewOn",
        Usage=_usage(View=_state_sub("ViewState", _N("ON"))),
    )
    add("usage_view_on", _arr(g), _config())

    g = _ocg(
        "UPrintOff",
        Usage=_usage(Print=_state_sub("PrintState", _N("OFF"))),
    )
    add("usage_print_off", _arr(g), _config())

    g = _ocg(
        "UExportOn",
        Usage=_usage(Export=_state_sub("ExportState", _N("ON"))),
    )
    add("usage_export_only", _arr(g), _config())

    g = _ocg(
        "UAllThree",
        Usage=_usage(
            View=_state_sub("ViewState", _N("ON")),
            Print=_state_sub("PrintState", _N("OFF")),
            Export=_state_sub("ExportState", _N("ON")),
        ),
    )
    add("usage_all_three", _arr(g), _config())

    # View present but no ViewState -> View slot null, falls back to Export.
    g = _ocg(
        "UViewNoState",
        Usage=_usage(
            View=COSDictionary(),
            Export=_state_sub("ExportState", _N("OFF")),
        ),
    )
    add("usage_view_no_state_export_fallback", _arr(g), _config())

    # /Usage present but empty -> all slots null.
    g = _ocg("UEmpty", Usage=COSDictionary())
    add("usage_empty", _arr(g), _config())

    # No /Usage at all.
    g = _ocg("UNone")
    add("usage_missing", _arr(g), _config())

    # /Usage wrong type (a string) -> treated as no usage.
    g = _ocg("UBadType")
    g.set_item(_N("Usage"), COSString("not-a-dict"))
    add("usage_wrong_type", _arr(g), _config())

    # /View sub-dict wrong type (string) -> View slot null, Export fallback.
    g = _ocg("UViewBad")
    bad_usage = COSDictionary()
    bad_usage.set_item(_N("View"), COSString("nope"))
    bad_usage.set_item(_N("Export"), _state_sub("ExportState", _N("ON")))
    g.set_item(_N("Usage"), bad_usage)
    add("usage_view_wrong_type", _arr(g), _config())

    # ViewState wrong type (string, not name) -> slot null, Export fallback.
    g = _ocg("UViewStateBad")
    vb = COSDictionary()
    vsub = COSDictionary()
    vsub.set_item(_N("ViewState"), COSString("ON"))
    vb.set_item(_N("View"), vsub)
    vb.set_item(_N("Export"), _state_sub("ExportState", _N("OFF")))
    g.set_item(_N("Usage"), vb)
    add("usage_view_state_wrong_type", _arr(g), _config())

    # ---- getGroupNames ordering / collisions ----------------------------
    add(
        "names_order",
        _arr(_ocg("Zebra"), _ocg("Apple"), _ocg("Mango")),
        _config(),
    )

    add(
        "names_collision",
        _arr(_ocg("Dup"), _ocg("Dup"), _ocg("Unique")),
        _config(),
    )

    # One OCG missing /Name -> getGroupNames yields "" for it.
    add(
        "names_one_missing",
        _arr(_ocg("Named"), _ocg(None)),
        _config(),
    )

    return cases


# Cases built dynamically via addGroup (write-side) rather than a static dict.
_ADD_GROUP_CASES = ("addgroup_then_names",)


def _build_addgroup_ocp() -> COSDictionary:
    """Authored via PDOptionalContentProperties.add_group so /OCGs + /D /Order
    are populated by the production write path (mirrors PDFBox addGroup)."""
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("First"))
    props.add_group(PDOptionalContentGroup("Second"))
    props.add_group(PDOptionalContentGroup("First"))  # name collision
    return props.get_cos_object()


def _all_cases() -> dict[str, COSDictionary]:
    cases = _build_corpus()
    cases["addgroup_then_names"] = _build_addgroup_ocp()
    return cases


# ----------------------------------------------------------------- PDF writer


def _write_case_pdf(path: Path, ocp: COSDictionary) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.get_cos_object().set_item(_N("OCProperties"), ocp)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _to_dict(value: COSBase | None) -> COSDictionary | None:
    if isinstance(value, COSObject):
        value = value.get_object()
    return value if isinstance(value, COSDictionary) else None


def _to_array(value: COSBase | None) -> COSArray | None:
    if isinstance(value, COSObject):
        value = value.get_object()
    return value if isinstance(value, COSArray) else None


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    if isinstance(exc, ValueError):
        return "IllegalArgumentException"
    return type(exc).__name__


def _ocg_name(entry: COSBase | None) -> str:
    d = _to_dict(entry)
    if d is None:
        return "?"
    n = d.get_string(_N("Name"))
    return "" if n is None else n


def _flatten_order(order: COSArray, tokens: list[str]) -> None:
    for i in range(order.size()):
        raw = order.get_object(i)
        if isinstance(raw, COSString):
            tokens.append("LABEL:" + raw.get_string())
            continue
        sub = _to_array(raw)
        if sub is not None:
            tokens.append("[")
            _flatten_order(sub, tokens)
            tokens.append("]")
            continue
        tokens.append(_ocg_name(raw))


def _render_slot(group: PDOptionalContentGroup, dest: str) -> str:
    rs = group.get_render_state(dest)
    return "none" if rs is None else rs


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"names=ERR:{_java_exc(e)} base=ERR order=ERR rb=ERR "
            "locked=ERR listmode=ERR configs=ERR render=ERR"
        )
    try:
        catalog = doc.get_document_catalog()
        ocp = catalog.get_oc_properties()
        if ocp is None:
            return prefix + (
                "names=null base=null order=null rb=null locked=null "
                "listmode=null configs=null render=null"
            )

        try:
            arr = ocp.get_group_names()
            # Mirror Java String.join, which renders a null array element as
            # the literal "null" (upstream getGroupNames stores an uncoalesced
            # getString(/Name), so a name-less OCG dict yields a null slot).
            names = (
                "0"
                if not arr
                else "|".join("null" if n is None else n for n in arr)
            )
        except Exception as e:
            names = f"ERR:{_java_exc(e)}"

        try:
            groups = ocp.get_optional_content_groups()
        except Exception:
            groups = None

        try:
            # Project via the upstream-faithful typed enum accessor (mirrors
            # Java getBaseState() returning the BaseState enum, raising on an
            # unknown /BaseState name).
            base = ocp.get_base_state_enum().name
        except Exception as e:
            base = f"ERR:{_java_exc(e)}"

        ocp_dict = ocp.get_cos_object()
        d = _to_dict(ocp_dict.get_dictionary_object(_N("D")))

        try:
            oa = None if d is None else _to_array(
                d.get_dictionary_object(_N("Order"))
            )
            if oa is None:
                order = "none"
            else:
                t: list[str] = []
                _flatten_order(oa, t)
                order = "empty" if not t else " ".join(t)
        except Exception as e:
            order = f"ERR:{_java_exc(e)}"

        try:
            ra = None if d is None else _to_array(
                d.get_dictionary_object(_N("RBGroups"))
            )
            if ra is None:
                rb = "none"
            else:
                rbg: list[str] = []
                for i in range(ra.size()):
                    grp = _to_array(ra.get_object(i))
                    if grp is None:
                        continue
                    m = [_ocg_name(grp.get_object(j)) for j in range(grp.size())]
                    m.sort()
                    rbg.append("|".join(m))
                rbg.sort()
                rb = "none" if not rbg else ";".join(rbg)
        except Exception as e:
            rb = f"ERR:{_java_exc(e)}"

        try:
            la = None if d is None else _to_array(
                d.get_dictionary_object(_N("Locked"))
            )
            if la is None:
                locked = "none"
            else:
                m = [_ocg_name(la.get_object(i)) for i in range(la.size())]
                m.sort()
                locked = "none" if not m else ",".join(m)
        except Exception as e:
            locked = f"ERR:{_java_exc(e)}"

        lm = None if d is None else d.get_dictionary_object(_N("ListMode"))
        listmode = lm.name if isinstance(lm, COSName) else "absent"

        ca = _to_array(ocp_dict.get_dictionary_object(_N("Configs")))
        if ca is None:
            configs = "none"
        else:
            cn: list[str] = []
            for i in range(ca.size()):
                cd = _to_dict(ca.get_object(i))
                if cd is None:
                    continue
                n = cd.get_string(_N("Name"))
                if n is not None:
                    cn.append(n)
            cn.sort()
            configs = "0" if not cn else ",".join(cn)

        try:
            if not groups:
                render = "none"
            else:
                g0 = groups[0]
                gn = g0.get_name()
                render = (
                    ("" if gn is None else gn)
                    + ":"
                    + _render_slot(g0, "View")
                    + "/"
                    + _render_slot(g0, "Print")
                    + "/"
                    + _render_slot(g0, "Export")
                )
        except Exception as e:
            render = f"ERR:{_java_exc(e)}"

        return prefix + (
            f"names={names} base={base} order={order} rb={rb} "
            f"locked={locked} listmode={listmode} configs={configs} "
            f"render={render}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_oc_config_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated /OCProperties configuration projects identically on
    pypdfbox and Apache PDFBox 3.0.7: same getGroupNames ordering, /BaseState,
    flattened /Order, /RBGroups membership, /Locked, /ListMode, /Configs names,
    and first-OCG getRenderState across VIEW/PRINT/EXPORT (incl. Export
    fallback). Divergences are pinned in ``_PINNED`` with a CHANGES.md row."""
    corpus = _all_cases()
    for name, ocp in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", ocp)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("OcConfigFuzzProbe", str(tmp_path))
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

    assert not mismatches, "oc-config fuzz divergences:\n" + "\n".join(
        mismatches
    )
