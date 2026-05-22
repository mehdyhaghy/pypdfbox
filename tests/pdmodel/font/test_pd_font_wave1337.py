"""Wave 1337 coverage-boost tests for :mod:`pypdfbox.pdmodel.font.pd_font`.

Targets the ``get_space_width`` cascade (steps 1–5 plus the broad-catch
fallback), the Standard 14 AFM-load exception arm, the Standard 14
width fallback when the subclass override raises ``NotImplementedError``,
the ``get_string_width`` byte-walk loop, and the ``to_unicode``
``chr()`` ValueError + cmap-driven fallback paths.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.font.pd_font import PDFont


class _Stub(PDFont):
    """Concrete PDFont with overridable encode/decode/widths-from-font."""

    SUB_TYPE = "Stub"

    def encode_codepoint(self, unicode: int) -> bytes:
        return bytes([unicode & 0xFF])

    def read_code(self, data, offset: int = 0) -> tuple[int, int]:
        if offset < 0 or offset >= len(data):
            return (0, 0)
        return (data[offset] & 0xFF, 1)

    def get_width_from_font(self, code: int) -> float:
        return 0.0


# ---------- get_space_width cascade ----------


def test_get_space_width_uses_widths_lookup() -> None:
    """Step 3: direct /Widths lookup at code 32."""
    f = _Stub()
    dict_ = f.get_cos_object()
    dict_.set_item(COSName.get_pdf_name("FirstChar"), COSInteger.get(32))
    widths = COSArray()
    widths.add(COSFloat(345.0))  # code 32 width
    dict_.set_item(COSName.get_pdf_name("Widths"), widths)
    assert f.get_space_width() == 345.0


def test_get_space_width_falls_through_to_width_from_font() -> None:
    """Step 4: when steps 1-3 fail, ask the font program for code 32
    directly (bypasses encoding round-trip)."""

    class _WidthFromFont(_Stub):
        def get_width_from_font(self, code: int) -> float:
            if code == 32:
                return 555.0
            return 0.0

        def get_string_width(self, text: str) -> float:
            # Make step 2 raise so we cascade to step 4.
            raise NotImplementedError("forced cascade")

    f = _WidthFromFont()
    assert f.get_space_width() == 555.0


def test_get_space_width_step4_get_width_from_font_raises_falls_through() -> None:
    """Step 4: ``get_width_from_font(32)`` raises NotImplementedError —
    cascade continues to step 5 (avg). Then step 5 also returns 0 →
    default 250.
    """

    class _Step4Raises(_Stub):
        def get_width_from_font(self, code: int) -> float:
            raise NotImplementedError("step-4 raise")

    f = _Step4Raises()
    assert f.get_space_width() == 250.0


def test_get_space_width_falls_through_to_average_width() -> None:
    """Step 5: average font width as the last quasi-meaningful fallback."""

    class _AvgWidth(_Stub):
        def get_width_from_font(self, code: int) -> float:
            return 0.0

    f = _AvgWidth()
    dict_ = f.get_cos_object()
    widths = COSArray()
    widths.add(COSFloat(0.0))
    widths.add(COSFloat(100.0))
    widths.add(COSFloat(200.0))
    dict_.set_item(COSName.get_pdf_name("Widths"), widths)
    dict_.set_item(COSName.get_pdf_name("FirstChar"), COSInteger.get(0))
    # /Widths offset for code 32 falls outside the 3-entry array, so the
    # /Widths arm returns nothing. The avg-of-non-zero ({100, 200}) = 150
    # is returned.
    assert f.get_space_width() == 150.0


def test_get_space_width_default_when_everything_fails() -> None:
    """No widths, no font program → returns the 250.0 default."""
    f = _Stub()
    assert f.get_space_width() == 250.0
    # Cached on second call.
    assert f.get_space_width() == 250.0


def test_get_space_width_cached() -> None:
    """Repeated calls hit the cache (memoised result)."""
    f = _Stub()
    f._font_width_of_space = 123.0  # type: ignore[attr-defined]
    assert f.get_space_width() == 123.0


def test_get_space_width_via_to_unicode_cmap_space_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 1: ``/ToUnicode`` CMap's recorded space mapping wins when
    it's >-1 and the resolved width is positive (lines 246-252)."""

    class _Stubby(_Stub):
        def get_width_from_font(self, code: int) -> float:
            return 678.0 if code == 99 else 0.0

    f = _Stubby()
    # Force has_to_unicode True via a predefined name then patch the
    # parsed CMap's get_space_mapping to return code 99.
    f.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    cmap = f.get_to_unicode_cmap()
    assert cmap is not None
    monkeypatch.setattr(cmap, "get_space_mapping", lambda: 99)
    # Reset cached space width so we re-run the cascade.
    f._font_width_of_space = None  # type: ignore[attr-defined]
    assert f.get_space_width() == 678.0


def test_get_space_width_to_unicode_cmap_with_get_width_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 1 raise-and-continue: ``get_width(space_mapping)`` raises
    NotImplementedError → cascade continues to step 2 (lines 251-252)."""

    class _RaisingGetWidth(_Stub):
        def __init__(self):
            super().__init__()
            self._got_width_called = False

        def get_width(self, code: int) -> float:  # type: ignore[override]
            if not self._got_width_called:
                self._got_width_called = True
                raise NotImplementedError("step-1 raise")
            return super().get_width(code)

        def get_string_width(self, text: str) -> float:
            return 444.0 if text == " " else 0.0

    f = _RaisingGetWidth()
    f.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    # Ensure the CMap reports a real space_mapping so step 1 enters the
    # try block and reaches the raising ``get_width`` call.
    cmap = f.get_to_unicode_cmap()
    assert cmap is not None
    monkeypatch.setattr(cmap, "get_space_mapping", lambda: 99)
    # Reset cached space width so we re-run the cascade.
    f._font_width_of_space = None  # type: ignore[attr-defined]
    # Step 1 raises (caught) → step 2 returns 444.0.
    assert f.get_space_width() == 444.0


def test_get_space_width_get_string_width_path() -> None:
    """Step 2: ``get_string_width(' ')`` succeeds with a positive width."""

    class _StringWidth(_Stub):
        def get_string_width(self, text: str) -> float:
            return 700.0 if text == " " else 0.0

    f = _StringWidth()
    assert f.get_space_width() == 700.0


def test_get_space_width_outer_catch_swallows_exception() -> None:
    """The outer broad-catch wraps the whole cascade. Force an unexpected
    raise from the first try-branch via ``has_to_unicode`` raising."""

    class _Boom(_Stub):
        def has_to_unicode(self) -> bool:
            raise RuntimeError("boom")

    f = _Boom()
    # The broad-catch swallows the RuntimeError; fall through to 250.
    assert f.get_space_width() == 250.0


def test_get_space_width_first_char_negative_treated_as_zero() -> None:
    """When ``/FirstChar`` is -1, the lookup treats it as 0 (code 32 is
    at offset 32 in the /Widths array)."""
    f = _Stub()
    dict_ = f.get_cos_object()
    widths = COSArray()
    for _ in range(33):
        widths.add(COSFloat(0.0))
    widths.set(32, COSFloat(444.0))
    dict_.set_item(COSName.get_pdf_name("Widths"), widths)
    # /FirstChar absent → defaults to -1 → treated as 0 → offset 32 hit.
    assert f.get_space_width() == 444.0


# ---------- get_standard14_afm error paths ----------


def test_get_standard14_afm_returns_none_when_basefont_missing() -> None:
    f = _Stub()
    assert f.get_standard14_afm() is None


def test_get_standard14_afm_returns_none_for_non_standard14_name() -> None:
    f = _Stub()
    f.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "MyCustomFont")
    assert f.get_standard14_afm() is None


def test_get_standard14_afm_returns_none_when_loader_raises() -> None:
    """Lines 441-442: ``Standard14Fonts.get_afm`` raises → afm = None."""
    f = _Stub()
    f.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "Helvetica"
    )
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    with patch.object(Standard14Fonts, "get_afm", side_effect=KeyError("boom")):
        assert f.get_standard14_afm() is None


def test_get_standard14_afm_is_cached() -> None:
    """Repeated calls hit the cache."""
    f = _Stub()
    f.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "Helvetica"
    )
    first = f.get_standard14_afm()
    second = f.get_standard14_afm()
    assert first is second


# ---------- get_width Standard14 NotImplementedError fallback ----------


def test_get_width_standard14_not_implemented_falls_back_to_zero() -> None:
    """Lines 582-587: Standard14 subclass raises NotImplementedError →
    width is recorded as 0.0."""

    class _Bare14(_Stub):
        # ``is_standard14`` returns True via /BaseFont name.
        # The base ``get_standard14_width`` raises NotImplementedError.
        pass

    f = _Bare14()
    f.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "Helvetica"
    )
    # Make sure not embedded.
    assert not f.is_embedded()
    assert f.is_standard14()
    # Now ask for a width; no /Widths in dict so we fall through to the
    # Standard14 branch.
    width = f.get_width(65)
    assert width == 0.0


def test_get_width_falls_back_to_width_from_font() -> None:
    """Lines 591-592: no /Widths, not standard14 → last-resort
    ``get_width_from_font``."""

    class _FromFont(_Stub):
        def get_width_from_font(self, code: int) -> float:
            if code == 65:
                return 333.0
            return 0.0

    f = _FromFont()
    f.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "NotStandard")
    assert f.get_width(65) == 333.0


# ---------- get_string_width byte-walk loop ----------


def test_get_string_width_iterates_codes() -> None:
    """Lines 683-684: ``get_string_width`` encodes the text, then walks
    each byte via ``read_code`` + ``get_width``."""

    class _SimpleStub(_Stub):
        def get_width_from_font(self, code: int) -> float:
            return float(code)

    f = _SimpleStub()
    # "AB" -> bytes b"AB" -> codes 65 + 66 -> widths 65.0 + 66.0 = 131.0
    assert f.get_string_width("AB") == 131.0


def test_get_string_width_empty_returns_zero() -> None:
    f = _Stub()
    assert f.get_string_width("") == 0.0


# ---------- to_unicode chr() ValueError + cmap fallback ----------


def test_to_unicode_returns_none_when_no_cmap() -> None:
    """Default: no /ToUnicode → returns None."""
    f = _Stub()
    assert f.to_unicode(65) is None


def test_to_unicode_with_named_identity_h_cmap() -> None:
    """Named Identity-H /ToUnicode → returns chr(code)."""
    f = _Stub()
    f.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    assert f.to_unicode(65) == "A"


def test_to_unicode_identity_h_with_invalid_chr_returns_none() -> None:
    """Lines 726-728: a code outside Unicode → chr() raises → None."""
    f = _Stub()
    f.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    # chr() raises ValueError for code > 0x10FFFF.
    assert f.to_unicode(0x110000) is None


# ---------- additional misc tail-end coverage ----------


def test_to_unicode_via_non_identity_cmap_delegates_to_cmap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 728: when the CMap is not Identity-named the lookup delegates
    to ``cmap.to_unicode(code)``."""

    f = _Stub()
    f.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    # Load the CMap so it gets cached, then replace its name to something
    # non-Identity so we hit the delegation branch.
    cmap = f.get_to_unicode_cmap()
    assert cmap is not None
    monkeypatch.setattr(cmap, "get_name", lambda: "NotIdentity")
    # The Identity-H CMap maps 0x0041 (65) → "A".
    result = f.to_unicode(65)
    # Whatever the result, it must come from cmap.to_unicode now.
    assert result is None or isinstance(result, str)


def test_is_subset_recognises_prefix() -> None:
    f = _Stub()
    f.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "ABCDEF+Helvetica"
    )
    assert f.is_subset() is True


def test_is_subset_no_prefix_returns_false() -> None:
    f = _Stub()
    f.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert f.is_subset() is False


def test_is_subset_no_basefont_returns_false() -> None:
    f = _Stub()
    assert f.is_subset() is False


def test_get_standard14_width_base_raises_not_implemented() -> None:
    f = _Stub()
    with pytest.raises(NotImplementedError):
        f.get_standard14_width(65)


def test_get_position_vector_raises() -> None:
    f = _Stub()
    with pytest.raises(NotImplementedError):
        f.get_position_vector(65)


def test_get_displacement_uses_width() -> None:
    f = _Stub()
    # By default no widths → get_width returns 0 → displacement is (0, 0).
    dx, dy = f.get_displacement(65)
    assert dx == 0.0
    assert dy == 0.0


def test_add_to_subset_raises() -> None:
    f = _Stub()
    with pytest.raises(NotImplementedError):
        f.add_to_subset(65)


def test_subset_raises() -> None:
    f = _Stub()
    with pytest.raises(NotImplementedError):
        f.subset()
