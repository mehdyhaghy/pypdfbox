from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.interactive.form.pd_field_factory import PDFieldFactory
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FT = COSName.get_pdf_name("FT")
_FF = COSName.get_pdf_name("Ff")
_V = COSName.get_pdf_name("V")
_DV = COSName.get_pdf_name("DV")
_PARENT = COSName.get_pdf_name("Parent")
_P = COSName.get_pdf_name("P")


# ---------- /DV accessors ----------


def test_non_terminal_get_default_value_absent_returns_none() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    assert nt.get_default_value() is None


def test_non_terminal_set_default_value_round_trip() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    value = COSString("hello")
    nt.set_default_value(value)
    assert nt.get_default_value() is value
    # raw entry on the underlying dictionary
    assert nt.get_cos_object().get_dictionary_object(_DV) is value


def test_non_terminal_set_default_value_none_removes_dv() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_default_value(COSString("x"))
    assert nt.get_default_value() is not None
    nt.set_default_value(None)
    assert nt.get_default_value() is None
    assert _DV not in nt.get_cos_object()


# ---------- /FT non-inheritance ----------


def test_non_terminal_field_type_is_local_only() -> None:
    """PDNonTerminalField.get_field_type returns its OWN /FT only.

    Mirrors upstream — non-terminal fields carry /FT as inheritable
    attribute for descendants but the local accessor doesn't walk up.
    """
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_name(_FT, "Tx")
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()  # no /FT of its own
    child = PDNonTerminalField(form, child_dict, parent)
    # Even though parent has /FT=Tx, child's local field type is None
    assert child.get_field_type() is None
    assert parent.get_field_type() == "Tx"


# ---------- /Ff non-inheritance ----------


def test_non_terminal_field_flags_is_local_only() -> None:
    """PDNonTerminalField.get_field_flags returns its OWN /Ff only."""
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_int(_FF, 12345)
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()
    child = PDNonTerminalField(form, child_dict, parent)
    # Inheritance not consulted: child reports 0
    assert child.get_field_flags() == 0
    assert parent.get_field_flags() == 12345


def test_non_terminal_field_flags_returns_local_int() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_int(_FF, 1 << 5)
    nt = PDNonTerminalField(form, d)
    assert nt.get_field_flags() == 32


# ---------- get_widgets() ----------


def test_non_terminal_widgets_empty_no_kids() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    assert nt.get_widgets() == []


def test_non_terminal_widgets_empty_with_kids() -> None:
    """Even when /Kids is populated, non-terminal fields have no widgets."""
    form = PDAcroForm()
    parent_dict = COSDictionary()
    kids = COSArray()
    child_dict = COSDictionary()
    child_dict.set_string(COSName.get_pdf_name("T"), "child")
    kids.add(child_dict)
    parent_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    nt = PDNonTerminalField(form, parent_dict)
    assert nt.get_widgets() == []


# ---------- PDFieldFactory.find_field_type ----------


def test_find_field_type_local() -> None:
    d = COSDictionary()
    d.set_name(_FT, "Btn")
    assert PDFieldFactory.find_field_type(d) == "Btn"


def test_find_field_type_walks_parent() -> None:
    parent = COSDictionary()
    parent.set_name(_FT, "Tx")
    child = COSDictionary()
    child.set_item(_PARENT, parent)
    assert PDFieldFactory.find_field_type(child) == "Tx"


def test_find_field_type_walks_p_when_no_parent() -> None:
    """Falls back to /P if /Parent is absent (per upstream)."""
    p_dict = COSDictionary()
    p_dict.set_name(_FT, "Sig")
    child = COSDictionary()
    child.set_item(_P, p_dict)
    assert PDFieldFactory.find_field_type(child) == "Sig"


def test_find_field_type_missing_returns_none() -> None:
    d = COSDictionary()
    assert PDFieldFactory.find_field_type(d) is None


def test_find_field_type_cycle_detection() -> None:
    """PDFBOX-5896 — a /Parent cycle must not loop forever."""
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(_PARENT, b)
    b.set_item(_PARENT, a)
    # Neither has /FT — must terminate and return None.
    assert PDFieldFactory.find_field_type(a) is None
    assert PDFieldFactory.find_field_type(b) is None


def test_find_field_type_self_cycle_detection() -> None:
    """A dictionary whose /Parent is itself must terminate."""
    a = COSDictionary()
    a.set_item(_PARENT, a)
    assert PDFieldFactory.find_field_type(a) is None


def test_find_field_type_two_level_chain() -> None:
    grand = COSDictionary()
    grand.set_name(_FT, "Ch")
    parent = COSDictionary()
    parent.set_item(_PARENT, grand)
    child = COSDictionary()
    child.set_item(_PARENT, parent)
    assert PDFieldFactory.find_field_type(child) == "Ch"


# ---------- /Ff value type guard ----------


def test_non_terminal_field_flags_non_int_returns_zero() -> None:
    """Defensive — if /Ff somehow holds a non-COSInteger, fall back to 0."""
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_FF, COSString("nope"))
    nt = PDNonTerminalField(form, d)
    assert nt.get_field_flags() == 0


# ---------- regression — /Ff stored as plain int still works ----------


def test_non_terminal_field_flags_via_cos_integer() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_FF, COSInteger.get(99))
    nt = PDNonTerminalField(form, d)
    assert nt.get_field_flags() == 99


# ---------- set_value(str) overload ----------


def test_non_terminal_set_value_string_writes_cos_string() -> None:
    """``set_value(str)`` mirrors upstream ``setValue(String)``: stores
    the value as a ``COSString`` under ``/V``."""
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_value("hello")
    item = nt.get_value()
    assert isinstance(item, COSString)
    assert item.get_string() == "hello"
    # The underlying entry on the dictionary is the same COSString
    assert nt.get_cos_object().get_dictionary_object(_V) is item


def test_non_terminal_set_value_string_round_trips_via_get_value_as_string() -> (
    None
):
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_value("round-trip")
    assert nt.get_value_as_string() == "round-trip"


def test_non_terminal_set_value_empty_string_stores_empty_cos_string() -> None:
    """Empty string is stored as a non-null empty ``COSString`` — distinct
    from passing ``None`` which removes ``/V``."""
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_value("")
    item = nt.get_value()
    assert isinstance(item, COSString)
    assert item.get_string() == ""
    assert _V in nt.get_cos_object()


def test_non_terminal_set_value_str_then_none_removes_v() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_value("present")
    assert nt.get_value() is not None
    nt.set_value(None)
    assert nt.get_value() is None
    assert _V not in nt.get_cos_object()


def test_non_terminal_set_value_cos_base_still_accepted() -> None:
    """The existing ``COSBase`` overload must keep working unchanged."""
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    name = COSName.get_pdf_name("Yes")
    nt.set_value(name)
    assert nt.get_value() is name


# ---------- get_value_as_string extended typing ----------


def test_get_value_as_string_returns_empty_when_v_absent() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    assert nt.get_value_as_string() == ""


def test_get_value_as_string_handles_cos_name() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_V, COSName.get_pdf_name("Yes"))
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == "Yes"


def test_get_value_as_string_handles_cos_integer() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_V, COSInteger.get(42))
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == "42"


def test_get_value_as_string_handles_cos_boolean_true() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_V, COSBoolean.get(True))
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == "True"


def test_get_value_as_string_handles_cos_boolean_false() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_V, COSBoolean.get(False))
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == "False"


def test_get_value_as_string_handles_cos_array_of_strings() -> None:
    """Multi-value choice-style ``/V`` array is comma-joined."""
    form = PDAcroForm()
    d = COSDictionary()
    arr = COSArray()
    arr.add(COSString("a"))
    arr.add(COSString("b"))
    arr.add(COSString("c"))
    d.set_item(_V, arr)
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == "a,b,c"


def test_get_value_as_string_handles_cos_array_of_names() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("X"))
    arr.add(COSName.get_pdf_name("Y"))
    d.set_item(_V, arr)
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == "X,Y"


def test_get_value_as_string_handles_empty_cos_array() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    d.set_item(_V, COSArray())
    nt = PDNonTerminalField(form, d)
    assert nt.get_value_as_string() == ""


def test_get_value_as_string_handles_cos_stream() -> None:
    """COSStream values decode through the filter chain."""
    form = PDAcroForm()
    d = COSDictionary()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"streamed value")
    d.set_item(_V, stream)
    nt = PDNonTerminalField(form, d)
    # COSStream.to_text_string decodes — for a plain ASCII body this
    # round-trips through PDFDocEncoding to the original text.
    assert nt.get_value_as_string() == "streamed value"


# ---------- PDField.from_dictionary helper ----------


def test_from_dictionary_dispatches_text_field() -> None:
    """``PDField.from_dictionary`` mirrors upstream's package-private
    ``PDField.fromDictionary`` and forwards to ``PDFieldFactory.create_field``."""
    form = PDAcroForm()
    d = COSDictionary()
    d.set_name(_FT, "Tx")
    result = PDField.from_dictionary(form, d)
    assert isinstance(result, PDTextField)


def test_from_dictionary_returns_non_terminal_when_kids_present() -> None:
    form = PDAcroForm()
    d = COSDictionary()
    kids = COSArray()
    child = COSDictionary()
    child.set_string(COSName.get_pdf_name("T"), "child")
    kids.add(child)
    d.set_item(COSName.get_pdf_name("Kids"), kids)
    result = PDField.from_dictionary(form, d)
    assert isinstance(result, PDNonTerminalField)


def test_from_dictionary_with_parent_inherits_ft() -> None:
    """When the kid dict has no /FT of its own, the supplied parent
    contributes the inherited /FT."""
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_name(_FT, "Tx")
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()
    result = PDField.from_dictionary(form, child_dict, parent)
    assert isinstance(result, PDTextField)


def test_from_dictionary_propagates_parent_argument() -> None:
    """The supplied parent is wired onto the returned PDField."""
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_name(_FT, "Tx")
    parent = PDNonTerminalField(form, parent_dict)
    child_dict = COSDictionary()
    result = PDField.from_dictionary(form, child_dict, parent)
    assert result is not None
    assert result.get_parent() is parent


# ---------- export_fdf ----------


def _build_non_terminal_with_text_child(
    form: PDAcroForm,
    parent_name: str = "parent",
    child_name: str = "child",
    parent_value: str | None = None,
    child_value: str | None = None,
) -> PDNonTerminalField:
    """Helper — assemble a non-terminal node with one text-field child."""
    parent_dict = COSDictionary()
    parent_dict.set_string(COSName.get_pdf_name("T"), parent_name)
    if parent_value is not None:
        parent_dict.set_string(_V, parent_value)
    kids = COSArray()
    child_dict = COSDictionary()
    child_dict.set_name(_FT, "Tx")
    child_dict.set_string(COSName.get_pdf_name("T"), child_name)
    if child_value is not None:
        child_dict.set_string(_V, child_value)
    kids.add(child_dict)
    parent_dict.set_item(COSName.get_pdf_name("Kids"), kids)
    return PDNonTerminalField(form, parent_dict)


def test_export_fdf_copies_partial_name_and_value() -> None:
    """``export_fdf`` mirrors upstream — copy /T and /V into the FDF node."""
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(
        form, parent_name="container", parent_value="local"
    )
    fdf = nt.export_fdf()
    assert isinstance(fdf, FDFField)
    assert fdf.get_partial_field_name() == "container"
    # /V is stored raw on the FDF dictionary (not via the Object overload)
    v_entry = fdf.get_cos_object().get_dictionary_object(_V)
    assert isinstance(v_entry, COSString)
    assert v_entry.get_string() == "local"


def test_export_fdf_no_value_omits_v() -> None:
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(form)
    fdf = nt.export_fdf()
    assert fdf.get_cos_object().get_dictionary_object(_V) is None


def test_export_fdf_includes_children() -> None:
    """``export_fdf`` recurses — child FDFFields appear under /Kids."""
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(
        form, child_name="leaf", child_value="x"
    )
    fdf = nt.export_fdf()
    fdf_kids = fdf.get_kids()
    assert fdf_kids is not None
    assert len(fdf_kids) == 1
    assert fdf_kids[0].get_partial_field_name() == "leaf"


def test_export_fdf_no_children_emits_empty_kids_array() -> None:
    """Mirrors upstream ``setKids(new ArrayList<>(0))`` — kids is set even
    when there are no children, just empty."""
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.get_cos_object().set_string(COSName.get_pdf_name("T"), "empty")
    fdf = nt.export_fdf()
    fdf_kids = fdf.get_kids()
    # set_kids([]) writes an empty COSArray, so get_kids() returns []
    assert fdf_kids == []


# ---------- import_fdf ----------


def test_import_fdf_applies_local_value() -> None:
    """Local ``/V`` from the FDF root is written onto this node."""
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.get_cos_object().set_string(COSName.get_pdf_name("T"), "container")
    fdf = FDFField()
    fdf.set_partial_field_name("container")
    fdf.set_value("hello")
    nt.import_fdf(fdf)
    v = nt.get_cos_object().get_dictionary_object(_V)
    assert isinstance(v, COSString)
    assert v.get_string() == "hello"


def test_import_fdf_no_kids_returns_early() -> None:
    """When the FDF has no /Kids the call is a no-op past the local fields."""
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(form, child_value="original")
    fdf = FDFField()
    fdf.set_partial_field_name("parent")
    nt.import_fdf(fdf)
    # Child unchanged
    children = nt.get_children()
    assert len(children) == 1
    leaf_v = children[0].get_cos_object().get_dictionary_object(_V)
    assert isinstance(leaf_v, COSString)
    assert leaf_v.get_string() == "original"


def test_import_fdf_recurses_into_matching_child() -> None:
    """An FDF /Kid whose /T matches the pypdfbox child gets recursively
    imported (the child's /V is updated)."""
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(
        form, child_name="leaf", child_value="old"
    )
    fdf = FDFField()
    fdf.set_partial_field_name("parent")
    leaf_fdf = FDFField()
    leaf_fdf.set_partial_field_name("leaf")
    leaf_fdf.set_value("new")
    fdf.set_kids([leaf_fdf])
    nt.import_fdf(fdf)
    children = nt.get_children()
    assert len(children) == 1
    leaf_v = children[0].get_cos_object().get_dictionary_object(_V)
    assert isinstance(leaf_v, COSString)
    assert leaf_v.get_string() == "new"


def test_import_fdf_skips_kid_with_no_partial_name() -> None:
    """Upstream guards on ``fdfName != null`` — FDF kids with no /T are
    silently skipped."""
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(
        form, child_name="leaf", child_value="kept"
    )
    fdf = FDFField()
    fdf.set_partial_field_name("parent")
    anonymous_kid = FDFField()  # no partial name
    anonymous_kid.set_value("ignored")
    fdf.set_kids([anonymous_kid])
    nt.import_fdf(fdf)
    children = nt.get_children()
    leaf_v = children[0].get_cos_object().get_dictionary_object(_V)
    assert isinstance(leaf_v, COSString)
    assert leaf_v.get_string() == "kept"


def test_import_fdf_skips_kid_with_unmatched_name() -> None:
    """An FDF kid whose /T doesn't match any pypdfbox child is silently
    discarded (mirrors upstream's name-based pairing)."""
    form = PDAcroForm()
    nt = _build_non_terminal_with_text_child(
        form, child_name="leaf", child_value="kept"
    )
    fdf = FDFField()
    fdf.set_partial_field_name("parent")
    other_kid = FDFField()
    other_kid.set_partial_field_name("other")
    other_kid.set_value("ignored")
    fdf.set_kids([other_kid])
    nt.import_fdf(fdf)
    children = nt.get_children()
    leaf_v = children[0].get_cos_object().get_dictionary_object(_V)
    assert isinstance(leaf_v, COSString)
    assert leaf_v.get_string() == "kept"


def test_export_then_import_round_trip_preserves_values() -> None:
    """End-to-end round-trip — export_fdf followed by import_fdf into a
    twin tree restores the original values."""
    form = PDAcroForm()
    src = _build_non_terminal_with_text_child(
        form,
        parent_name="root",
        child_name="leaf",
        parent_value="P",
        child_value="C",
    )
    fdf = src.export_fdf()

    dst = _build_non_terminal_with_text_child(
        form,
        parent_name="root",
        child_name="leaf",
        parent_value=None,
        child_value=None,
    )
    dst.import_fdf(fdf)
    assert dst.get_value_as_string() == "P"
    leaf_v = dst.get_children()[0].get_cos_object().get_dictionary_object(_V)
    assert isinstance(leaf_v, COSString)
    assert leaf_v.get_string() == "C"
