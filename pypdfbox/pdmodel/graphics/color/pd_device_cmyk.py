from __future__ import annotations

from typing import Any, ClassVar

from .pd_color import PDColor
from .pd_device_color_space import PDDeviceColorSpace


class PDDeviceCMYK(PDDeviceColorSpace):
    """Allows colors to be specified according to the subtractive CMYK
    (cyan, magenta, yellow, black) model typical of printers and other
    paper-based output devices. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceCMYK``. Use the
    singleton ``PDDeviceCMYK.INSTANCE``.

    Lite surface: both ``to_rgb`` (scalar) and ``to_rgb_image`` (raster)
    use the textbook subtractive CMYK to RGB transform::

        R = (1 - C) * (1 - K) * 255
        G = (1 - M) * (1 - K) * 255
        B = (1 - Y) * (1 - K) * 255

    The upstream class lazily loads the ``CGATS001Compat-v2-micro`` ICC
    profile through Java's ``ICC_Profile`` APIs (PDDeviceCMYK.java line
    78). pypdfbox does not bundle that profile and the raster path uses
    a numpy-based subtractive transform instead of Pillow's
    ``Image.convert('CMYK')``. The motivation: Pillow's CMYK to RGB
    conversion goes through LittleCMS with a bundled CMYK profile we do
    not control, so its output drifts with Pillow versions. The
    subtractive formula is explicit, deterministic across platforms, and
    matches the convention every PDF viewer uses when the source CMYK
    has no attached ICC profile.

    For colour-accurate CMYK rendering, callers should attach an ICC
    profile via ``/ICCBased`` — that path routes through
    :class:`~pypdfbox.pdmodel.graphics.color.pd_icc_based.PDICCBased`
    and Pillow's ``ImageCms``, not through ``PDDeviceCMYK``.
    """

    INSTANCE: ClassVar[PDDeviceCMYK]

    def __init__(self) -> None:
        super().__init__()
        self._initial_color = PDColor([0.0, 0.0, 0.0, 1.0], self)
        # Lazy-init parity with upstream's ``initDone`` / ``awtColorSpace``
        # fields (PDDeviceCMYK.java lines 50-52). pypdfbox does not load
        # the ICC profile, so ``_init_done`` flips to True on first call
        # and ``_awt_color_space`` stays ``None``.
        self._init_done = False
        self._awt_color_space: Any | None = None
        self._use_pure_java_cmyk_conversion = False

    # ---------- ICC plumbing (parity slots) ----------

    def init(self) -> None:
        """Lazy-load the CMYK ICC profile. Mirrors upstream
        ``PDDeviceCMYK.init()`` (PDDeviceCMYK.java line 63).

        Upstream loads ``CGATS001Compat-v2-micro.icc`` and seeds an
        ``ICC_ColorSpace`` against the JVM's CMM. pypdfbox does not
        bundle that profile and relies on Pillow's built-in CMYK
        transform instead, so this method just flips the
        ``_init_done`` latch on the first call. Idempotent.
        """
        if self._init_done:
            return
        # No-op: pypdfbox does not bundle the upstream ICC profile.
        # Subclasses (the upstream test pattern) may override
        # ``get_icc_profile`` to install a custom default profile.
        profile = self.get_icc_profile()
        self._awt_color_space = profile
        self._init_done = True

    def get_icc_profile(self) -> Any | None:
        """Return the bundled CMYK ICC profile. Mirrors upstream
        ``PDDeviceCMYK.getICCProfile()`` (PDDeviceCMYK.java line 97)
        which streams ``CGATS001Compat-v2-micro.icc`` from classpath
        resources.

        pypdfbox does not bundle that ICC profile (Pillow's built-in
        CMYK to RGB transform is used for rendering). Subclasses may
        override to inject a custom profile; the base implementation
        returns ``None`` so callers can detect the absence and fall
        back to the subtractive approximation.
        """
        return None

    def get_name(self) -> str:
        return "DeviceCMYK"

    def get_number_of_components(self) -> int:
        return 4

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        return [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]

    def to_rgb(self, value: list[float]) -> list[float]:
        """Convert a single DeviceCMYK color value into sRGB. Mirrors
        upstream ``PDDeviceCMYK.toRGB(float[])`` (PDDeviceCMYK.java line
        141) — but rather than the bundled ``CGATS001Compat-v2-micro``
        ICC profile pypdfbox uses the textbook subtractive
        approximation ``r = (1-c)(1-k)``, ``g = (1-m)(1-k)``,
        ``b = (1-y)(1-k)``. This matches the formula already used by
        :meth:`PDColor.to_rgb` for DeviceCMYK so the two paths agree
        and is the same transform every PDF viewer applies when no
        ICC profile is attached to the source CMYK.

        ``value`` must be a list of four floats in ``[0.0, 1.0]``.
        """
        self.init()
        c, m, y, k = value[0], value[1], value[2], value[3]
        r = (1.0 - c) * (1.0 - k)
        g = (1.0 - m) * (1.0 - k)
        b = (1.0 - y) * (1.0 - k)
        return [r, g, b]

    # ---------- raster helpers ----------

    def to_raw_image(
        self, raster: bytes, width: int = 0, height: int = 0
    ) -> Any | None:
        """Return ``None`` for DeviceCMYK rasters. Mirrors upstream
        ``PDDeviceCMYK.toRawImage(WritableRaster)`` (PDDeviceCMYK.java
        line 148): "Device CMYK is not specified, as its the colors of
        whatever device you use. The user should fallback to the RGB
        image."
        """
        return None

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Convert a CMYK raster (8 bits per component, 4 components) to
        an sRGB Pillow image. Mirrors upstream
        ``PDDeviceCMYK.toRGBImage(WritableRaster)`` (PDDeviceCMYK.java
        line 156).

        Implementation: a numpy-vectorised subtractive transform — the
        per-channel formula is ``r = (255 - C) * (255 - K) // 255``
        (and analogously for G, B). The previous version round-tripped
        through ``Image.frombytes('CMYK', ...).convert('RGB')``, which
        delegates to Pillow's LittleCMS pipeline with a bundled CMYK
        profile we do not control. Going through numpy makes the
        transform explicit, deterministic across platforms / Pillow
        versions, and consistent with :meth:`to_rgb`. The returned
        container is still ``PIL.Image`` so callers (rendering pipeline)
        are unaffected.
        """
        import numpy as np
        from PIL import Image

        self.init()
        w = int(width)
        h = int(height)
        n = self.get_number_of_components()
        expected = w * h * n
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        # uint16 widening so ``(255 - x) * (255 - k)`` does not overflow
        # the 0-255 range before the //255 reduction.
        arr = np.frombuffer(data[:expected], dtype=np.uint8).reshape(
            h, w, n
        ).astype(np.uint16)
        c = arr[..., 0]
        m = arr[..., 1]
        y = arr[..., 2]
        k = arr[..., 3]
        inv_k = 255 - k
        r = ((255 - c) * inv_k // 255).astype(np.uint8)
        g = ((255 - m) * inv_k // 255).astype(np.uint8)
        b = ((255 - y) * inv_k // 255).astype(np.uint8)
        rgb = np.stack([r, g, b], axis=-1)
        return Image.fromarray(rgb, mode="RGB")

    def to_rgb_image_awt(
        self,
        raster: bytes,
        awt_color_space: Any = None,
        width: int = 0,
        height: int = 0,
    ) -> Any:
        """Convert ``raster`` via the ``awtColorSpace`` adapter. Mirrors
        upstream ``PDDeviceCMYK.toRGBImageAWT(WritableRaster, ColorSpace)``
        (PDDeviceCMYK.java line 163) which optionally falls back to a
        per-pixel pure-Java conversion when the
        ``org.apache.pdfbox.rendering.UsePureJavaCMYKConversion`` system
        property is set.

        Java AWT has no Python analogue. pypdfbox routes through
        :meth:`to_rgb_image` (numpy subtractive transform), which
        matches upstream's K-zero output for the ICC path and is
        equivalent to the upstream pure-Java per-pixel branch.
        """
        return self.to_rgb_image(raster, width, height)


PDDeviceCMYK.INSTANCE = PDDeviceCMYK()


__all__ = ["PDDeviceCMYK"]
