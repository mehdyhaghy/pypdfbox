from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.multipdf import Splitter
from tests.multipdf.test_splitter_wave654 import _IdentityNameTree, _Root


class _IdTree:
    def __init__(self, name: str, struct_dict: COSDictionary) -> None:
        self.name = name
        self.struct_dict = struct_dict

    def get_names(self) -> dict[str, COSDictionary]:
        return {self.name: self.struct_dict}


def test_wave874_root_and_identity_name_tree_helpers_record_assigned_values() -> None:
    tree = _IdentityNameTree()
    names = {"kept": object()}

    tree.set_names(names)

    assert tree.names is names

    root = _Root()
    root.set_id_tree(tree)
    assert root.get_id_tree() is tree


def test_wave874_clone_id_tree_uses_wave654_helper_stubs_for_retained_name() -> None:
    source_struct = COSDictionary()
    cloned_struct = COSDictionary()
    source = _Root()
    destination = _Root()
    source.id_tree = _IdTree("kept", source_struct)
    splitter = Splitter()
    splitter._id_set = {"kept"}  # noqa: SLF001
    splitter._struct_dict_map = {id(source_struct): cloned_struct}  # noqa: SLF001

    splitter._clone_id_tree(source, destination, _IdentityNameTree)  # noqa: SLF001

    assert isinstance(destination.id_tree, _IdentityNameTree)
    assert list(destination.id_tree.names) == ["kept"]
