from __future__ import annotations

from .pd_color_space import PDColorSpace


class PDSpecialColorSpace(PDColorSpace):
    """Special colour spaces add features or properties to an underlying
    colour space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDSpecialColorSpace``.

    Upstream declares no members of its own — it is an intermediate abstract
    marker between ``PDColorSpace`` and the concrete special color spaces
    (``PDSeparation``, ``PDDeviceN``, ``PDIndexed``, ``PDPattern``). The
    constructor simply forwards to ``PDColorSpace`` so the array-form slot is
    populated identically.
    """


__all__ = ["PDSpecialColorSpace"]
