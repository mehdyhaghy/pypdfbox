from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_color_space import PDColorSpace


class PDDeviceNProcess:
    """Wrapper around a DeviceN ``/Process`` dictionary. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNProcess``.

    Carries the process color space and the names of its components, so
    that DeviceN attributes can describe how named colorants map onto
    underlying process colors (per PDF 32000-1 §8.6.6.5, NChannel).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary = dictionary if dictionary is not None else COSDictionary()

    def get_cos_dictionary(self) -> COSDictionary:
        return self._dictionary

    def get_color_space(self) -> PDColorSpace | None:
        """Return the process color space, or ``None`` if absent."""
        cos_cs = self._dictionary.get_dictionary_object("ColorSpace")
        if cos_cs is None:
            return None
        return PDColorSpace.create(cos_cs)

    def get_components(self) -> list[str]:
        """Return the names of the process color components."""
        cos_components = self._dictionary.get_dictionary_object("Components")
        if not isinstance(cos_components, COSArray):
            return []
        out: list[str] = []
        for item in cos_components:
            if isinstance(item, COSName):
                out.append(item.get_name())
        return out


__all__ = ["PDDeviceNProcess"]
