from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace
from .pd_special_color_space import PDSpecialColorSpace

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

    def __str__(self) -> str:
        """Mirrors upstream ``PDDeviceNProcess.toString``:
        ``Process{<color-space> "<comp0>" "<comp1>" ...}``.

        ``<color-space>`` falls back to ``None`` when ``/ColorSpace`` is
        absent or unresolvable — keeps the lite-path behaviour of
        :meth:`get_color_space` visible through the string form."""
        return self.to_string()

    def to_string(self) -> str:
        """Mirrors upstream ``PDDeviceNProcess.toString()`` —
        ``Process{<color-space> "<comp0>" "<comp1>" ...}``. Surfaced
        explicitly so callers porting from PDFBox can keep the literal
        ``.toString()`` invocation spelled snake_case.

        DELIBERATE DIVERGENCE: upstream appends ``getColorSpace()`` via
        ``StringBuilder.append(Object)`` and neither ``PDColorSpace`` nor
        the device colour spaces override ``Object.toString()``, so the
        upstream string embeds a non-deterministic JVM hashcode
        (``...PDDeviceCMYK@1b6d3586``). We substitute the stable
        :meth:`PDColorSpace.get_name` form so the rendering is
        reproducible; this is recorded in CHANGES.md."""
        cs = self.get_color_space()
        cs_repr = "None" if cs is None else cs.get_name()
        parts = [f'Process{{{cs_repr}']
        for component in self.get_components():
            parts.append(f' "{component}"')
        parts.append("}")
        return "".join(parts)


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
        """Return ``True`` if ``/Subtype`` is ``NChannel`` (PDF 1.6+).

        Upstream ``PDDeviceNAttributes.isNChannel`` reads ``/Subtype`` via
        ``getNameAsString``, so a ``COSString`` value is honoured too.
        """
        return self._dictionary.get_name_as_string("Subtype") == "NChannel"

    def get_subtype(self) -> str | None:
        """Return the raw ``/Subtype`` name (``"DeviceN"`` or
        ``"NChannel"``); ``None`` when the entry is absent. Reads ``/Subtype``
        via ``getNameAsString`` for parity with :meth:`is_n_channel`."""
        return self._dictionary.get_name_as_string("Subtype")

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

    def has_process(self) -> bool:
        """Return ``True`` when ``/Process`` is present as a dictionary."""
        return self.get_process() is not None

    def set_process(self, process: PDDeviceNProcess | COSDictionary | None) -> None:
        """Set ``/Process``. Accepts a typed process wrapper, raw dictionary, or
        ``None`` to remove the entry."""
        if process is None:
            self._dictionary.remove_item("Process")
            return
        if isinstance(process, PDDeviceNProcess):
            self._dictionary.set_item("Process", process.get_cos_dictionary())
            return
        self._dictionary.set_item("Process", process)

    def clear_process(self) -> None:
        """Remove the optional ``/Process`` dictionary."""
        self.set_process(None)

    def get_colorants(self) -> dict[str, PDColorSpace]:
        """Return the ``/Colorants`` map (colorant name → color space).

        Each value is created via :meth:`PDColorSpace.create`. Entries
        whose color space cannot be created are silently skipped — keep
        the lite path tolerant of partial dictionaries.

        Side effect (matches upstream ``getColorants(PDResources)``,
        ``PDDeviceNAttributes.java`` line 80): when ``/Colorants`` is
        absent the backing dictionary gets a fresh empty ``/Colorants``
        COSDictionary inserted, and the returned map is empty. This makes
        a subsequent ``has_colorants()`` true even on an attributes dict
        that started without the entry.
        """
        cos_colorants = self._dictionary.get_dictionary_object("Colorants")
        out: dict[str, PDColorSpace] = {}
        if not isinstance(cos_colorants, COSDictionary):
            self._dictionary.set_item("Colorants", COSDictionary())
            return out
        for key in cos_colorants.key_set():
            value = cos_colorants.get_dictionary_object(key)
            if value is None:
                continue
            try:
                cs = PDColorSpace.create(value)
            except (TypeError, ValueError, OSError):
                continue
            if cs is not None:
                out[key.get_name()] = cs
        return out

    def set_colorants(self, colorants: dict[str, PDColorSpace] | None) -> None:
        """Replace the ``/Colorants`` map. Mirrors upstream
        ``PDDeviceNAttributes.setColorants(Map<String, PDColorSpace>)``.

        ``None`` removes the entry entirely — matches upstream's behaviour
        of writing a ``null`` value, which the writer drops.
        """
        if colorants is None:
            self._dictionary.remove_item("Colorants")
            return
        out = COSDictionary()
        for name, cs in colorants.items():
            cos = cs.get_cos_object()
            if cos is None:
                raise TypeError(
                    "set_colorants requires color spaces with COS forms"
                )
            out.set_item(name, cos)
        self._dictionary.set_item("Colorants", out)

    def has_colorants(self) -> bool:
        """Return ``True`` when ``/Colorants`` is present as a dictionary."""
        return isinstance(
            self._dictionary.get_dictionary_object("Colorants"), COSDictionary
        )

    def clear_colorants(self) -> None:
        """Remove the optional ``/Colorants`` map."""
        self.set_colorants(None)

    def get_mixing_hints(self) -> COSDictionary | None:
        """Return the raw ``/MixingHints`` dictionary, or ``None``.

        We expose the raw COS object — full ``PDDeviceNMixingHints``
        modeling lives further down the rendering path.
        """
        item = self._dictionary.get_dictionary_object("MixingHints")
        if isinstance(item, COSDictionary):
            return item
        return None

    def has_mixing_hints(self) -> bool:
        """Return ``True`` when ``/MixingHints`` is present as a dictionary."""
        return self.get_mixing_hints() is not None

    def clear_mixing_hints(self) -> None:
        """Remove the optional ``/MixingHints`` dictionary."""
        self._dictionary.remove_item("MixingHints")

    def __str__(self) -> str:
        """Mirrors upstream ``PDDeviceNAttributes.toString`` (PDFBox
        ``PDDeviceNAttributes.java`` line 150):
        ``<subtype>{<process>? Colorants{"<name>": <cs> ...}}``.

        The leading prefix is the ``/Subtype`` name (``DeviceN`` /
        ``NChannel``); empty when the entry is absent. ``<process>`` is
        the :meth:`PDDeviceNProcess.__str__` form when present, followed
        by a single space. Each ``/Colorants`` entry is rendered as
        ``"<name>": <cs>`` using the colour space's FULL ``str()`` form
        (upstream appends the ``PDSeparation`` object, not just its name)
        and is ALWAYS followed by a trailing space — so the closing
        ``}}`` is preceded by a space when at least one colorant exists.
        Colorants entries whose color space cannot be resolved are
        silently skipped — matches the leniency of :meth:`get_colorants`.
        """
        subtype = self.get_subtype() or ""
        parts: list[str] = [f"{subtype}{{"]
        process = self.get_process()
        if process is not None:
            parts.append(str(process))
            parts.append(" ")
        parts.append("Colorants{")
        for name, cs in self.get_colorants().items():
            parts.append(f'"{name}": {cs} ')
        parts.append("}")
        parts.append("}")
        return "".join(parts)

    def to_string(self) -> str:
        """Snake-case wrapper around :meth:`__str__` mirroring upstream
        ``PDDeviceNAttributes.toString`` (``PDDeviceNAttributes.java``
        line 150). Lets callers porting Java code keep the
        ``attrs.toString()`` shape.
        """
        return self.__str__()


# ---------- PDDeviceN ----------


class PDDeviceN(PDSpecialColorSpace):
    """A DeviceN color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN``.

    Array form: ``[/DeviceN <colorant names array> <alternate CS>
    <tint transform> <attributes dict>?]``.

    Tint transforms are exposed through :class:`PDFunction` and the
    attributes dictionary has typed process/colorant wrappers. Full
    overprint/rendering behavior remains in the rendering path.
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
        # Color-conversion cache (mirrors upstream private fields populated
        # by initColorConversionCache). Lazily filled by
        # :meth:`init_color_conversion_cache` — left empty when the space
        # has no /Attributes (the tint-transform path doesn't need it).
        self._num_colorants: int = 0
        self._colorant_to_component: list[int] = []
        self._process_color_space: PDColorSpace | None = None
        self._spot_color_spaces: list[PDColorSpace | None] = []

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return len(self.get_colorant_names())

    def get_initial_color(self) -> PDColor:
        # Refresh in case colorant names changed after construction.
        # Compare against the raw internal components (PDColor.get_components
        # pads/truncates to the CS arity per PDFBOX-4279, so it would
        # always agree on length here).
        n = self.get_number_of_components()
        if len(self._initial_color._components) != n:
            self._initial_color = PDColor([1.0] * n, self)
        return self._initial_color

    # ---------- DeviceN-specific ----------

    def _get_array_object(self, index: int) -> COSBase | None:
        assert self._array is not None
        if self._array.size() <= index:
            return None
        return self._array.get_object(index)

    def _ensure_array_size(self, size: int) -> None:
        assert self._array is not None
        while self._array.size() < size:
            self._array.add(COSName.get_pdf_name(""))

    def get_colorant_names(self) -> list[str]:
        assert self._array is not None
        entry = self._get_array_object(self._COLORANT_NAMES)
        if not isinstance(entry, COSArray):
            return []
        out: list[str] = []
        for item in entry:
            if isinstance(item, COSName):
                out.append(item.get_name())
        return out

    def set_colorant_names(self, names: list[str]) -> None:
        assert self._array is not None
        self._ensure_array_size(self._COLORANT_NAMES + 1)
        self._array.set(self._COLORANT_NAMES, COSArray.of_cos_names(names))

    def get_alternate_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        entry = self._get_array_object(self._ALTERNATE_CS)
        if entry is None:
            return None
        return PDColorSpace.create(entry)

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        assert self._array is not None
        self._ensure_array_size(self._ALTERNATE_CS + 1)
        cos = alternate.get_cos_object()
        if cos is None:
            raise TypeError(
                "set_alternate_color_space requires a color space with a COS form"
            )
        self._array.set(self._ALTERNATE_CS, cos)

    def has_alternate_color_space(self) -> bool:
        """Return ``True`` when the alternate-CS slot resolves."""
        return self.get_alternate_color_space() is not None

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
        return self._get_array_object(self._TINT_TRANSFORM)

    def has_tint_transform(self) -> bool:
        """Return ``True`` when the tint-transform slot resolves to a function."""
        return self.get_tint_transform() is not None

    def clear_tint_transform(self) -> None:
        """Clear the tint-transform slot back to the default placeholder."""
        assert self._array is not None
        self._ensure_array_size(self._TINT_TRANSFORM + 1)
        self._array.set(self._TINT_TRANSFORM, COSName.get_pdf_name(""))

    def set_tint_transform(self, transform: object) -> None:
        """Store the tint transform. Accepts either a :class:`PDFunction`
        (upstream signature) or a raw COS object (pypdfbox enrichment).
        """
        assert self._array is not None
        self._ensure_array_size(self._TINT_TRANSFORM + 1)
        if hasattr(transform, "get_cos_object"):
            cos = transform.get_cos_object()
            if cos is None:
                raise TypeError(
                    "set_tint_transform requires an object with a COS form"
                )
            self._array.set(self._TINT_TRANSFORM, cos)
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
        entry = self._get_array_object(self._DEVICEN_ATTRIBUTES)
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
        self._ensure_array_size(self._DEVICEN_ATTRIBUTES + 1)
        self._array.set(
            self._DEVICEN_ATTRIBUTES, attributes.get_cos_dictionary()
        )

    def clear_attributes(self) -> None:
        """Remove the optional attributes slot. No-op if absent."""
        self.set_attributes(None)

    def is_n_channel(self) -> bool:
        """Return ``True`` if the attributes dictionary declares
        ``/Subtype = NChannel``. Mirrors upstream
        ``PDDeviceN.isNChannel()``."""
        attrs = self.get_attributes()
        if attrs is None:
            return False
        return attrs.is_n_channel()

    def has_attributes(self) -> bool:
        """Return ``True`` if the ``/Attributes`` slot is present and
        carries a real dictionary. Pypdfbox enrichment — upstream
        callers infer the same by null-checking ``getAttributes()``,
        but a typed predicate makes intent obvious at call sites
        branching on attribute-only vs tint-transform color paths
        (see PDF 32000-1 §8.6.6.5)."""
        return self.get_attributes() is not None

    def get_colorant_index(self, name: str) -> int:
        """Return the index of the colorant ``name`` in the colorant
        names array, or ``-1`` if the name is not present.

        Pypdfbox enrichment over upstream's private
        ``colorantToComponent`` cache (which maps colorant index →
        process-component index). This is the inverse direction:
        callers that want to look up "where does my spot colorant
        live in the multi-tint vector" can do so without rebuilding
        the colorant list themselves. Matches the upstream conv
        of returning ``-1`` for "not present"."""
        names = self.get_colorant_names()
        try:
            return names.index(name)
        except ValueError:
            return -1

    def get_subtype(self) -> str:
        """Return the DeviceN subtype: ``"NChannel"`` or ``"DeviceN"``.

        Pypdfbox enrichment — upstream exposes only the boolean
        ``isNChannel()``. Per PDF 32000-1 §8.6.6.5, when ``/Attributes``
        is absent or carries no ``/Subtype`` entry the implicit subtype
        is ``DeviceN`` (NChannel was added in PDF 1.6 and must opt-in).
        """
        attrs = self.get_attributes()
        if attrs is None:
            return "DeviceN"
        sub = attrs.get_subtype()
        if sub == "NChannel":
            return "NChannel"
        return "DeviceN"

    def get_process_color_space(self) -> PDColorSpace | None:
        """Return the process color space declared in
        ``/Attributes/Process/ColorSpace``, or ``None`` when absent.

        Pypdfbox enrichment — upstream exposes the same data only via
        ``getAttributes().getProcess().getColorSpace()``; this collapses
        the chain for a common consumer.
        """
        attrs = self.get_attributes()
        if attrs is None:
            return None
        process = attrs.get_process()
        if process is None:
            return None
        return process.get_color_space()

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Return ``[0, 1]`` per colorant. Mirrors upstream
        ``PDDeviceN.getDefaultDecode`` — for each component the decode
        pair is ``[0, 1]``."""
        n = self.get_number_of_components()
        out: list[float] = []
        for _ in range(n):
            out.append(0.0)
            out.append(1.0)
        return out

    # ---------- color conversion cache ----------

    def init_color_conversion_cache(self, resources: Any = None) -> None:
        """Populate the per-colorant attribute cache used by the
        attribute-driven RGB path. Mirrors upstream private
        ``initColorConversionCache(PDResources)`` (PDDeviceN.java line
        126) and is invoked automatically the first time
        :meth:`to_rgb_with_attributes` is called.

        For each colorant name we record:

        - which process-component slot it maps onto (``-1`` if none), and
        - the spot color space, when the ``/Attributes /Colorants`` map
          declares one. For non-NChannel subtypes a spot colorant
          masks any same-named process component (PDF 32000-1
          §8.6.6.5).

        ``resources`` is accepted for surface compatibility — pypdfbox's
        :meth:`PDDeviceNAttributes.get_colorants` does not require a
        :class:`PDResources` because color spaces are eagerly resolved.
        """
        attrs = self.get_attributes()
        # Reset cache fields whether or not we have attributes — keeps
        # the contract that calling this method clears prior state.
        self._num_colorants = 0
        self._colorant_to_component = []
        self._process_color_space = None
        self._spot_color_spaces = []
        if attrs is None:
            return
        del resources  # accepted for parity, not consumed (see docstring)
        colorant_names = self.get_colorant_names()
        self._num_colorants = len(colorant_names)
        self._colorant_to_component = [-1] * self._num_colorants
        process = attrs.get_process()
        if process is not None:
            components = process.get_components()
            for c in range(self._num_colorants):
                try:
                    self._colorant_to_component[c] = components.index(
                        colorant_names[c]
                    )
                except ValueError:
                    self._colorant_to_component[c] = -1
            self._process_color_space = process.get_color_space()
        self._spot_color_spaces = [None] * self._num_colorants
        spot_colorants = attrs.get_colorants()
        is_nchannel = self.is_n_channel()
        for c in range(self._num_colorants):
            name = colorant_names[c]
            spot = spot_colorants.get(name)
            if spot is None:
                continue
            self._spot_color_spaces[c] = spot
            # spot colors may replace process colors with same name
            # providing that the subtype is not NChannel (PDF 32000-1
            # §8.6.6.5).
            if not is_nchannel:
                self._colorant_to_component[c] = -1

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Evaluate the tint vector to sRGB. Mirrors upstream
        ``PDDeviceN.toRGB(float[])`` — dispatches to
        :meth:`to_rgb_with_attributes` when ``/Attributes`` is present,
        else :meth:`to_rgb_with_tint_transform`."""
        if self.has_attributes():
            return self.to_rgb_with_attributes(components)
        return self.to_rgb_with_tint_transform(components)

    def to_rgb_with_tint_transform(
        self, value: list[float]
    ) -> tuple[float, float, float] | None:
        """Evaluate the tint transform and route through the alternate
        color space. Mirrors upstream private
        ``toRGBWithTintTransform(float[])`` (PDDeviceN.java line 432)."""
        alternate = self.get_alternate_color_space()
        if alternate is None:
            return None
        function = self.get_tint_transform()
        if function is None:
            return None
        alt_value = function.eval(list(value))
        # Defensive arity guard (pypdfbox lazy-path equivalent of upstream's
        # eager constructor validation): PDFBox's ``PDDeviceN(COSArray)``
        # rejects a tint transform whose output-parameter count is fewer than
        # the alternate's component count at CONSTRUCTION time. pypdfbox
        # resolves the alternate + tint lazily, so a malformed pairing only
        # surfaces here — without this guard a short ``alt_value`` vector
        # would raise IndexError inside the alternate's ``to_rgb``. Return
        # ``None`` (the lenient lite-path "cannot convert") instead.
        if len(alt_value) < alternate.get_number_of_components():
            return None
        return PDColor(alt_value, alternate).to_rgb()

    def to_rgb_with_attributes(
        self, value: list[float]
    ) -> tuple[float, float, float] | None:
        """Compose the per-colorant tint contributions through the
        ``/Attributes`` ``/Process`` and ``/Colorants`` color spaces by
        multiply-blending each colorant's RGB output. Mirrors upstream
        private ``toRGBWithAttributes(float[])`` (PDDeviceN.java line
        377). Falls back to :meth:`to_rgb_with_tint_transform` when a
        spot colorant has no entry in ``/Colorants`` — the same Altona
        Visual workaround the upstream method takes."""
        # Lazily build the attribute cache (upstream does this in its
        # constructor; we do it on first use to keep the cheap default
        # ctor path allocation-free).
        if not self._spot_color_spaces and self.has_attributes():
            self.init_color_conversion_cache()
        rgb_value = [1.0, 1.0, 1.0]
        for c in range(self._num_colorants):
            is_process_colorant = self._colorant_to_component[c] >= 0
            if is_process_colorant:
                component_color_space = self._process_color_space
            elif self._spot_color_spaces[c] is None:
                # Missing spot color, fall back to tint-transform path.
                return self.to_rgb_with_tint_transform(value)
            else:
                component_color_space = self._spot_color_spaces[c]
            if component_color_space is None:
                return self.to_rgb_with_tint_transform(value)
            n_components = component_color_space.get_number_of_components()
            component_samples = [0.0] * n_components
            if is_process_colorant:
                component_samples[self._colorant_to_component[c]] = value[c]
            else:
                component_samples[0] = value[c]
            rgb_component = component_color_space.to_rgb(component_samples)
            if rgb_component is None:
                return self.to_rgb_with_tint_transform(value)
            # multiply (blend mode)
            rgb_value[0] *= rgb_component[0]
            rgb_value[1] *= rgb_component[1]
            rgb_value[2] *= rgb_component[2]
        return (rgb_value[0], rgb_value[1], rgb_value[2])

    # ---------- raster-level conversion ----------

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Render an 8-bit-per-component DeviceN raster to a Pillow sRGB
        image. Mirrors upstream ``PDDeviceN.toRGBImage(WritableRaster)``
        (PDDeviceN.java line 193) — dispatches to the attribute-driven
        path when ``/Attributes`` is present, else the tint-transform
        path.

        The raster path is NOT the generic per-pixel
        :meth:`PDColorSpace.to_rgb_image` (which rounds): upstream's
        ``toRGBWithTintTransform(WritableRaster)`` (PDDeviceN.java line
        261) scales each input band by ``/255f`` in 32-bit ``float``,
        evaluates the tint transform, routes through the alternate's
        ``toRGB``, then packs each RGB channel with the truncating
        ``(int)(c * 255f)`` cast (``f2i``) — also in 32-bit float. Doing
        the scale/truncate in double precision (as the generic base does)
        diverges by one byte on values like ``1 - 127/255`` (``128.0`` in
        double truncates to ``128`` but ``127.99999`` in float truncates
        to ``127``). We reproduce upstream's float arithmetic so the
        per-pixel bytes match (wave 1456).
        """
        import numpy as np
        from PIL import Image

        alternate = self.get_alternate_color_space()
        function = self.get_tint_transform()
        if alternate is None or function is None:
            return super().to_rgb_image(raster, width, height)

        n = self.get_number_of_components()
        w = int(width)
        h = int(height)
        expected = w * h * n
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))

        f255 = np.float32(255.0)
        cache: dict[bytes, tuple[int, int, int]] = {}
        out = bytearray(w * h * 3)
        for pixel_index in range(w * h):
            offset = pixel_index * n
            key = data[offset:offset + n]
            rgb = cache.get(key)
            if rgb is None:
                # scale each 8-bit band 0..255 -> 0..1 in 32-bit float.
                samples = [float(np.float32(b) / f255) for b in key]
                if self.has_attributes():
                    triple = self.to_rgb_with_attributes(samples)
                else:
                    triple = self.to_rgb_with_tint_transform(samples)
                if triple is None:
                    rgb = (0, 0, 0)
                else:
                    rgb = tuple(
                        max(0, min(255, int(np.float32(c) * f255)))
                        for c in triple
                    )
                cache[key] = rgb
            base = pixel_index * 3
            out[base] = rgb[0]
            out[base + 1] = rgb[1]
            out[base + 2] = rgb[2]
        return Image.frombytes("RGB", (w, h), bytes(out))

    def to_raw_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Mirrors upstream ``PDDeviceN.toRawImage(WritableRaster)``
        (PDDeviceN.java line 442) — DeviceN has no raw raster form
        (the channel set is unbounded), so the upstream method
        unconditionally returns ``null``. We match that contract."""
        del raster, width, height
        return None

    # ---------- string form ----------

    def __str__(self) -> str:
        """Mirrors upstream ``PDDeviceN.toString``:
        ``DeviceN{"<col0>" "<col1>" ... <alternate-name> <tint> <attrs>?}``.

        Lenient to placeholder slots — alternate falls back to
        ``"None"`` when unresolvable, tint to ``"None"`` when the
        function dispatch fails (default ctor placeholder), and the
        attributes section is omitted when no ``/Attributes`` slot is
        present.
        """
        parts: list[str] = [f"{self.get_name()}{{"]
        for colorant in self.get_colorant_names():
            parts.append(f'"{colorant}" ')
        alternate = self.get_alternate_color_space()
        parts.append("None" if alternate is None else alternate.get_name())
        parts.append(" ")
        tint = self.get_tint_transform()
        parts.append("None" if tint is None else str(tint))
        attrs = self.get_attributes()
        if attrs is not None:
            parts.append(" ")
            parts.append(str(attrs))
        parts.append("}")
        return "".join(parts)

    def to_string(self) -> str:
        """Return the upstream-style ``toString`` rendering. Mirrors
        upstream ``PDDeviceN.toString()`` (PDDeviceN.java line 600).
        Surfaced explicitly so callers porting from PDFBox can keep the
        literal ``.toString()`` invocation spelled snake_case."""
        return self.__str__()


__all__ = ["PDDeviceN", "PDDeviceNAttributes", "PDDeviceNProcess"]
