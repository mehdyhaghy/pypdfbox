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
        try:
            return PDColorSpace.create(cos_cs)
        except (TypeError, ValueError, OSError):
            return None

    def set_color_space(self, color_space: PDColorSpace | None) -> None:
        """Set the process ``/ColorSpace``. Pass ``None`` to remove it."""
        if color_space is None:
            self._dictionary.remove_item("ColorSpace")
            return
        cos = color_space.get_cos_object()
        if cos is None:
            raise TypeError("set_color_space requires a color space with a COS form")
        self._dictionary.set_item("ColorSpace", cos)

    def has_color_space(self) -> bool:
        """Return ``True`` when ``/ColorSpace`` resolves to a color space."""
        return self.get_color_space() is not None

    def clear_color_space(self) -> None:
        """Remove the process ``/ColorSpace`` entry."""
        self.set_color_space(None)

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

    def set_components(self, components: list[str] | None) -> None:
        """Set the process ``/Components`` names. Pass ``None`` to remove it."""
        if components is None:
            self._dictionary.remove_item("Components")
            return
        self._dictionary.set_item("Components", COSArray.of_cos_names(components))

    def has_components(self) -> bool:
        """Return ``True`` when ``/Components`` is present as an array."""
        return isinstance(
            self._dictionary.get_dictionary_object("Components"), COSArray
        )

    def clear_components(self) -> None:
        """Remove the process ``/Components`` entry."""
        self.set_components(None)


__all__ = ["PDDeviceNProcess"]
