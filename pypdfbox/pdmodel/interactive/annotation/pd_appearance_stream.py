from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.pd_resources import PDResources

_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]


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

    The ``get_stream`` / ``get_resources`` / ``set_resources`` accessors
    cover the surface needed by :class:`PDAppearanceContentStream` to
    open a writer against the appearance.
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

    def get_stream(self) -> COSStream:
        """Return the underlying ``COSStream`` body — mirrors upstream
        ``PDFormXObject.getStream()`` (which returns the ``PDStream``
        wrapper; the lite port exposes the raw ``COSStream`` directly
        because :class:`PDStream` isn't on the appearance surface yet)."""
        return self._stream

    # ---------- /Resources ----------

    def get_resources(self) -> PDResources | None:
        """``/Resources`` of this appearance stream, or ``None`` if absent.

        Mirrors upstream ``PDFormXObject.getResources()``. When the key
        is present but the value isn't a dictionary, returns an empty
        :class:`PDResources` (PDFBOX-4372 — guards against a
        self-reference where the form refers to itself)."""
        value = self._stream.get_dictionary_object(_RESOURCES)
        if isinstance(value, COSDictionary):
            return PDResources(value)
        if self._stream.contains_key(_RESOURCES):
            return PDResources()
        return None

    def set_resources(
        self, resources: PDResources | COSDictionary | None
    ) -> None:
        """Set the ``/Resources`` entry for this appearance stream."""
        if resources is None:
            self._stream.remove_item(_RESOURCES)
            return
        target = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        self._stream.set_item(_RESOURCES, target)


__all__ = ["PDAppearanceStream"]
