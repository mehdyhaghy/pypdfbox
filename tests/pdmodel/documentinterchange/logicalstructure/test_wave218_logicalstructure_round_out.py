"""Wave 218 round-out tests for pdmodel/documentinterchange/logicalstructure.

Targets small remaining gaps on PDStructureTreeRoot and PDObjectReference:

- PDStructureTreeRoot presence predicates: ``has_id_tree`` / ``has_parent_tree``
  / ``has_role_map`` / ``has_class_map`` / ``has_kids``.
- PDStructureTreeRoot ``count_kids`` and ``next_parent_tree_key`` allocator.
- PDObjectReference presence predicates: ``has_obj`` / ``has_pg``.
- PDObjectReference subtype probes: ``is_referenced_form_xobject`` /
  ``is_referenced_image_xobject`` / ``is_referenced_annotation``.
- PDObjectReference public subtype constants (SUBTYPE_ANNOT /
  SUBTYPE_XOBJECT_FORM / SUBTYPE_XOBJECT_IMAGE).
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDObjectReference,
    PDStructureElement,
    PDStructureTreeRoot,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.get_pdf_name("Subtype")
_K = COSName.get_pdf_name("K")
_ID_TREE = COSName.get_pdf_name("IDTree")
_PARENT_TREE = COSName.get_pdf_name("ParentTree")
_PARENT_TREE_NEXT_KEY = COSName.get_pdf_name("ParentTreeNextKey")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_CLASS_MAP = COSName.get_pdf_name("ClassMap")
_OBJ = COSName.get_pdf_name("Obj")
_PG = COSName.get_pdf_name("Pg")


# ---------------------------------------------------------------------------
# PDStructureTreeRoot.has_id_tree / has_parent_tree / has_role_map / has_class_map
# ---------------------------------------------------------------------------


def test_struct_tree_root_has_id_tree_false_when_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.has_id_tree() is False


def test_struct_tree_root_has_id_tree_true_when_present() -> None:
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_ID_TREE, COSDictionary())
    assert root.has_id_tree() is True


def test_struct_tree_root_has_id_tree_false_when_not_a_dict() -> None:
    """Defensive: reject array-shaped /IDTree as upstream guards do."""
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_ID_TREE, COSArray())
    assert root.has_id_tree() is False


def test_struct_tree_root_has_parent_tree_false_when_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.has_parent_tree() is False


def test_struct_tree_root_has_parent_tree_true_when_present() -> None:
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_PARENT_TREE, COSDictionary())
    assert root.has_parent_tree() is True


def test_struct_tree_root_has_role_map_false_when_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.has_role_map() is False


def test_struct_tree_root_has_role_map_true_for_empty_dict() -> None:
    """has_role_map distinguishes absent from present-but-empty."""
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_ROLE_MAP, COSDictionary())
    assert root.has_role_map() is True
    # And get_role_map agrees the entries are empty.
    assert root.get_role_map() == {}


def test_struct_tree_root_has_role_map_true_after_setter() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"MyHeading": "H1"})
    assert root.has_role_map() is True


def test_struct_tree_root_has_class_map_false_when_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.has_class_map() is False


def test_struct_tree_root_has_class_map_true_for_empty_dict() -> None:
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_CLASS_MAP, COSDictionary())
    assert root.has_class_map() is True


# ---------------------------------------------------------------------------
# PDStructureTreeRoot.has_kids / count_kids
# ---------------------------------------------------------------------------


def test_struct_tree_root_has_kids_false_when_k_absent() -> None:
    root = PDStructureTreeRoot()
    assert root.has_kids() is False
    assert root.count_kids() == 0


def test_struct_tree_root_has_kids_false_when_k_empty_array() -> None:
    """An empty /K COSArray reports no kids — common for freshly built roots."""
    root = PDStructureTreeRoot()
    root.get_cos_object().set_item(_K, COSArray())
    assert root.has_kids() is False
    assert root.count_kids() == 0


def test_struct_tree_root_has_kids_true_with_single_kid() -> None:
    root = PDStructureTreeRoot()
    doc = PDStructureElement(structure_type="Document")
    root.append_kid(doc)
    assert root.has_kids() is True
    assert root.count_kids() == 1


def test_struct_tree_root_has_kids_true_with_array_of_kids() -> None:
    root = PDStructureTreeRoot()
    root.append_kid(PDStructureElement(structure_type="Document"))
    root.append_kid(PDStructureElement(structure_type="Document"))
    assert root.has_kids() is True
    assert root.count_kids() == 2


# ---------------------------------------------------------------------------
# PDStructureTreeRoot.next_parent_tree_key allocator
# ---------------------------------------------------------------------------


def test_next_parent_tree_key_starts_at_zero() -> None:
    root = PDStructureTreeRoot()
    assert root.next_parent_tree_key() == 0
    # And the entry now reads 1 (we burned the 0 slot).
    assert root.get_parent_tree_next_key() == 1


def test_next_parent_tree_key_increments_each_call() -> None:
    root = PDStructureTreeRoot()
    keys = [root.next_parent_tree_key() for _ in range(4)]
    assert keys == [0, 1, 2, 3]
    assert root.get_parent_tree_next_key() == 4


def test_next_parent_tree_key_respects_existing_value() -> None:
    """When a doc already has /ParentTreeNextKey set we resume from there."""
    root = PDStructureTreeRoot()
    root.set_parent_tree_next_key(7)
    assert root.next_parent_tree_key() == 7
    assert root.next_parent_tree_key() == 8
    assert root.get_parent_tree_next_key() == 9


# ---------------------------------------------------------------------------
# PDObjectReference subtype constants
# ---------------------------------------------------------------------------


def test_objr_subtype_constants_match_pdf_spec() -> None:
    assert PDObjectReference.SUBTYPE_ANNOT == "Annot"
    assert PDObjectReference.SUBTYPE_XOBJECT_FORM == "Form"
    assert PDObjectReference.SUBTYPE_XOBJECT_IMAGE == "Image"


# ---------------------------------------------------------------------------
# PDObjectReference.has_obj / has_pg
# ---------------------------------------------------------------------------


def test_objr_has_obj_false_when_absent() -> None:
    objr = PDObjectReference()
    assert objr.has_obj() is False


def test_objr_has_obj_true_when_set_to_dict() -> None:
    objr = PDObjectReference()
    objr.get_cos_object().set_item(_OBJ, COSDictionary())
    assert objr.has_obj() is True


def test_objr_has_pg_false_when_absent() -> None:
    objr = PDObjectReference()
    assert objr.has_pg() is False


def test_objr_has_pg_true_when_dict_present() -> None:
    objr = PDObjectReference()
    objr.get_cos_object().set_item(_PG, COSDictionary())
    assert objr.has_pg() is True


def test_objr_has_pg_false_when_not_dict() -> None:
    """A malformed /Pg (e.g. array) is reported as absent for typed callers."""
    objr = PDObjectReference()
    objr.get_cos_object().set_item(_PG, COSArray())
    assert objr.has_pg() is False


# ---------------------------------------------------------------------------
# PDObjectReference.is_referenced_form_xobject / image_xobject / annotation
# ---------------------------------------------------------------------------


def test_is_referenced_form_xobject_true_when_form_stream() -> None:
    objr = PDObjectReference()
    form = COSStream()
    form.set_name(_SUBTYPE, "Form")
    objr.get_cos_object().set_item(_OBJ, form)
    assert objr.is_referenced_form_xobject() is True
    assert objr.is_referenced_image_xobject() is False
    assert objr.is_referenced_annotation() is False


def test_is_referenced_image_xobject_true_when_image_stream() -> None:
    objr = PDObjectReference()
    image = COSStream()
    image.set_name(_SUBTYPE, "Image")
    objr.get_cos_object().set_item(_OBJ, image)
    assert objr.is_referenced_image_xobject() is True
    assert objr.is_referenced_form_xobject() is False
    assert objr.is_referenced_annotation() is False


def test_is_referenced_annotation_true_when_dict_with_type_annot() -> None:
    objr = PDObjectReference()
    annot = COSDictionary()
    annot.set_name(_TYPE, "Annot")
    objr.get_cos_object().set_item(_OBJ, annot)
    assert objr.is_referenced_annotation() is True
    assert objr.is_referenced_form_xobject() is False
    assert objr.is_referenced_image_xobject() is False


def test_is_referenced_annotation_false_when_dict_without_type() -> None:
    """An /Obj dict without /Type /Annot is the narrow-no answer; upstream
    dispatch would still treat it as unknown — see is_referenced_annotation
    docstring."""
    objr = PDObjectReference()
    annot = COSDictionary()
    annot.set_name(_SUBTYPE, "Link")
    objr.get_cos_object().set_item(_OBJ, annot)
    assert objr.is_referenced_annotation() is False


def test_is_referenced_predicates_all_false_when_obj_absent() -> None:
    objr = PDObjectReference()
    assert objr.is_referenced_form_xobject() is False
    assert objr.is_referenced_image_xobject() is False
    assert objr.is_referenced_annotation() is False


def test_is_referenced_form_xobject_false_for_unknown_subtype() -> None:
    objr = PDObjectReference()
    stm = COSStream()
    stm.set_name(_SUBTYPE, "PS")
    objr.get_cos_object().set_item(_OBJ, stm)
    assert objr.is_referenced_form_xobject() is False
    assert objr.is_referenced_image_xobject() is False
    # Streams aren't dicts in the annotation sense either.
    assert objr.is_referenced_annotation() is False


def test_is_referenced_annotation_false_for_stream_with_type_annot() -> None:
    """Streams are /Obj's "this is an XObject" lane; even with /Type /Annot a
    stream isn't a valid annotation per upstream dispatch (matches
    get_referenced_object's stream short-circuit)."""
    objr = PDObjectReference()
    stm = COSStream()
    stm.set_name(_TYPE, "Annot")
    objr.get_cos_object().set_item(_OBJ, stm)
    assert objr.is_referenced_annotation() is False
