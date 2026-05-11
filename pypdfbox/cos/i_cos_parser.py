from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read_view import RandomAccessReadView

    from .cos_base import COSBase
    from .cos_object import COSObject


class ICOSParser(ABC):
    """Parser-side hooks the COS layer relies on for indirect-reference
    resolution and stream materialization.

    Mirrors upstream ``org.apache.pdfbox.cos.ICOSParser`` (an interface
    in Java). Implementations dereference ``COSObject`` placeholders and
    hand out sliced ``RandomAccessReadView`` views over the underlying
    PDF source for stream bodies.
    """

    @abstractmethod
    def dereference_cos_object(self, obj: COSObject) -> COSBase:
        """Resolve the indirect ``COSObject`` placeholder to its concrete
        ``COSBase``. Mirrors upstream ``dereferenceCOSObject`` (Java
        line 33).
        """

    @abstractmethod
    def create_random_access_read_view(
        self, start_position: int, stream_length: int
    ) -> RandomAccessReadView:
        """Create a read-only view onto the underlying source spanning
        ``[start_position, start_position + stream_length)``. Mirrors
        upstream ``createRandomAccessReadView`` (Java line 43)."""
