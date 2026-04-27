"""Hand-written tests for the :class:`FontMappers` singleton registry.

Mirrors the surface of upstream
``org.apache.pdfbox.pdmodel.font.FontMappers`` plus the pypdfbox
:meth:`reset` extension.
"""

from __future__ import annotations

import threading

import pytest

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_mapper import DefaultFontMapper, FontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.font_mapping import FontMapping


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Drop the override + cached default before/after every test.

    Without this each test would see whatever the previous test
    installed; the registry is process-global by design.
    """
    FontMappers.reset()
    yield
    FontMappers.reset()


# ---------------------------------------------------------------------------
# instance() / set()
# ---------------------------------------------------------------------------


def test_instance_returns_default_mapper_by_default() -> None:
    mapper = FontMappers.instance()
    assert isinstance(mapper, DefaultFontMapper)


def test_instance_is_idempotent_until_set() -> None:
    a = FontMappers.instance()
    b = FontMappers.instance()
    assert a is b


def test_set_swaps_the_active_mapper() -> None:
    class _Stub(FontMapper):
        def get_true_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_open_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_font_box_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

    stub = _Stub()
    FontMappers.set(stub)
    assert FontMappers.instance() is stub


def test_set_none_resets_to_default() -> None:
    class _Stub(FontMapper):
        def get_true_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_open_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_font_box_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

    FontMappers.set(_Stub())
    FontMappers.set(None)
    assert isinstance(FontMappers.instance(), DefaultFontMapper)


def test_reset_clears_override() -> None:
    class _Stub(FontMapper):
        def get_true_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_open_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_font_box_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

    FontMappers.set(_Stub())
    FontMappers.reset()
    assert isinstance(FontMappers.instance(), DefaultFontMapper)


def test_set_rejects_non_font_mapper_instances() -> None:
    with pytest.raises(TypeError):
        FontMappers.set("not a mapper")  # type: ignore[arg-type]


def test_set_mapper_camelcase_alias_works() -> None:
    class _Stub(FontMapper):
        def get_true_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_open_type_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

        def get_font_box_font(self, base_font, font_descriptor):  # type: ignore[override]
            return None

    stub = _Stub()
    FontMappers.setMapper(stub)
    assert FontMappers.instance() is stub


def test_constructing_font_mappers_raises() -> None:
    """Static-only registry — direct construction is refused."""
    with pytest.raises(TypeError):
        FontMappers()


# ---------------------------------------------------------------------------
# Default mapper round-trip through the singleton
# ---------------------------------------------------------------------------


def test_singleton_resolves_standard14_via_default_mapper() -> None:
    mapping = FontMappers.instance().get_font_box_font("Helvetica", None)
    assert isinstance(mapping, FontMapping)
    assert mapping.is_fallback() is False
    assert isinstance(mapping.get_font(), FontBoxFont)
    assert mapping.get_font().get_name() == "Helvetica"


# ---------------------------------------------------------------------------
# Thread-safety smoke test
# ---------------------------------------------------------------------------


def test_concurrent_instance_calls_return_same_object() -> None:
    """``instance()`` under contention always returns the same singleton."""
    seen: list[FontMapper] = []
    lock = threading.Lock()

    def _grab() -> None:
        m = FontMappers.instance()
        with lock:
            seen.append(m)

    threads = [threading.Thread(target=_grab) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(seen) == 8
    first = seen[0]
    assert all(m is first for m in seen)
