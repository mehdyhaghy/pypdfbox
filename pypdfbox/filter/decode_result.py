from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pypdfbox.cos import COSDictionary


@dataclass
class DecodeResult:
    """Outcome of a ``Filter.decode()`` call.

    Mirrors `org.apache.pdfbox.filter.DecodeResult`. Some filters
    (notably DCT and JPX) update the stream parameters during decode —
    e.g. populating ``/ColorSpace`` from JPEG markers. ``parameters``
    starts as a copy of the input dictionary and may be mutated.

    JPX-specific outputs (``color_space`` / ``jpx_smask``) are typed as
    :class:`typing.Any` to avoid a hard dependency from this leaf module
    on ``pdmodel.graphics.color`` / ``BufferedImage``-equivalent classes.
    """

    parameters: COSDictionary = field(default_factory=COSDictionary)
    bytes_written: int = 0
    #: Embedded JPX color space, populated by ``JPXFilter`` when the
    #: codestream carries a ``COLR`` box. ``None`` for non-JPX filters.
    #: Kept as :class:`typing.Any` to avoid pulling in the color-space
    #: package at import time (mirrors the field-on-``DecodeResult``
    #: pattern from upstream PDFBox without the type coupling).
    color_space: Any = None
    #: Embedded JPX soft-mask image, populated when the JPX codestream
    #: carries an opacity channel. ``None`` for non-JPX filters.
    jpx_smask: Any = None

    # ------------------------------------------------------------------
    # Upstream-named accessors (mirror ``org.apache.pdfbox.filter.DecodeResult``).
    # ------------------------------------------------------------------

    @staticmethod
    def create_default() -> DecodeResult:
        """Return a ``DecodeResult`` with empty parameters and no embedded
        color space or smask.

        Mirrors ``DecodeResult#createDefault``. Used by filters that have
        nothing to surface back to the caller (e.g. plain pass-through).
        """
        return DecodeResult(parameters=COSDictionary())

    def get_parameters(self) -> COSDictionary:
        """Return the (possibly repaired) stream parameters.

        Mirrors ``DecodeResult#getParameters``.
        """
        return self.parameters

    def get_jpx_color_space(self) -> Any:
        """Return the embedded JPX color space, or ``None`` when the
        decoder did not encounter one.

        Mirrors ``DecodeResult#getJPXColorSpace``.
        """
        return self.color_space

    def set_color_space(self, color_space: Any) -> None:
        """Set the embedded JPX color space.

        Mirrors the package-private ``DecodeResult#setColorSpace`` setter
        upstream — used by ``JPXFilter`` after parsing the codestream.
        """
        self.color_space = color_space

    def get_jpx_smask(self) -> Any:
        """Return the embedded JPX soft-mask image, or ``None``.

        Mirrors ``DecodeResult#getJPXSMask``.
        """
        return self.jpx_smask

    def set_jpx_smask(self, smask: Any) -> None:
        """Set the embedded JPX soft-mask image.

        Mirrors the package-private ``DecodeResult#setJPXSMask`` setter
        upstream.
        """
        self.jpx_smask = smask

    def get_jpxs_mask(self) -> Any:
        """Alternate snake-case spelling of :meth:`get_jpx_smask`.

        Upstream ``getJPXSMask`` is ambiguous when split into snake_case —
        ``jpx_smask`` (JPX + SMask) and ``jpxs_mask`` (JPXS + Mask) both
        appear in the wild. This alias keeps callers that picked the
        latter spelling working without forcing a rename.
        """
        return self.get_jpx_smask()

    def set_jpxs_mask(self, smask: Any) -> None:
        """Alternate snake-case spelling of :meth:`set_jpx_smask`. See
        :meth:`get_jpxs_mask` for the rationale."""
        self.set_jpx_smask(smask)
