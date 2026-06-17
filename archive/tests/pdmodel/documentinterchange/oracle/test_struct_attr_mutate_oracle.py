"""Live PDFBox differential parity for tagged-PDF ``/A`` attribute-object and
``/C`` class-name *mutation + stateful read projection* on
``PDStructureElement``.

Where ``test_struct_element_oracle`` checks a well-formed tagged PDF round
trip, this module isolates the COS-shape effects of
``add_attribute`` / ``remove_attribute`` / ``attribute_changed`` (and the
``/C`` analogues), plus the stateful ``getAttributes()`` / ``getClassNames()``
array parse over hand-built (including malformed) arrays:

* removing the only attribute from ``[dict, 0]`` leaves an orphan ``[0]`` array
  (upstream's ``removeAttribute`` drops the dict but the ``size()==2`` collapse
  never fires at size 1),
* removing one of two leaves the removed entry's orphan revision integer,
* the bare-dict ``/A`` is read at revision **0** (not the element's ``/R``),
* a leading / orphan integer in ``/A`` is dropped, and a double integer after a
  dict makes the *last* revision win,
* ``add_attribute`` onto a bare dict promotes to ``[dict, 0, dict, R]``,
* removing a *missing* attribute from ``[dict, 0]`` still collapses to a bare
  dict (the remove is a no-op but the collapse check fires).

The ``StructAttrMutateProbe`` runs the same fixed mutation sequence in-memory
through Apache PDFBox; pypdfbox reproduces it field-for-field so the comparison
is a genuine differential check of the attribute/class-name maintenance surface,
not a self-comparison.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_layout_attribute_object import (
    PDLayoutAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_list_attribute_object import (
    PDListAttributeObject,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")
_O = COSName.get_pdf_name("O")


def _layout_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_name(_O, "Layout")
    return d


def _list_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_name(_O, "List")
    return d


def _a_shape(elem: PDStructureElement, key: COSName) -> str:
    """Render the COS shape of ``/A`` or ``/C`` exactly like the probe."""
    v = elem.get_cos_object().get_dictionary_object(key)
    if v is None:
        return "null"
    if isinstance(v, COSArray):
        parts: list[str] = []
        for i in range(v.size()):
            item = v.get_object(i)
            if isinstance(item, COSDictionary):
                o = item.get_dictionary_object(_O)
                parts.append("d:" + (o.get_name() if isinstance(o, COSName) else "?"))
            elif isinstance(item, COSInteger):
                parts.append("i" + str(item.int_value()))
            elif isinstance(item, COSName):
                parts.append("n:" + item.get_name())
            else:
                parts.append("?")
        return "[" + ";".join(parts) + "]"
    if isinstance(v, COSDictionary):
        o = v.get_dictionary_object(_O)
        return "dict:" + (o.get_name() if isinstance(o, COSName) else "?")
    if isinstance(v, COSName):
        return "name:" + v.get_name()
    return "?"


def _a_get(elem: PDStructureElement) -> str:
    revs = elem.get_attributes()
    parts: list[str] = []
    for i in range(revs.size()):
        ao = revs.get_object_at(i)
        owner = ao.get_owner() if isinstance(ao, PDAttributeObject) else None
        if owner is None and isinstance(ao, COSDictionary):
            o = ao.get_dictionary_object(_O)
            owner = o.get_name() if isinstance(o, COSName) else None
        parts.append(f"{owner}@{revs.get_revision_number_at(i)}")
    return ",".join(parts) if parts else "-"


def _dump() -> str:
    """pypdfbox reproduction of ``StructAttrMutateProbe`` (in-memory)."""
    lines: list[str] = []

    e1 = PDStructureElement("P")
    a1 = PDLayoutAttributeObject()
    e1.add_attribute(a1)
    e1.remove_attribute(a1)
    lines.append("ASHAPE\tremove_only\t" + _a_shape(e1, _A))

    e2 = PDStructureElement("P")
    layout = PDLayoutAttributeObject()
    lst = PDListAttributeObject()
    e2.add_attribute(layout)
    e2.add_attribute(lst)
    e2.remove_attribute(layout)
    lines.append("ASHAPE\tremove_first_of_two\t" + _a_shape(e2, _A))

    e3 = PDStructureElement("P")
    e3.add_class_name("warm")
    e3.remove_class_name("warm")
    lines.append("CSHAPE\tremove_only\t" + _a_shape(e3, _C))

    e4 = PDStructureElement("P")
    e4.add_class_name("warm")
    e4.add_class_name("cold")
    e4.remove_class_name("warm")
    lines.append("CSHAPE\tremove_first_of_two\t" + _a_shape(e4, _C))

    e5 = PDStructureElement("P")
    e5.set_revision_number(4)
    bare = COSDictionary()
    bare.set_name(_O, "Layout")
    e5.get_cos_object().set_item(_A, bare)
    lines.append("AGET\tbare_dict_rev4\t" + _a_get(e5))

    e6 = PDStructureElement("P")
    arr6 = COSArray()
    arr6.add(COSInteger.get(5))
    arr6.add(_layout_dict())
    e6.get_cos_object().set_item(_A, arr6)
    lines.append("AGET\tleading_int\t" + _a_get(e6))

    e7 = PDStructureElement("P")
    arr7 = COSArray()
    arr7.add(_layout_dict())
    arr7.add(COSInteger.get(1))
    arr7.add(COSInteger.get(2))
    arr7.add(_list_dict())
    e7.get_cos_object().set_item(_A, arr7)
    lines.append("AGET\tdouble_int\t" + _a_get(e7))

    e8 = PDStructureElement("P")
    bare8 = COSDictionary()
    bare8.set_name(_O, "Layout")
    e8.get_cos_object().set_item(_A, bare8)
    e8.set_revision_number(3)
    e8.add_attribute(PDListAttributeObject())
    lines.append("ASHAPE\tadd_onto_bare\t" + _a_shape(e8, _A))

    e9 = PDStructureElement("P")
    present = PDLayoutAttributeObject()
    missing = PDListAttributeObject()
    e9.add_attribute(present)
    e9.remove_attribute(missing)
    lines.append("ASHAPE\tremove_missing\t" + _a_shape(e9, _A))
    e9.remove_attribute(present)
    lines.append("ASHAPE\tremove_missing_then_present\t" + _a_shape(e9, _A))

    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_struct_attr_mutate_matches_pdfbox():
    """Differential: the COS-shape effects of attribute/class-name mutation and
    the stateful getAttributes()/getClassNames() projection equal Java PDFBox's
    over the same fixed in-memory sequence."""
    java = run_probe_text("StructAttrMutateProbe")
    py = _dump()
    assert py == java

    # Pin the expected shape so a regression that happens to agree on both
    # sides still fails.
    expected = (
        "ASHAPE\tremove_only\t[i0]\n"
        "ASHAPE\tremove_first_of_two\t[i0;d:List;i0]\n"
        "CSHAPE\tremove_only\t[i0]\n"
        "CSHAPE\tremove_first_of_two\t[i0;n:cold;i0]\n"
        "AGET\tbare_dict_rev4\tLayout@0\n"
        "AGET\tleading_int\tLayout@0\n"
        "AGET\tdouble_int\tLayout@2,List@0\n"
        "ASHAPE\tadd_onto_bare\t[d:Layout;i0;d:List;i3]\n"
        "ASHAPE\tremove_missing\tdict:Layout\n"
        "ASHAPE\tremove_missing_then_present\tnull\n"
    )
    assert java == expected
    assert py == expected


def test_struct_attr_mutate_pin_without_oracle():
    """Guard (no oracle): pypdfbox alone produces the pinned upstream shape, so
    the differential test above is non-vacuous on machines without the jar."""
    expected = (
        "ASHAPE\tremove_only\t[i0]\n"
        "ASHAPE\tremove_first_of_two\t[i0;d:List;i0]\n"
        "CSHAPE\tremove_only\t[i0]\n"
        "CSHAPE\tremove_first_of_two\t[i0;n:cold;i0]\n"
        "AGET\tbare_dict_rev4\tLayout@0\n"
        "AGET\tleading_int\tLayout@0\n"
        "AGET\tdouble_int\tLayout@2,List@0\n"
        "ASHAPE\tadd_onto_bare\t[d:Layout;i0;d:List;i3]\n"
        "ASHAPE\tremove_missing\tdict:Layout\n"
        "ASHAPE\tremove_missing_then_present\tnull\n"
    )
    assert _dump() == expected
