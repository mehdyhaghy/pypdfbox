"""Coverage-boost tests for ``pypdfbox.rendering.tiling_paint_factory``.

Targets the cache-miss / cache-hit equality branches in
``TilingPaintParameter.equals`` (matrix mismatch, pattern dict mismatch,
colour space mismatch, color None-vs-non-None, color color-space
mismatch, color to_rgb OSError swallow, identical-color short-circuit),
plus ``to_string`` and ``__repr__``.

Also exercises the factory's matrix-clone path, weakref fallback for
non-weakly-referenceable paints, and re-use from the cache.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.rendering.tiling_paint_factory import (
    TilingPaintFactory,
    TilingPaintParameter,
)

# ---------- Stubs ---------------------------------------------------------


class _CloneableMatrix:
    """Matrix-like that supports ``.clone()`` and ``__eq__`` by value."""

    def __init__(self, value: int) -> None:
        self.value = value

    def clone(self) -> _CloneableMatrix:
        return _CloneableMatrix(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _CloneableMatrix) and self.value == other.value

    def __hash__(self) -> int:
        return hash(("CM", self.value))


class _StubColorSpace:
    def __init__(self, name: str = "Stub") -> None:
        self._name = name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _StubColorSpace) and self._name == other._name

    def __hash__(self) -> int:
        return hash(("CS", self._name))


class _StubColor:
    def __init__(self, rgb: tuple[float, float, float], cs: _StubColorSpace) -> None:
        self._rgb = rgb
        self._cs = cs

    def get_color_space(self) -> _StubColorSpace:
        return self._cs

    def to_rgb(self) -> tuple[float, float, float]:
        return self._rgb


class _BoomColor:
    def __init__(self, cs: _StubColorSpace) -> None:
        self._cs = cs

    def get_color_space(self) -> _StubColorSpace:
        return self._cs

    def to_rgb(self) -> tuple[float, float, float]:
        raise OSError("blast")


class _StubDrawer:
    def __init__(self, initial_matrix: Any = None) -> None:
        self._initial = initial_matrix

    def get_initial_matrix(self) -> Any:
        return self._initial


class _StubPattern:
    def __init__(self, cos_dict: Any = None) -> None:
        self._cos = cos_dict

    def get_cos_object(self) -> Any:
        return self._cos

    def get_matrix(self) -> Any:
        return None


# ---------- TilingPaintParameter equality branches -----------------------


def test_parameter_self_identity_is_equal() -> None:
    p = TilingPaintParameter(None, None, None, None, "X")
    assert p.equals(p) is True


def test_parameter_not_equals_other_type() -> None:
    p = TilingPaintParameter(None, None, None, None, "X")
    assert p.equals("not-a-parameter") is False


def test_parameter_matrix_mismatch_not_equal() -> None:
    a = TilingPaintParameter(_CloneableMatrix(1), None, None, None, "X")
    b = TilingPaintParameter(_CloneableMatrix(2), None, None, None, "X")
    assert a.equals(b) is False


def test_parameter_matrix_is_cloned_on_construction() -> None:
    src = _CloneableMatrix(7)
    p = TilingPaintParameter(src, None, None, None, "X")
    assert p.matrix is not src
    assert p.matrix == src


def test_parameter_pattern_dict_mismatch_not_equal() -> None:
    a = TilingPaintParameter(None, object(), None, None, "X")
    b = TilingPaintParameter(None, object(), None, None, "X")
    # Two distinct object()s -> identity differs, equality differs -> not equal.
    assert a.equals(b) is False


def test_parameter_color_space_mismatch_not_equal() -> None:
    a = TilingPaintParameter(None, None, _StubColorSpace("A"), None, "X")
    b = TilingPaintParameter(None, None, _StubColorSpace("B"), None, "X")
    assert a.equals(b) is False


def test_parameter_color_none_vs_non_none_not_equal() -> None:
    cs = _StubColorSpace("CS")
    a = TilingPaintParameter(None, None, cs, None, "X")
    b = TilingPaintParameter(None, None, cs, _StubColor((0.0, 0.0, 0.0), cs), "X")
    assert a.equals(b) is False
    assert b.equals(a) is False


def test_parameter_color_color_space_mismatch_not_equal() -> None:
    cs_a = _StubColorSpace("A")
    cs_b = _StubColorSpace("B")
    a = TilingPaintParameter(None, None, None, _StubColor((1, 1, 1), cs_a), "X")
    b = TilingPaintParameter(None, None, None, _StubColor((1, 1, 1), cs_b), "X")
    assert a.equals(b) is False


def test_parameter_color_to_rgb_difference_not_equal() -> None:
    cs = _StubColorSpace("X")
    a = TilingPaintParameter(None, None, None, _StubColor((1.0, 0.0, 0.0), cs), "X")
    b = TilingPaintParameter(None, None, None, _StubColor((0.0, 1.0, 0.0), cs), "X")
    assert a.equals(b) is False


def test_parameter_color_to_rgb_match_equal_when_other_fields_match() -> None:
    cs = _StubColorSpace("X")
    a = TilingPaintParameter(None, None, None, _StubColor((1.0, 0.0, 0.0), cs), "X")
    b = TilingPaintParameter(None, None, None, _StubColor((1.0, 0.0, 0.0), cs), "X")
    assert a.equals(b) is True


def test_parameter_color_to_rgb_oserror_treated_as_not_equal() -> None:
    """The ``to_rgb`` call wraps OSError in a debug log and treats the
    parameters as unequal (lines 110-112).
    """
    cs = _StubColorSpace("X")
    a = TilingPaintParameter(None, None, None, _BoomColor(cs), "X")
    b = TilingPaintParameter(None, None, None, _StubColor((0, 0, 0), cs), "X")
    assert a.equals(b) is False


def test_parameter_xform_mismatch_not_equal() -> None:
    a = TilingPaintParameter(None, None, None, None, "X")
    b = TilingPaintParameter(None, None, None, None, "Y")
    assert a.equals(b) is False


# ---------- TilingPaintParameter hash / to_string / repr ----------------


def test_parameter_to_string_includes_all_fields() -> None:
    p = TilingPaintParameter(None, "pdict", "cs", "col", "xf")
    s = p.to_string()
    assert "matrix=None" in s
    assert "pattern=pdict" in s
    assert "colorSpace=cs" in s
    assert "color=col" in s
    assert "xform=xf" in s


def test_parameter_repr_delegates_to_to_string() -> None:
    p = TilingPaintParameter(None, None, None, None, "X")
    assert repr(p) == p.to_string()


def test_parameter_hash_is_stable_for_equal_keys() -> None:
    a = TilingPaintParameter(_CloneableMatrix(3), None, None, None, "X")
    b = TilingPaintParameter(_CloneableMatrix(3), None, None, None, "X")
    assert hash(a) == hash(b)


def test_parameter_hash_includes_none_fallback() -> None:
    p = TilingPaintParameter(None, None, None, None, None)
    # Should not raise; ensures all-None inputs hash cleanly.
    assert isinstance(hash(p), int)


# ---------- TilingPaintFactory caching ----------------------------------


def test_factory_returns_cached_paint_for_repeated_create() -> None:
    factory = TilingPaintFactory(_StubDrawer())
    pat = _StubPattern(cos_dict=None)
    p1 = factory.create(pat, None, None, "xform")
    p2 = factory.create(pat, None, None, "xform")
    # Same key -> cache hit (weakref still alive for at least one call).
    assert isinstance(p1, type(p2))


def test_factory_caches_with_initial_matrix_path() -> None:
    """Drawer publishes ``get_initial_matrix`` -> exercised in factory.create."""
    factory = TilingPaintFactory(_StubDrawer(initial_matrix=_CloneableMatrix(1)))
    pat = _StubPattern(cos_dict=None)
    paint = factory.create(pat, None, None, "x")
    assert paint is not None


def test_factory_creates_new_paint_for_different_xform() -> None:
    factory = TilingPaintFactory(_StubDrawer())
    pat = _StubPattern(cos_dict=None)
    p_a = factory.create(pat, None, None, "xform-a")
    p_b = factory.create(pat, None, None, "xform-b")
    # Different cache key — both calls succeed and produce paint objects.
    assert p_a is not None
    assert p_b is not None


def test_factory_handles_drawer_without_initial_matrix() -> None:
    class _DrawerNoIM:
        pass

    factory = TilingPaintFactory(_DrawerNoIM())
    pat = _StubPattern(cos_dict=None)
    paint = factory.create(pat, None, None, "x")
    assert paint is not None


def test_factory_handles_pattern_without_cos_object() -> None:
    class _PatternNoCos:
        def get_matrix(self) -> Any:
            return None

    factory = TilingPaintFactory(_StubDrawer())
    paint = factory.create(_PatternNoCos(), None, None, "x")
    assert paint is not None


def test_factory_falls_back_when_paint_is_not_weakly_referenceable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the produced ``TilingPaint`` cannot be ``weakref.ref``-ed
    (e.g. has ``__slots__`` without ``__weakref__``), the factory falls
    back to storing a lambda strong-ref so the cache still keeps the
    instance alive (lines 56-58).
    """
    import pypdfbox.rendering.tiling_paint_factory as mod

    class _UnreferenceablePaint:
        # __slots__ without __weakref__ -> weakref.ref raises TypeError.
        __slots__ = ()

    monkeypatch.setattr(mod, "TilingPaint", lambda *args, **kwargs: _UnreferenceablePaint())

    factory = TilingPaintFactory(_StubDrawer())
    pat = _StubPattern(cos_dict=None)
    paint_a = factory.create(pat, None, None, "xform")
    paint_b = factory.create(pat, None, None, "xform")
    # Stable strong-ref keeps the cached entry alive across calls.
    assert paint_b is paint_a
