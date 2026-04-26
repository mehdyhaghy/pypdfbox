from __future__ import annotations

from .pd_destination import PDDestination
from .pd_named_destination import PDNamedDestination
from .pd_page_destination import PDPageDestination
from .pd_page_fit_destination import PDPageFitDestination
from .pd_page_fit_height_destination import PDPageFitHeightDestination
from .pd_page_fit_width_destination import PDPageFitWidthDestination
from .pd_page_xyz_destination import PDPageXYZDestination

__all__ = [
    "PDDestination",
    "PDNamedDestination",
    "PDPageDestination",
    "PDPageFitDestination",
    "PDPageFitHeightDestination",
    "PDPageFitWidthDestination",
    "PDPageXYZDestination",
]
