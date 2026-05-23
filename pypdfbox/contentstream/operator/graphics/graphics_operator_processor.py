from __future__ import annotations

from ..operator_processor import OperatorProcessor


class GraphicsOperatorProcessor(OperatorProcessor):
    """Base class for graphics operators. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.GraphicsOperatorProcessor``.

    Upstream defines a thin subclass of ``OperatorProcessor`` that
    narrows the engine binding from ``PDFStreamEngine`` to
    ``PDFGraphicsStreamEngine`` via a ``getGraphicsContext`` accessor.
    :meth:`get_graphics_context` is the single point that returns the
    graphics-typed engine for graphics operator subclasses.
    """

    def get_graphics_context(self):  # noqa: ANN201 - mirrors upstream
        """Return the bound stream engine, typed as the graphics engine."""
        return self.get_context()


__all__ = ["GraphicsOperatorProcessor"]
