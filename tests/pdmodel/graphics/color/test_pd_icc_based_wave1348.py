"""Coverage-boost tests for :mod:`pypdfbox.pdmodel.graphics.color.pd_icc_based`.

Targets the resource-cache create() path, the malformed-stream short-
circuit branches in ``set_alternate`` / ``set_alternate_color_spaces`` /
``clear_range``, the in-place ``set_range_for_component`` replace path,
and the to_rgb()/N-based-alternate inference fallbacks (N=1 -> Gray,
N=4 -> CMYK, N=2 -> None).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
from pypdfbox.pdmodel.pd_resources import PDResources

_N: COSName = COSName.get_pdf_name("N")
_RANGE: COSName = COSName.get_pdf_name("Range")


def _icc_array(n: int = 3) -> COSArray:
    array = COSArray()
    array.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_int(_N, n)
    array.add(stream)
    return array


def _broken_icc_array() -> COSArray:
    """An ICCBased COSArray whose slot-1 entry is NOT a stream, so
    ``_check_array`` would reject it but tests that already hold a
    constructed :class:`PDICCBased` can swap their internal array."""
    array = COSArray()
    array.add(COSName.get_pdf_name("ICCBased"))
    array.add(COSName.get_pdf_name("NotAStream"))
    return array


# ----------------------------------------------------------------------
# create() with a resource cache — lines 85-92
# ----------------------------------------------------------------------


def test_create_indirect_stream_uses_resource_cache_miss_then_hit() -> None:
    """When slot 1 is an indirect ``COSObject`` and the resources carry a
    cache, the first create stores into the cache and a subsequent create
    returns the cached :class:`PDICCBased` directly."""
    inner = COSStream()
    inner.set_int(_N, 3)
    indirect = COSObject(42, 0, resolved=inner)

    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    icc_array.add(indirect)

    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)

    first = PDICCBased.create(icc_array, resources)
    assert isinstance(first, PDICCBased)
    # Cache must hold it now.
    assert cache.get_color_space(indirect) is first

    # Second call: the cache hit returns the cached instance unchanged.
    second = PDICCBased.create(icc_array, resources)
    assert second is first


def test_create_indirect_stream_with_non_icc_cache_entry_replaces() -> None:
    """When the cache holds a non-``PDICCBased`` color space under the
    indirect, the create-path falls through to building a fresh
    PDICCBased and storing it."""
    inner = COSStream()
    inner.set_int(_N, 3)
    indirect = COSObject(99, 0, resolved=inner)

    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    icc_array.add(indirect)

    cache = DefaultResourceCache()
    # Plant a non-ICC color space in the cache slot.
    cache.put_color_space(indirect, PDDeviceRGB.INSTANCE)
    resources = PDResources(resource_cache=cache)

    space = PDICCBased.create(icc_array, resources)
    assert isinstance(space, PDICCBased)
    # The cache slot is now repointed at the freshly-built ICCBased.
    assert cache.get_color_space(indirect) is space


def test_create_indirect_stream_without_cache_short_circuits() -> None:
    """When the resources expose no cache the cache-path is skipped."""
    inner = COSStream()
    inner.set_int(_N, 3)
    indirect = COSObject(7, 0, resolved=inner)

    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    icc_array.add(indirect)

    resources = PDResources()  # No cache supplied.
    assert resources.get_resource_cache() is None
    space = PDICCBased.create(icc_array, resources)
    assert isinstance(space, PDICCBased)


def test_create_direct_stream_skips_cache_branch() -> None:
    """When slot 1 is a direct ``COSStream`` (not an indirect reference)
    the cache lookup is bypassed entirely."""
    icc_array = _icc_array(n=3)
    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)
    space = PDICCBased.create(icc_array, resources)
    assert isinstance(space, PDICCBased)


# ----------------------------------------------------------------------
# set_alternate when stream is malformed — line 198-199 / 201-202
# ----------------------------------------------------------------------


def test_set_alternate_none_short_circuits_when_stream_missing() -> None:
    """Line 201-202: a malformed ICCBased (slot 1 not a stream) returns
    silently from set_alternate(None) without raising."""
    cs = PDICCBased()
    cs._array = _broken_icc_array()
    # No-op rather than raising.
    cs.set_alternate(None)


def test_set_alternate_with_value_short_circuits_when_stream_missing() -> None:
    cs = PDICCBased()
    cs._array = _broken_icc_array()
    cs.set_alternate(PDDeviceRGB.INSTANCE)


def test_set_alternate_color_spaces_short_circuits_when_stream_missing() -> None:
    """Line 238: similar short-circuit on the list-form setter."""
    cs = PDICCBased()
    cs._array = _broken_icc_array()
    cs.set_alternate_color_spaces([PDDeviceRGB.INSTANCE])


def test_clear_range_short_circuits_when_stream_missing() -> None:
    """Line 272: ``clear_range`` is a no-op when the stream is absent."""
    cs = PDICCBased()
    cs._array = _broken_icc_array()
    cs.clear_range()


def test_set_range_short_circuits_when_stream_missing() -> None:
    cs = PDICCBased()
    cs._array = _broken_icc_array()
    cs.set_range(COSArray())


# ----------------------------------------------------------------------
# set_range_for_component in-place replace path — lines 314-315
# ----------------------------------------------------------------------


def test_set_range_for_component_replaces_existing_pair_in_place() -> None:
    """Lines 314-315: when ``/Range`` already has enough entries for the
    requested component the new pair overwrites in place via ``rng.set``."""
    cs = PDICCBased()
    cs.set_n(3)
    # Seed a 6-element /Range that already covers components 0..2.
    rng = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        rng.add(COSFloat(v))
    cs.set_range(rng)
    # Overwrite component 1 in place.
    cs.set_range_for_component(1, -2.5, 2.5)
    assert cs.get_range_for_component(0) == (0.0, 1.0)
    assert cs.get_range_for_component(1) == (-2.5, 2.5)
    assert cs.get_range_for_component(2) == (0.0, 1.0)


# ----------------------------------------------------------------------
# to_rgb fallback inference — lines 729, 732-735
# ----------------------------------------------------------------------


def test_to_rgb_falls_back_to_device_gray_for_n_1() -> None:
    """Line 729: when ``/N`` == 1 and no /Alternate is set, ``to_rgb``
    builds a PDColor in DeviceGray and dispatches."""
    cs = PDICCBased()
    cs.set_n(1)
    # No profile body -> _try_icc_to_rgb returns None -> fall through.
    rgb = cs.to_rgb([0.5])
    assert rgb is not None
    r, g, b = rgb
    assert r == g == b  # DeviceGray maps to equal R/G/B.


def test_to_rgb_falls_back_to_device_rgb_for_n_3() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    rgb = cs.to_rgb([0.25, 0.5, 0.75])
    assert rgb is not None


def test_to_rgb_falls_back_to_device_cmyk_for_n_4() -> None:
    """Lines 732-733: ``/N`` == 4 selects DeviceCMYK."""
    cs = PDICCBased()
    cs.set_n(4)
    rgb = cs.to_rgb([0.0, 0.0, 0.0, 0.5])
    assert rgb is not None


def test_to_rgb_returns_none_for_unsupported_n_2() -> None:
    """Lines 734-735: unsupported ``/N`` (here 2) returns None when no
    alternate is set."""
    cs = PDICCBased()
    cs.set_n(2)
    assert cs.to_rgb([0.5, 0.5]) is None


def test_to_rgb_uses_explicit_alternate_when_present() -> None:
    """When /Alternate IS set, the fallback inference branch is skipped."""
    cs = PDICCBased()
    cs.set_n(2)  # Unsupported via /N inference.
    cs.set_alternate(PDDeviceRGB.INSTANCE)
    rgb = cs.to_rgb([0.4, 0.6, 0.8])
    assert rgb is not None


# ----------------------------------------------------------------------
# _try_icc_to_rgb branches — lines 772-773, 776-777, 788-789, 803,
# 805-806, 808
# ----------------------------------------------------------------------


def test_try_icc_to_rgb_returns_none_when_profile_bytes_empty() -> None:
    """The early `if not profile_bytes: return None` exit."""
    cs = PDICCBased()
    cs.set_n(3)
    assert cs._try_icc_to_rgb([0.0, 0.0, 0.0]) is None


def test_try_icc_to_rgb_returns_none_for_unsupported_n() -> None:
    """``n not in (1, 3, 4)`` early-out."""
    cs = PDICCBased()
    cs.set_n(2)
    # Plant fake profile bytes so we get past the ``if not profile_bytes``
    # guard.
    stream = cs._get_stream()
    assert stream is not None
    with stream.create_output_stream() as out:
        out.write(b"\x00" * 200)
    assert cs._try_icc_to_rgb([0.5, 0.5]) is None


def test_try_icc_to_rgb_returns_none_when_components_too_short() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    stream = cs._get_stream()
    assert stream is not None
    with stream.create_output_stream() as out:
        out.write(b"\x00" * 200)
    assert cs._try_icc_to_rgb([0.5]) is None


def test_try_icc_to_rgb_returns_none_for_malformed_profile() -> None:
    """Lines 766-769: invalid ICC profile bytes raise inside
    ``ImageCms.ImageCmsProfile`` and the wrapper returns None."""
    pytest.importorskip("PIL.ImageCms")
    cs = PDICCBased()
    cs.set_n(3)
    stream = cs._get_stream()
    assert stream is not None
    # 200 bytes of zero is *not* a valid ICC profile — ImageCms raises.
    with stream.create_output_stream() as out:
        out.write(b"\x00" * 200)
    assert cs._try_icc_to_rgb([0.5, 0.5, 0.5]) is None


def test_try_icc_to_rgb_paths_n1_n4_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 775-794: exercise the n=1 and n=4 branches even though the
    transform itself will fail — the goal is to walk the per-n sample
    construction. Use a malformed profile so the inner build raises and
    we land on the `return None` exit at 805-806."""
    pytest.importorskip("PIL.ImageCms")
    for n, components in ((1, [0.5]), (4, [0.1, 0.2, 0.3, 0.4])):
        cs = PDICCBased()
        cs.set_n(n)
        stream = cs._get_stream()
        assert stream is not None
        with stream.create_output_stream() as out:
            out.write(b"\x00" * 200)
        assert cs._try_icc_to_rgb(components) is None


# ----------------------------------------------------------------------
# UnicodeDecodeError defensive branches — lines 444-445, 478-479, 525-526
#
# These ``except UnicodeDecodeError:`` blocks guard ``bytes.decode("ascii",
# errors="replace")`` calls. With ``errors="replace"`` the decode never
# raises, so these branches are defensive dead-code paths. To exercise
# them we monkey-patch ``bytes.decode`` indirectly by forcing decode to
# raise through a custom bytes-like subclass.
# ----------------------------------------------------------------------


class _SlicingProxy:
    """A bytes-like proxy whose ``__getitem__`` returns a custom object
    whose ``.decode`` raises :class:`UnicodeDecodeError`. ``bytes``
    slicing strips subclasses so we need a proxy that intercepts the
    slice itself."""

    def __init__(self, length: int) -> None:
        self._length = length

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, key: object) -> object:
        return _RaisingSlice()


class _RaisingSlice:
    def decode(self, *args: object, **kwargs: object) -> str:
        raise UnicodeDecodeError("ascii", b"", 0, 1, "synthetic")


def test_is_srgb_decode_failure_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 444-445: force the ``.decode`` call to raise
    UnicodeDecodeError so the defensive except branch executes."""
    cs = PDICCBased()
    monkeypatch.setattr(
        cs, "get_iccprofile_bytes", lambda: _SlicingProxy(128)
    )
    # device_model resolves to "" via the except branch; isRGB falls
    # back to /Alternate inspection and returns False because none is
    # set.
    assert cs.is_srgb() is False


def test_is_s_rgb_static_decode_failure_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 525-526: the static :meth:`is_s_rgb` returns False when
    decode raises. Pass the proxy directly — the length check passes
    because ``len()`` reports 128."""
    proxy = _SlicingProxy(128)
    assert PDICCBased.is_s_rgb(proxy) is False  # type: ignore[arg-type]


def test_get_color_space_type_decode_failure_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 478-479: force decode to raise inside
    :meth:`get_color_space_type` so the except branch fires; the empty
    signature falls through to the /N-based inference."""
    cs = PDICCBased()
    cs.set_n(3)
    monkeypatch.setattr(
        cs, "get_iccprofile_bytes", lambda: _SlicingProxy(128)
    )
    # signature becomes "" — falls back to /N=3 → TYPE_RGB.
    from pypdfbox.pdmodel.graphics.color.pd_icc_based import TYPE_RGB

    assert cs.get_color_space_type() == TYPE_RGB
