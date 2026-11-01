import tests.multipdf.test_splitter_wave387 as wave387


def test_wave920_wave387_stream_cache_factory_stub_is_called(monkeypatch) -> None:
    original = wave387.Splitter.set_stream_cache_create_function

    def set_stream_cache_and_call(self, factory):
        assert factory() is not None
        return original(self, factory)

    monkeypatch.setattr(
        wave387.Splitter,
        "set_stream_cache_create_function",
        set_stream_cache_and_call,
    )

    wave387.test_wave387_configuration_predicates_and_fluent_setters()
