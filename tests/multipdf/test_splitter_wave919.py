import tests.multipdf.test_splitter_wave503 as wave503
from pypdfbox.cos import COSDictionary, COSName


def test_wave919_wave503_page_tree_stubs_are_exercised(monkeypatch) -> None:
    def clone_with_page_tree_call(self, src, parent, root, page_tree):
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
