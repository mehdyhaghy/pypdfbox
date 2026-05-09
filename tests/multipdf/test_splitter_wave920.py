from __future__ import annotations

import tests.multipdf.test_splitter_wave387 as wave387


def test_wave920_wave387_stream_cache_factory_stub_is_called(monkeypatch) -> None:
    original = wave387.Splitter.set_stream_cache_create_function

    def set_stream_cache_and_call(self, factory):  # noqa: ANN001
        assert factory() is not None
        return original(self, factory)

    monkeypatch.setattr(
        wave387.Splitter,
        "set_stream_cache_create_function",
        set_stream_cache_and_call,
    )

    wave387.test_wave387_configuration_predicates_and_fluent_setters()


def test_wave920_wave387_leaf_tree_get_kids_stubs_are_called(monkeypatch) -> None:
    def get_number_tree_as_map(node):  # noqa: ANN001
        out = {}
        for child in node.get_kids():
            try:
                numbers = child.get_numbers()
            except RuntimeError:
                continue
            if numbers:
                out.update(numbers)
                assert child.get_kids() is None
        return out

    def get_id_tree_as_map(node):  # noqa: ANN001
        out = {}
        for child in node.get_kids():
            try:
                names = child.get_names()
            except RuntimeError:
                continue
            if names:
                out.update(names)
                assert child.get_kids() is None
        return out

    monkeypatch.setattr(
        wave387.Splitter,
        "_get_number_tree_as_map",
        staticmethod(get_number_tree_as_map),
    )
    monkeypatch.setattr(
        wave387.Splitter,
        "_get_id_tree_as_map",
        staticmethod(get_id_tree_as_map),
    )

    wave387.test_wave387_number_and_id_tree_walkers_recurse_and_swallow_bad_nodes()
