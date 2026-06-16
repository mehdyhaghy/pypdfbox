from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSName, COSNumber
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)

if TYPE_CHECKING:
    from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
    from pypdfbox.pdmodel.graphics.color import PDColorSpace

# Map each device colour space's canonical name to its ``/ColorSpace``
# COSName, so the device operators can resolve through ``/Resources`` the
# same way upstream's ``SetNonStrokingDeviceGrayColor`` &c. do
# (``getResources().getColorSpace(COSName.DEVICEGRAY)``), picking up any
# ``/DefaultGray`` / ``/DefaultRGB`` / ``/DefaultCMYK`` substitution.
_DEVICE_COS_NAME = {
    "DeviceGray": COSName.get_pdf_name("DeviceGray"),
    "DeviceRGB": COSName.get_pdf_name("DeviceRGB"),
    "DeviceCMYK": COSName.get_pdf_name("DeviceCMYK"),
}


def _resolve_device_color_space(
    engine: PDFStreamEngine,
    fallback: PDColorSpace,
) -> PDColorSpace:
    """Resolve the device colour space through the engine's resources.

    Mirrors upstream's ``getResources().getColorSpace(COSName.DEVICE*)``
    so a page-level ``/DefaultGray`` / ``/DefaultRGB`` / ``/DefaultCMYK``
    override is honoured. Falls back to the device singleton when no
    resources are present or resolution fails (the operator must still
    set a colour)."""
    device_name = _DEVICE_COS_NAME.get(fallback.get_name())
    if device_name is None:
        return fallback
    get_resources = getattr(engine, "get_resources", None)
    if get_resources is None:
        return fallback
    resources = get_resources()
    if resources is None:
        return fallback
    resolved = resources.get_color_space(device_name)
    return resolved if resolved is not None else fallback


def set_device_color(
    engine: PDFStreamEngine | None,
    operands: list[COSBase],
    *,
    color_space: PDColorSpace,
    component_count: int,
    stroking: bool,
) -> None:
    """Set the device colour space on the graphics state, then the colour.

    Mirrors upstream ``SetNonStrokingDeviceGrayColor.process`` (and the
    five sibling device operators): the operator first installs the
    resolved device colour space onto the graphics state's stroking /
    non-stroking colour-space slot, then sets the colour in that space.
    Installing the colour space matters when a named colour space was set
    earlier with ``cs`` / ``CS`` — a subsequent ``g`` / ``rg`` / ``k``
    must switch the current colour space so later bare ``sc`` / ``scn``
    operands are interpreted against the device space.

    Order matches upstream exactly: the colour space is installed onto the
    graphics state *first* (right after the should-process gate), then the
    colour is set. Upstream throws ``MissingOperandException`` from the
    inherited ``SetColor.process`` for a too-short operand list — by which
    point the colour space has already been switched — so a malformed
    ``0.1 0.2 rg`` still leaves the current colour space at ``DeviceRGB``
    even though the colour value is left unchanged.
    """
    if engine is None or not engine.is_should_process_color_operators():
        return
    resolved_cs = _resolve_device_color_space(engine, color_space)
    graphics_state = engine.get_graphics_state()
    if graphics_state is not None:
        if stroking:
            setter = getattr(
                graphics_state, "set_stroking_color_space", None
            )
        else:
            setter = getattr(
                graphics_state, "set_non_stroking_color_space", None
            )
        if setter is not None:
            setter(resolved_cs)
    # Too few operands / a non-numeric operand: upstream's SetColor.process
    # throws / bails before setColor, so the colour stays at its previous
    # value (the colour space switch above is still in effect).
    if len(operands) < component_count:
        return
    components: list[float] = []
    for operand in operands[:component_count]:
        if not isinstance(operand, COSNumber):
            return
        components.append(operand.float_value())
    color = PDColor(components, resolved_cs)
    if stroking:
        engine.set_stroking_color(color)
    else:
        engine.set_non_stroking_color(color)


__all__ = [
    "PDDeviceCMYK",
    "PDDeviceGray",
    "PDDeviceRGB",
    "set_device_color",
]
