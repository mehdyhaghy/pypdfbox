"""OpenType layout-common tables (Coverage, FeatureList, LookupList, ...).

Mirrors ``org.apache.fontbox.ttf.table.common``.
"""

from .coverage_table_format1 import CoverageTableFormat1
from .coverage_table_format2 import CoverageTableFormat2
from .feature_list_table import FeatureListTable
from .lookup_list_table import LookupListTable
from .range_record import RangeRecord

__all__ = [
    "CoverageTableFormat1",
    "CoverageTableFormat2",
    "FeatureListTable",
    "LookupListTable",
    "RangeRecord",
]
