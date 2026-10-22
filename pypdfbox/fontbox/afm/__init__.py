"""Adobe Font Metrics (AFM) parser and data classes.

Mirrors ``org.apache.fontbox.afm`` from upstream Apache PDFBox: classes
:class:`FontMetrics`, :class:`CharMetric`, :class:`KernPair`,
:class:`Ligature`, :class:`Composite`, :class:`CompositePart`,
:class:`TrackKern`, plus the streaming :class:`AFMParser`.

The parser is implemented in pure Python (no upstream Java dependency)
but recognises the same set of AFM keywords and produces an object graph
shaped like upstream's :class:`org.apache.fontbox.afm.FontMetrics`.

Per the AFM spec (Adobe Tech Note 5004) the default file encoding is
ISO-8859-1; the parser opens text files with that codec.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .afm_parser import AFMParser
    from .char_metric import CharMetric
    from .composite import Composite
    from .composite_part import CompositePart
    from .font_metrics import FontMetrics
    from .kern_pair import KernPair
    from .ligature import Ligature
    from .track_kern import TrackKern

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AFMParser": ".afm_parser",
        "CharMetric": ".char_metric",
        "Composite": ".composite",
        "CompositePart": ".composite_part",
        "FontMetrics": ".font_metrics",
        "KernPair": ".kern_pair",
        "Ligature": ".ligature",
        "TrackKern": ".track_kern",
    },
)

__all__ = [
    "AFMParser",
    "CharMetric",
    "Composite",
    "CompositePart",
    "FontMetrics",
    "KernPair",
    "Ligature",
    "TrackKern",
]
