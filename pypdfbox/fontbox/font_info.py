"""Per-font metadata returned by :class:`FontProvider`.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontInfo`` from PDFBox 3.0.

A :class:`FontInfo` carries the stable identity bits of a system font
that the :class:`FontMapper` needs to score candidates: PostScript name,
on-disk format, OS/2 weight class, OS/2 family class, head-table
mac-style flags, code-page-range bitmaps, and a Panose classification.
The actual font program is loaded lazily via :meth:`get_font` so the
font-info list can be enumerated without materialising every TTF on
disk.

Upstream Java exposes seven abstract accessors plus three concrete
helpers (``getWeightClassAsPanose``, ``getCodePageRange``, ``toString``).
The concrete helpers are package-private in Java; we surface them as
public methods because Python has no equivalent visibility level and
the helpers are useful for callers building their own font scorers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .font_format import FontFormat

if TYPE_CHECKING:
    from .font_box_font import FontBoxFont


# usWeightClass → Panose weight mapping. Lifted verbatim from upstream
# ``FontInfo.getWeightClassAsPanose``. Panose weight runs 0..11; OS/2
# weights are multiples of 100. Anything outside the table maps to 0
# (Panose "Any"), matching upstream's ``default`` branch.
_USWEIGHT_TO_PANOSE: dict[int, int] = {
    -1: 0,
    0: 0,
    100: 2,
    200: 3,
    300: 4,
    400: 5,
    500: 6,
    600: 7,
    700: 8,
    800: 9,
    900: 10,
}


class FontInfo(ABC):
    """Information about a font discovered by a :class:`FontProvider`.

    Mirrors the upstream abstract class. Subclasses must provide all
    eight abstract accessors; the three concrete helpers
    (:meth:`get_weight_class_as_panose`, :meth:`get_code_page_range`,
    :meth:`__str__`) are inherited unchanged.
    """

    # ---------- abstract accessors ----------

    @abstractmethod
    def get_post_script_name(self) -> str:
        """Return the PostScript name of the font.

        Mirrors upstream ``String getPostScriptName()``.
        """

    @abstractmethod
    def get_format(self) -> FontFormat:
        """Return the font's on-disk format (TTF / OTF / PFB).

        Mirrors upstream ``FontFormat getFormat()``.
        """

    @abstractmethod
    def get_cid_system_info(self) -> Any | None:
        """Return the :class:`PDCIDSystemInfo` of the font, if any.

        Mirrors upstream ``CIDSystemInfo getCIDSystemInfo()``. ``None``
        for non-CID fonts. Typed as ``Any`` here to avoid an import
        cycle with :mod:`pypdfbox.pdmodel.font.pd_cid_system_info`.
        """

    @abstractmethod
    def get_font(self) -> FontBoxFont:
        """Return a fresh :class:`FontBoxFont` for the font.

        Mirrors upstream ``FontBoxFont getFont()``. Implementors must
        not cache the return value here unless doing so via a
        :class:`FontCache` — the upstream contract is explicit on that
        point.
        """

    @abstractmethod
    def get_family_class(self) -> int:
        """Return ``OS/2.sFamilyClass``, or ``-1`` if unavailable.

        Mirrors upstream ``int getFamilyClass()``.
        """

    @abstractmethod
    def get_weight_class(self) -> int:
        """Return ``OS/2.usWeightClass``, or ``-1`` if unavailable.

        Mirrors upstream ``int getWeightClass()``.
        """

    @abstractmethod
    def get_code_page_range1(self) -> int:
        """Return ``OS/2.ulCodePageRange1``, or ``0`` if unavailable.

        Mirrors upstream ``int getCodePageRange1()``.
        """

    @abstractmethod
    def get_code_page_range2(self) -> int:
        """Return ``OS/2.ulCodePageRange2``, or ``0`` if unavailable.

        Mirrors upstream ``int getCodePageRange2()``.
        """

    @abstractmethod
    def get_mac_style(self) -> int:
        """Return ``head.macStyle``, or ``-1`` if unavailable.

        Mirrors upstream ``int getMacStyle()``.
        """

    @abstractmethod
    def get_panose(self) -> Any | None:
        """Return the Panose classification of the font, if any.

        Mirrors upstream ``PDPanoseClassification getPanose()``. Typed
        as ``Any`` to avoid an import cycle with
        :mod:`pypdfbox.pdmodel.font.pd_panose_classification`.
        """

    # ---------- concrete helpers ----------

    def get_weight_class_as_panose(self) -> int:
        """Translate ``usWeightClass`` to a Panose weight (0..10).

        Mirrors upstream package-private ``getWeightClassAsPanose()``.
        Anything outside the documented OS/2 weight ladder maps to 0
        (Panose "Any") — matches upstream's ``default`` branch.
        """
        return _USWEIGHT_TO_PANOSE.get(self.get_weight_class(), 0)

    def get_code_page_range(self) -> int:
        """Return the combined 64-bit code-page-range bitmap.

        Mirrors upstream package-private ``getCodePageRange()``: range1
        in the low 32 bits, range2 in the high 32 bits, both treated
        as unsigned. Java's ``& 0x00000000ffffffffL`` mask is a no-op
        in Python (ints are unbounded) but we apply it for parity so
        a negative-int implementation still produces an unsigned
        64-bit value.
        """
        range1 = self.get_code_page_range1() & 0xFFFFFFFF
        range2 = self.get_code_page_range2() & 0xFFFFFFFF
        return (range2 << 32) | range1

    # ---------- repr ----------

    def to_string(self) -> str:
        """Mirror upstream ``FontInfo.toString()``.

        Upstream format (Java lines 143-146):
        ``getPostScriptName() + " (" + getFormat() +
        ", mac: 0x" + Integer.toHexString(getMacStyle()) +
        ", os/2: 0x" + Integer.toHexString(getFamilyClass()) +
        ", cid: " + getCIDSystemInfo() + ")"``.
        """
        return (
            f"{self.get_post_script_name()} ({self.get_format()}, "
            f"mac: 0x{self.get_mac_style():x}, "
            f"os/2: 0x{self.get_family_class():x}, "
            f"cid: {self.get_cid_system_info()})"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["FontInfo"]
