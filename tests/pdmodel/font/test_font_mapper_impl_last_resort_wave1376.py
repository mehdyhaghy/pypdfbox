"""Wave 1376 — wiring tests for the bundled Liberation last-resort font.

These tests cover the four call sites in
:class:`pypdfbox.pdmodel.font.font_mapper_impl.FontMapperImpl` that
previously silently returned ``None`` and let downstream code fall
through to ``.notdef`` rendering:

* :meth:`get_true_type_font` (line 315)
* :meth:`get_open_type_font` (line 330)
* :meth:`get_font_box_font`  (line 348)
* :meth:`get_cid_font`        (line 391)

The bundled Liberation TTFs (12 fonts, 3.94 MB total, SIL OFL 1.1)
ride through the active :class:`FontProvider`'s ``scan_fonts`` path so
the resulting font is a real :class:`FontBoxFont` indistinguishable
from one resolved off the system font directories.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl


class _StubDescriptor:
    """Minimal :class:`PDFontDescriptor` stand-in (also used in loader tests)."""

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

    def get_font_family(self) -> str | None:
        return None


def _resolved_path_name(impl: FontMapperImpl, key: str) -> str:
    """Return the filename of the bundled TTF cached under *key*."""
    path = impl._last_resort_paths.get(key)  # type: ignore[attr-defined]
    assert path is not None, f"no path cached under {key!r}"
    return path.name


# ---------- _get_last_resort_font dispatch ----------


def test_last_resort_default_descriptor_resolves_to_liberation_sans() -> None:
    impl = FontMapperImpl()
    font = impl._get_last_resort_font()  # type: ignore[attr-defined]
    assert font is not None
    # Probe the parallel path cache so we know which Liberation TTF
    # the loader picked — fontTools' TTFont doesn't expose a stable
    # name attribute we can match against.
    assert "LiberationSans" in _resolved_path_name(impl, "Sans-Regular")


def test_last_resort_serif_descriptor_resolves_to_liberation_serif() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor(serif=True)
    font = impl._get_last_resort_font(descriptor)  # type: ignore[attr-defined]
    assert font is not None
    assert "LiberationSerif" in _resolved_path_name(impl, "Serif-Regular")


def test_last_resort_mono_descriptor_resolves_to_liberation_mono() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor(fixed_pitch=True)
    font = impl._get_last_resort_font(descriptor)  # type: ignore[attr-defined]
    assert font is not None
    assert "LiberationMono" in _resolved_path_name(impl, "Mono-Regular")


def test_last_resort_bold_descriptor_resolves_to_bold_variant() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor(weight=700)
    font = impl._get_last_resort_font(descriptor)  # type: ignore[attr-defined]
    assert font is not None
    assert "Bold" in _resolved_path_name(impl, "Sans-Bold")


# ---------- is_fallback_font_loaded flips after resolution ----------


def test_is_fallback_font_loaded_initially_false() -> None:
    impl = FontMapperImpl()
    assert impl.is_fallback_font_loaded() is False


def test_is_fallback_font_loaded_flips_after_resolution() -> None:
    impl = FontMapperImpl()
    impl._get_last_resort_font()  # type: ignore[attr-defined]
    assert impl.is_fallback_font_loaded() is True


# ---------- descriptor cache behaviour ----------


def test_last_resort_caches_per_descriptor_key() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor(serif=True)
    a = impl._get_last_resort_font(descriptor)  # type: ignore[attr-defined]
    b = impl._get_last_resort_font(descriptor)  # type: ignore[attr-defined]
    # Same descriptor style -> identical cached FontBox font.
    assert a is b


def test_last_resort_distinct_styles_yield_distinct_fonts() -> None:
    impl = FontMapperImpl()
    sans = impl._get_last_resort_font(_StubDescriptor())  # type: ignore[attr-defined]
    mono = impl._get_last_resort_font(_StubDescriptor(fixed_pitch=True))  # type: ignore[attr-defined]
    assert sans is not None
    assert mono is not None
    assert sans is not mono


# ---------- call-site pass-through ----------


def test_get_true_type_font_unknown_falls_through_to_last_resort() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor()
    mapping = impl.get_true_type_font("NoSuchFont-Regular", descriptor)
    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font() is not None


def test_get_open_type_font_unknown_falls_through_to_last_resort() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor()
    mapping = impl.get_open_type_font("NoSuchFont-Regular", descriptor)
    # OTF fallback may resolve to a TTF via the last-resort path (no OTF
    # variants in the bundle), which is the intended behaviour — a real
    # FontBoxFont still beats a placeholder rectangle.
    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font() is not None


def test_get_font_box_font_unknown_falls_through_to_last_resort() -> None:
    impl = FontMapperImpl()
    descriptor = _StubDescriptor(serif=True)
    mapping = impl.get_font_box_font("NoSuchSerifFont", descriptor)
    assert mapping is not None
    assert mapping.is_fallback() is True
    assert mapping.get_font() is not None


def test_get_cid_font_no_cid_info_falls_through_to_last_resort() -> None:
    # When ``cid_system_info`` is ``None`` the CJK branch is skipped and
    # the call goes directly to ``_get_last_resort_font(font_descriptor)``.
    impl = FontMapperImpl()
    descriptor = _StubDescriptor()
    mapping = impl.get_cid_font("NoSuchCIDFont", descriptor, None)
    assert mapping is not None
    assert mapping.is_fallback() is True
    # The Liberation TTFs are TTF format -> arrive on the TrueType side.
    assert mapping.get_true_type_font() is not None


# ---------- explicit lookup by Liberation PostScript name ----------


def test_liberation_sans_resolves_through_provider_index() -> None:
    # Wave 1376 added ``pypdfbox/resources/ttf/`` to
    # ``_default_font_dirs``, so an explicit lookup by PostScript name
    # should find the bundled TTF without going through the last-resort
    # fallback at all.
    impl = FontMapperImpl()
    found = impl.find_font(FontFormat.TTF, "LiberationSans")
    assert found is not None


# ---------- descriptor-keyed cache key matches loader's key ----------


@pytest.mark.parametrize(
    ("descriptor", "expected_key", "expected_substring"),
    [
        (_StubDescriptor(), "Sans-Regular", "Sans"),
        (_StubDescriptor(serif=True), "Serif-Regular", "Serif"),
        (_StubDescriptor(fixed_pitch=True), "Mono-Regular", "Mono"),
        (_StubDescriptor(weight=700), "Sans-Bold", "Bold"),
        (_StubDescriptor(italic=True), "Sans-Italic", "Italic"),
    ],
    ids=["sans", "serif", "mono", "bold", "italic"],
)
def test_last_resort_picks_matching_family(
    descriptor: _StubDescriptor,
    expected_key: str,
    expected_substring: str,
) -> None:
    impl = FontMapperImpl()
    font = impl._get_last_resort_font(descriptor)  # type: ignore[attr-defined]
    assert font is not None
    assert expected_substring in _resolved_path_name(impl, expected_key)


# ---------- non-blank rendering smoke test ----------


def test_resolved_font_yields_ascii_glyph_metrics_not_notdef() -> None:
    """End-to-end smoke test that closes CHANGES.md:454.

    Before wave 1376, a font reference with no embedded program and no
    matching system font resolved to ``None`` -> placeholder rectangle.
    With the Liberation bundle wired in, the same path returns a real
    fontTools TTFont whose ``A`` glyph has a real (>0) advance width —
    the minimum proof that downstream rendering will produce a real
    glyph outline rather than a ``.notdef`` box.
    """
    impl = FontMapperImpl()
    font = impl._get_last_resort_font()  # type: ignore[attr-defined]
    assert font is not None
    # The bundled resolver returns whatever the active FontProvider
    # produces. With :class:`FileSystemFontProvider` that's a fontTools
    # :class:`TTFont`. Probe via the ``hmtx`` table for the capital A
    # advance width — a Liberation font has a positive value here.
    try:
        hmtx = font["hmtx"]
    except (TypeError, KeyError):
        hmtx = None
    if hmtx is not None:
        metrics = getattr(hmtx, "metrics", {})
        a_metrics = metrics.get("A")
        assert a_metrics is not None, "Liberation TTF lacks 'A' glyph metrics"
        advance = a_metrics[0]
        assert advance > 0, f"expected positive advance, got {advance}"
        return
    # Fallback assertion: the path cache records the Liberation TTF
    # that was loaded.
    path_name = _resolved_path_name(impl, "Sans-Regular")
    assert "Liberation" in path_name
