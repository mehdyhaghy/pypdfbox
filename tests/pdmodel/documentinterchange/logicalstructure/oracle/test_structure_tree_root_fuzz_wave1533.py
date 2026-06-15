"""Live PDFBox differential fuzz for PDStructureTreeRoot accessors (wave 1533).

Angle distinct from wave 1518 (StructureTreeParseFuzzProbe, which bundles kids /
role / class / next together) and the StructParentTree / RoleMapResolve probes:
this exercises each OTHER accessor independently against malformed
/StructTreeRoot dictionaries — getK() shape, getKids() on malformed /K,
getIDTree() / getParentTree() presence on non-dict, getParentTreeNextKey()
default and non-int coercion, getRoleMap() on non-dict, getClassMap() entry
shape (single attr vs array vs wrong-type entry).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure import PDStructureTreeRoot
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _array(*values: COSBase) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


def _typed(type_name: str | None) -> COSDictionary:
    out = COSDictionary()
    if type_name is not None:
        out.set_name(_N("Type"), type_name)
    return out


def _cos_tag(base: COSBase | None) -> str:
    if base is None:
        return "null"
    return type(base).__name__


def _kid_tag(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return f"int:{value}"
    if hasattr(value, "get_cos_object"):
        return type(value).__name__
    return f"cos:{type(value).__name__}"


def _role_tag(root: PDStructureTreeRoot) -> str:
    role_map = root.get_role_map()
    value = role_map.get("Custom")
    # Upstream getRoleMap() converts the COS value to a Java String for both
    # COSName and COSString entries; pypdfbox narrows to a Python str. Project
    # the Java simple-name "String" when the entry resolves to text.
    v = "null" if value is None else "String"
    return f"size={len(role_map)}:Custom={v}"


def _class_tag(root: PDStructureTreeRoot) -> str:
    # Unalignable divergence (CHANGES.md wave 1533): upstream getClassMap()
    # returns a Map<String,Object> and is never null — an absent or non-dict
    # /ClassMap yields an empty Map. pypdfbox returns a typed
    # PDStructureClassMap wrapper, or None for absent/non-dict. We compare the
    # observable ENTRY content (which both expose identically), normalising the
    # empty/absent container to "empty" on both sides.
    class_map = root.get_class_map()
    if class_map is None:
        return "empty"
    raw = class_map.get_cos_object()
    # Mirror upstream getClassMap()'s Map<String,Object>: only entries whose
    # value coerces to an attribute object (single dict) or a list of them
    # (array) survive; a wrong-type entry is silently dropped. Size counts the
    # surviving entries, matching upstream's filtered map.
    surviving: dict[str, str] = {}
    for key, base in raw.entry_set():
        if isinstance(base, COSDictionary):
            surviving[key.get_name()] = "PDDefaultAttributeObject"
        elif isinstance(base, COSArray):
            surviving[key.get_name()] = "List"
    if not surviving:
        return "empty"
    value = surviving.get("C", "absent")
    return f"size={len(surviving)}:{value}"


def _cases() -> list[tuple[str, COSDictionary]]:
    cases: list[tuple[str, COSDictionary]] = []

    # ---- /K shape ----
    cases.append(("k_absent", COSDictionary()))

    k_single = COSDictionary()
    k_single.set_item(_N("K"), _typed("StructElem"))
    cases.append(("k_single_dict", k_single))

    k_array = COSDictionary()
    k_array.set_item(_N("K"), _array(_typed("StructElem"), _typed("StructElem")))
    cases.append(("k_array", k_array))

    k_int = COSDictionary()
    k_int.set_item(_N("K"), COSInteger.get(5))
    cases.append(("k_int", k_int))

    k_string = COSDictionary()
    k_string.set_item(_N("K"), COSString("oops"))
    cases.append(("k_string", k_string))

    k_name = COSDictionary()
    k_name.set_item(_N("K"), _N("oops"))
    cases.append(("k_name", k_name))

    k_empty = COSDictionary()
    k_empty.set_item(_N("K"), COSArray())
    cases.append(("k_empty_array", k_empty))

    k_mixed = COSDictionary()
    k_mixed.set_item(
        _N("K"),
        _array(COSInteger.get(2), COSString("x"), _N("y"), _typed("StructElem")),
    )
    cases.append(("k_array_mixed", k_mixed))

    # ---- /IDTree ----
    cases.append(("idtree_absent", COSDictionary()))

    id_dict = COSDictionary()
    id_dict.set_item(_N("IDTree"), COSDictionary())
    cases.append(("idtree_dict", id_dict))

    id_arr = COSDictionary()
    id_arr.set_item(_N("IDTree"), COSArray())
    cases.append(("idtree_array", id_arr))

    id_int = COSDictionary()
    id_int.set_item(_N("IDTree"), COSInteger.get(1))
    cases.append(("idtree_int", id_int))

    # ---- /ParentTree ----
    pt_dict = COSDictionary()
    pt_dict.set_item(_N("ParentTree"), COSDictionary())
    cases.append(("ptree_dict", pt_dict))

    pt_arr = COSDictionary()
    pt_arr.set_item(_N("ParentTree"), COSArray())
    cases.append(("ptree_array", pt_arr))

    pt_int = COSDictionary()
    pt_int.set_item(_N("ParentTree"), COSInteger.get(0))
    cases.append(("ptree_int", pt_int))

    # ---- /ParentTreeNextKey ----
    cases.append(("next_absent", COSDictionary()))

    next_int = COSDictionary()
    next_int.set_item(_N("ParentTreeNextKey"), COSInteger.get(42))
    cases.append(("next_int", next_int))

    next_float = COSDictionary()
    next_float.set_item(_N("ParentTreeNextKey"), COSFloat(4.9))
    cases.append(("next_float", next_float))

    next_string = COSDictionary()
    next_string.set_item(_N("ParentTreeNextKey"), COSString("4"))
    cases.append(("next_string", next_string))

    next_name = COSDictionary()
    next_name.set_item(_N("ParentTreeNextKey"), _N("x"))
    cases.append(("next_name", next_name))

    next_neg = COSDictionary()
    next_neg.set_item(_N("ParentTreeNextKey"), COSInteger.get(-3))
    cases.append(("next_neg", next_neg))

    # ---- /RoleMap non-dict ----
    role_arr = COSDictionary()
    role_arr.set_item(_N("RoleMap"), COSArray())
    cases.append(("role_array", role_arr))

    role_int = COSDictionary()
    role_int.set_item(_N("RoleMap"), COSInteger.get(1))
    cases.append(("role_int", role_int))

    role_empty = COSDictionary()
    role_empty.set_item(_N("RoleMap"), COSDictionary())
    cases.append(("role_empty", role_empty))

    role_name = COSDictionary()
    rm = COSDictionary()
    rm.set_item(_N("Custom"), _N("P"))
    role_name.set_item(_N("RoleMap"), rm)
    cases.append(("role_name", role_name))

    # ---- /ClassMap shapes ----
    cases.append(("class_absent", COSDictionary()))

    cm_arr_type = COSDictionary()
    cm_arr_type.set_item(_N("ClassMap"), COSArray())
    cases.append(("class_array_type", cm_arr_type))

    cm_int = COSDictionary()
    cm_int.set_item(_N("ClassMap"), COSInteger.get(1))
    cases.append(("class_int", cm_int))

    cm_single = COSDictionary()
    cm1 = COSDictionary()
    cm1.set_item(_N("C"), COSDictionary())
    cm_single.set_item(_N("ClassMap"), cm1)
    cases.append(("class_single_attr", cm_single))

    cm_multi = COSDictionary()
    cm2 = COSDictionary()
    cm2.set_item(_N("C"), _array(COSDictionary(), COSDictionary()))
    cm_multi.set_item(_N("ClassMap"), cm2)
    cases.append(("class_array_attr", cm_multi))

    cm_wrong = COSDictionary()
    cm3 = COSDictionary()
    cm3.set_item(_N("C"), COSString("nope"))
    cm_wrong.set_item(_N("ClassMap"), cm3)
    cases.append(("class_wrong_entry", cm_wrong))

    cm_empty = COSDictionary()
    cm_empty.set_item(_N("ClassMap"), COSDictionary())
    cases.append(("class_empty", cm_empty))

    return cases


def _py_line(name: str, dictionary: COSDictionary) -> str:
    root = PDStructureTreeRoot(dictionary)
    kids = root.get_kids()
    kid_dump = ",".join(_kid_tag(kid) for kid in kids)
    return (
        f"CASE {name}"
        f" k={_cos_tag(root.get_k())}"
        f" kidn={len(kids)}"
        f" kids={kid_dump}"
        f" idtree={'null' if root.get_id_tree() is None else 'present'}"
        f" ptree={'null' if root.get_parent_tree() is None else 'present'}"
        f" next={root.get_parent_tree_next_key()}"
        f" role={_role_tag(root)}"
        f" class={_class_tag(root)}"
    )


def _py_dump() -> str:
    return "".join(_py_line(name, dic) + "\n" for name, dic in _cases())


@requires_oracle
def test_structure_tree_root_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("StructureTreeRootFuzzProbe")
