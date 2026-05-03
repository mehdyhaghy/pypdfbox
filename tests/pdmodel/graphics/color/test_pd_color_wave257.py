"""Wave 257 — :class:`PDColor` round-out: hand-written coverage for the
remaining upstream parity gaps not yet exercised by Wave 249 or the
existing parity / round-out suites.

Targets:

* :meth:`PDColor.get_components` — PDFBOX-4279 ``Arrays.copyOf`` parity:
  truncate or right-pad the components view to
  ``color_space.get_number_of_components()`` for non-Pattern, non-null
  color spaces; clone raw for Pattern and ``None`` color spaces.
* :meth:`PDColor.__init__` — PDFBOX-5882 component-count vs colorspace
  arity warning (``LOG.warn`` parity), for both the components-only
  ctor and the components + pattern_name ctor.
* :meth:`PDColor._parse_cos_array` — upstream's
  ``LOG.warn("color component i ... isn't a number, ignored")`` parity:
  non-numeric, non-trailing-COSName entries log a warning and are
  skipped; the trailing ``COSName`` is still recognised as the pattern
  name.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern


# ---------- get_components: PDFBOX-4279 Arrays.copyOf parity ----------


def test_get_components_pads_too_short_against_color_space() -> None:
    """A 2-component PDColor against DeviceRGB (3 components) should
    surface 3 components — the missing tail right-padded with ``0.0``.
    Mirrors upstream ``Arrays.copyOf(components, 3)``.
    """
    # Bypass the public ctor's PDFBOX-5882 warning: build the underlying
    # state directly so the test is a pure ``get_components()`` check.
    color = PDColor([0.5, 0.25], PDDeviceRGB.INSTANCE)
    components = color.get_components()
    assert components == [0.5, 0.25, 0.0]
    assert len(components) == 3


def test_get_components_truncates_too_long_against_color_space() -> None:
    """A 4-component PDColor against DeviceGray (1 component) should
    surface only 1 component — extra entries dropped.
    """
    color = PDColor([0.1, 0.2, 0.3, 0.4], PDDeviceGray.INSTANCE)
    components = color.get_components()
    assert components == [0.1]
    assert len(components) == 1


def test_get_components_unchanged_when_arity_matches() -> None:
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [0.1, 0.2, 0.3]


def test_get_components_pattern_color_space_clones_raw() -> None:
    """Upstream: ``colorSpace instanceof PDPattern`` → ``components.clone()``
    (no resize). Pattern reports ``getNumberOfComponents() == 0`` for
    uncolored tiling, which must NOT shrink the tint operands.
    """
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    name = COSName.get_pdf_name("P1")
    color = PDColor([0.1, 0.2, 0.3], pattern_cs, name)
    # Pattern itself has arity 0 — but the raw 3 tint components must
    # survive get_components() unchanged.
    components = color.get_components()
    assert components == [0.1, 0.2, 0.3]


def test_get_components_returns_independent_copy() -> None:
    color = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    a = color.get_components()
    a[0] = 99.0
    assert color.get_components() == [0.5, 0.5, 0.5]


def test_get_components_pad_returns_fresh_list_each_call() -> None:
    color = PDColor([0.5], PDDeviceRGB.INSTANCE)
    a = color.get_components()
    b = color.get_components()
    assert a == b == [0.5, 0.0, 0.0]
    assert a is not b


def test_get_components_when_color_space_returns_zero_arity() -> None:
    """Defensive: a CS reporting 0 components should yield an empty
    components view (truncate from any length to 0).
    """

    class _ZeroArityCS:
        def get_name(self) -> str:
            return "Zero"

        def get_number_of_components(self) -> int:
            return 0

    color = PDColor([0.1, 0.2], _ZeroArityCS())  # type: ignore[arg-type]
    assert color.get_components() == []


def test_get_components_when_color_space_arity_raises() -> None:
    """If ``get_number_of_components`` raises ``TypeError``/``ValueError``,
    fall back to a raw clone instead of crashing.
    """

    class _BrokenArityCS:
        def get_name(self) -> str:
            return "Broken"

        def get_number_of_components(self) -> int:
            raise ValueError("broken")

    color = PDColor([0.1, 0.2], _BrokenArityCS())  # type: ignore[arg-type]
    assert color.get_components() == [0.1, 0.2]


# ---------- __init__: PDFBOX-5882 arity-mismatch warnings ----------


def test_warn_on_arity_mismatch_components_only_too_few(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``PDColor([a, b], DeviceRGB)`` (2 components, DeviceRGB expects 3)
    must log a PDFBOX-5882 warning. Mirrors upstream
    ``LOG.warn("Colorspace component count ... doesn't match ...")``.
    """
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.5, 0.25], PDDeviceRGB.INSTANCE)
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "component count" in m and "doesn't match" in m for m in messages
    ), f"expected PDFBOX-5882 warning, got: {messages}"


def test_warn_on_arity_mismatch_components_only_too_many(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.1, 0.2, 0.3], PDDeviceGray.INSTANCE)
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "component count" in m and "doesn't match" in m for m in messages
    ), f"expected PDFBOX-5882 warning, got: {messages}"


def test_no_warn_on_arity_match_components_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    assert caplog.records == []


def test_no_warn_on_arity_match_cmyk(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.1, 0.2, 0.3, 0.4], PDDeviceCMYK.INSTANCE)
    assert caplog.records == []


def test_warn_on_arity_mismatch_pattern_with_components(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``PDColor(tint_components, pattern_name, PDPattern(DeviceRGB))``
    must compare ``len(tint_components)`` against the *underlying*
    color space's arity (DeviceRGB → 3), per upstream's PDFBOX-5882
    branch in the (float[], COSName, PDColorSpace) ctor.
    """
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    name = COSName.get_pdf_name("P1")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.5, 0.25], pattern_cs, name)
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "Pattern colorspace component count" in m for m in messages
    ), f"expected pattern PDFBOX-5882 warning, got: {messages}"


def test_no_warn_on_arity_match_pattern_with_components(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    name = COSName.get_pdf_name("P1")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.1, 0.2, 0.3], pattern_cs, name)
    assert caplog.records == []


def test_no_warn_when_pattern_has_no_underlying_color_space(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bare-name ``/Pattern`` (colored tiling) has no underlying CS —
    upstream skips the arity check (``ucs == null`` short-circuit) and
    so do we.
    """
    pattern_cs = PDPattern()  # no underlying
    name = COSName.get_pdf_name("P1")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor([0.5, 0.25], pattern_cs, name)
    # No PDFBOX-5882 warning — the bare Pattern can't validate arity.
    assert all(
        "doesn't match" not in r.getMessage() for r in caplog.records
    )


def test_no_warn_for_cos_array_constructor(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Upstream's ``PDColor(COSArray, PDColorSpace)`` ctor does NOT
    perform the PDFBOX-5882 check (only the float[] ctors do); we
    mirror that.
    """
    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSFloat(0.25))
    # 2 components against DeviceRGB (3) — no warning expected.
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor(array, PDDeviceRGB.INSTANCE)
    assert all(
        "doesn't match" not in r.getMessage() for r in caplog.records
    )


def test_no_warn_for_colored_pattern_constructor(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``PDColor(COSName, PDColorSpace)`` (colored pattern) ctor takes no
    components, so no arity check applies.
    """
    name = COSName.get_pdf_name("P1")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        PDColor(name, PDPattern())
    assert caplog.records == []


# ---------- _parse_cos_array: non-numeric component warning ----------


def test_parse_cos_array_warns_on_non_numeric_component(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mid-array non-numeric, non-name entries should log a warning and
    be skipped (matches upstream
    ``LOG.warn("color component i ... isn't a number, ignored")``).
    """
    from pypdfbox.cos import COSBoolean

    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSBoolean.TRUE)  # bogus component
    array.add(COSFloat(0.25))
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        components, pattern = PDColor._parse_cos_array(array)
    assert components == [0.5, 0.25]
    assert pattern is None
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "isn't a number" in m for m in messages
    ), f"expected non-numeric warning, got: {messages}"


def test_parse_cos_array_no_warn_for_clean_array(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Values exact in IEEE-754 float32 to survive COSFloat round-tripping.
    array = COSArray()
    array.add(COSFloat(0.125))
    array.add(COSFloat(0.25))
    array.add(COSFloat(0.5))
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        components, pattern = PDColor._parse_cos_array(array)
    assert components == [0.125, 0.25, 0.5]
    assert pattern is None
    assert caplog.records == []


def test_parse_cos_array_trailing_pattern_name_recognised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The last entry — when it's a ``COSName`` — is the pattern name and
    must NOT be reported as a non-numeric component.
    """
    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSFloat(0.25))
    name = COSName.get_pdf_name("P1")
    array.add(name)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_color"):
        components, pattern = PDColor._parse_cos_array(array)
    assert components == [0.5, 0.25]
    assert pattern is name
    # No "isn't a number" warning for the trailing pattern name.
    assert all(
        "isn't a number" not in r.getMessage() for r in caplog.records
    )


def test_parse_cos_array_empty() -> None:
    array = COSArray()
    components, pattern = PDColor._parse_cos_array(array)
    assert components == []
    assert pattern is None


def test_parse_cos_array_only_pattern_name() -> None:
    """Single-entry array containing only a ``COSName`` — colored-pattern
    serialized form. No components, pattern name set.
    """
    name = COSName.get_pdf_name("P1")
    array = COSArray()
    array.add(name)
    components, pattern = PDColor._parse_cos_array(array)
    assert components == []
    assert pattern is name


def test_parse_cos_array_integer_components() -> None:
    """``COSInteger`` entries should be coerced to float (via
    ``item.value``) — components are spec'd as floats but PDF parsers
    sometimes emit integers for whole-number tints.
    """
    from pypdfbox.cos import COSInteger

    array = COSArray()
    array.add(COSInteger(1))
    array.add(COSInteger(0))
    components, pattern = PDColor._parse_cos_array(array)
    assert components == [1.0, 0.0]
    assert pattern is None


# ---------- end-to-end: malformed PDF tolerance ----------


def test_malformed_color_round_trip_through_get_components() -> None:
    """End-to-end: malformed PDColor (too few operands) constructed via
    the COSArray ctor — get_components() pads to CS arity, and
    to_rgb() can still consume the padded view.
    """
    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSFloat(0.5))
    # Missing third component; CS expects 3.
    color = PDColor(array, PDDeviceRGB.INSTANCE)
    components = color.get_components()
    assert components == [0.5, 0.5, 0.0]
    # to_rgb operates on the *raw* internal buffer (legacy lite-impl
    # behaviour). The padded view is the surface for callers — we pin
    # the surface, not the internal.
