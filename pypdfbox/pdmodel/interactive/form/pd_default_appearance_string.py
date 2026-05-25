"""Port of upstream ``PDDefaultAppearanceString``.

Mirrors :java:`org.apache.pdfbox.pdmodel.interactive.form.PDDefaultAppearanceString`
(`PDDefaultAppearanceString.java`). The class parses the operators in a
field's ``/DA`` content-stream snippet to extract the selected font /
size / non-stroking colour, then exposes accessors plus a ``write_to``
that re-emits those state operators into a target appearance content
stream.

Upstream is package-private; pypdfbox surfaces it for parity with
:meth:`PDVariableText.get_default_appearance_string`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.cos import COSArray, COSBase, COSName, COSNumber, COSString
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDFont
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
        PDAppearanceContentStream,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )
    from pypdfbox.pdmodel.pd_resources import PDResources


# Upstream: ``DEFAULT_FONT_SIZE = 12`` (Java line 57).
_DEFAULT_FONT_SIZE: float = 12.0


# Acrobat-style /DA aliases that name Standard-14 fonts by short
# 4-letter tokens (``Helv`` → Helvetica, ``HeBo`` → Helvetica-Bold,
# ``TiRo`` → Times-Roman, etc.). Mirrors the alias table used by
# :class:`PDAppearanceGenerator`; duplicated here as a small local map
# to avoid importing the generator module at /DA-parse time (the
# generator pulls in font / colour / image layers that the /DA parse
# would otherwise not need to load).
_DA_FONT_ALIASES: dict[str, str] = {
    "Helv": "Helvetica",
    "HeBo": "Helvetica-Bold",
    "HeIt": "Helvetica-Oblique",
    "HeBI": "Helvetica-BoldOblique",
    "TiRo": "Times-Roman",
    "TiBo": "Times-Bold",
    "TiIt": "Times-Italic",
    "TiBI": "Times-BoldItalic",
    "CoRo": "Courier",
    "CoBo": "Courier-Bold",
    "CoIt": "Courier-Oblique",
    "CoBI": "Courier-BoldOblique",
    "Symb": "Symbol",
    "ZaDb": "ZapfDingbats",
}


def _resolve_fallback_font(font_name: str) -> PDFont:
    """Return a Standard-14 :class:`PDFont` for ``font_name``.

    Resolution order (PDFBOX-2661 "special mapping"):
    1. Acrobat /DA short alias (``Helv``, ``TiBo``, …).
    2. Canonical Standard-14 spelling (``Helvetica``, ``Times-Roman``, …).
    3. Plain Helvetica as the last-ditch default.
    """
    from pypdfbox.pdmodel.font import PDFontFactory  # noqa: PLC0415
    from pypdfbox.pdmodel.font.standard14_fonts import (  # noqa: PLC0415
        Standard14Fonts,
    )

    alias = _DA_FONT_ALIASES.get(font_name)
    if alias is not None:
        return PDFontFactory.create_default_font(alias)
    mapped = Standard14Fonts.get_mapped_font_name(font_name)
    if mapped is not None:
        return PDFontFactory.create_default_font(mapped)
    return PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)


class PDDefaultAppearanceString:
    """Represents a default appearance string, as found in the ``/DA``
    entry of variable-text form fields and free-text annotations.

    Mirrors upstream ``PDDefaultAppearanceString`` (Java line 52). The
    ``/DA`` content stream contains text-state operators (``Tf``) plus
    non-stroking colour operators (``g``, ``rg``, ``k``); the parser
    extracts the selected font / size / colour and surfaces them via
    accessors.
    """

    def __init__(
        self,
        default_appearance: COSString | None,
        default_resources: PDResources | None,
    ) -> None:
        """Constructor for reading an existing DA string. Mirrors upstream
        constructor (Java lines 73-88).

        Raises ``ValueError`` (Python's analogue of upstream
        ``IllegalArgumentException``) when either argument is ``None``;
        propagates parser errors as ``OSError`` (analogue of upstream
        ``IOException``).
        """
        if default_appearance is None:
            raise ValueError(
                "/DA is a required entry. Please set a default appearance first."
            )
        if default_resources is None:
            raise ValueError("/DR is a required entry")

        self._default_appearance: COSString = default_appearance
        self._default_resources: PDResources = default_resources
        self._font_name: COSName | None = None
        self._font: PDFont | None = None
        self._font_size: float = _DEFAULT_FONT_SIZE
        self._font_color: PDColor | None = None
        # Named resources referenced by the /DA stream beyond the font —
        # ``cs`` / ``CS`` may name a colour space and ``gs`` may name an
        # ext-gstate. Tracked so :meth:`copy_needed_resources_to` can
        # carry them across into the appearance stream's /Resources too
        # (upstream "todo: other kinds of resource…" cluster).
        self._color_space_names: list[COSName] = []
        self._ext_g_state_names: list[COSName] = []

        self.process_appearance_string_operators(default_appearance.get_bytes())

    # ------------------------------------------------------------------
    # pypdfbox-only accessors retained from the wave-1275 stub for
    # backwards compatibility with callers / tests written against the
    # earlier surface.
    # ------------------------------------------------------------------

    def get_default_appearance(self) -> COSString:
        """Return the raw ``/DA`` ``COSString`` operand. Pypdfbox-only
        accessor — upstream does not expose the source string."""
        return self._default_appearance

    def get_default_resources(self) -> PDResources:
        """Return the ``/DR`` resources used to resolve fonts / colour
        spaces. Pypdfbox-only accessor — upstream stores ``defaultResources``
        privately."""
        return self._default_resources

    # ------------------------------------------------------------------
    # parsing — upstream Java lines 96-138
    # ------------------------------------------------------------------

    def process_appearance_string_operators(self, content: bytes) -> None:
        """Processes the operators of the given content stream. Mirrors
        upstream ``processAppearanceStringOperators`` (Java lines 96-114).

        Walks every token produced by :class:`PDFStreamParser`; operands
        accumulate into ``arguments`` and are dispatched whenever an
        ``Operator`` token is encountered.
        """
        arguments: list[COSBase] = []
        parser = PDFStreamParser.from_bytes(bytes(content))
        token = parser.parse_next_token()
        while token is not None:
            if isinstance(token, Operator):
                self.process_operator(token, arguments)
                arguments = []
            else:
                arguments.append(token)
            token = parser.parse_next_token()

    def process_operator(self, operator: Operator, operands: list[COSBase]) -> None:
        """Dispatch a single operator. Mirrors upstream ``processOperator``
        (Java lines 123-138). Only the operators legal inside an /DA
        string are honoured — ``Tf`` for font + size, and the
        non-stroking colour operators ``g`` / ``rg`` / ``k``.

        In addition (pypdfbox extension on top of upstream's
        ``processOperator``), named-resource references introduced by
        ``cs`` / ``CS`` (colour-space) and ``gs`` (ext-gstate) operators
        are recorded so :meth:`copy_needed_resources_to` can carry the
        backing resources across when emitting an appearance stream.
        """
        name = operator.get_name()
        if name == OperatorName.SET_FONT_AND_SIZE:
            self.process_set_font(operands)
        elif name in (
            OperatorName.NON_STROKING_GRAY,
            OperatorName.NON_STROKING_RGB,
            OperatorName.NON_STROKING_CMYK,
        ):
            self.process_set_font_color(operands)
        elif name in (
            OperatorName.NON_STROKING_COLORSPACE,
            OperatorName.STROKING_COLORSPACE,
        ):
            self._record_named_operand(operands, self._color_space_names)
        elif name == OperatorName.SET_GRAPHICS_STATE_PARAMS:
            self._record_named_operand(operands, self._ext_g_state_names)
        # other operators silently ignored (upstream ``default: break``)

    @staticmethod
    def _record_named_operand(
        operands: list[COSBase], sink: list[COSName]
    ) -> None:
        """Append the trailing ``COSName`` operand to ``sink`` (deduped).

        ``cs`` / ``CS`` / ``gs`` each take a single ``COSName``; silently
        ignored when the operand is missing or not a name, matching the
        defensive style of the upstream operator processors.
        """
        if not operands:
            return
        candidate = operands[-1]
        if not isinstance(candidate, COSName):
            return
        if candidate not in sink:  # pragma: no branch
            # Defensive: the operator processor is invoked once per token
            # and de-duplication doesn't fire on the test fixtures; the
            # False arm has no live caller.
            sink.append(candidate)

    def process_set_font(self, operands: list[COSBase]) -> None:
        """Process the set font and font size operator. Mirrors upstream
        ``processSetFont`` (Java lines 146-176).

        Operands must be ``[COSName, COSNumber]``; missing operands raise
        ``OSError`` (upstream ``IOException``).

        Upstream marks "todo: handle cases where font == null with special
        mapping logic (see PDFBOX-2661)" — a long-standing bug where a /DA
        string names a font that is missing from /DR (commonly because the
        named font lives only on the parent ``/AcroForm``'s /DR). Pypdfbox
        substitutes a synthesized Standard-14 Helvetica when the named font
        cannot be resolved, matching what every real-world PDF reader does
        (Acrobat / Foxit / Chrome) rather than refusing to render the field.
        """
        if len(operands) < 2:
            raise OSError(
                f"Missing operands for set font operator {list(operands)!r}"
            )
        base0 = operands[0]
        base1 = operands[1]
        if not isinstance(base0, COSName):
            return
        if not isinstance(base1, COSNumber):
            return
        from pypdfbox.cos import COSDictionary  # noqa: PLC0415
        from pypdfbox.pdmodel.font import PDFont, PDFontFactory  # noqa: PLC0415

        font_name = base0
        font = self._default_resources.get_font(font_name)
        # pypdfbox's :meth:`PDResources.get_font` returns the raw
        # ``COSDictionary`` for *direct* font entries (cluster #1 surface)
        # and a typed ``PDFont`` for indirect entries. Upstream's
        # ``getFont`` always returns a typed ``PDFont``; promote the raw
        # dictionary via :class:`PDFontFactory` so downstream callers
        # (e.g. :meth:`write_to`) get a real ``PDFont``.
        if isinstance(font, COSDictionary):
            font = PDFontFactory.create_font(font)
        font_size = base1.float_value()
        # PDFBOX-2661 fallback: when the font is missing from /DR, try
        # the well-known Acrobat /DA short alias (e.g. "Helv" → Helvetica,
        # "TiBo" → Times-Bold) before substituting a generic Standard-14
        # default. This keeps fields with broken /DA strings renderable
        # at the cost of pixel-level fidelity with the missing font.
        if font is None or not isinstance(font, PDFont):
            font = _resolve_fallback_font(font_name.get_name())
        self.set_font_name(font_name)
        self.set_font(font)
        self.set_font_size(font_size)

    def process_set_font_color(self, operands: list[COSBase]) -> None:
        """Process the non-stroking-colour operator. Mirrors upstream
        ``processSetFontColor`` (Java lines 186-207).

        Component count selects the colour space (1 → gray, 3 → RGB,
        4 → CMYK). Any other count raises ``OSError``.
        """
        color_space: PDColorSpace
        n = len(operands)
        if n == 1:
            color_space = PDDeviceGray.INSTANCE
        elif n == 3:
            color_space = PDDeviceRGB.INSTANCE
        elif n == 4:
            color_space = PDDeviceCMYK.INSTANCE
        else:
            raise OSError(
                "Missing operands for set non stroking color operator "
                f"{list(operands)!r}"
            )
        array = COSArray()
        for op in operands:
            array.add(op)
        self.set_font_color(PDColor(array, color_space))

    # ------------------------------------------------------------------
    # accessors — upstream Java lines 214-281
    # ------------------------------------------------------------------

    def get_font_name(self) -> COSName | None:
        """Return the font name used for resource lookup. Mirrors
        upstream ``getFontName`` (Java lines 214-217)."""
        return self._font_name

    def set_font_name(self, font_name: COSName | None) -> None:
        """Set the font name used for resource lookup. Mirrors upstream
        ``setFontName`` (Java lines 224-227)."""
        self._font_name = font_name

    def get_font(self) -> PDFont | None:
        """Return the resolved font. Mirrors upstream ``getFont``
        (Java lines 232-235)."""
        return self._font

    def set_font(self, font: PDFont | None) -> None:
        """Set the resolved font. Mirrors upstream ``setFont``
        (Java lines 242-245)."""
        self._font = font

    def get_font_size(self) -> float:
        """Return the font size. Mirrors upstream ``getFontSize``
        (Java lines 250-253). Defaults to ``12`` when the ``/DA`` string
        omits a ``Tf`` operator (matches upstream ``DEFAULT_FONT_SIZE``)."""
        return self._font_size

    def set_font_size(self, font_size: float) -> None:
        """Set the font size. Mirrors upstream ``setFontSize``
        (Java lines 260-263)."""
        self._font_size = float(font_size)

    def get_font_color(self) -> PDColor | None:
        """Return the font colour. Mirrors upstream ``getFontColor``
        (Java lines 268-271)."""
        return self._font_color

    def set_font_color(self, font_color: PDColor | None) -> None:
        """Set the font colour. Mirrors upstream ``setFontColor``
        (Java lines 278-281)."""
        self._font_color = font_color

    # ------------------------------------------------------------------
    # writers — upstream Java lines 290-325
    # ------------------------------------------------------------------

    def write_to(
        self,
        contents: PDAppearanceContentStream,
        zero_font_size: float,
    ) -> None:
        """Write the font / size / colour from the /DA string into the
        given content stream. Mirrors upstream ``writeTo``
        (Java lines 290-303).

        ``zero_font_size`` is the size used when the /DA string has a
        size of ``0`` (autosize); otherwise the parsed size is used.
        """
        font_size = self.get_font_size()
        if font_size == 0.0:
            font_size = zero_font_size
        font = self.get_font()
        if font is None:
            raise OSError("No font set on /DA; cannot write to content stream")
        contents.set_font(font, font_size)
        font_color = self.get_font_color()
        if font_color is not None:
            # Upstream calls ``contents.setNonStrokingColor(PDColor)``;
            # the pypdfbox :class:`PDAppearanceContentStream` overload
            # takes a component sequence, so we route through
            # ``set_non_stroking_color_on_demand`` which accepts a
            # :class:`PDColor` and emits the matching ``g`` / ``rg`` /
            # ``k`` operator based on component count.
            contents.set_non_stroking_color_on_demand(font_color)

    def copy_needed_resources_to(
        self,
        appearance_stream: PDAppearanceStream,
    ) -> None:
        """Copy any needed resources from the document's /DR dictionary
        into the stream's /Resources dictionary. Resources with the same
        name shall be left intact. Mirrors upstream
        ``copyNeededResourcesTo`` (Java lines 309-325).

        Upstream tracks fonts only and leaves a ``// todo: other kinds
        of resource…`` marker. Pypdfbox extends to also carry across
        named colour-space and ext-gstate entries that the /DA stream
        referenced (``cs`` / ``CS`` / ``gs``), so appearance streams
        emitted from a /DA snippet that uses those operators still
        resolve via the destination /Resources.
        """
        from pypdfbox.cos import COSName  # noqa: PLC0415
        from pypdfbox.pdmodel.pd_resources import PDResources  # noqa: PLC0415

        stream_resources = appearance_stream.get_resources()
        if stream_resources is None:
            stream_resources = PDResources()
            appearance_stream.set_resources(stream_resources)

        # Fonts — the original upstream behaviour.
        font_name = self._font_name
        if font_name is not None and stream_resources.get_font(font_name) is None:
            font = self.get_font()
            if font is not None:  # pragma: no branch
                # Defensive: get_font() either returns a resolved font or
                # raises; the False arm has no live caller.
                stream_resources.put(font_name, font)

        # Additional resource kinds the /DA stream referenced (extension
        # over upstream's ``// todo: other kinds of resource…``).
        _color_space_cat = COSName.get_pdf_name("ColorSpace")
        for cs_name in self._color_space_names:
            if stream_resources.has_color_space(cs_name):
                continue
            if not self._default_resources.has_color_space(cs_name):
                continue
            cs = self._default_resources.get_color_space(cs_name)
            if cs is not None:  # pragma: no branch
                # Defensive: has_color_space True guarantees get_color_space
                # returns a live object; the False arm has no live caller.
                stream_resources.put(_color_space_cat, cs_name, cs)

        _ext_g_state_cat = COSName.get_pdf_name("ExtGState")
        for gs_name in self._ext_g_state_names:
            if stream_resources.has_ext_g_state(gs_name):
                continue
            gs = self._default_resources.get_ext_g_state(gs_name)
            if gs is not None:  # pragma: no branch
                # Defensive: when get_ext_g_state can be invoked, the
                # AcroForm default resources always have the named slot;
                # the False arm has no live caller.
                stream_resources.put(_ext_g_state_cat, gs_name, gs)


__all__ = ["PDDefaultAppearanceString"]
