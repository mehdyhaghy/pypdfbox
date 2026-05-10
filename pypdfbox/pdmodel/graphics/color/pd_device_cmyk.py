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

    Lite surface: ``to_rgb`` uses a simple subtractive approximation when
    no ICC profile is supplied. The upstream class lazily loads the
    ``CGATS001Compat-v2-micro`` ICC profile through Java's ``ICC_Profile``
    APIs (PDDeviceCMYK.java line 78); pypdfbox does not bundle that
    profile and instead delegates raster conversion to Pillow's built-in
    CMYK to RGB transform, which uses the same K-zero subtractive
    approximation.
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
        141) — but until the ICC profile pipeline lands, pypdfbox uses
        the simple subtractive approximation ``r = (1-c)(1-k)``,
        ``g = (1-m)(1-k)``, ``b = (1-y)(1-k)``. This matches the formula
        already used by :meth:`PDColor.to_rgb` for DeviceCMYK so the two
        paths agree, and matches the K-zero result of Pillow's built-in
        CMYK to RGB transform.

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

        Library-first: pypdfbox uses Pillow's built-in CMYK to RGB
        transform (``Image.frombytes('CMYK', ...).convert('RGB')``),
        which applies the same K-zero subtractive approximation used by
        :meth:`to_rgb` and matches the K-zero output of upstream's ICC
        pipeline.
        """
        from PIL import Image

        self.init()
        n = self.get_number_of_components()
        expected = int(width) * int(height) * n
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        cmyk = Image.frombytes(
            "CMYK", (int(width), int(height)), data[:expected]
        )
        return cmyk.convert("RGB")

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
        :meth:`to_rgb_image` (Pillow's CMYK to RGB transform), which
        matches upstream's K-zero output for the ICC path and is
        equivalent to the pure-Java per-pixel branch.
        """
        return self.to_rgb_image(raster, width, height)


PDDeviceCMYK.INSTANCE = PDDeviceCMYK()


__all__ = ["PDDeviceCMYK"]
