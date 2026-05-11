"""Utility helpers ported from ``org.apache.pdfbox.util``.

This package mirrors the upstream layout for compatibility. New ports added
in Wave 1281 cover ``Hex``, ``IterativeMergeSort``, ``Matrix``, ``Vector``,
``NumberFormatUtil``, ``SmallMap``/``SmallMapEntry``, ``StringUtil`` and
``XMLUtil``.
"""

from __future__ import annotations

from pypdfbox.util.hex import Hex
from pypdfbox.util.iterative_merge_sort import IterativeMergeSort
from pypdfbox.util.matrix import Matrix
from pypdfbox.util.number_format_util import NumberFormatUtil
from pypdfbox.util.small_map import SmallMap, SmallMapEntry
from pypdfbox.util.string_util import StringUtil
from pypdfbox.util.vector import Vector
from pypdfbox.util.xml_util import XMLUtil

__all__ = [
    "Hex",
    "IterativeMergeSort",
    "Matrix",
    "NumberFormatUtil",
    "SmallMap",
    "SmallMapEntry",
    "StringUtil",
    "Vector",
    "XMLUtil",
]
