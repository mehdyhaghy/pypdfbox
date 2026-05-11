from __future__ import annotations

from ..operator_processor import OperatorProcessor


class GraphicsOperatorProcessor(OperatorProcessor):
    """Base class for graphics operators. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.GraphicsOperatorProcessor``.

    Upstream defines a thin subclass of ``OperatorProcessor`` that
    narrows the engine binding from ``PDFStreamEngine`` to
    ``PDFGraphicsStreamEngine`` via a ``getGraphicsContext`` accessor.

    In pypdfbox the rendering / graphics engine is not yet implemented
    (it lands with the rendering cluster), so the narrowed type does
    not exist as a separate class. The subclass therefore exposes
    :meth:`get_graphics_context` as a typed alias of
    :meth:`OperatorProcessor.get_context` — when the graphics engine
    arrives, this accessor will be the single point that gets a tighter
    return type without touching individual operator implementations.
    """

    def get_graphics_context(self):  # noqa: ANN201 - mirrors upstream
        """Return the bound stream engine, typed as the graphics engine
        once the rendering cluster lands."""
        return self.get_context()


__all__ = ["GraphicsOperatorProcessor"]
