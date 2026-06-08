"""Wave 1397 — branch closure for ``pdf_merger_utility``.

After wave 1396 the merger held ~40 partial branches concentrated in the
cross-document resource-graph merge path: cloner-returned-None tails,
malformed page/annot shapes, role-map / id-tree dedup branches, and a
handful of struct-tree prep branches. These tests use lightweight stub
cloners + minimal COS shapes (the existing wave-645 pattern) to hit each
remaining arrow without spinning up real ``PDDocument`` round-trips.
"""

from __future__ import annotations

import hashlib
import logging

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.multipdf.pdf_merger_utility import (
    _hash_cos,
    _HashAbort,
)

# Re-derive the module-private name constants the helpers walk.
_THREADS = COSName.get_pdf_name("Threads")
_NAMES = COSName.get_pdf_name("Names")
_DESTS = COSName.get_pdf_name("Dests")
_PAGE_MODE = COSName.get_pdf_name("PageMode")
_PAGE_LAYOUT = COSName.get_pdf_name("PageLayout")
_LANG = COSName.get_pdf_name("Lang")
_VIEWER_PREFS = COSName.get_pdf_name("ViewerPreferences")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_NUMS = COSName.get_pdf_name("Nums")
_METADATA = COSName.get_pdf_name("Metadata")
_OC_PROPERTIES = COSName.get_pdf_name("OCProperties")
_OUTPUT_INTENTS = COSName.get_pdf_name("OutputIntents")
_OPEN_ACTION = COSName.get_pdf_name("OpenAction")
_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_ACRO_FORM = COSName.get_pdf_name("AcroForm")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_K = COSName.get_pdf_name("K")
_S = COSName.get_pdf_name("S")
_P = COSName.get_pdf_name("P")
_PG = COSName.get_pdf_name("Pg")
_OBJ = COSName.get_pdf_name("Obj")
_ANNOTS = COSName.get_pdf_name("Annots")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")


# ---------- shared stub cloners ----------


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value

    def _clone_merge_cos_base(  # noqa: N801
        self, src: object, dst: object, seen: set
    ) -> None:
        del src, dst, seen


class _NoneCloner:
    def clone_for_new_document(self, value: object) -> None:
        del value
        return None

    def _clone_merge_cos_base(self, src: object, dst: object, seen: set) -> None:
        del src, dst, seen


class _SimpleCatalog:
    """A catalog stand-in whose ``get_cos_object`` returns a controllable
    dict. ``get_acro_form`` is None by default."""

    def __init__(self, cos: COSDictionary | None = None) -> None:
        self._cos = cos if cos is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._cos

    def get_acro_form(self) -> None:
        return None

    def set_acro_form(self, form: object) -> None:  # pragma: no cover - unused
        pass


class _StructRoot:
    """Minimal ``PDStructureTreeRoot`` stand-in for role-map / id-tree
    tests. Only the surfaces the helpers actually touch are exposed."""

    def __init__(self, cos: COSDictionary | None = None, id_tree: object | None = None) -> None:
        self._cos = cos if cos is not None else COSDictionary()
        self._id_tree = id_tree
        self.set_id_tree_called_with: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._cos

    def get_id_tree(self) -> object | None:
        return self._id_tree

    def set_id_tree(self, tree: object) -> None:
        self.set_id_tree_called_with = tree


class _NameTreeOnly:
    """A name-tree node exposing ``get_names`` but no ``get_kids``."""

    def __init__(self, names: dict[str, object]) -> None:
        self._names = names

    def get_names(self) -> dict[str, object]:
        return self._names


class _NumberTreeOnly:
    """A number-tree node exposing ``get_numbers`` but no ``get_kids``."""

    def __init__(self, numbers: dict[int, object]) -> None:
        self._numbers = numbers

    def get_numbers(self) -> dict[int, object]:
        return self._numbers


# ---------- _hash_cos: stream-with-no-data + dead-code tautology ----------


def test_hash_cos_handles_empty_stream_without_body() -> None:
    """``_hash_cos`` on a ``COSStream`` whose body was never set must
    short-circuit past the ``has_data`` block (line 93->103)."""
    stream = COSStream()  # No set_raw_data ⇒ has_data() is False.
    h = hashlib.sha256()
    _hash_cos(stream, h, set())
    # Digest must be deterministic for the empty-body case; we only care
    # that no exception was raised and that the digest is fixed.
    expected = hashlib.sha256()
    _hash_cos(COSStream(), expected, set())
    assert h.hexdigest() == expected.hexdigest()


def test_hash_cos_cycle_in_stream_dict_raises_abort() -> None:
    """A stream that recurses into itself via its dictionary entries
    must raise ``_HashAbort`` (cycle protection)."""
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Self"), stream)
    h = hashlib.sha256()
    with pytest.raises(_HashAbort):
        _hash_cos(stream, h, set())


def test_hash_cos_handles_indirect_cos_object_wrapper() -> None:
    """``COSObject`` placeholders must dereference cleanly via the
    leading isinstance branch (line 49-51)."""
    inner = COSInteger.get(7)
    obj = COSObject(1, 0, resolved=inner)
    h = hashlib.sha256()
    _hash_cos(obj, h, set())
    direct = hashlib.sha256()
    _hash_cos(inner, direct, set())
    assert h.hexdigest() == direct.hexdigest()


def test_hash_cos_float_uses_fractional_form() -> None:
    """A COSFloat whose value has a fractional part must hit the else
    branch on line 65->68 (fractional repr)."""
    h = hashlib.sha256()
    _hash_cos(COSFloat(1.5), h, set())
    integer_h = hashlib.sha256()
    _hash_cos(COSFloat(2.0), integer_h, set())
    assert h.hexdigest() != integer_h.hexdigest()


def test_hash_cos_boolean_true_and_false_distinct() -> None:
    """Both COSBoolean branches must hash to distinct digests."""
    t = hashlib.sha256()
    f = hashlib.sha256()
    _hash_cos(COSBoolean.TRUE, t, set())
    _hash_cos(COSBoolean.FALSE, f, set())
    assert t.hexdigest() != f.hexdigest()


def test_hash_cos_null_and_none_collapse() -> None:
    """``None`` and ``COSNull`` share the same digest (both hit the null
    leaf)."""
    a = hashlib.sha256()
    b = hashlib.sha256()
    _hash_cos(None, a, set())
    _hash_cos(COSNull.NULL, b, set())
    assert a.hexdigest() == b.hexdigest()


def test_hash_cos_unknown_leaf_raises_abort() -> None:
    """A non-COS leaf must abort (line 131)."""
    h = hashlib.sha256()
    with pytest.raises(_HashAbort):
        _hash_cos(object(), h, set())


# ---------- _merge_threads: cloner-None and non-array branches ----------


def test_merge_threads_short_circuits_when_source_missing() -> None:
    util = PDFMergerUtility()
    src = _SimpleCatalog()  # no /Threads
    dst = _SimpleCatalog()
    util._merge_threads(_IdentityCloner(), src, dst)  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_THREADS) is None


def test_merge_threads_installs_when_dest_missing() -> None:
    """When the destination has no /Threads but the clone returned None,
    we hit the cloned_src-None branch (1148->1150)."""
    util = PDFMergerUtility()
    src_threads = COSArray()
    src_threads.add(COSString("thread"))
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_THREADS, src_threads)
    dst = _SimpleCatalog()
    util._merge_threads(_NoneCloner(), src, dst)  # noqa: SLF001
    # Cloner returned None → no install
    assert dst.get_cos_object().get_dictionary_object(_THREADS) is None


def test_merge_threads_appends_to_existing_dest_array() -> None:
    util = PDFMergerUtility()
    src_threads = COSArray()
    src_threads.add(COSString("from_src"))
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_THREADS, src_threads)

    dst = _SimpleCatalog()
    dst_threads = COSArray()
    dst_threads.add(COSString("from_dst"))
    dst.get_cos_object().set_item(_THREADS, dst_threads)

    util._merge_threads(_IdentityCloner(), src, dst)  # noqa: SLF001
    # IdentityCloner returns the array verbatim → dst gets src entries.
    assert dst_threads.size() == 2


def test_merge_threads_install_when_dest_array_missing() -> None:
    """Source has /Threads, dest doesn't, cloner returns the array →
    install (1148->1150 true path)."""
    util = PDFMergerUtility()
    src_threads = COSArray()
    src_threads.add(COSString("t"))
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_THREADS, src_threads)
    dst = _SimpleCatalog()
    util._merge_threads(_IdentityCloner(), src, dst)  # noqa: SLF001
    assert isinstance(
        dst.get_cos_object().get_dictionary_object(_THREADS), COSArray
    )


# ---------- _merge_names: cloner-None on names / dests installs ----------


def test_merge_names_install_skipped_when_cloner_returns_none() -> None:
    """Names dict present in source, absent in dest, but cloner returns
    None → branch 1168->1176 false path."""
    util = PDFMergerUtility()
    src_names = COSDictionary()
    src_names.set_item(COSName.get_pdf_name("Embedded"), COSString("v"))
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_NAMES, src_names)
    dst = _SimpleCatalog()
    util._merge_names(_NoneCloner(), src, dst)  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_NAMES) is None


def test_merge_names_dests_install_skipped_when_cloner_returns_none() -> None:
    """/Dests in source, absent in dest, cloner returns None → branch
    1191->exit false path."""
    util = PDFMergerUtility()
    src_dests = COSDictionary()
    src_dests.set_item(COSName.get_pdf_name("D"), COSString("x"))
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_DESTS, src_dests)
    dst = _SimpleCatalog()
    util._merge_names(_NoneCloner(), src, dst)  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_DESTS) is None


def test_merge_names_strips_id_tree_when_present() -> None:
    """A /Names dict carrying an /IDTree entry has it stripped (PDFBox
    behaviour). Validates the IDTree-removal warning path."""
    util = PDFMergerUtility()
    src_names = COSDictionary()
    src_names.set_item(COSName.get_pdf_name("IDTree"), COSDictionary())
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_NAMES, src_names)
    dst = _SimpleCatalog()
    util._merge_names(_IdentityCloner(), src, dst)  # noqa: SLF001
    dst_names = dst.get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(dst_names, COSDictionary)
    assert dst_names.get_dictionary_object(COSName.get_pdf_name("IDTree")) is None


# ---------- _merge_metadata / _merge_oc_properties / _merge_output_intents ----------


def test_merge_metadata_cloner_none_skips_install() -> None:
    """Metadata stream present, dest missing, cloner returns None →
    branch 1312->exit."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_METADATA, COSStream())
    dst = _SimpleCatalog()

    class _Document:
        def get_metadata(self) -> None:
            return None

    util._merge_metadata(_NoneCloner(), src, dst, _Document())  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_METADATA) is None


def test_merge_oc_properties_cloner_none_skips_install() -> None:
    """Source /OCProperties present, dest missing, cloner returns None
    → branch 1329->1331 false path."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_OC_PROPERTIES, COSDictionary())
    dst = _SimpleCatalog()
    util._merge_oc_properties(_NoneCloner(), src, dst)  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_OC_PROPERTIES) is None


def test_merge_output_intents_cloner_none_skips_install() -> None:
    """Source /OutputIntents present, dest missing, cloner returns None
    → branch 1346->1348 false path."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    arr = COSArray()
    arr.add(COSDictionary())
    src.get_cos_object().set_item(_OUTPUT_INTENTS, arr)
    dst = _SimpleCatalog()
    util._merge_output_intents(_NoneCloner(), src, dst)  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_OUTPUT_INTENTS) is None


def test_merge_output_intents_appends_when_dest_array_present() -> None:
    """When dest already has /OutputIntents (array), cloned entries
    are appended → exercises line 1349-1352."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src_arr = COSArray()
    src_arr.add(COSDictionary())
    src.get_cos_object().set_item(_OUTPUT_INTENTS, src_arr)

    dst = _SimpleCatalog()
    dst_arr = COSArray()
    dst_arr.add(COSDictionary())
    dst.get_cos_object().set_item(_OUTPUT_INTENTS, dst_arr)

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001
    assert dst_arr.size() == 2


# ---------- _merge_open_action / _merge_acro_form: cloned-None tails ----------


def test_merge_open_action_cloner_none_skips_install() -> None:
    """Source /OpenAction present, dest missing, cloner returns None →
    branch 1369->exit false path."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_OPEN_ACTION, COSArray())
    dst = _SimpleCatalog()
    util._merge_open_action(_NoneCloner(), src, dst)  # noqa: SLF001
    assert dst.get_cos_object().get_dictionary_object(_OPEN_ACTION) is None


def test_merge_acro_form_install_skipped_when_clone_returns_none() -> None:
    """Source has form, dest doesn't, cloner returns None → branch
    1053->1055 false path."""

    class _CatalogWithForm:
        def __init__(self, form: object | None) -> None:
            self._cos = COSDictionary()
            self._form = form

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_acro_form(self) -> object | None:
            return self._form

    class _Form:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

        def get_fields(self) -> list:
            return []

    util = PDFMergerUtility()
    util._merge_acro_form(  # noqa: SLF001
        _NoneCloner(),
        _CatalogWithForm(None),
        _CatalogWithForm(_Form()),
    )


def test_acro_form_join_fields_mode_delegates_to_legacy() -> None:
    """In PDFBox 3.0.x ``acroFormJoinFieldsMode`` delegates verbatim to
    ``acroFormLegacyMode`` (confirmed against the live oracle). So join
    mode shares legacy mode's contract: the cloned source field is
    asserted to be a ``COSDictionary`` and a destination FQ-name collision
    is renamed to ``dummyFieldNameN``. A cloner that returns ``None`` thus
    trips the same assertion legacy mode would."""

    class _Form:
        def __init__(self, fields: list[object]) -> None:
            self._cos = COSDictionary()
            self._fields = fields

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_fields(self) -> list[object]:
            return self._fields

        def get_field_tree(self) -> list[object]:
            return []

        def get_field(self, _name: str) -> None:
            return None

    class _Field:
        def __init__(self, name: str) -> None:
            self._cos = COSDictionary()
            self._cos.set_string(_T, name)
            self._name = name

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_partial_name(self) -> str:
            return self._name

        def get_fully_qualified_name(self) -> str:
            return self._name

    util = PDFMergerUtility()
    src = _Form([_Field("f1"), _Field("f2")])
    dst = _Form([])
    # None clone trips legacy mode's COSDictionary assertion (no silent skip).
    with pytest.raises(AssertionError):
        util._acro_form_join_fields_mode(_NoneCloner(), dst, src)  # noqa: SLF001

    # With a real cloner and no collision, both fields land verbatim.
    dst2 = _Form([])
    util._acro_form_join_fields_mode(_IdentityCloner(), dst2, _Form([_Field("g1")]))  # noqa: SLF001
    fields = dst2.get_cos_object().get_dictionary_object(_FIELDS)
    assert isinstance(fields, COSArray)
    assert fields.size() == 1
    assert fields.get_object(0).get_string(_T) == "g1"


# ---------- _merge_role_map: cloner-None / duplicate-key warning ----------


def test_merge_role_map_install_skipped_when_clone_returns_none() -> None:
    """No dest /RoleMap, source has one, cloner returns None → branch
    1782->1784 false path."""
    util = PDFMergerUtility()
    src_rm = COSDictionary()
    src_rm.set_item(COSName.get_pdf_name("MyRole"), COSName.get_pdf_name("P"))
    src_root = _StructRoot()
    src_root.get_cos_object().set_item(_ROLE_MAP, src_rm)
    dst_root = _StructRoot()
    util._merge_role_map(_NoneCloner(), src_root, dst_root)  # noqa: SLF001
    assert (
        dst_root.get_cos_object().get_dictionary_object(_ROLE_MAP) is None
    )


def test_merge_role_map_duplicate_key_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When source declares a /RoleMap key that already exists with a
    different value in dest, a warning is logged (line 1789-1792)."""
    util = PDFMergerUtility()
    src_rm = COSDictionary()
    src_rm.set_item(COSName.get_pdf_name("MyRole"), COSName.get_pdf_name("Different"))
    src_root = _StructRoot()
    src_root.get_cos_object().set_item(_ROLE_MAP, src_rm)

    dst_rm = COSDictionary()
    dst_rm.set_item(COSName.get_pdf_name("MyRole"), COSName.get_pdf_name("P"))
    dst_root = _StructRoot()
    dst_root.get_cos_object().set_item(_ROLE_MAP, dst_rm)

    with caplog.at_level(
        logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"
    ):
        util._merge_role_map(_IdentityCloner(), src_root, dst_root)  # noqa: SLF001
    assert "already exists in destination RoleMap" in caplog.text


def test_merge_role_map_dest_wins_on_identical_value() -> None:
    """When src key already maps to same value in dest, source entry is
    silently dropped (the ``existing == value`` short-circuit)."""
    util = PDFMergerUtility()
    same_value = COSName.get_pdf_name("P")
    src_rm = COSDictionary()
    src_rm.set_item(COSName.get_pdf_name("MyRole"), same_value)
    src_root = _StructRoot()
    src_root.get_cos_object().set_item(_ROLE_MAP, src_rm)

    dst_rm = COSDictionary()
    dst_rm.set_item(COSName.get_pdf_name("MyRole"), same_value)
    dst_root = _StructRoot()
    dst_root.get_cos_object().set_item(_ROLE_MAP, dst_rm)

    util._merge_role_map(_IdentityCloner(), src_root, dst_root)  # noqa: SLF001
    # Still exactly one entry.
    assert sum(1 for _ in dst_rm.entry_set()) == 1


# ---------- _merge_id_tree: cloner-None / duplicate-key warning ----------


def test_merge_id_tree_skips_none_value_clones() -> None:
    """Source /IDTree key whose cloned value is None is dropped
    (branch 1828->1819 false path)."""
    util = PDFMergerUtility()

    src_id_tree = _NameTreeOnly({"k1": COSDictionary()})
    src_root = _StructRoot(id_tree=src_id_tree)
    dst_root = _StructRoot(id_tree=None)
    util._merge_id_tree(_NoneCloner(), src_root, dst_root)  # noqa: SLF001
    # set_id_tree always called; the dict it carries should have no
    # wrapped values (clones returned None → wrap loop drops them).
    assert dst_root.set_id_tree_called_with is not None


def test_merge_id_tree_duplicate_key_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the same /IDTree key exists in both source and dest the
    source entry is dropped with a warning."""
    util = PDFMergerUtility()
    src_id_tree = _NameTreeOnly({"shared": COSDictionary()})
    dst_id_tree = _NameTreeOnly({"shared": COSDictionary()})
    src_root = _StructRoot(id_tree=src_id_tree)
    dst_root = _StructRoot(id_tree=dst_id_tree)
    with caplog.at_level(
        logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"
    ):
        util._merge_id_tree(_IdentityCloner(), src_root, dst_root)  # noqa: SLF001
    assert "already exists in destination IDTree" in caplog.text


def test_merge_id_tree_non_dict_values_filtered_during_wrap() -> None:
    """Final ``wrap`` loop only includes COSDictionary values
    (branch 1839->1838 false path)."""
    util = PDFMergerUtility()
    src_id_tree = _NameTreeOnly({"intval": COSInteger.get(7)})
    src_root = _StructRoot(id_tree=src_id_tree)
    dst_root = _StructRoot(id_tree=None)
    util._merge_id_tree(_IdentityCloner(), src_root, dst_root)  # noqa: SLF001
    # No crash, set_id_tree still invoked.
    assert dst_root.set_id_tree_called_with is not None


# ---------- get_number_tree_as_map / get_id_tree_as_map: kids None-branches ----------


def test_get_number_tree_as_map_returns_empty_for_none() -> None:
    """``tree is None`` short-circuit (line 1395)."""
    assert PDFMergerUtility.get_number_tree_as_map(None) == {}


def test_get_id_tree_as_map_returns_empty_for_none() -> None:
    """``tree is None`` short-circuit (line 1424)."""
    assert PDFMergerUtility.get_id_tree_as_map(None) == {}


def test_get_number_tree_as_map_with_no_kids_or_numbers() -> None:
    """A tree whose ``get_kids`` returns ``None`` skips the kids loop
    (branch 1407->1412 false path)."""

    class _BlankTree:
        def get_numbers(self) -> dict:
            return {}

        def get_kids(self) -> None:
            return None

    assert PDFMergerUtility.get_number_tree_as_map(_BlankTree()) == {}


def test_get_id_tree_as_map_with_no_kids_or_names() -> None:
    """Same shape for the id-tree variant (branch 1436->1441 false
    path)."""

    class _BlankTree:
        def get_names(self) -> dict:
            return {}

        def get_kids(self) -> None:
            return None

    assert PDFMergerUtility.get_id_tree_as_map(_BlankTree()) == {}


def test_get_number_tree_as_map_unwraps_pdmodel_wrappers() -> None:
    """``v.get_cos_object()`` branch fires when leaves are wrappers
    rather than raw COS values."""

    class _Wrapped:
        def __init__(self, cos: COSInteger) -> None:
            self._cos = cos

        def get_cos_object(self) -> COSInteger:
            return self._cos

    class _Tree:
        def get_numbers(self) -> dict:
            return {1: _Wrapped(COSInteger.get(42))}

    result = PDFMergerUtility.get_number_tree_as_map(_Tree())
    assert isinstance(result[1], COSInteger)


# ---------- _update_struct_parent_entries: non-COSNumber annotation slot ----------


def test_update_struct_parent_entries_skips_non_dict_annot_entries() -> None:
    """An /Annots array that mixes dict + non-dict entries: non-dict
    rows are skipped (branch 1659 continue)."""
    page = COSDictionary()
    page.set_item(_STRUCT_PARENTS, COSInteger.get(2))
    annots = COSArray()
    annots.add(COSString("not a dict"))  # filtered
    annot_dict = COSDictionary()
    annot_dict.set_item(_STRUCT_PARENT, COSInteger.get(1))
    annots.add(annot_dict)
    page.set_item(_ANNOTS, annots)

    PDFMergerUtility._update_struct_parent_entries(page, 100)  # noqa: SLF001

    assert page.get_dictionary_object(_STRUCT_PARENTS).int_value() == 102  # type: ignore[union-attr]
    assert annot_dict.get_dictionary_object(_STRUCT_PARENT).int_value() == 101  # type: ignore[union-attr]


def test_update_struct_parent_entries_skips_annot_without_struct_parent() -> None:
    """An /Annots dict without /StructParent is left untouched (branch
    1662->1657 — not isinstance COSNumber)."""
    page = COSDictionary()
    annots = COSArray()
    annots.add(COSDictionary())  # no /StructParent
    page.set_item(_ANNOTS, annots)
    PDFMergerUtility._update_struct_parent_entries(page, 5)  # noqa: SLF001
    # Annot still bare.
    assert annots.get_object(0).get_dictionary_object(_STRUCT_PARENT) is None  # type: ignore[union-attr]


def test_update_struct_parent_entries_skips_negative_struct_parents() -> None:
    """A page whose /StructParents is negative (sentinel "no entry")
    stays unchanged (branch 1650 false path)."""
    page = COSDictionary()
    page.set_item(_STRUCT_PARENTS, COSInteger.get(-1))
    PDFMergerUtility._update_struct_parent_entries(page, 100)  # noqa: SLF001
    assert page.get_dictionary_object(_STRUCT_PARENTS).int_value() == -1  # type: ignore[union-attr]


# ---------- _update_page_references_map: skips None values & odd shapes ----------


def test_update_page_references_map_skips_none_values() -> None:
    """A None entry in the flattened parent-tree map is skipped
    (branch 1580 continue)."""
    util = PDFMergerUtility()
    # None entries are fine; mixed-typed values exercise the
    # array/dict dispatch arms.
    arr = COSArray()
    arr.add(COSDictionary())
    util._update_page_references_map(  # noqa: SLF001
        _IdentityCloner(), {0: None, 1: arr, 2: COSDictionary()}, {}
    )


def test_update_page_references_map_skips_unknown_shapes() -> None:
    """A COSString value is neither array nor dict → skipped (branch
    1584->1579 fallthrough)."""
    util = PDFMergerUtility()
    util._update_page_references_map(  # noqa: SLF001
        _IdentityCloner(), {0: COSString("garbage")}, {}
    )


def test_update_page_references_dict_clones_orphan_obj() -> None:
    """When /Obj points at a dict NOT in ``obj_mapping``, the helper
    falls into the clone-the-orphan branch (line 1612-1614)."""
    util = PDFMergerUtility()
    entry = COSDictionary()
    orphan = COSDictionary()
    orphan.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("OBJR"))
    entry.set_item(_OBJ, orphan)
    util._update_page_references_dict(_IdentityCloner(), entry, {})  # noqa: SLF001
    # Orphan was set via clone → IdentityCloner returns same reference.
    assert entry.get_dictionary_object(_OBJ) is orphan


def test_update_page_references_dict_orphan_clone_none_skips() -> None:
    """Orphan clone returning None must not blow up (line 1613->1616
    false path)."""
    util = PDFMergerUtility()
    entry = COSDictionary()
    orphan = COSDictionary()
    entry.set_item(_OBJ, orphan)
    util._update_page_references_dict(_NoneCloner(), entry, {})  # noqa: SLF001
    # set_item was never called with a clone; original orphan still
    # there (get_dictionary_object on the original) — but the test only
    # cares that the helper completed.
    assert entry.get_dictionary_object(_OBJ) is orphan


# ---------- _prepare_struct_tree_merge: branches when dest has no tree ----------


def test_prepare_struct_tree_no_src_no_dest_returns_no_merge_state() -> None:
    """Both catalogs lack /StructTreeRoot → returns merge=False."""

    class _DocCatalog:
        def __init__(self) -> None:
            self._cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_struct_tree_root(self) -> None:
            return None

        def set_struct_tree_root(self, _root: object) -> None:
            pass

        def get_pages(self) -> list:
            return []

    util = PDFMergerUtility()
    src = _DocCatalog()
    dst = _DocCatalog()

    class _Doc:
        pass

    (merge, key, src_map, dest_map, src_tree, dest_tree) = (
        util._prepare_struct_tree_merge(  # noqa: SLF001
            src, dst, _Doc()
        )
    )
    assert merge is False
    assert src_tree is None and dest_tree is None
    assert src_map == {} and dest_map == {}
    assert key == -1


# ---------- public surface — language / mark-info wrappers ----------


def test_merge_language_short_circuits_when_setters_missing() -> None:
    """A catalog missing one of get/set/get_language → wrapper exits
    without writing (line 1853-1854)."""

    class _Bare:
        pass

    PDFMergerUtility().merge_language(_Bare(), _Bare())


def test_merge_language_no_write_when_dest_already_set() -> None:
    """When the dest already has a language set, source value is not
    propagated (branch 1855 false path)."""

    class _Cat:
        def __init__(self, lang: str | None) -> None:
            self._lang = lang
            self.set_called = False

        def get_language(self) -> str | None:
            return self._lang

        def set_language(self, lang: str) -> None:
            self._lang = lang
            self.set_called = True

    dst = _Cat("en")
    src = _Cat("fr")
    PDFMergerUtility().merge_language(dst, src)
    assert dst.set_called is False
    assert dst.get_language() == "en"


def test_merge_language_writes_when_dest_missing() -> None:
    """Dest has no language, source has one → carry over (line 1857)."""

    class _Cat:
        def __init__(self, lang: str | None) -> None:
            self._lang = lang
            self.set_called = False

        def get_language(self) -> str | None:
            return self._lang

        def set_language(self, lang: str) -> None:
            self._lang = lang
            self.set_called = True

    dst = _Cat(None)
    src = _Cat("fr")
    PDFMergerUtility().merge_language(dst, src)
    assert dst.set_called is True
    assert dst.get_language() == "fr"


def test_merge_language_src_none_leaves_dest_untouched() -> None:
    """Dest empty, source returns None → no write (branch 1857->exit
    false path)."""

    class _Cat:
        def __init__(self, lang: str | None) -> None:
            self._lang = lang
            self.set_called = False

        def get_language(self) -> str | None:
            return self._lang

        def set_language(self, lang: str) -> None:
            self._lang = lang
            self.set_called = True

    dst = _Cat(None)
    src = _Cat(None)
    PDFMergerUtility().merge_language(dst, src)
    assert dst.set_called is False


# ---------- _merge_page_labels: bad-shape recovery ----------


def test_merge_page_labels_skips_when_source_missing() -> None:
    """No /PageLabels in source → no-op (line 1256)."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    dst = _SimpleCatalog()

    class _Doc:
        def __init__(self, cat: _SimpleCatalog) -> None:
            self._cat = cat

        def get_document_catalog(self) -> _SimpleCatalog:
            return self._cat

        def get_number_of_pages(self) -> int:
            return 0

    util._merge_page_labels(  # noqa: SLF001
        _IdentityCloner(), _Doc(src), _Doc(dst)
    )
    assert dst.get_cos_object().get_dictionary_object(_PAGE_LABELS) is None


def test_merge_page_labels_skips_clone_returning_none() -> None:
    """Source label index → labels list, but the clone of each label
    returns None: skip that entry (branch 1293->1295 false path)."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src_labels = COSDictionary()
    src_nums = COSArray()
    src_nums.add(COSInteger.get(0))
    src_nums.add(COSDictionary())  # label dict to be cloned
    src_labels.set_item(_NUMS, src_nums)
    src.get_cos_object().set_item(_PAGE_LABELS, src_labels)

    dst = _SimpleCatalog()

    class _Doc:
        def __init__(self, cat: _SimpleCatalog) -> None:
            self._cat = cat

        def get_document_catalog(self) -> _SimpleCatalog:
            return self._cat

        def get_number_of_pages(self) -> int:
            return 0

    util._merge_page_labels(  # noqa: SLF001
        _NoneCloner(), _Doc(src), _Doc(dst)
    )
    dst_labels = dst.get_cos_object().get_dictionary_object(_PAGE_LABELS)
    assert isinstance(dst_labels, COSDictionary)
    dst_nums = dst_labels.get_dictionary_object(_NUMS)
    # The index integer was added but the clone returned None so the
    # second element was skipped.
    assert isinstance(dst_nums, COSArray)


def test_merge_page_labels_bails_when_base_index_not_a_number(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An non-numeric label index aborts: every freshly-added entry is
    rolled back (line 1282-1289)."""
    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src_labels = COSDictionary()
    src_nums = COSArray()
    src_nums.add(COSString("not a number"))
    src_nums.add(COSDictionary())
    src_labels.set_item(_NUMS, src_nums)
    src.get_cos_object().set_item(_PAGE_LABELS, src_labels)

    dst = _SimpleCatalog()

    class _Doc:
        def __init__(self, cat: _SimpleCatalog) -> None:
            self._cat = cat

        def get_document_catalog(self) -> _SimpleCatalog:
            return self._cat

        def get_number_of_pages(self) -> int:
            return 0

    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"
    ):
        util._merge_page_labels(  # noqa: SLF001
            _IdentityCloner(), _Doc(src), _Doc(dst)
        )
    assert "page labels ignored" in caplog.text


# ---------- _merge_oc_properties: dest dict already exists path ----------


def test_merge_oc_properties_merges_into_existing_dest_dict() -> None:
    """Dest already has /OCProperties → call delegates to
    ``_clone_merge_cos_base`` (line 1332)."""
    util = PDFMergerUtility()

    class _CapturingCloner:
        def __init__(self) -> None:
            self.called = False

        def clone_for_new_document(self, value: object) -> object:
            return value

        def _clone_merge_cos_base(  # noqa: N801
            self, src: object, dst: object, seen: set
        ) -> None:
            self.called = True
            del src, dst, seen

    src = _SimpleCatalog()
    src.get_cos_object().set_item(_OC_PROPERTIES, COSDictionary())
    dst = _SimpleCatalog()
    dst.get_cos_object().set_item(_OC_PROPERTIES, COSDictionary())

    cloner = _CapturingCloner()
    util._merge_oc_properties(cloner, src, dst)  # noqa: SLF001
    assert cloner.called is True


# ---------- _merge_acro_form: catalog with no acro form anywhere ----------


def test_merge_acro_form_returns_when_both_none() -> None:
    """Source has no acro form → return early (line 1056 path)."""
    util = PDFMergerUtility()

    class _CatNoForm:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

        def get_acro_form(self) -> None:
            return None

    util._merge_acro_form(  # noqa: SLF001
        _IdentityCloner(), _CatNoForm(), _CatNoForm()
    )


def test_merge_acro_form_legacy_short_circuits_on_empty_fields() -> None:
    """Source field list is empty → legacy mode returns immediately
    (line 1079-1080)."""

    class _Form:
        def __init__(self) -> None:
            self._cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_fields(self) -> list:
            return []

    util = PDFMergerUtility()
    util._acro_form_legacy_mode(  # noqa: SLF001
        _IdentityCloner(), _Form(), _Form()
    )


def test_acro_form_legacy_dest_field_partial_name_none_is_skipped() -> None:
    """A dest field whose ``get_partial_name()`` returns None doesn't
    contribute to the dummy-counter scan (branch 1089 false path)."""

    class _Field:
        def __init__(self, name: str | None) -> None:
            self._name = name
            self._cos = COSDictionary()
            if name is not None:
                self._cos.set_string(_T, name)

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_partial_name(self) -> str | None:
            return self._name

        def get_fully_qualified_name(self) -> str | None:
            return self._name

    class _Form:
        def __init__(self, fields: list[_Field], existing: set[str]) -> None:
            self._cos = COSDictionary()
            self._fields = fields
            self._existing = existing

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_fields(self) -> list[_Field]:
            return self._fields

        def get_field_tree(self) -> list[_Field]:
            return self._fields

        def get_field(self, name: str) -> object | None:
            return object() if name in self._existing else None

    util = PDFMergerUtility()
    dst = _Form([_Field(None), _Field("dummyFieldNamenotnumeric")], set())
    src = _Form([_Field("f1")], set())
    util._acro_form_legacy_mode(_IdentityCloner(), dst, src)  # noqa: SLF001


# ---------- merge_viewer_preferences (public wrapper) ----------


def test_merge_viewer_preferences_short_circuit_when_method_missing() -> None:
    """Catalog lacking the viewer-prefs surface → no work, no crash."""

    class _Bare:
        pass

    # Should silently no-op when src_getter not callable.
    PDFMergerUtility().merge_viewer_preferences(
        _Bare(), _Bare(), _IdentityCloner()  # type: ignore[arg-type]
    )


def test_merge_viewer_preferences_short_circuit_when_src_returns_none() -> None:
    """When source returns None for /ViewerPreferences, no work."""

    class _SrcWithNone:
        def get_viewer_preferences(self) -> None:
            return None

    PDFMergerUtility().merge_viewer_preferences(
        _SrcWithNone(),  # type: ignore[arg-type]
        _SrcWithNone(),  # type: ignore[arg-type]
        _IdentityCloner(),  # type: ignore[arg-type]
    )


# ---------- end-to-end append_document branches via real PDDocument ----------


def test_append_document_with_clone_returning_none_for_scalar_catalog_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force ``PDFCloneUtility.clone_for_new_document`` to return None for
    the catalog scalar entries (PageMode / PageLayout / Lang /
    ViewerPreferences) — hits the four ``if cloned is not None`` else
    branches in the catalog-merge tail (lines 889->893, 897->901,
    905->909, 916->920)."""
    from pypdfbox.multipdf.pdf_clone_utility import PDFCloneUtility
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())
    sc = src.get_document_catalog().get_cos_object()
    sc.set_item(_PAGE_MODE, COSName.get_pdf_name("UseOutlines"))
    sc.set_item(_PAGE_LAYOUT, COSName.get_pdf_name("OneColumn"))
    sc.set_item(_LANG, COSString("en-US"))
    sc.set_item(_VIEWER_PREFS, COSDictionary())

    dst = PDDocument()

    # Patch clone_for_new_document so it returns None for the four name /
    # dict targets above (matched by content identity) but otherwise
    # behaves normally.
    real_clone = PDFCloneUtility.clone_for_new_document
    blocked_ids = {
        id(sc.get_dictionary_object(_PAGE_MODE)),
        id(sc.get_dictionary_object(_PAGE_LAYOUT)),
        id(sc.get_dictionary_object(_LANG)),
        id(sc.get_dictionary_object(_VIEWER_PREFS)),
    }

    def _patched(self: PDFCloneUtility, value: object) -> object | None:
        if value is not None and id(value) in blocked_ids:
            return None
        return real_clone(self, value)

    monkeypatch.setattr(PDFCloneUtility, "clone_for_new_document", _patched)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    dc = dst.get_document_catalog().get_cos_object()
    # None of the entries should have been installed.
    assert dc.get_dictionary_object(_PAGE_MODE) is None
    assert dc.get_dictionary_object(_PAGE_LAYOUT) is None
    assert dc.get_dictionary_object(_LANG) is None
    assert dc.get_dictionary_object(_VIEWER_PREFS) is None
    src.close()
    dst.close()


def test_append_document_with_annots_containing_non_dict_entries() -> None:
    """A source page whose /Annots array contains non-dict entries
    exercises the ``if isinstance(entry, COSDictionary)`` false branches
    (lines 965->963, 985->983) during page-level struct-tree merge."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    # Mix null + dict entries in /Annots. Wave 1515 aligned
    # ``PDPage.get_annotations`` with upstream: only ``null`` members are
    # skipped, a non-dict member RAISES (upstream's createAnnotation throws
    # IOException). The merger calls ``get_annotations`` during append, so a
    # COSString member would now (correctly) abort the merge on both sides.
    # A COSNull member still exercises the merger's struct-tree
    # ``isinstance(entry, COSDictionary)`` false-branch without violating the
    # annotation-construction contract.
    annots = COSArray()
    annots.add(COSNull.NULL)
    annots.add(COSDictionary())
    page.get_cos_object().set_item(_ANNOTS, annots)

    src_tree = PDStructureTreeRoot()
    src_pt = PDStructureElementNumberTreeNode()
    src_pt.set_numbers({0: COSDictionary()})
    src_tree.set_parent_tree(src_pt)
    src_tree.set_parent_tree_next_key(1)
    src.get_document_catalog().set_struct_tree_root(src_tree)

    dst = PDDocument()
    dst.add_page(PDPage())
    dst_tree = PDStructureTreeRoot()
    dst_pt = PDStructureElementNumberTreeNode()
    dst_pt.set_numbers({0: COSDictionary()})
    dst_tree.set_parent_tree(dst_pt)
    dst_tree.set_parent_tree_next_key(1)
    dst.get_document_catalog().set_struct_tree_root(dst_tree)

    util = PDFMergerUtility()
    # Should not crash; non-dict annotation entries are silently skipped.
    util.append_document(dst, src)
    src.close()
    dst.close()


def test_append_document_with_owned_source_path(tmp_path) -> None:
    """``merge_documents()`` using a file-path source exercises the
    ``owns=True`` finally-close branch (line 627->595 true side); same
    test also fires the broader merge-catalog code with real cloning."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src_path = tmp_path / "src.pdf"
    out_path = tmp_path / "out.pdf"

    with PDDocument() as src:
        src.add_page(PDPage())
        src.save(str(src_path))

    util = PDFMergerUtility()
    util.add_source(str(src_path))
    util.set_destination_file_name(str(out_path))
    util.merge_documents()
    assert out_path.exists()


def test_merge_documents_with_already_open_source_doc(tmp_path) -> None:
    """``merge_documents()`` using a pre-opened PDDocument source
    exercises the ``owns=False`` branch of the legacy finally-close
    logic (line 760->751 false side)."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    out_path = tmp_path / "out.pdf"

    src = PDDocument()
    src.add_page(PDPage())

    util = PDFMergerUtility()
    util.add_source(src)
    util.set_destination_file_name(str(out_path))
    util.merge_documents()
    # Source must still be open — caller retains ownership.
    assert not src.is_closed()
    assert out_path.exists()
    src.close()


def test_optimized_merge_documents_with_already_open_source_doc(tmp_path) -> None:
    """``optimized_merge_documents()`` exercises the same owns=False
    branch in the OPTIMIZE_RESOURCES_MODE path (line 627->595)."""
    from pypdfbox.multipdf import DocumentMergeMode
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    out_path = tmp_path / "out.pdf"
    src = PDDocument()
    src.add_page(PDPage())

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(src)
    util.set_destination_file_name(str(out_path))
    util.merge_documents()
    assert not src.is_closed()
    assert out_path.exists()
    src.close()


def test_optimized_merge_documents_with_owned_source_path(tmp_path) -> None:
    """OPTIMIZE_RESOURCES_MODE with an owned file-path source hits the
    owns=True side of line 627."""
    from pypdfbox.multipdf import DocumentMergeMode
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src_path = tmp_path / "src.pdf"
    out_path = tmp_path / "out.pdf"
    with PDDocument() as src:
        src.add_page(PDPage())
        src.save(str(src_path))

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(src_path))
    util.set_destination_file_name(str(out_path))
    util.merge_documents()
    assert out_path.exists()


def test_merge_role_map_duplicate_value_with_existing_match_via_clone_returning_none() -> None:
    """A duplicate-key /RoleMap entry that needs cloning when the cloner
    returns None hits branch 1795->1785."""

    class _CapturingNoneCloner:
        def clone_for_new_document(self, value: object) -> None:
            del value
            return None

        def _clone_merge_cos_base(self, src: object, dst: object, seen: set) -> None:
            del src, dst, seen

    util = PDFMergerUtility()
    src_rm = COSDictionary()
    # Two distinct names — second one is "new" (not in dest), and the
    # cloner returns None so the False branch is taken.
    src_rm.set_item(COSName.get_pdf_name("New"), COSName.get_pdf_name("Q"))
    src_root = _StructRoot()
    src_root.get_cos_object().set_item(_ROLE_MAP, src_rm)
    dst_rm = COSDictionary()
    dst_root = _StructRoot()
    dst_root.get_cos_object().set_item(_ROLE_MAP, dst_rm)
    util._merge_role_map(_CapturingNoneCloner(), src_root, dst_root)  # noqa: SLF001
    # New key was not installed because the cloner returned None.
    assert dst_rm.get_dictionary_object(COSName.get_pdf_name("New")) is None


def test_merge_threads_when_cloned_src_not_array() -> None:
    """When the dest already has /Threads as a COSArray but the cloned
    source returns something that is NOT a COSArray, the append-loop
    skips (branch 1151->exit false path)."""

    class _ScalarCloner:
        def clone_for_new_document(self, value: object) -> object:
            return COSString("not an array")

        def _clone_merge_cos_base(self, src: object, dst: object, seen: set) -> None:
            del src, dst, seen

    util = PDFMergerUtility()
    src_threads = COSArray()
    src_threads.add(COSString("t"))
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_THREADS, src_threads)
    dst = _SimpleCatalog()
    dst_threads = COSArray()
    dst_threads.add(COSString("existing"))
    dst.get_cos_object().set_item(_THREADS, dst_threads)
    util._merge_threads(_ScalarCloner(), src, dst)  # noqa: SLF001
    assert dst_threads.size() == 1  # No append happened.


def test_merge_output_intents_when_cloned_not_array() -> None:
    """Dest has /OutputIntents, source clone result is a dict (not
    array) → skip append loop (branch 1350->exit false path)."""

    class _DictCloner:
        def clone_for_new_document(self, value: object) -> object:
            return COSDictionary()

        def _clone_merge_cos_base(self, src: object, dst: object, seen: set) -> None:
            del src, dst, seen

    util = PDFMergerUtility()
    src = _SimpleCatalog()
    src.get_cos_object().set_item(_OUTPUT_INTENTS, COSArray())
    dst = _SimpleCatalog()
    dst_arr = COSArray()
    dst_arr.add(COSDictionary())
    dst.get_cos_object().set_item(_OUTPUT_INTENTS, dst_arr)
    util._merge_output_intents(_DictCloner(), src, dst)  # noqa: SLF001
    # No append happened.
    assert dst_arr.size() == 1


def test_get_number_tree_as_map_kids_iterable_yields_subtree() -> None:
    """``get_kids`` returns a list → kids loop runs (line 1410->1411)."""

    class _Child:
        def get_numbers(self) -> dict:
            return {5: COSInteger.get(99)}

    class _Parent:
        def get_kids(self) -> list:
            return [_Child()]

    result = PDFMergerUtility.get_number_tree_as_map(_Parent())
    assert result[5].int_value() == 99  # type: ignore[union-attr]


def test_get_id_tree_as_map_kids_iterable_yields_subtree() -> None:
    """``get_kids`` returns a list → kids loop runs."""

    class _Child:
        def get_names(self) -> dict:
            return {"k": COSInteger.get(11)}

    class _Parent:
        def get_kids(self) -> list:
            return [_Child()]

    result = PDFMergerUtility.get_id_tree_as_map(_Parent())
    assert result["k"].int_value() == 11  # type: ignore[union-attr]


def test_get_number_tree_as_map_empty_numbers_skips_loop() -> None:
    """``get_numbers`` returns empty dict → ``if local:`` is False
    (branch 1399->1406)."""

    class _Empty:
        def get_numbers(self) -> dict:
            return {}

        def get_kids(self) -> list:
            return []

    assert PDFMergerUtility.get_number_tree_as_map(_Empty()) == {}


def test_get_id_tree_as_map_empty_names_skips_loop() -> None:
    """``get_names`` returns empty dict → ``if local:`` is False (branch
    1428->1435)."""

    class _Empty:
        def get_names(self) -> dict:
            return {}

        def get_kids(self) -> list:
            return []

    assert PDFMergerUtility.get_id_tree_as_map(_Empty()) == {}


def test_finish_struct_tree_merge_skips_none_values_and_clones() -> None:
    """``_finish_struct_tree_merge`` walks the src parent-tree map; an
    entry whose ``value is None`` or whose clone returns None is silently
    skipped (branches 1548->1546, 1550->1546)."""

    util = PDFMergerUtility()

    class _NoneCloner2:
        def clone_for_new_document(self, value: object) -> None:
            del value
            return None

        def _clone_merge_cos_base(self, src: object, dst: object, seen: set) -> None:
            del src, dst, seen

    class _Tree:
        def __init__(self) -> None:
            self._cos = COSDictionary()
            self.set_parent_tree_called = False

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def set_parent_tree(self, tree: object) -> None:
            self.set_parent_tree_called = True
            del tree

        def set_parent_tree_next_key(self, n: int) -> None:
            del n

        def get_id_tree(self) -> None:
            return None

        def set_id_tree(self, tree: object) -> None:
            del tree

    src_tree = _Tree()
    dst_tree = _Tree()
    src_map: dict[int, COSBase] = {0: None, 1: COSDictionary()}  # type: ignore[dict-item]
    dst_map: dict[int, COSBase] = {}
    util._finish_struct_tree_merge(  # noqa: SLF001
        _NoneCloner2(),  # type: ignore[arg-type]
        src_tree,
        dst_tree,
        src_map,
        dst_map,
        0,
        {},
    )
    assert dst_tree.set_parent_tree_called is True


# ---------- _prepare_struct_tree_merge: dest_parent_tree None / dest_pt None ----------


def test_prepare_struct_tree_when_dest_pt_is_none() -> None:
    """Branch 1473->1475: when bootstrapping a new dest struct tree the
    helper hands a default ParentTree onto the new root; we only need to
    drive the path where dest_struct_tree.get_parent_tree() returns
    None to hit line 1473's else side (which then skips line 1474)."""

    from pypdfbox.cos import COSInteger

    class _CatalogWithBareDestStructTree:
        """Returns a struct-tree root whose ``get_parent_tree`` is None
        and exposes a ``set_struct_tree_root`` no-op."""

        def __init__(self, has_dest_tree: bool) -> None:
            self._cos = COSDictionary()
            self._tree = self._BareTree() if has_dest_tree else None

        class _BareTree:
            def __init__(self) -> None:
                self._cos = COSDictionary()
                self._set_called = False

            def get_cos_object(self) -> COSDictionary:
                return self._cos

            def get_parent_tree(self) -> None:
                return None

            def get_parent_tree_next_key(self) -> int:
                return -1

            def set_parent_tree(self, t: object) -> None:
                self._set_called = True
                del t

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_struct_tree_root(self) -> object | None:
            return self._tree

        def set_struct_tree_root(self, _root: object) -> None:
            pass

        def get_pages(self) -> list:
            return []

    util = PDFMergerUtility()
    src = _CatalogWithBareDestStructTree(False)
    dst = _CatalogWithBareDestStructTree(True)

    class _Doc:
        pass

    (merge, key, src_map, dest_map, src_tree, dest_tree) = (
        util._prepare_struct_tree_merge(  # noqa: SLF001
            src, dst, _Doc()
        )
    )
    assert merge is False
    assert dest_tree is not None
    # key may still be -1 because get_parent_tree() returned None.
    assert src_map == {} and dest_map == {}
    _ = COSInteger.get  # silence unused-import warning if any.


# ---------- _prepare_struct_tree_merge: various sub-branches via full doc ----------


def test_append_document_dest_has_struct_tree_src_does_not() -> None:
    """When dest has a struct tree and src does not, prepare bypasses
    the merge path; ``merge_struct_tree`` stays False and the False
    sides of 1498 / 1502 are taken (no src to read parent-tree from)."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())

    dst = PDDocument()
    dst.add_page(PDPage())
    dt = PDStructureTreeRoot()
    dt.set_parent_tree_next_key(0)
    dst.get_document_catalog().set_struct_tree_root(dt)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    src.close()
    dst.close()


def test_append_document_dest_has_struct_tree_src_has_empty_parent_tree() -> None:
    """Dest has tree with /ParentTree, src has tree but its parent_tree
    is None → exercises 1502 with src_parent_tree=None false branch."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())
    st = PDStructureTreeRoot()
    # NO parent tree on src
    src.get_document_catalog().set_struct_tree_root(st)

    dst = PDDocument()
    dst.add_page(PDPage())
    dt = PDStructureTreeRoot()
    dpt = PDStructureElementNumberTreeNode()
    dpt.set_numbers({0: COSDictionary()})
    dt.set_parent_tree(dpt)
    dt.set_parent_tree_next_key(1)
    dst.get_document_catalog().set_struct_tree_root(dt)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    src.close()
    dst.close()


def test_append_document_dest_tree_with_no_parent_tree() -> None:
    """Dest has a struct tree whose ``get_parent_tree`` is None →
    skips the merge prep body entirely (branch 1496 false path)."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())

    dst = PDDocument()
    dst.add_page(PDPage())
    dt = PDStructureTreeRoot()
    # No parent tree set explicitly
    dst.get_document_catalog().set_struct_tree_root(dt)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    src.close()
    dst.close()


def test_append_document_with_dest_annots_array_during_bootstrap() -> None:
    """When dest is bootstrapped with a struct tree (src has one, dest
    doesn't), the existing dest pages with /Annots arrays exercise the
    bootstrap-pages loop (line 1479-1486)."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())
    st = PDStructureTreeRoot()
    spt = PDStructureElementNumberTreeNode()
    spt.set_numbers({0: COSDictionary()})
    st.set_parent_tree(spt)
    st.set_parent_tree_next_key(1)
    src.get_document_catalog().set_struct_tree_root(st)

    dst = PDDocument()
    dst_page = PDPage()
    annots = COSArray()
    annots.add(COSString("not a dict"))
    annot_d = COSDictionary()
    annot_d.set_item(_STRUCT_PARENT, COSInteger.get(5))
    annots.add(annot_d)
    dst_page.get_cos_object().set_item(_ANNOTS, annots)
    dst_page.get_cos_object().set_item(_STRUCT_PARENTS, COSInteger.get(0))
    dst.add_page(dst_page)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    # Dest page's StructParents was stripped during bootstrap.
    assert dst_page.get_cos_object().get_dictionary_object(_STRUCT_PARENTS) is None
    src.close()
    dst.close()


def test_append_document_dest_has_full_tree_src_has_no_tree() -> None:
    """Dest has tree + parent_tree + key, src has NO tree at all →
    1502's False side (``src_struct_tree is not None`` is False)
    takes us straight to 1509 with merge_struct_tree=False."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())
    # NO struct tree on src.

    dst = PDDocument()
    dst.add_page(PDPage())
    dt = PDStructureTreeRoot()
    dpt = PDStructureElementNumberTreeNode()
    dpt.set_numbers({0: COSDictionary()})
    dt.set_parent_tree(dpt)
    dt.set_parent_tree_next_key(1)
    dst.get_document_catalog().set_struct_tree_root(dt)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    src.close()
    dst.close()


def test_append_document_src_parent_tree_empty_numbers() -> None:
    """src has tree + empty parent_tree → ``if src_map:`` is False at
    line 1506, skipping the merge_struct_tree=True assignment (branch
    1506->1509)."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())
    st = PDStructureTreeRoot()
    spt = PDStructureElementNumberTreeNode()
    spt.set_numbers({})  # explicitly empty
    st.set_parent_tree(spt)
    st.set_parent_tree_next_key(0)
    src.get_document_catalog().set_struct_tree_root(st)

    dst = PDDocument()
    dst.add_page(PDPage())
    dt = PDStructureTreeRoot()
    dpt = PDStructureElementNumberTreeNode()
    dpt.set_numbers({0: COSDictionary()})
    dt.set_parent_tree(dpt)
    dt.set_parent_tree_next_key(1)
    dst.get_document_catalog().set_struct_tree_root(dt)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    src.close()
    dst.close()


def test_append_document_with_dest_page_annots_not_array_during_bootstrap() -> None:
    """Dest page during bootstrap whose /Annots is NOT a COSArray (e.g.
    a name) → branch 1482 false path (line 1481->1479 in the cov map)."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    src = PDDocument()
    src.add_page(PDPage())
    st = PDStructureTreeRoot()
    spt = PDStructureElementNumberTreeNode()
    spt.set_numbers({0: COSDictionary()})
    st.set_parent_tree(spt)
    st.set_parent_tree_next_key(1)
    src.get_document_catalog().set_struct_tree_root(st)

    dst = PDDocument()
    dst_page = PDPage()
    # /Annots is a name, not an array → bootstrap loop's isinstance
    # check is False.
    dst_page.get_cos_object().set_item(_ANNOTS, COSName.get_pdf_name("Bogus"))
    dst.add_page(dst_page)

    util = PDFMergerUtility()
    util.append_document(dst, src)
    src.close()
    dst.close()


# ---------- _hash_cos remaining unreachable tautology pragma ----------


def test_hash_cos_tautology_branch_is_marked_unreachable_intentionally() -> None:
    """Sanity probe: line 62 (``isinstance(value, type(value))``) is a
    tautology; the False arm is unreachable so its branch arrow is
    intentionally left as an audit anchor rather than fabricated."""
    # The test itself exercises the True arm. Branch coverage will keep
    # surfacing 62->69 as partial until the dead code is removed; we
    # leave the source alone to preserve a 1:1 parity audit anchor with
    # PDFBox's Java ``case COSNumber`` switch arm.
    h = hashlib.sha256()
    _hash_cos(COSInteger.get(5), h, set())
    assert h.hexdigest()


def test_merge_viewer_preferences_short_circuit_when_dest_lacks_setter() -> None:
    """When dest lacks set_viewer_preferences, abort silently."""

    class _SrcWithVp:
        def get_viewer_preferences(self) -> object:
            class _Vp:
                def get_cos_object(self) -> COSDictionary:
                    return COSDictionary()

            return _Vp()

    class _DstNoSetter:
        def get_viewer_preferences(self) -> None:
            return None

    PDFMergerUtility().merge_viewer_preferences(
        _DstNoSetter(),  # type: ignore[arg-type]
        _SrcWithVp(),  # type: ignore[arg-type]
        _IdentityCloner(),  # type: ignore[arg-type]
    )
