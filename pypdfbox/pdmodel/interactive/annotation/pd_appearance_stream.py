from __future__ import annotations

from pypdfbox.cos import COSStream


class PDAppearanceStream:
    """
    An appearance stream is a Form XObject — a self-contained content
    stream rendered inside the annotation rectangle. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream``.

    Upstream extends ``PDFormXObject``. The cluster #6 lite port of
    PDAppearanceStream wraps a ``COSStream`` directly without going
    through ``PDFormXObject`` — the form XObject base brings in
    ``/Type /XObject``, ``/Subtype /Form``, ``/BBox``, ``/Matrix``,
    ``/Resources`` semantics that aren't yet exercised by the appearance
    surface we expose to callers. The full inheritance chain
    ``PDAppearanceStream -> PDFormXObject -> PDXObject`` lands with the
    rendering cluster (PRD §6.13). Documented in ``CHANGES.md``.
    """

    def __init__(self, stream: COSStream) -> None:
        if not isinstance(stream, COSStream):
            raise TypeError(
                "PDAppearanceStream requires a COSStream; got "
                f"{type(stream).__name__}"
            )
        self._stream = stream

    def get_cos_object(self) -> COSStream:
        return self._stream


__all__ = ["PDAppearanceStream"]
