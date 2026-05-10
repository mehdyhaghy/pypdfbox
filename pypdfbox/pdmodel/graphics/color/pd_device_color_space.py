from __future__ import annotations

from abc import ABC

from pypdfbox.cos import COSBase, COSName

from .pd_color_space import PDColorSpace


class PDDeviceColorSpace(PDColorSpace, ABC):
    """Device colour spaces directly specify colours or shades of gray
    produced by an output device. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceColorSpace``."""

    def get_cos_object(self) -> COSBase:
        return COSName.get_pdf_name(self.get_name())

    def to_string(self) -> str:
        """Mirror upstream ``PDDeviceColorSpace.toString()``
        (``PDDeviceColorSpace.java`` lines 29-33): returns the device
        color space's PDF name (``DeviceGray`` / ``DeviceRGB`` /
        ``DeviceCMYK``)."""
        return self.get_name()

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["PDDeviceColorSpace"]
