from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.function import PDFunction


# ---------- Process / Attributes wrappers ----------


class PDDeviceNProcess:
    """Wrapper around a DeviceN ``/Process`` dictionary. Mirrors
    PDFBox ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNProcess``.

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


class PDDeviceNAttributes:
    """Wrapper around a DeviceN ``/Attributes`` dictionary. Mirrors
    PDFBox ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNAttributes``.

    The attributes dictionary describes the relationship between named
    colorants and their underlying process / spot color spaces, plus the
    optional ``/Subtype`` (``DeviceN`` vs ``NChannel``) and
    ``/MixingHints`` entries.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary = dictionary if dictionary is not None else COSDictionary()

    def get_cos_dictionary(self) -> COSDictionary:
        return self._dictionary

    def is_n_channel(self) -> bool:
        """Return ``True`` if ``/Subtype`` is ``NChannel`` (PDF 1.6+)."""
        return self._dictionary.get_name("Subtype") == "NChannel"

    def get_subtype(self) -> str | None:
        """Return the raw ``/Subtype`` name (``"DeviceN"`` or
        ``"NChannel"``); ``None`` when the entry is absent."""
        return self._dictionary.get_name("Subtype")

    def set_subtype(self, subtype: str | None) -> None:
        if subtype is None:
            self._dictionary.remove_item("Subtype")
        else:
            self._dictionary.set_name("Subtype", subtype)

    def get_process(self) -> PDDeviceNProcess | None:
        """Return the ``/Process`` sub-dictionary as a
        :class:`PDDeviceNProcess`, or ``None`` if absent."""
        cos_process = self._dictionary.get_dictionary_object("Process")
        if not isinstance(cos_process, COSDictionary):
            return None
        return PDDeviceNProcess(cos_process)

    def get_colorants(self) -> dict[str, PDColorSpace]:
        """Return the ``/Colorants`` map (colorant name → color space).

        Each value is created via :meth:`PDColorSpace.create`. Entries
        whose color space cannot be created are silently skipped — keep
        the lite path tolerant of partial dictionaries.
        """
        cos_colorants = self._dictionary.get_dictionary_object("Colorants")
        out: dict[str, PDColorSpace] = {}
        if not isinstance(cos_colorants, COSDictionary):
            return out
        for key in cos_colorants.key_set():
            value = cos_colorants.get_dictionary_object(key)
            if value is None:
                continue
            cs = PDColorSpace.create(value)
            if cs is not None:
                out[key.get_name()] = cs
        return out

    def get_mixing_hints(self) -> COSDictionary | None:
        """Return the raw ``/MixingHints`` dictionary, or ``None``.

        We expose the raw COS object — full ``PDDeviceNMixingHints``
        modeling lives further down the rendering path.
        """
        item = self._dictionary.get_dictionary_object("MixingHints")
        if isinstance(item, COSDictionary):
            return item
        return None


# ---------- PDDeviceN ----------


class PDDeviceN(PDColorSpace):
    """A DeviceN color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN``.

    Array form: ``[/DeviceN <colorant names array> <alternate CS>
    <tint transform> <attributes dict>?]``.

    Lite surface: tint transform evaluation and attribute (process
    colorants, mixing hints) parsing land alongside the function and
    rendering modules.
    """

    NAME: str = "DeviceN"

    # Array index constants — match upstream private fields.
    _COLORANT_NAMES = 1
    _ALTERNATE_CS = 2
    _TINT_TRANSFORM = 3
    _DEVICEN_ATTRIBUTES = 4

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSArray())  # empty colorant names
            array.add(COSName.get_pdf_name(""))  # alternate CS placeholder
            array.add(COSName.get_pdf_name(""))  # tint transform placeholder
        super().__init__(array)
        # Initial color: 1.0 per component (full tint of every colorant)
        # — upstream constructs this lazily once colorant names are set.
        n = self.get_number_of_components()
        self._initial_color = PDColor([1.0] * n, self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return len(self.get_colorant_names())

    def get_initial_color(self) -> PDColor:
        # Refresh in case colorant names changed after construction.
        n = self.get_number_of_components()
        if len(self._initial_color.get_components()) != n:
            self._initial_color = PDColor([1.0] * n, self)
        return self._initial_color

    # ---------- DeviceN-specific ----------

    def get_colorant_names(self) -> list[str]:
        assert self._array is not None
        entry = self._array.get_object(self._COLORANT_NAMES)
        if not isinstance(entry, COSArray):
            return []
        out: list[str] = []
        for item in entry:
            if isinstance(item, COSName):
                out.append(item.get_name())
        return out

    def set_colorant_names(self, names: list[str]) -> None:
        assert self._array is not None
        self._array.set(self._COLORANT_NAMES, COSArray.of_cos_names(names))

    def get_alternate_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        entry = self._array.get_object(self._ALTERNATE_CS)
        if entry is None:
            return None
        return PDColorSpace.create(entry)

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        assert self._array is not None
        self._array.set(self._ALTERNATE_CS, alternate.get_cos_object())

    def get_tint_transform(self) -> PDFunction | None:
        """Return the tint transform as a :class:`PDFunction`. Mirrors
        upstream ``PDDeviceN.getTintTransform()``.

        Returns ``None`` when the array slot is empty / a placeholder
        that doesn't dispatch to a concrete function type.
        """
        from pypdfbox.pdmodel.common.function import PDFunction

        raw = self.get_tint_transform_cos()
        if raw is None:
            return None
        # ``PDFunction.create`` raises on truly invalid types but we want
        # parity with upstream, which lets the caller see ``None`` for
        # missing functions and a real function otherwise. Catch the
        # type/value errors raised by placeholder COSName slots.
        try:
            return PDFunction.create(raw)
        except (TypeError, ValueError):
            return None

    def get_tint_transform_cos(self) -> COSBase | None:
        """Return the raw tint transform COS object (function dictionary
        or stream). Pypdfbox enrichment — upstream exposes only the
        typed ``PDFunction`` accessor."""
        assert self._array is not None
        return self._array.get_object(self._TINT_TRANSFORM)

    def set_tint_transform(self, transform: object) -> None:
        """Store the tint transform. Accepts either a :class:`PDFunction`
        (upstream signature) or a raw COS object (pypdfbox enrichment).
        """
        assert self._array is not None
        if hasattr(transform, "get_cos_object"):
            self._array.set(self._TINT_TRANSFORM, transform.get_cos_object())
        elif isinstance(transform, COSBase):
            self._array.set(self._TINT_TRANSFORM, transform)
        else:
            raise TypeError(
                "set_tint_transform expects PDFunction or COSBase, "
                f"got {type(transform).__name__}"
            )

    # ---------- /Attributes ----------

    def get_attributes(self) -> PDDeviceNAttributes | None:
        """Return the ``/Attributes`` sub-dictionary as a
        :class:`PDDeviceNAttributes`, or ``None`` when missing."""
        assert self._array is not None
        if self._array.size() <= self._DEVICEN_ATTRIBUTES:
            return None
        entry = self._array.get_object(self._DEVICEN_ATTRIBUTES)
        if not isinstance(entry, COSDictionary):
            return None
        return PDDeviceNAttributes(entry)

    def set_attributes(self, attributes: PDDeviceNAttributes | None) -> None:
        """Store ``/Attributes``. ``None`` removes the slot (upstream
        ``setAttributes(null)`` removes the index)."""
        assert self._array is not None
        if attributes is None:
            # Drop the trailing attributes slot if present.
            if self._array.size() > self._DEVICEN_ATTRIBUTES:
                self._array.remove_at(self._DEVICEN_ATTRIBUTES)
            return
        # Make sure the array is large enough.
        while self._array.size() <= self._DEVICEN_ATTRIBUTES:
            self._array.add(COSName.get_pdf_name(""))
        self._array.set(
            self._DEVICEN_ATTRIBUTES, attributes.get_cos_dictionary()
        )

    def is_n_channel(self) -> bool:
        """Return ``True`` if the attributes dictionary declares
        ``/Subtype = NChannel``. Mirrors upstream
        ``PDDeviceN.isNChannel()``."""
        attrs = self.get_attributes()
        if attrs is None:
            return False
        return attrs.is_n_channel()

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Evaluate the tint transform on the multi-component tint
        vector and forward to the alternate CS. Per PDF 32000-1
        §8.6.6.5, ``components`` is one value per colorant."""
        alternate = self.get_alternate_color_space()
        if alternate is None:
            return None
        function = self.get_tint_transform()
        if function is None:
            return None
        alt_components = function.eval(list(components))
        return PDColor(alt_components, alternate).to_rgb()


__all__ = ["PDDeviceN", "PDDeviceNAttributes", "PDDeviceNProcess"]
