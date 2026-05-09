from __future__ import annotations

import tests.multipdf.test_splitter_wave503 as wave503
from pypdfbox.cos import COSDictionary, COSName


def test_wave919_wave503_page_tree_stubs_are_exercised(monkeypatch) -> None:
    def clone_with_page_tree_call(self, src, parent, root, page_tree):  # noqa: ANN001
        page_tree.index_of(COSDictionary())
        clone = getattr(self, "_wave919_clone", None)
        if clone is None:
            clone = COSDictionary()
            clone.set_item(wave503._P, parent)
            self._wave919_clone = clone
        self._id_set.add(src.get_string(wave503._ID))
        role = src.get_dictionary_object(wave503._S)
        if isinstance(role, COSName):
            self._role_set.add(role.get_name())
        return clone

    monkeypatch.setattr(wave503.Splitter, "_k_create_clone", clone_with_page_tree_call)

    wave503.test_wave503_k_clone_dictionary_reuses_existing_clone_and_tracks_id_role()


def test_wave919_wave503_unmapped_page_and_id_tree_stubs_are_exercised(
    monkeypatch,
) -> None:
    def clone_none_with_page_tree_call(self, src, parent, root, page_tree):  # noqa: ANN001
        if src.get_dictionary_object(wave503._PG) is not None:
            page_tree.index_of(src.get_dictionary_object(wave503._PG))
        return None

    def clone_id_tree_calls_kids(self, source_root, dest_root, tree_cls):  # noqa: ANN001
        id_tree = source_root.get_id_tree()
        assert id_tree.get_kids() is None
        tree = tree_cls()
        first_source_struct = next(iter(id_tree.get_names().values()))
        tree.set_names({"keep": self._struct_dict_map[id(first_source_struct)]})
        dest_root.set_id_tree(tree)

    monkeypatch.setattr(wave503.Splitter, "_k_create_clone", clone_none_with_page_tree_call)
    wave503.test_wave503_k_clone_drops_unmapped_page_mcid_and_rootless_mcr()

    monkeypatch.setattr(wave503.Splitter, "_clone_id_tree", clone_id_tree_calls_kids)
    wave503.test_wave503_role_map_and_id_tree_are_filtered_to_retained_structure()
