from __future__ import annotations

from abc import ABC, abstractmethod
from typing import IO, Any

from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


class PDContentStream(ABC):
    """
    Anything that yields PDF content-stream bytes alongside its resource
    dictionary, bounding box, and transformation matrix.

    Mirrors ``org.apache.pdfbox.contentstream.PDContentStream``. Concrete
    upstream implementations include ``PDPage``, ``PDFormXObject``,
    ``PDPattern`` (tiling), ``PDAnnotation`` appearance streams, and
    ``PDType3CharProc``.

    Note on package: upstream nests this interface under
    ``org.apache.pdfbox.contentstream`` (NOT ``pdmodel.common``); we
    follow upstream and keep it in ``pypdfbox.contentstream``.

    Note on ``get_matrix`` return type: upstream returns
    ``org.apache.pdfbox.util.Matrix``. The ``Matrix`` class is not yet
    ported (lands with the rendering cluster); for cluster #1 the
    return is typed as ``Any`` so subclasses ported in later clusters
    can return either a ``COSArray`` (the on-disk form) today or a real
    ``Matrix`` once available without breaking the signature.
    """

    @abstractmethod
    def get_contents(self) -> IO[bytes]:
        """Stream of raw content-stream bytes (post-filter decode)."""

    @abstractmethod
    def get_contents_for_random_access(self) -> RandomAccessRead:
        """Random-access view of the same bytes — needed by token parsers
        that peek/seek."""

    def get_contents_for_stream_parsing(self) -> RandomAccessRead:
        """Default delegates to :meth:`get_contents_for_random_access`,
        matching the upstream Java default method."""
        return self.get_contents_for_random_access()

    @abstractmethod
    def get_resources(self) -> PDResources | None:
        """Associated ``/Resources`` dictionary, or ``None`` if the
        consumer should walk up the parent chain."""

    @abstractmethod
    def get_bbox(self) -> PDRectangle:
        """Bounding box for the stream's graphics."""

    def get_b_box(self) -> PDRectangle:
        """Upstream-named alias of :meth:`get_bbox`.

        Mirrors upstream ``PDContentStream.getBBox()`` snake-cased one
        capital at a time (PDFBox's ``BBox`` → ``b_box``). Concrete
        subclasses override :meth:`get_bbox`; this alias delegates to it
        so callers using the upstream-letter-for-letter snake_case name
        get the same value without each subclass needing two overrides.
        """
        return self.get_bbox()

    @abstractmethod
    def get_matrix(self) -> Any:
        """Transformation matrix applied to the stream. See class
        docstring for the return-type note."""
