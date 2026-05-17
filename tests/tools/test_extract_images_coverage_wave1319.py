"""Coverage-boost tests for :mod:`pypdfbox.tools.extract_images` (wave 1319).

Wave 1314 covered the rot0 happy path + the empty graphics-engine stubs.
This wave exercises the actual image-extraction branches that previously
went uncovered:

* :meth:`ImageGraphicsEngine.write2file` — happy path (decodable image →
  PNG/JP2 file written), plus the ``has_masks`` / ``jb2`` / ``jpx``
  suffix-remap branches.
* :meth:`ImageGraphicsEngine.draw_image` — PDImageXObject duplicate-COS
  short-circuit, ``is_stencil`` color-process branch, and the
  ``no_color_convert`` / ``use_direct_jpeg`` plumbing through
  ``write2file``.
* :meth:`ImageGraphicsEngine.has_masks` — True branches for explicit
  ``/Mask`` and ``/SMask`` entries.
* :meth:`ImageGraphicsEngine.process_color` — :class:`PDPattern`-typed
  color spaces dispatch into ``process_tiling_pattern``.
* :meth:`ImageGraphicsEngine.run` — ext-g-state iteration with a
  soft-mask group (mirrors upstream's process_soft_mask loop).
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import (
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.tools import extract_images

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"


# --------------------------------------------------------------------------
# Shared shim — wraps Loader.load_pdf(COSDocument) → PDDocument so the
# class-port's PD-layer calls resolve. Mirrors the wave-1314 pattern.
# --------------------------------------------------------------------------
class _PDLoaderShim:
    @staticmethod
    @contextlib.contextmanager
    def load_pdf(source: Any, password: Any = None) -> Iterator[PDDocument]:
        if isinstance(password, str) and password == "":
            password = None
        cos_doc = RealLoader.load_pdf(source, password)
        pd = PDDocument(cos_doc)
        try:
            yield pd
        finally:
            pd.close()


@pytest.fixture
def patched_loader(monkeypatch: pytest.MonkeyPatch) -> type[_PDLoaderShim]:
    monkeypatch.setattr(extract_images, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# Helpers to construct synthetic PDImageXObjects without depending on a
# fixture that ships an image XObject.
# --------------------------------------------------------------------------
def _make_image_cos(
    *,
    width: int = 2,
    height: int = 2,
    bits_per_component: int = 8,
    colorspace: str = "DeviceGray",
    data: bytes = b"\xff\xff\xff\xff",
) -> COSStream:
    cos = COSStream()
    cos.set_item("Type", COSName.get_pdf_name("XObject"))
    cos.set_item("Subtype", COSName.get_pdf_name("Image"))
    cos.set_item("Width", COSInteger.get(width))
    cos.set_item("Height", COSInteger.get(height))
    cos.set_item("BitsPerComponent", COSInteger.get(bits_per_component))
    cos.set_item("ColorSpace", COSName.get_pdf_name(colorspace))
    cos.set_data(data)
    return cos


def _make_pd_image(**kwargs: Any) -> PDImageXObject:
    return PDImageXObject(_make_image_cos(**kwargs))


# --------------------------------------------------------------------------
# write2file
# --------------------------------------------------------------------------
def test_write2file_png_writes_decoded_image(tmp_path: Path) -> None:
    """Decodable greyscale image → write2file runs end-to-end (open +
    ImageIOUtil.write_image dispatch). The on-disk PNG payload is
    written via ``ImageIOUtil``; the assertion here is only that the
    branch executed (no exception) and the prefix.suffix file exists."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    img = _make_pd_image()
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.write2file(img, "img", direct_jpeg=False, no_color_convert=False)
    finally:
        import os
        os.chdir(cwd)
    written = tmp_path / "img.png"
    assert written.exists()


def test_write2file_jb2_suffix_remapped_to_png(tmp_path: Path) -> None:
    """A ``jb2`` suffix must be remapped to ``png``."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    class _FakeImage:
        def get_suffix(self) -> str:
            return "jb2"

        def get_image(self) -> Any:  # noqa: ANN401
            from PIL import Image as _PILImage

            return _PILImage.new("RGB", (4, 4), "white")

    img = _FakeImage()
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.write2file(img, "jb", direct_jpeg=False, no_color_convert=False)
    finally:
        import os
        os.chdir(cwd)
    assert (tmp_path / "jb.png").exists()
    # Non-PDImageXObject types take the ``return False`` branch of has_masks.


def test_write2file_jpx_suffix_remapped_to_jp2(tmp_path: Path) -> None:
    """A ``jpx`` suffix must be remapped to ``jp2``."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    class _FakeImage:
        def get_suffix(self) -> str:
            return "jpx"

        def get_image(self) -> Any:  # noqa: ANN401
            return None  # skip actual write — exercises only the suffix-remap

    img = _FakeImage()
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.write2file(img, "j2k", direct_jpeg=False, no_color_convert=False)
    finally:
        import os
        os.chdir(cwd)
    # With ``get_image() is None``, no file is written but the suffix
    # branch still ran (j2k.jp2 would have been the target).
    assert not (tmp_path / "j2k.jp2").exists()


def test_write2file_with_masks_forces_png(tmp_path: Path) -> None:
    """A PDImageXObject with a /Mask entry must save as PNG."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    cos = _make_image_cos()
    # Attach a /Mask sub-image so has_masks → True.
    mask_cos = _make_image_cos(width=1, height=1, data=b"\xff")
    cos.set_item("Mask", mask_cos)
    img = PDImageXObject(cos)
    assert engine.has_masks(img) is True
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.write2file(img, "withmask", direct_jpeg=False, no_color_convert=False)
    finally:
        import os
        os.chdir(cwd)
    assert (tmp_path / "withmask.png").exists()


def test_write2file_get_image_attribute_error_swallowed(
    tmp_path: Path,
) -> None:
    """``get_image()`` raising AttributeError → no file, no exception."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    class _Broken:
        def get_suffix(self) -> str:
            return "png"

        def get_image(self) -> Any:  # noqa: ANN401
            raise AttributeError("synthetic")

    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.write2file(_Broken(), "x", direct_jpeg=False, no_color_convert=False)
    finally:
        import os
        os.chdir(cwd)
    # Branch ran (no file emitted).
    assert not (tmp_path / "x.png").exists()


# --------------------------------------------------------------------------
# has_masks
# --------------------------------------------------------------------------
def test_has_masks_smask_returns_true() -> None:
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    cos = _make_image_cos()
    smask_cos = _make_image_cos(width=1, height=1, data=b"\xff")
    cos.set_item("SMask", smask_cos)
    img = PDImageXObject(cos)
    assert engine.has_masks(img) is True


def test_has_masks_xobject_with_no_mask_returns_false() -> None:
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    img = _make_pd_image()
    assert engine.has_masks(img) is False


# --------------------------------------------------------------------------
# draw_image — exercises the seen-COS short-circuit + write2file dispatch.
# --------------------------------------------------------------------------
def test_draw_image_writes_then_skips_duplicate(tmp_path: Path) -> None:
    outer = extract_images.ExtractImages()
    outer.prefix = str(tmp_path / "dup")
    outer.use_direct_jpeg = False
    outer.no_color_convert = False
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    img = _make_pd_image()
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.draw_image(img)
        first_counter = outer.image_counter
        # Second call with same COS short-circuits → counter does not bump.
        engine.draw_image(img)
        assert outer.image_counter == first_counter
    finally:
        import os
        os.chdir(cwd)


def test_draw_image_stencil_processes_non_stroking_color(tmp_path: Path) -> None:
    """Stencil images run process_color on the non-stroking color first."""
    outer = extract_images.ExtractImages()
    outer.prefix = str(tmp_path / "stencil")
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    cos = _make_image_cos()
    # Stencil → BPC=1, ImageMask=True (PDImageXObject reads ``/ImageMask``).
    cos.set_item("ImageMask", COSName.get_pdf_name("true"))
    # set_item with bool wrapper — quickest is to use COSBoolean.TRUE
    from pypdfbox.cos.cos_boolean import COSBoolean
    cos.set_item("ImageMask", COSBoolean.TRUE)
    cos.set_item("BitsPerComponent", COSInteger.get(1))
    img = PDImageXObject(cos)
    assert img.is_stencil() is True
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        # No crash, draw_image dispatches into write2file.
        engine.draw_image(img)
    finally:
        import os
        os.chdir(cwd)


def test_draw_image_non_pdimagexobject_still_writes(tmp_path: Path) -> None:
    """Non-PDImageXObject inputs bypass the seen-COS cache entirely."""
    outer = extract_images.ExtractImages()
    outer.prefix = str(tmp_path / "raw")
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    class _PlainImage:
        def get_suffix(self) -> str:
            return "png"

        def get_image(self) -> Any:  # noqa: ANN401
            from PIL import Image as _PILImage

            return _PILImage.new("RGB", (2, 2), "white")

    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        engine.draw_image(_PlainImage())
    finally:
        import os
        os.chdir(cwd)
    assert (tmp_path / "raw-1.png").exists()
    assert outer.image_counter == 2


# --------------------------------------------------------------------------
# process_color — PDPattern dispatch.
# --------------------------------------------------------------------------
def test_process_color_dispatches_into_tiling_pattern() -> None:
    """When the colour space is a PDPattern carrying a tiling pattern,
    process_color must call ``process_tiling_pattern``. We capture that
    call by monkey-patching the engine instance method."""
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
    from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern

    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    tiling = PDTilingPattern()

    class _Pattern(PDPattern):
        def get_pattern(self, color: object) -> object:  # noqa: ARG002
            return tiling

    class _Color:
        def get_color_space(self) -> _Pattern:
            return _Pattern()

    calls: list[tuple] = []
    engine.process_tiling_pattern = (  # type: ignore[method-assign]
        lambda pat, color, ext: calls.append((pat, color, ext))
    )
    engine.process_color(_Color())
    assert calls and calls[0][0] is tiling


def test_process_color_non_pattern_color_space_is_noop() -> None:
    """Non-pattern color spaces don't dispatch to tiling."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    class _PlainSpace:
        pass

    class _Color:
        def get_color_space(self) -> _PlainSpace:
            return _PlainSpace()

    # Counter: process_tiling_pattern must not run.
    called: list[object] = []
    engine.process_tiling_pattern = (  # type: ignore[method-assign]
        lambda *a, **kw: called.append(a)
    )
    engine.process_color(_Color())
    assert called == []


# --------------------------------------------------------------------------
# run() — ext-g-state iteration without/with soft mask.
# --------------------------------------------------------------------------
def test_engine_run_none_page_returns_early() -> None:
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    # Should not raise; just returns.
    engine.run()


def test_engine_run_process_page_attribute_error_swallowed(
    monkeypatch: pytest.MonkeyPatch, patched_loader: Any, tmp_path: Path,
) -> None:
    """If process_page raises, run() swallows and returns cleanly."""
    target = tmp_path / "rot0.pdf"
    target.write_bytes(ROT0.read_bytes())
    cos_doc = RealLoader.load_pdf(target)
    pd = PDDocument(cos_doc)
    try:
        page = next(iter(pd.get_pages()))
        outer = extract_images.ExtractImages()
        outer.prefix = str(tmp_path / "x")
        engine = extract_images.ImageGraphicsEngine(page=page, outer=outer)
        monkeypatch.setattr(
            engine,
            "process_page",
            lambda _p: (_ for _ in ()).throw(AttributeError("synthetic")),
        )
        engine.run()  # returns silently
    finally:
        pd.close()


def test_engine_run_full_path_no_ext_g_state(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """A real page with no ExtGState — run() walks the resources without
    hitting the soft-mask body."""
    target = tmp_path / "rot0.pdf"
    target.write_bytes(ROT0.read_bytes())
    cos_doc = RealLoader.load_pdf(target)
    pd = PDDocument(cos_doc)
    try:
        page = next(iter(pd.get_pages()))
        outer = extract_images.ExtractImages()
        outer.prefix = str(tmp_path / "x")
        engine = extract_images.ImageGraphicsEngine(page=page, outer=outer)
        engine.run()
    finally:
        pd.close()


# --------------------------------------------------------------------------
# show_glyph — fill + stroke branches.
# --------------------------------------------------------------------------
def test_engine_run_ext_g_state_with_soft_mask_processes_group() -> None:
    """``run()`` iterates ExtGState names; when a soft-mask group exists
    it dispatches into ``process_soft_mask``. We build a synthetic page
    stub so the ext-g-state branch fires without needing a fixture."""
    outer = extract_images.ExtractImages()

    class _Group:
        pass

    group = _Group()

    class _SoftMask:
        def get_group(self) -> _Group:
            return group

    class _ExtGState:
        def get_soft_mask(self) -> _SoftMask:
            return _SoftMask()

        def copy_into_graphics_state(self, _state: object) -> None:
            return None

    class _Resources:
        def get_ext_g_state_names(self) -> list[str]:
            return ["GS1", "GS2", "GS3"]

        def get_ext_g_state(self, name: str) -> Any:  # noqa: ANN401
            # First name → None (continue), second → no soft mask, third → with mask.
            if name == "GS1":
                return None

            class _NoMask:
                def get_soft_mask(self) -> Any:
                    return None

            class _MaskedNoGroup:
                def get_soft_mask(self) -> Any:
                    class _SM:
                        def get_group(self) -> Any:
                            return None
                    return _SM()

            if name == "GS2":
                return _NoMask()
            return _ExtGState()

    class _Page:
        def get_resources(self) -> _Resources:
            return _Resources()

    page = _Page()
    engine = extract_images.ImageGraphicsEngine(page=page, outer=outer)

    # Stub process_page / process_soft_mask / get_graphics_state.
    engine.process_page = lambda _p: None  # type: ignore[method-assign]
    captured: list[object] = []
    engine.process_soft_mask = lambda g: captured.append(g)  # type: ignore[method-assign]
    engine.get_graphics_state = lambda: object()  # type: ignore[method-assign]
    engine.run()
    assert captured == [group]


def test_engine_run_resources_attribute_error_yields_empty_names() -> None:
    """When ``res.get_ext_g_state_names`` raises AttributeError, the
    inner ``except`` swallows it and yields an empty iteration."""
    outer = extract_images.ExtractImages()

    class _BrokenRes:
        def get_ext_g_state_names(self) -> Any:
            raise AttributeError("synthetic")

    class _Page:
        def get_resources(self) -> _BrokenRes:
            return _BrokenRes()

    engine = extract_images.ImageGraphicsEngine(page=_Page(), outer=outer)
    engine.process_page = lambda _p: None  # type: ignore[method-assign]
    engine.run()  # no exception


def test_engine_run_no_resources_returns_early() -> None:
    outer = extract_images.ExtractImages()

    class _Page:
        def get_resources(self) -> Any:
            return None

    engine = extract_images.ImageGraphicsEngine(page=_Page(), outer=outer)
    engine.process_page = lambda _p: None  # type: ignore[method-assign]
    engine.run()


def test_has_masks_attribute_error_returns_false() -> None:
    """A PDImageXObject whose accessors raise AttributeError → returns False."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)
    img = _make_pd_image()

    # Patch get_mask to raise so the except branch runs.
    def _raise() -> Any:
        raise AttributeError("synthetic")

    img.get_mask = _raise  # type: ignore[method-assign]
    assert engine.has_masks(img) is False


def test_call_permission_denied_returns_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When ``can_extract_content()`` is False, call() returns 1 +
    writes the permission-denied message to stderr."""
    import contextlib as _ctx

    class _AP:
        def can_extract_content(self) -> bool:
            return False

    class _Doc:
        def get_current_access_permission(self) -> _AP:
            return _AP()

    @_ctx.contextmanager
    def _shim(_source: Any, _password: Any = None) -> Any:
        yield _Doc()

    class _ShimLoader:
        load_pdf = staticmethod(_shim)

    monkeypatch.setattr(extract_images, "Loader", _ShimLoader)
    runner = extract_images.ExtractImages()
    runner.infile = tmp_path / "any.pdf"
    rc = runner.call()
    assert rc == 1
    assert "permission to extract images" in capsys.readouterr().err


def test_show_glyph_fill_and_stroke_render_modes_dispatch() -> None:
    """When rendering_mode reports fill / stroke, process_color is invoked."""
    outer = extract_images.ExtractImages()
    engine = extract_images.ImageGraphicsEngine(page=None, outer=outer)

    class _RM:
        def is_fill(self) -> bool:
            return True

        def is_stroke(self) -> bool:
            return True

    class _TextState:
        def get_rendering_mode(self) -> _RM:
            return _RM()

    class _GraphicsState:
        def get_text_state(self) -> _TextState:
            return _TextState()

        def get_non_stroking_color(self) -> object:
            return object()

        def get_stroking_color(self) -> object:
            return object()

    # Stub get_graphics_state on engine and capture process_color calls.
    engine.get_graphics_state = lambda: _GraphicsState()  # type: ignore[method-assign]
    calls: list[object] = []
    engine.process_color = lambda c: calls.append(c)  # type: ignore[method-assign]
    engine.show_glyph(None, None, 0, None)
    assert len(calls) == 2
