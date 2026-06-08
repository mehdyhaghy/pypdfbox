"""Live PDFBox differential fuzz for tagged-PDF tree reads (wave 1518)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureNode,
    PDStructureTreeRoot,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _array(*values) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


def _typed(type_name: str | None) -> COSDictionary:
    out = COSDictionary()
    if type_name is not None:
        out.set_name(_N("Type"), type_name)
    return out


def _kid_tag(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return f"int:{value}"
    if hasattr(value, "get_cos_object"):
        return type(value).__name__
    return f"cos:{type(value).__name__}"


def _value_tag(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return f"str:{value}"
    if isinstance(value, list):
        return "ArrayList"
    return type(value).__name__


def _nullable(value: str | None) -> str:
    return "null" if value is None else value


def _cases() -> list[tuple[str, COSDictionary]]:
    single_int = COSDictionary()
    single_int.set_item(_N("K"), COSInteger.get(7))
    mixed = COSDictionary()
    mixed.set_item(
        _N("K"),
        _array(
            COSInteger.get(1),
            _typed("StructElem"),
            _typed("MCR"),
            _typed("OBJR"),
            _typed("Bogus"),
            COSString("bad"),
        ),
    )
    role_name = COSDictionary()
    rm = COSDictionary()
    rm.set_item(_N("Custom"), _N("P"))
    role_name.set_item(_N("RoleMap"), rm)
    role_string = COSDictionary()
    rm_string = COSDictionary()
    rm_string.set_item(_N("Custom"), COSString("P"))
    role_string.set_item(_N("RoleMap"), rm_string)
    class_dict = COSDictionary()
    cm = COSDictionary()
    cm.set_item(_N("C"), COSDictionary())
    class_dict.set_item(_N("ClassMap"), cm)
    class_array = COSDictionary()
    cm_array = COSDictionary()
    cm_array.set_item(_N("C"), _array(COSDictionary(), COSDictionary()))
    class_array.set_item(_N("ClassMap"), cm_array)
    next_float = COSDictionary()
    next_float.set_item(_N("ParentTreeNextKey"), COSFloat(4.9))
    next_string = COSDictionary()
    next_string.set_item(_N("ParentTreeNextKey"), COSString("4"))
    return [
        ("empty", COSDictionary()),
        ("single_int", single_int),
        ("mixed_kids", mixed),
        ("role_name", role_name),
        ("role_string", role_string),
        ("class_dict", class_dict),
        ("class_array", class_array),
        ("next_float", next_float),
        ("next_string", next_string),
    ]


def _class_value(root: PDStructureTreeRoot):
    class_map = root.get_class_map()
    if class_map is None:
        return None
    raw = class_map.get_cos_object().get_dictionary_object(_N("C"))
    if isinstance(raw, COSArray):
        return []
    if isinstance(raw, COSDictionary):
        from pypdfbox.pdmodel.documentinterchange.logicalstructure import PDAttributeObject

        return PDAttributeObject.create(raw)
    return None


def _py_dump() -> str:
    lines: list[str] = []
    for name, dictionary in _cases():
        try:
            root = PDStructureTreeRoot(dictionary)
            kids = ",".join(_kid_tag(kid) for kid in root.get_kids())
            roles = root.get_role_map()
            lines.append(
                f"CASE {name} type={_nullable(root.get_type())} kids={kids} "
                f"role={_value_tag(roles.get('Custom'))} "
                f"class={_value_tag(_class_value(root))} "
                f"next={root.get_parent_tree_next_key()}"
            )
        except Exception as exc:
            lines.append(f"CASE {name} ERR:{type(exc).__name__}")

    for name, dictionary in [
        ("root", _typed("StructTreeRoot")),
        ("elem", _typed("StructElem")),
        ("missing", _typed(None)),
        ("unknown", _typed("Bogus")),
    ]:
        try:
            node = PDStructureNode.create(dictionary)
            lines.append(f"CREATE {name} class={type(node).__name__}")
        except Exception as exc:
            java_name = (
                "IllegalArgumentException"
                if isinstance(exc, ValueError)
                else type(exc).__name__
            )
            lines.append(f"CREATE {name} ERR:{java_name}")
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_structure_tree_parse_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("StructureTreeParseFuzzProbe")
