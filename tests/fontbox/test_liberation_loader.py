"""Tests for the bundled Liberation TTF descriptor-keyed resolver.

The loader is original work (no upstream counterpart). It adapts the
architectural pattern from :mod:`pypdfbox.fontbox.cjk_loader` to a
bundled font set rather than a network-fetched one. These tests exercise
the contract from the perspective of callers in
:mod:`pypdfbox.pdmodel.font.font_mapper_impl`:

* ``font_descriptor=None`` -> ``LiberationSans-Regular`` (matches
  upstream PDFBox's eager constructor load).
* Each descriptor combination (Sans/Serif/Mono × Regular/Bold/Italic/
  BoldItalic) resolves to the correct file.
* Bold detection honours ``/FontWeight >= 600`` and the
  ``"bold"`` / ``"black"`` / ``"heavy"`` name heuristic.
* The bundled directory contains the 12 Liberation TTFs + DejaVuSans
  expected by the rest of the pipeline.

Tests run entirely off the bundled wheel resources — no network, no
filesystem mutation outside ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox import liberation_loader

# ---------- helpers ----------


class _StubDescriptor:
    """Minimal stand-in for :class:`PDFontDescriptor`.

    The real class wraps a COSDictionary; for resolver dispatch tests we
    only need the five boolean / string / float accessors that
    :func:`liberation_loader._descriptor_to_key` consults.
    """

    def __init__(
        self,
        *,
        fixed_pitch: bool = False,
        serif: bool = False,
        italic: bool = False,
        weight: float = 0.0,
        name: str | None = None,
    ) -> None:
        self._fixed_pitch = fixed_pitch
        self._serif = serif
        self._italic = italic
        self._weight = weight
        self._name = name

    def is_fixed_pitch(self) -> bool:
        return self._fixed_pitch

    def is_serif(self) -> bool:
        return self._serif

    def is_italic(self) -> bool:
        return self._italic

    def get_font_weight(self) -> float:
        return self._weight

    def get_font_name(self) -> str | None:
        return self._name


# ---------- bundled_dir / dejavu_path ----------


def test_bundled_dir_exists_and_holds_all_libration_ttfs() -> None:
    root = liberation_loader.bundled_dir()
    assert root.is_dir()
    expected = {
        "LiberationSans-Regular.ttf",
        "LiberationSans-Bold.ttf",
        "LiberationSans-Italic.ttf",
        "LiberationSans-BoldItalic.ttf",
        "LiberationSerif-Regular.ttf",
        "LiberationSerif-Bold.ttf",
        "LiberationSerif-Italic.ttf",
        "LiberationSerif-BoldItalic.ttf",
        "LiberationMono-Regular.ttf",
        "LiberationMono-Bold.ttf",
        "LiberationMono-Italic.ttf",
        "LiberationMono-BoldItalic.ttf",
    }
    on_disk = {p.name for p in root.iterdir() if p.suffix == ".ttf"}
    missing = expected - on_disk
    assert not missing, f"Liberation TTFs missing from bundle: {missing}"


def test_dejavu_path_resolves_to_bundled_file() -> None:
    path = liberation_loader.dejavu_path()
    assert path.is_file()
    assert path.name == "DejaVuSans.ttf"


# ---------- ensure_font(None) baseline ----------


def test_ensure_font_none_returns_sans_regular() -> None:
    # Upstream PDFBox constructor eagerly loads LiberationSans-Regular.
    # ensure_font(None) preserves that default.
    path = liberation_loader.ensure_font(None)
    assert path is not None
    assert path.name == "LiberationSans-Regular.ttf"


def test_descriptor_to_key_none_yields_sans_regular() -> None:
    assert liberation_loader.descriptor_to_key(None) == "Sans-Regular"


# ---------- 12 descriptor permutations ----------


_PERMUTATIONS = [
    (_StubDescriptor(), "Sans-Regular", "LiberationSans-Regular.ttf"),
    (
        _StubDescriptor(name="Helvetica-Bold"),
        "Sans-Bold",
        "LiberationSans-Bold.ttf",
    ),
    (
        _StubDescriptor(italic=True),
        "Sans-Italic",
        "LiberationSans-Italic.ttf",
    ),
    (
        _StubDescriptor(italic=True, name="Arial-BoldItalic"),
        "Sans-BoldItalic",
        "LiberationSans-BoldItalic.ttf",
    ),
    (
        _StubDescriptor(serif=True),
        "Serif-Regular",
        "LiberationSerif-Regular.ttf",
    ),
    (
        _StubDescriptor(serif=True, weight=700),
        "Serif-Bold",
        "LiberationSerif-Bold.ttf",
    ),
    (
        _StubDescriptor(serif=True, italic=True),
        "Serif-Italic",
        "LiberationSerif-Italic.ttf",
    ),
    (
        _StubDescriptor(serif=True, italic=True, weight=800),
        "Serif-BoldItalic",
        "LiberationSerif-BoldItalic.ttf",
    ),
    (
        _StubDescriptor(fixed_pitch=True),
        "Mono-Regular",
        "LiberationMono-Regular.ttf",
    ),
    (
        _StubDescriptor(fixed_pitch=True, weight=700),
        "Mono-Bold",
        "LiberationMono-Bold.ttf",
    ),
    (
        _StubDescriptor(fixed_pitch=True, italic=True),
        "Mono-Italic",
        "LiberationMono-Italic.ttf",
    ),
    (
        _StubDescriptor(fixed_pitch=True, italic=True, name="Courier-BoldOblique"),
        "Mono-BoldItalic",
        "LiberationMono-BoldItalic.ttf",
    ),
]


@pytest.mark.parametrize(
    ("descriptor", "expected_key", "expected_filename"),
    _PERMUTATIONS,
    ids=[
        "sans_regular",
        "sans_bold_via_name",
        "sans_italic",
        "sans_bolditalic_via_name",
        "serif_regular",
        "serif_bold_via_weight700",
        "serif_italic",
        "serif_bolditalic_via_weight800",
        "mono_regular",
        "mono_bold_via_weight700",
        "mono_italic",
        "mono_bolditalic_via_name",
    ],
)
def test_descriptor_permutations(
    descriptor: _StubDescriptor,
    expected_key: str,
    expected_filename: str,
) -> None:
    assert liberation_loader.descriptor_to_key(descriptor) == expected_key
    path = liberation_loader.ensure_font(descriptor)
    assert path is not None
    assert path.name == expected_filename


# ---------- targeted heuristics ----------


def test_fixed_pitch_takes_priority_over_serif() -> None:
    # Upstream's _get_fallback_font_name picks Courier when fixed-pitch
    # is set, regardless of serif. Mirror that here.
    descriptor = _StubDescriptor(fixed_pitch=True, serif=True)
    assert liberation_loader.descriptor_to_key(descriptor) == "Mono-Regular"


def test_bold_detected_via_font_weight_700() -> None:
    descriptor = _StubDescriptor(weight=700.0)
    assert liberation_loader.descriptor_to_key(descriptor) == "Sans-Bold"


def test_bold_not_detected_below_600_threshold() -> None:
    # /FontWeight 500 is "Medium", not Bold per PDF 32000-1 §9.8.1
    # (we follow the OS/2 usWeightClass convention).
    descriptor = _StubDescriptor(weight=500.0)
    assert liberation_loader.descriptor_to_key(descriptor) == "Sans-Regular"


def test_bold_detected_via_name_black() -> None:
    descriptor = _StubDescriptor(name="Helvetica-Black")
    assert liberation_loader.descriptor_to_key(descriptor) == "Sans-Bold"


def test_bold_detected_via_name_heavy() -> None:
    descriptor = _StubDescriptor(name="MyHeavyFont")
    assert liberation_loader.descriptor_to_key(descriptor) == "Sans-Bold"


def test_bold_detected_case_insensitive() -> None:
    descriptor = _StubDescriptor(name="ArialBOLD")
    assert liberation_loader.descriptor_to_key(descriptor) == "Sans-Bold"


# ---------- cache ----------


def test_ensure_font_caches_repeat_calls() -> None:
    # Two ``ensure_font`` calls with structurally-identical descriptors
    # should hit the @lru_cache wrapping ``_resolve_key`` and return
    # the exact same Path object.
    first = liberation_loader.ensure_font(None)
    second = liberation_loader.ensure_font(None)
    assert first is second  # identity, not just equality


def test_bundled_dir_is_cached() -> None:
    a = liberation_loader.bundled_dir()
    b = liberation_loader.bundled_dir()
    assert a is b


# ---------- descriptor without methods (defensive) ----------


def test_descriptor_missing_methods_defaults_to_sans_regular() -> None:
    class _Empty:
        pass

    # Missing attributes should fall through to Sans-Regular rather than
    # raising. The loader is defensive — descriptors from upstream-style
    # parsers may be partially populated.
    assert liberation_loader.descriptor_to_key(_Empty()) == "Sans-Regular"  # type: ignore[arg-type]


# ---------- return value is a Path ----------


def test_ensure_font_returns_pathlib_path() -> None:
    path = liberation_loader.ensure_font(None)
    assert isinstance(path, Path)
