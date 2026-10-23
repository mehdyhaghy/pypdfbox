
from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter

_ANNOTS = COSName.get_pdf_name("Annots")
_CLASS_MAP = COSName.get_pdf_name("ClassMap")
_ID = COSName.get_pdf_name("ID")
_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_P = COSName.get_pdf_name("P")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


class _PageTree:
    def __init__(self, index: int = 0) -> None:
        self.index = index

    def index_of(self, page_dict: COSDictionary) -> int:
        return self.index


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict if root_dict is not None else COSDictionary()
        self.id_tree: object | None = None
        self.parent_tree: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_parent_tree(self) -> object | None:
        return self.parent_tree

    def get_id_tree(self) -> object | None:
        return self.id_tree

    def set_id_tree(self, tree: object) -> None:
        self.id_tree = tree


class _IdentityNameTree:
    def __init__(self) -> None:
        self.names: dict[str, object] = {}

    def set_names(self, names: dict[str, object]) -> None:
        self.names = names


def test_wave654_k_clone_drops_page_reference_not_in_destination_tree() -> None:
    source_page = COSDictionary()
    cloned_page = COSDictionary()
    src = COSDictionary()
    src.set_item(_PG, source_page)
    splitter = Splitter()
    splitter._page_dict_map = {id(source_page): cloned_page}

    assert (
        splitter._k_create_clone(src, COSDictionary(), None, _PageTree(index=-1))
        is None
    )


def test_wave654_k_clone_drops_parent_when_all_kids_are_dropped() -> None:
    child = COSDictionary()
    child.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    child.set_item(_K, COSInteger.get(0))
    src = COSDictionary()
    src.set_item(_K, child)

    assert (
        Splitter()._k_create_clone(src, COSDictionary(), COSDictionary(), _PageTree())
        is None
    )


def test_wave654_remove_possible_orphan_annotation_keeps_obj_without_host_page() -> None:
    source_annotation = COSDictionary()
    source_annotation.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    dst = COSDictionary()
    dst.set_item(_OBJ, source_annotation)

    Splitter()._remove_possible_orphan_annotation(
        source_annotation, COSDictionary(), None, dst
    )

    assert dst.get_dictionary_object(_OBJ) is source_annotation


def test_wave654_clone_role_map_noops_without_source_role_map() -> None:
    destination = _Root()

    Splitter()._clone_role_map(_Root(), destination)

    assert not destination.get_cos_object().contains_key(_ROLE_MAP)


def test_wave654_clone_id_tree_noops_for_missing_empty_and_unretained_names() -> None:
    class EmptyTree:
        def get_names(self) -> dict[str, object]:
            return {}

        def get_tree_as_map(self) -> dict[str, object]:
            return {}

        def get_kids(self) -> None:
            return None

    class UnretainedTree:
        def get_names(self) -> dict[str, COSDictionary]:
            return {"drop": COSDictionary()}

        def get_tree_as_map(self) -> dict[str, COSDictionary]:
            return self.get_names()

        def get_kids(self) -> None:
            return None

    destination = _Root()
    splitter = Splitter()
    splitter._clone_id_tree(_Root(), destination)
    assert destination.id_tree is None

    # like upstream cloneIDTree, a source /IDTree always yields one in the
    # destination, empty when no id is retained
    source = _Root()
    source.id_tree = EmptyTree()
    splitter._clone_id_tree(source, destination)
    names = destination.id_tree.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Names")
    )
    assert names.size() == 0

    destination = _Root()
    source.id_tree = UnretainedTree()
    assert source.id_tree.get_kids() is None
    splitter._id_set = {"keep"}
    splitter._clone_id_tree(source, destination)
    names = destination.id_tree.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Names")
    )
    assert names.size() == 0


def test_wave654_k_clone_tracks_id_and_role_on_retained_child() -> None:
    source_page = COSDictionary()
    cloned_page = COSDictionary()
    child = COSDictionary()
    child.set_item(_PG, source_page)
    child.set_string(_ID, "child-id")
    child.set_item(_S, COSName.get_pdf_name("P"))
    src = COSDictionary()
    src.set_item(_K, child)
    splitter = Splitter()
    splitter._page_dict_map = {id(source_page): cloned_page}

    cloned = splitter._k_create_clone(src, COSDictionary(), None, _PageTree())

    assert isinstance(cloned, COSDictionary)
    assert splitter._id_set == {"child-id"}
    assert splitter._role_set == {"P"}
    assert isinstance(cloned.get_dictionary_object(_K), COSDictionary)
