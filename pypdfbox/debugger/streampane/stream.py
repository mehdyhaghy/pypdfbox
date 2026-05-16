"""Pure-data wrapper around a ``COSStream`` for the debugger Stream pane.

Tkinter-agnostic port of ``org.apache.pdfbox.debugger.streampane.Stream``.

The class exposes a list of "filter views" that the StreamPane combobox
displays:

* ``"Image"`` — only when the stream is an Image XObject (or thumbnail).
* ``"Decoded (Plain Text)"`` — full decode through every ``/Filter``.
* zero or more ``"Keep <FilterA> & <FilterB> ..."`` partials — produced
  by stopping decoding before filter *i*. Skipped when the stream has
  fewer than two filters.
* ``"Encoded (<filter chain>)"`` — raw bytes, undecoded.

Each entry maps to the list of ``stop_filters`` accepted by
``PDStream.create_input_stream``; ``None`` means the canonical decoded
or raw views, handled by the dispatcher in :meth:`get_stream`.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

_LOG = logging.getLogger(__name__)


class Stream:
    """Surface a ``COSStream`` in the views the debugger needs.

    Mirrors upstream ``Stream`` (package-private). Image rendering is
    deferred to :meth:`get_image`, which lazily imports
    ``PDImageXObject`` (rendering subsystem) so importing the debugger
    package does not pull in the image pipeline.
    """

    DECODED: str = "Decoded (Plain Text)"
    IMAGE: str = "Image"

    def __init__(self, cos_stream: COSStream, is_thumb: bool) -> None:
        """Build a view over ``cos_stream``.

        :param cos_stream: the underlying ``COSStream``.
        :param is_thumb: ``True`` when ``cos_stream`` is a page's
            ``/Thumb`` image — upstream treats this as an implicit
            image stream even when ``/Subtype`` is absent.
        """
        self._strm = cos_stream
        self._is_thumb = is_thumb
        self._is_image = self.is_image_stream(cos_stream, is_thumb)
        self._is_xml_metadata = self.is_xml_metadata_stream(cos_stream)
        self._filters: OrderedDict[str, list[str] | None] = self.create_filter_list(
            cos_stream
        )

    # ---- accessors ---------------------------------------------------------

    def is_image(self) -> bool:
        """Return ``True`` when the stream is an Image XObject / thumbnail."""
        return self._is_image

    def is_xml_metadata(self) -> bool:
        """Return ``True`` when the stream is an XML metadata stream."""
        return self._is_xml_metadata

    def get_filter_list(self) -> list[str]:
        """Return the ordered list of filter view labels."""
        return list(self._filters.keys())

    # ---- views -------------------------------------------------------------

    def get_stream(self, key: str) -> BinaryIO | None:
        """Return a binary stream for the filter view ``key``.

        ``None`` is returned when the requested view fails to decode —
        upstream logs and returns ``null``; we log and return ``None``.
        Unknown ``key`` values likewise yield ``None`` (upstream relies
        on Java ``Map.get`` returning ``null`` followed by a no-op
        ``createInputStream(null)``; we make the absence explicit).
        """
        try:
            if key == self.DECODED:
                return self._strm.create_input_stream()
            if key == self.get_filtered_label():
                return self._strm.create_raw_input_stream()
            if key not in self._filters:
                return None
            return PDStream(self._strm).create_input_stream(self._filters[key])
        except OSError as exc:
            _LOG.error("%s", exc)
        return None

    def get_image(self, resources: object | None) -> object | None:
        """Return a decoded PIL image for an Image XObject stream.

        ``resources`` must be a ``pypdfbox.pdmodel.PDResources`` (typed
        loosely to avoid an import cycle with the rendering subsystem).
        Returns ``None`` on decode failure, matching upstream behaviour.
        """
        try:
            from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
                PDImageXObject,
            )
        except ImportError:  # pragma: no cover — image subsystem unavailable
            _LOG.error("PDImageXObject unavailable")
            return None

        try:
            if self._is_thumb:
                image_x_object = PDImageXObject.create_thumbnail(self._strm)
            else:
                # ``resources`` is accepted for API parity with upstream
                # (the original Java ctor takes a ``PDResources`` for
                # inline XObject lookups) but the pypdfbox constructor
                # operates directly on the stream — the resource cache
                # is consulted lazily by the image pipeline when needed.
                del resources
                image_x_object = PDImageXObject(PDStream(self._strm))
            return image_x_object.get_image()
        except OSError as exc:
            _LOG.error("%s", exc)
        except Exception as exc:  # noqa: BLE001 — surface unexpected decode failures
            _LOG.error("image decode failed: %s", exc)
        return None

    # ---- helpers (ported from upstream private API) ------------------------

    def get_filtered_label(self) -> str:
        """Build the ``"Encoded (<chain>)"`` label.

        Mirrors upstream private ``getFilteredLabel()``. Promoted to
        public (snake_case) for parity tooling — upstream Java treats
        the method as instance-private but the label is also useful to
        debugger callers comparing the dropdown selection.
        """
        parts: list[str] = []
        base = self._strm.get_filters()
        if isinstance(base, COSName):
            parts.append(base.get_name())
        elif isinstance(base, COSArray):
            for i in range(base.size()):
                parts.append(base.get(i).get_name())
        return "Encoded (" + ", ".join(parts) + ")"

    def create_filter_list(
        self, stream: COSStream
    ) -> OrderedDict[str, list[str] | None]:
        """Build the ordered dropdown map of view-label → stop-filter list.

        Mirrors upstream private ``createFilterList(COSStream)``. The
        first entry is ``IMAGE`` (only when the stream is an image),
        followed by ``DECODED``, then a ``Keep <chain> ...`` entry for
        every intermediate filter in reverse, finishing with the
        ``"Encoded (...)"`` raw view.
        """
        filters: OrderedDict[str, list[str] | None] = OrderedDict()
        if self._is_image:
            filters[self.IMAGE] = None
        filters[self.DECODED] = None

        pd_stream = PDStream(stream)
        chain = pd_stream.get_filters()

        # Partial-decode entries — one per intermediate stop filter, in
        # reverse order to match upstream (which iterates "filtersSize - 1
        # down to 1").
        for i in range(len(chain) - 1, 0, -1):
            filters[self.get_partial_stream_command(i)] = self.get_stop_filter_list(i)

        filters[self.get_filtered_label()] = None
        return filters

    def get_partial_stream_command(self, index_of_stop_filter: int) -> str:
        """Return the ``"Keep <name> & <name> ..."`` label for a stop index.

        Mirrors upstream private ``getPartialStreamCommand(int)``.
        ``index_of_stop_filter`` is the position in the ``/Filter``
        chain where decoding should stop; the label lists every filter
        from that index onward, joined by ``" & "``.
        """
        available_filters = PDStream(self._strm).get_filters()
        names: list[str] = []
        for i in range(index_of_stop_filter, len(available_filters)):
            names.append(available_filters[i].get_name())
        return "Keep " + " & ".join(names) + " ..."

    def get_stop_filter_list(self, stop_filter_index: int) -> list[str]:
        """Return the single-element stop-filter list for a given index.

        Mirrors upstream private ``getStopFilterList(int)``. Upstream
        returns a one-element ``List<String>`` containing the name of
        the filter at ``stop_filter_index``; that list is fed to
        ``PDStream.create_input_stream`` to halt decoding before that
        filter runs.
        """
        available_filters = PDStream(self._strm).get_filters()
        return [available_filters[stop_filter_index].get_name()]

    @staticmethod
    def is_image_stream(dic: COSDictionary, is_thumb: bool) -> bool:
        """Return ``True`` when ``dic`` is an Image XObject (or thumb).

        Mirrors upstream private static ``isImageStream(COSDictionary,
        boolean)``. Thumbnails are always treated as image streams even
        when ``/Subtype`` is absent.
        """
        if is_thumb:
            return True
        if not dic.contains_key(COSName.SUBTYPE):
            return False
        subtype = dic.get_cos_name(COSName.SUBTYPE)
        return subtype == COSName.get_pdf_name("Image")

    @staticmethod
    def is_xml_metadata_stream(dic: COSDictionary) -> bool:
        """Return ``True`` when ``dic`` is an XML metadata stream.

        Mirrors upstream private ``isXmlMetadataStream(COSDictionary)``.
        Promoted to public (snake_case) for parity tooling — upstream
        Java treats the method as instance-private but the predicate is
        useful to debugger callers that need to short-circuit decoding
        for XMP packets.
        """

        if not dic.contains_key(COSName.SUBTYPE):
            return False
        subtype = dic.get_cos_name(COSName.SUBTYPE)
        return subtype == COSName.get_pdf_name("XML")

    # Backwards-compatible private alias.
    _is_xml_metadata_stream = is_xml_metadata_stream
