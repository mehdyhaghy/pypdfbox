from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_destination import PDDestination
    from .pd_destination_name_tree_node import PDDestinationNameTreeNode
    from .pd_named_destination import PDNamedDestination
    from .pd_page_destination import PDPageDestination
    from .pd_page_fit_destination import PDPageFitDestination
    from .pd_page_fit_height_destination import PDPageFitHeightDestination
    from .pd_page_fit_rectangle_destination import PDPageFitRectangleDestination
    from .pd_page_fit_width_destination import PDPageFitWidthDestination
    from .pd_page_xyz_destination import PDPageXYZDestination

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDDestination": ".pd_destination",
        "PDDestinationNameTreeNode": ".pd_destination_name_tree_node",
        "PDNamedDestination": ".pd_named_destination",
        "PDPageDestination": ".pd_page_destination",
        "PDPageFitDestination": ".pd_page_fit_destination",
        "PDPageFitHeightDestination": ".pd_page_fit_height_destination",
        "PDPageFitRectangleDestination": ".pd_page_fit_rectangle_destination",
        "PDPageFitWidthDestination": ".pd_page_fit_width_destination",
        "PDPageXYZDestination": ".pd_page_xyz_destination",
    },
)

__all__ = [
    "PDDestination",
    "PDDestinationNameTreeNode",
    "PDNamedDestination",
    "PDPageDestination",
    "PDPageFitDestination",
    "PDPageFitHeightDestination",
    "PDPageFitRectangleDestination",
    "PDPageFitWidthDestination",
    "PDPageXYZDestination",
]
