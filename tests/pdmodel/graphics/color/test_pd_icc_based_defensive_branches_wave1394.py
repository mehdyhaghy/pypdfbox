"""Wave 1394 — defensive branches in
``PDICCBased._try_icc_to_rgb`` and ``_try_icc_to_rgb_image``.

Covers lines 927, 944-948, 984, 987, 1003-1011, 1013 in
``pypdfbox.pdmodel.graphics.color.pd_icc_based``.

Strategy: rather than mock Pillow (which would create brittle
internal-detail tests), build ICC-based color spaces whose
``profile_bytes`` / ``/N`` / ``_resolve_in_mode`` result steer the
branch the test wants to hit. For the exception paths we feed the
methods a profile that ``ImageCms`` rejects.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased


def _make_icc_based(profile_bytes: bytes, n: int) -> PDICCBased:
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), n)
    with stream.create_output_stream() as out:
        out.write(profile_bytes)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(stream)
    return PDICCBased(arr)


def _make_icc_profile(
    *,
    color_space: bytes = b"RGB ",
    device_class: bytes = b"mntr",
    pcs: bytes = b"XYZ ",
    size: int = 128,
) -> bytes:
    header = bytearray(size)
    header[0:4] = size.to_bytes(4, "big", signed=False)
    header[12:16] = device_class
    header[16:20] = color_space
    header[20:24] = pcs
    return bytes(header)


# ---------- _try_icc_to_rgb defensive branches ----------


def test_try_icc_to_rgb_returns_none_when_n_invalid() -> None:
    """``_try_icc_to_rgb`` bails when /N is outside {1, 3, 4} (line 921)."""
    cs = _make_icc_based(_make_icc_profile(), n=5)
    assert cs._try_icc_to_rgb([0.5, 0.5, 0.5, 0.5, 0.5]) is None  # noqa: SLF001


def test_try_icc_to_rgb_returns_none_when_components_too_few() -> None:
    """Components shorter than /N — defensive (line 922-923)."""
    cs = _make_icc_based(_make_icc_profile(color_space=b"RGB "), n=3)
    assert cs._try_icc_to_rgb([0.5]) is None  # noqa: SLF001


def test_try_icc_to_rgb_returns_none_when_in_mode_unresolvable() -> None:
    """``_resolve_in_mode`` returns ``None`` for an unknown signature +
    /N outside the supported set — but /N must still be in {1,3,4}.
    Force the in-mode path to fail by feeding a too-short profile *and*
    /N=2 (line 927 via the n-check; or use direct monkeypatch)."""
    cs = _make_icc_based(_make_icc_profile(color_space=b"RGB "), n=3)

    # Direct test of line 927: monkeypatch _resolve_in_mode to return None.
    def _none_mode(_profile: bytes) -> str | None:
        return None

    cs._resolve_in_mode = _none_mode  # type: ignore[method-assign]  # noqa: SLF001
    assert cs._try_icc_to_rgb([0.0, 0.0, 0.0]) is None  # noqa: SLF001


def test_try_icc_to_rgb_returns_none_on_pillow_apply_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ImageCms.applyTransform`` raises — lines 944-948."""
    cs = _make_icc_based(_make_icc_profile(color_space=b"RGB "), n=3)

    try:
        from PIL import Image, ImageCms
    except ImportError:
        pytest.skip("Pillow not available")

    # Make _get_transform succeed (so we don't trip the earlier return).
    fake_transform = object()
    monkeypatch.setattr(cs, "_get_transform", lambda *a, **kw: fake_transform)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise ImageCms.PyCMSError("simulated apply failure")

    monkeypatch.setattr(ImageCms, "applyTransform", _boom)
    monkeypatch.setattr(Image, "new", lambda *a, **kw: object())

    assert cs._try_icc_to_rgb([0.5, 0.5, 0.5]) is None  # noqa: SLF001


# ---------- _try_icc_to_rgb_image defensive branches ----------


def test_try_icc_to_rgb_image_returns_none_when_n_invalid() -> None:
    """``/N`` outside {1,3,4} → ``None`` (line 983-984)."""
    cs = _make_icc_based(_make_icc_profile(), n=5)
    assert cs._try_icc_to_rgb_image(b"\x00" * 12, 2, 2) is None  # noqa: SLF001


def test_try_icc_to_rgb_image_returns_none_when_in_mode_unresolvable() -> None:
    """``_resolve_in_mode`` returns ``None`` (line 986-987)."""
    cs = _make_icc_based(_make_icc_profile(color_space=b"RGB "), n=3)
    cs._resolve_in_mode = lambda _profile: None  # type: ignore[method-assign]  # noqa: SLF001
    assert cs._try_icc_to_rgb_image(b"\x00" * 12, 2, 2) is None  # noqa: SLF001


def test_try_icc_to_rgb_image_returns_none_on_pillow_apply_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ImageCms.applyTransform`` raises — lines 1003-1011."""
    cs = _make_icc_based(_make_icc_profile(color_space=b"RGB "), n=3)

    try:
        from PIL import Image, ImageCms
    except ImportError:
        pytest.skip("Pillow not available")

    fake_transform = object()
    monkeypatch.setattr(cs, "_get_transform", lambda *a, **kw: fake_transform)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise ImageCms.PyCMSError("simulated bulk apply failure")

    monkeypatch.setattr(ImageCms, "applyTransform", _boom)
    monkeypatch.setattr(Image, "frombytes", lambda *a, **kw: object())

    assert cs._try_icc_to_rgb_image(b"\x00" * 12, 2, 2) is None  # noqa: SLF001


def test_try_icc_to_rgb_image_returns_none_when_apply_yields_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``applyTransform`` returns ``None`` → line 1012-1013."""
    cs = _make_icc_based(_make_icc_profile(color_space=b"RGB "), n=3)

    try:
        from PIL import Image, ImageCms
    except ImportError:
        pytest.skip("Pillow not available")

    fake_transform = object()
    monkeypatch.setattr(cs, "_get_transform", lambda *a, **kw: fake_transform)
    monkeypatch.setattr(Image, "frombytes", lambda *a, **kw: object())
    monkeypatch.setattr(ImageCms, "applyTransform", lambda *a, **kw: None)
    assert cs._try_icc_to_rgb_image(b"\x00" * 12, 2, 2) is None  # noqa: SLF001
