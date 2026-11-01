"""OpenType layout-common tables (Coverage, FeatureList, LookupList, ...).

Mirrors ``org.apache.fontbox.ttf.table.common``.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .coverage_table_format1 import CoverageTableFormat1
    from .coverage_table_format2 import CoverageTableFormat2
    from .feature_list_table import FeatureListTable
    from .lookup_list_table import LookupListTable
    from .range_record import RangeRecord

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CoverageTableFormat1": ".coverage_table_format1",
        "CoverageTableFormat2": ".coverage_table_format2",
        "FeatureListTable": ".feature_list_table",
        "LookupListTable": ".lookup_list_table",
        "RangeRecord": ".range_record",
    },
)

__all__ = [
    "CoverageTableFormat1",
    "CoverageTableFormat2",
    "FeatureListTable",
    "LookupListTable",
    "RangeRecord",
]
