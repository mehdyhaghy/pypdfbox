from __future__ import annotations

import tests.xmpbox.upstream.test_dublin_core_schema as dc_schema


class _StringFallbackSchema:
    def __init__(self) -> None:
        self.value: str | None = None

    def set_text_property_value(self, field: str, value: str) -> None:
        assert field == "custom"
        self.value = value

    def get_custom(self) -> str | None:
        return self.value


class _NonTextFetchedProperty:
    def __init__(self, value: object) -> None:
        self.value = value

    def get_string_value(self) -> str:
        return str(self.value)


class _NonTextPropertyFactory:
    def __init__(
        self,
        metadata: object,
        namespace: str,
        prefix: str,
        field: str,
        value: object,
    ) -> None:
        del metadata, namespace, prefix, field
        self.value = value


class _TypedFallbackSchema:
    def __init__(self) -> None:
        self.prop: _NonTextPropertyFactory | None = None

    def set_custom_property(self, prop: _NonTextPropertyFactory) -> None:
        self.prop = prop

    def get_custom_property(self) -> _NonTextFetchedProperty:
        assert self.prop is not None
        return _NonTextFetchedProperty(self.prop.value)


def test_wave960_setting_value_simple_falls_back_to_text_property(monkeypatch) -> None:
    monkeypatch.setattr(dc_schema, "_string_getter_for", lambda _field: "get_custom")

    schema = _StringFallbackSchema()

    dc_schema.test_setting_value(schema, "custom", "Text", "Simple")

    assert schema.value == "sample-value"


def test_wave960_property_setter_simple_non_text_fetched_branch(monkeypatch) -> None:
    monkeypatch.setattr(
        dc_schema,
        "_typed_simple_factory",
        lambda _type_token: _NonTextPropertyFactory,
    )
    monkeypatch.setattr(
        dc_schema,
        "_typed_setter_for",
        lambda _field: "set_custom_property",
    )
    monkeypatch.setattr(
        dc_schema,
        "_typed_getter_for",
        lambda _field: "get_custom_property",
    )

    dc_schema.test_property_setter_simple(
        metadata=object(),
        schema=_TypedFallbackSchema(),
        field="custom",
        type_token="Custom",
        _card="Simple",
    )
