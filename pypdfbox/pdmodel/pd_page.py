from __future__ import annotations

import math
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
)

from .pd_rectangle import PDRectangle
from .pd_resources import PDResources

# Names referenced by PDPage. Upstream uses constants from COSName but
# many of these aren't pre-interned in our COSName module yet — we do it
# lazily here to avoid mutating the catalog from this file.
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PAGE: COSName = COSName.PAGE  # type: ignore[attr-defined]
_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]
_MEDIA_BOX: COSName = COSName.MEDIA_BOX  # type: ignore[attr-defined]
_CROP_BOX: COSName = COSName.get_pdf_name("CropBox")
_BLEED_BOX: COSName = COSName.get_pdf_name("BleedBox")
_TRIM_BOX: COSName = COSName.get_pdf_name("TrimBox")
_ART_BOX: COSName = COSName.get_pdf_name("ArtBox")
_ROTATE: COSName = COSName.get_pdf_name("Rotate")
_USER_UNIT: COSName = COSName.get_pdf_name("UserUnit")
_PARENT: COSName = COSName.PARENT  # type: ignore[attr-defined]
# /P is the legacy single-letter alias upstream PDFBox falls back to when
# /Parent is missing (see ``getCOSDictionary(COSName.PARENT, COSName.P)``
# in PDPageTree). Kept here so PDPage's inheritable walk matches.
_P: COSName = COSName.get_pdf_name("P")
_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_AA: COSName = COSName.get_pdf_name("AA")
_THUMB: COSName = COSName.get_pdf_name("Thumb")
_TRANS: COSName = COSName.get_pdf_name("Trans")
_STRUCT_PARENTS: COSName = COSName.get_pdf_name("StructParents")
_BEADS: COSName = COSName.get_pdf_name("B")
_GROUP: COSName = COSName.get_pdf_name("Group")
_METADATA: COSName = COSName.get_pdf_name("Metadata")
_TABS: COSName = COSName.get_pdf_name("Tabs")
_VP: COSName = COSName.get_pdf_name("VP")
_DUR: COSName = COSName.get_pdf_name("Dur")


class PDPage:
    """
    Single PDF page wrapper. Mirrors
    ``org.apache.pdfbox.pdmodel.PDPage``.

    A page is fundamentally a ``COSDictionary`` with ``/Type /Page``
    and a handful of inheritable attributes (``/Resources``,
    ``/MediaBox``, ``/CropBox``, ``/Rotate``). PDPage resolves those
    inheritable attributes by walking the ``/Parent`` chain.
    """

    # ---------- /Tabs values (PDF 1.7 §12.5 / PDF 2.0 §12.5) ----------
    #
    # Single-letter codes for the page's annotation tab order. These mirror
    # the literal name values written into ``/Tabs`` and let callers porting
    # from PDFBox use named constants instead of hard-coding the letters.
    # Upstream PDPage.java does not declare these (it threads the raw strings
    # directly), but providing them here keeps user code self-documenting and
    # avoids typo-class bugs at the call site.
    TAB_ORDER_ROW: str = "R"
    TAB_ORDER_COLUMN: str = "C"
    TAB_ORDER_STRUCTURE: str = "S"
    TAB_ORDER_ANNOTATIONS_ARRAY: str = "A"
    TAB_ORDER_WIDGETS: str = "W"

    def __init__(
        self,
        page: COSDictionary | PDRectangle | None = None,
    ) -> None:
        # Three constructor shapes matching upstream:
        #   PDPage()                -> blank Letter page
        #   PDPage(media_box)       -> blank page with custom MediaBox
        #   PDPage(cos_dictionary)  -> wrap an existing page dict
        if page is None:
            self._page = COSDictionary()
            self._page.set_item(_TYPE, _PAGE)
            self._page.set_item(_MEDIA_BOX, PDRectangle.LETTER.to_cos_array())  # type: ignore[attr-defined]
        elif isinstance(page, PDRectangle):
            self._page = COSDictionary()
            self._page.set_item(_TYPE, _PAGE)
            self._page.set_item(_MEDIA_BOX, page.to_cos_array())
        elif isinstance(page, COSDictionary):
            self._page = page
        else:
            raise TypeError(
                f"PDPage requires None, PDRectangle, or COSDictionary; got "
                f"{type(page).__name__}"
            )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._page

    # ---------- inheritable resolution ----------

    def _get_inheritable(self, key: COSName) -> COSBase | None:
        """Walk this page's ``/Parent`` chain looking for ``key``.
        Mirrors upstream ``PDPageTree.getInheritableAttribute``.

        Upstream PDFBox accepts ``/P`` as a legacy alias for ``/Parent``
        (see ``COSDictionary.getCOSDictionary(COSName.PARENT, COSName.P)``
        used throughout PDPageTree); we honour the same fallback here so
        pages that use the short-form key still resolve their ancestors.
        """
        node: COSDictionary | None = self._page
        seen: set[int] = set()
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            value = node.get_dictionary_object(key)
            if value is not None:
                return value
            parent = node.get_dictionary_object(_PARENT)
            if not isinstance(parent, COSDictionary):
                parent = node.get_dictionary_object(_P)
            node = parent if isinstance(parent, COSDictionary) else None
        return None

    def get_inherited_cos_object(self, name: COSName | str) -> COSBase | None:
        """Resolve an inheritable attribute on this page by walking the
        ``/Parent`` chain. Returns ``None`` when no ancestor (including this
        page) carries it. Mirrors upstream ``PDPage.getInheritableAttribute``
        (renamed to ``get_inherited_cos_object`` to keep the snake_case
        translation explicit)."""
        key = name if isinstance(name, COSName) else COSName.get_pdf_name(name)
        return self._get_inheritable(key)

    # Upstream's exact spelling kept as an alias so callers porting from
    # PDFBox don't have to relearn the camelCase→snake_case mapping.
    def get_inheritable_attribute(self, name: COSName | str) -> COSBase | None:
        """Alias for :meth:`get_inherited_cos_object`."""
        return self.get_inherited_cos_object(name)

    def get_cos_parent(self) -> COSDictionary | None:
        """Return the immediate ``/Parent`` ``COSDictionary`` (a page-tree
        intermediate node, *not* a :class:`PDPageTree`). Mirrors upstream
        ``PDPage.getCOSParent`` — used by the page-tree walker to splice
        pages into and out of intermediate nodes."""
        parent = self._page.get_dictionary_object(_PARENT)
        if isinstance(parent, COSDictionary):
            return parent
        return None

    # ---------- resources ----------

    def get_resources(self) -> PDResources:
        """Resolve ``/Resources`` walking parents. If absent everywhere,
        returns an empty resource dict and does **not** attach it (matches
        upstream's lazy behaviour — set_resources is required to persist)."""
        resolved = self._get_inheritable(_RESOURCES)
        if isinstance(resolved, COSDictionary):
            return PDResources(resolved)
        return PDResources()

    def set_resources(self, resources: PDResources | COSDictionary | None) -> None:
        if resources is None:
            self._page.remove_item(_RESOURCES)
            return
        cos = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        self._page.set_item(_RESOURCES, cos)

    # ---------- PDContentStream surface ----------

    def get_b_box(self) -> PDRectangle:
        """Return the page content bounding box.

        Mirrors upstream ``PDPage.getBBox()`` from the ``PDContentStream``
        contract. For a page, the content stream's bounding box is the
        resolved crop box.
        """
        return self.get_crop_box()

    def get_bbox(self) -> PDRectangle:
        """Alias for :meth:`get_b_box`.

        ``get_b_box`` follows the PDFBox ``getBBox`` case-conversion, while
        ``get_bbox`` matches the spelling used by several local wrappers.
        """
        return self.get_b_box()

    # ---------- contents ----------

    def get_contents(self) -> bytes:
        """Concatenate ``/Contents`` stream bodies and return raw bytes.

        Cluster #1 ships **raw** bytes — the typed ``PDFContentStream``
        wrapper lands with the contentstream cluster (PRD §6.7). See
        ``CHANGES.md``.

        ``/Contents`` may be absent (blank page → ``b""``), a single
        stream, or an array of streams that the spec says must be
        concatenated with whitespace between them. We mirror upstream's
        ``COSArrayList<COSStream>`` aggregation by joining the raw bodies
        with a single newline so adjacent operator runs don't merge.
        """
        contents = self._page.get_dictionary_object(_CONTENTS)
        if contents is None:
            return b""
        chunks: list[bytes] = []
        if isinstance(contents, COSStream):
            chunks.append(self._stream_bytes(contents))
        elif isinstance(contents, COSArray):
            for i in range(contents.size()):
                entry = contents.get_object(i)
                if isinstance(entry, COSStream):
                    chunks.append(self._stream_bytes(entry))
        else:
            return b""
        return b"\n".join(chunks)

    @staticmethod
    def _stream_bytes(stream: COSStream) -> bytes:
        if not stream.has_data():
            return b""
        # ``create_input_stream`` (not the raw variant) so the security
        # handler decrypts and the /Filter chain — typically
        # ``/FlateDecode`` for content streams emitted by our writer — is
        # unwound before the bytes hit the consumer. Returning still-
        # encrypted or still-compressed bytes here makes
        # ``PDFTextStripper`` see garbage operators on any encrypted or
        # compressed page.
        with stream.create_input_stream() as src:
            return src.read()

    def has_contents(self) -> bool:
        """Return whether this page has one or more content streams.

        Mirrors upstream ``PDPage.hasContents()``: a direct stream counts
        only when it has bytes, while an array counts when the array is
        present and non-empty.
        """
        contents = self._page.get_dictionary_object(_CONTENTS)
        if isinstance(contents, COSStream):
            return contents.has_data()
        if isinstance(contents, COSArray):
            return not contents.is_empty()
        return False

    def set_contents(
        self,
        stream: COSStream | list[COSStream] | COSArray | None,
    ) -> None:
        """Replace ``/Contents``.

        Accepts:

        - ``None`` — remove the entry entirely.
        - a single :class:`COSStream` — written verbatim (single-stream form).
        - a ``list[COSStream]`` or :class:`COSArray` of streams — written as
          the array form. Mirrors upstream's ``setContents(List<PDStream>)``
          overload.
        """
        if stream is None:
            self._page.remove_item(_CONTENTS)
            return
        if isinstance(stream, COSStream):
            self._page.set_item(_CONTENTS, stream)
            return
        if isinstance(stream, COSArray):
            self._page.set_item(_CONTENTS, stream)
            return
        if isinstance(stream, list):
            arr = COSArray()
            for entry in stream:
                if isinstance(entry, COSStream):
                    arr.add(entry)
                elif hasattr(entry, "get_cos_object"):
                    cos = entry.get_cos_object()
                    if isinstance(cos, COSStream):
                        arr.add(cos)
                        continue
                    raise TypeError(
                        "PDPage.set_contents list entries must wrap a "
                        f"COSStream; got {type(entry).__name__}"
                    )
                else:
                    raise TypeError(
                        "PDPage.set_contents list entries must be "
                        f"COSStream-like; got {type(entry).__name__}"
                    )
            self._page.set_item(_CONTENTS, arr)
            return
        raise TypeError(
            "PDPage.set_contents expected None, COSStream, COSArray, or "
            f"list[COSStream]; got {type(stream).__name__}"
        )

    def get_content_streams(self) -> list[Any]:
        """List form of ``/Contents``. Mirrors upstream
        ``PDPage.getContentStreams()``: returns one :class:`PDStream` per
        underlying stream, regardless of whether ``/Contents`` is a single
        stream or an array. Empty list when ``/Contents`` is absent.
        """
        # Local import — PDStream lives in common/ and shouldn't be at
        # module scope (avoids the writer/parser bring-up cycle).
        from .common.pd_stream import PDStream

        contents = self._page.get_dictionary_object(_CONTENTS)
        if contents is None:
            return []
        result: list[Any] = []
        if isinstance(contents, COSStream):
            result.append(PDStream(contents))
        elif isinstance(contents, COSArray):
            for i in range(contents.size()):
                entry = contents.get_object(i)
                if isinstance(entry, COSStream):
                    result.append(PDStream(entry))
        return result

    def get_contents_for_random_access(self) -> Any:
        """Return a :class:`RandomAccessRead` over this page's content
        stream bytes. Mirrors upstream
        ``PDPage.getContentsForRandomAccess()`` — used by token parsers
        that need seekable/peek-capable input.

        For single-stream ``/Contents`` we wrap the decoded bytes; for the
        array form we concatenate decoded bodies separated by a single
        newline (matching upstream's ``DELIMITER``). Empty buffer when
        ``/Contents`` is absent or holds no streams.
        """
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

        return RandomAccessReadBuffer(self.get_contents())

    def get_contents_for_stream_parsing(self) -> Any:
        """Return a :class:`RandomAccessRead` for the page's content streams,
        suitable for the PDF stream parser. Mirrors upstream
        ``PDPage.getContentsForStreamParsing()``.

        Upstream short-circuits single-stream ``/FlateDecode`` content by
        feeding a ``FlateFilterDecoderStream`` directly. We do not bypass
        the filter chain — :meth:`get_contents` already runs the security
        handler + filters — so we delegate to
        :meth:`get_contents_for_random_access` exactly like the
        ``PDContentStream`` default method.
        """
        return self.get_contents_for_random_access()

    # ---------- matrix ----------

    def get_matrix(self) -> list[float]:
        """Transformation matrix applied to the page's content stream.

        Mirrors upstream ``PDPage.getMatrix()`` which returns
        ``new Matrix()`` (the identity transform). The pypdfbox ``Matrix``
        class lands with the rendering cluster (PRD §6.7); until then we
        surface the same six numbers as a list — same shape used by
        :class:`PDFormXObject.get_matrix` and :class:`PDAbstractPattern.get_matrix`.

        Note: the upstream comment on this method (``// todo: take into
        account user-space unit redefinition as scale?``) is a known
        upstream gap, not something we attempt to fix here.
        """
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    # ---------- boxes ----------

    def _get_box(self, key: COSName, fallback: PDRectangle | None = None) -> PDRectangle:
        value = self._get_inheritable(key) if key is _MEDIA_BOX else (
            self._page.get_dictionary_object(key)
        )
        if isinstance(value, COSArray):
            return PDRectangle.from_cos_array(value)
        if fallback is not None:
            return fallback
        # MediaBox absent everywhere — upstream defaults to Letter.
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def _clip_to_media_box(self, box: PDRectangle) -> PDRectangle:
        """Clip ``box`` to the resolved media-box bounds.

        Mirrors upstream ``PDPage.clipToMediaBox(PDRectangle)``: any portion
        of the supplied rectangle that extends past the media box is trimmed
        in place (lower-left snaps up, upper-right snaps down). Used by the
        crop/bleed/trim/art accessors so an oversized box never reports
        coordinates outside the page's printable surface.
        """
        media = self.get_media_box()
        return PDRectangle(
            max(media.lower_left_x, box.lower_left_x),
            max(media.lower_left_y, box.lower_left_y),
            min(media.upper_right_x, box.upper_right_x),
            min(media.upper_right_y, box.upper_right_y),
        )

    def get_media_box(self) -> PDRectangle:
        """Resolved ``/MediaBox``. Walks ``/Parent`` chain. Defaults to
        US Letter when absent (matches upstream)."""
        return self._get_box(_MEDIA_BOX)

    def set_media_box(self, rect: PDRectangle | COSArray | None) -> None:
        if rect is None:
            self._page.remove_item(_MEDIA_BOX)
            return
        cos = rect if isinstance(rect, COSArray) else rect.to_cos_array()
        self._page.set_item(_MEDIA_BOX, cos)

    def get_crop_box(self) -> PDRectangle:
        """``/CropBox`` if present (inheritable), else ``/MediaBox``.

        The returned rectangle is clipped to the media-box bounds when an
        explicit ``/CropBox`` is in effect (mirrors upstream
        ``clipToMediaBox`` — see PDPage.java line 472).
        """
        # CropBox is inheritable per spec (PDF 1.7 §14.11.2).
        value = self._get_inheritable(_CROP_BOX)
        if isinstance(value, COSArray):
            return self._clip_to_media_box(PDRectangle.from_cos_array(value))
        return self.get_media_box()

    def set_crop_box(self, rect: PDRectangle | COSArray | None) -> None:
        if rect is None:
            self._page.remove_item(_CROP_BOX)
            return
        cos = rect if isinstance(rect, COSArray) else rect.to_cos_array()
        self._page.set_item(_CROP_BOX, cos)

    def get_bleed_box(self) -> PDRectangle:
        """``/BleedBox`` if present, else ``/CropBox``.

        Like the crop box, an explicit bleed box is clipped to the media-box
        bounds (matches upstream's ``clipToMediaBox`` call).
        """
        value = self._page.get_dictionary_object(_BLEED_BOX)
        if isinstance(value, COSArray):
            return self._clip_to_media_box(PDRectangle.from_cos_array(value))
        return self.get_crop_box()

    def set_bleed_box(self, rect: PDRectangle | COSArray | None) -> None:
        if rect is None:
            self._page.remove_item(_BLEED_BOX)
            return
        cos = rect if isinstance(rect, COSArray) else rect.to_cos_array()
        self._page.set_item(_BLEED_BOX, cos)

    def get_trim_box(self) -> PDRectangle:
        """``/TrimBox`` if present, else ``/CropBox`` (clipped to media)."""
        value = self._page.get_dictionary_object(_TRIM_BOX)
        if isinstance(value, COSArray):
            return self._clip_to_media_box(PDRectangle.from_cos_array(value))
        return self.get_crop_box()

    def set_trim_box(self, rect: PDRectangle | COSArray | None) -> None:
        if rect is None:
            self._page.remove_item(_TRIM_BOX)
            return
        cos = rect if isinstance(rect, COSArray) else rect.to_cos_array()
        self._page.set_item(_TRIM_BOX, cos)

    def get_art_box(self) -> PDRectangle:
        """``/ArtBox`` if present, else ``/CropBox`` (clipped to media)."""
        value = self._page.get_dictionary_object(_ART_BOX)
        if isinstance(value, COSArray):
            return self._clip_to_media_box(PDRectangle.from_cos_array(value))
        return self.get_crop_box()

    def set_art_box(self, rect: PDRectangle | COSArray | None) -> None:
        if rect is None:
            self._page.remove_item(_ART_BOX)
            return
        cos = rect if isinstance(rect, COSArray) else rect.to_cos_array()
        self._page.set_item(_ART_BOX, cos)

    # ---------- rotation / user unit ----------

    def get_rotation(self) -> int:
        """Inheritable; default 0. Normalised to 0/90/180/270.

        Mirrors upstream ``PDPage.getRotation()`` exactly: a ``COSNumber``
        whose integer value is a multiple of 90 is reduced via
        ``(angle % 360 + 360) % 360`` so negatives wrap correctly. Any other
        value (non-numeric, or not a multiple of 90) returns 0 — upstream
        treats off-axis rotations as "not set at this level"."""
        value = self._get_inheritable(_ROTATE)
        if value is None:
            return 0
        # Both COSInteger and COSFloat are accepted upstream (COSNumber).
        from pypdfbox.cos import COSFloat, COSInteger

        raw: int
        if isinstance(value, COSInteger):
            raw = value.value
        elif isinstance(value, COSFloat):
            # Upstream COSNumber.intValue() truncates toward zero.
            raw = int(value.value)
        else:
            return 0
        # Upstream gates on ``rotationAngle % 90 == 0`` — anything else is
        # treated as unset and returns 0 rather than being snapped.
        if raw % 90 != 0:
            return 0
        return ((raw % 360) + 360) % 360

    def set_rotation(self, rotation: int) -> None:
        from pypdfbox.cos import COSInteger

        self._page.set_item(_ROTATE, COSInteger.get(int(rotation)))

    def is_rotated(self) -> bool:
        """Return whether this page carries any non-zero rotation.

        Equivalent to ``self.get_rotation() != 0`` — convenience predicate so
        callers can branch on "page needs un-rotation" without doing the
        comparison themselves. Off-axis ``/Rotate`` values (anything not a
        multiple of 90, including odd numerics or non-numeric COS objects)
        are reported by :meth:`get_rotation` as ``0``, so this returns
        ``False`` for those too — matching the upstream "treat malformed
        rotation as unset" contract.
        """
        return self.get_rotation() != 0

    def get_rotation_in_radians(self) -> float:
        """Return the resolved page rotation expressed in radians.

        Convenience over :meth:`get_rotation` for callers that need to feed
        the angle directly into a transform matrix or trig routine. Always
        non-negative because :meth:`get_rotation` normalises to ``[0, 360)``.
        """
        return math.radians(self.get_rotation())

    def get_user_unit(self) -> float:
        """``/UserUnit`` (PDF 1.6+). Default 1.0.

        PDFBox also treats malformed non-positive values as absent.
        """
        from pypdfbox.cos import COSFloat, COSInteger

        value = self._page.get_dictionary_object(_USER_UNIT)
        if isinstance(value, (COSInteger, COSFloat)):
            unit = float(value.value)
            return unit if unit > 0 else 1.0
        return 1.0

    def set_user_unit(self, unit: float) -> None:
        from pypdfbox.cos import COSFloat

        if unit <= 0:
            raise ValueError("user_unit must be positive")
        self._page.set_item(_USER_UNIT, COSFloat(float(unit)))

    # ---------- annotations ----------

    def get_annotations(
        self,
        annotation_filter: Any = None,
    ) -> list[Any]:
        """Resolve ``/Annots`` into a list of :class:`PDAnnotation`.

        Returns an empty list when ``/Annots`` is absent. Each entry is
        dispatched to the appropriate subclass via
        :meth:`PDAnnotation.create`. Non-dictionary entries (rare but
        legal under defensive parsing) are skipped.

        ``annotation_filter`` mirrors upstream's
        ``getAnnotations(AnnotationFilter)``: a ``Callable[[PDAnnotation],
        bool]`` invoked on every dispatched annotation; only annotations
        for which the callable returns truthy are kept. ``None`` means
        accept-all (matches the no-arg upstream overload).
        """
        # Local import — annotation module imports PDRectangle from this
        # package, and a top-level import would create a cycle.
        from .interactive.annotation import PDAnnotation

        annots = self._page.get_dictionary_object(_ANNOTS)
        if annots is None:
            return []
        if not isinstance(annots, COSArray):
            return []
        result: list[Any] = []
        for i in range(annots.size()):
            entry = annots.get_object(i)
            if entry is None:
                # Match upstream's ``if (item == null) continue;`` defensive skip.
                continue
            if isinstance(entry, COSDictionary):
                created = PDAnnotation.create(entry)
                if annotation_filter is None or annotation_filter(created):
                    result.append(created)
        return result

    def set_annotations(self, annotations: list[Any] | None) -> None:
        """Replace ``/Annots`` with a fresh array built from ``annotations``.

        ``None`` removes the entry. Each item must be a
        :class:`PDAnnotation` (we read its underlying ``COSDictionary``).
        """
        if annotations is None:
            self._page.remove_item(_ANNOTS)
            return
        from .interactive.annotation import PDAnnotation

        arr = COSArray()
        for ann in annotations:
            if not isinstance(ann, PDAnnotation):
                raise TypeError(
                    "PDPage.set_annotations entries must be PDAnnotation; "
                    f"got {type(ann).__name__}"
                )
            arr.add(ann.get_cos_object())
        self._page.set_item(_ANNOTS, arr)

    # ---------- stubs for later clusters ----------

    def get_thumb(self) -> Any:
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

        v = self._page.get_dictionary_object(_THUMB)
        if isinstance(v, COSStream):
            return PDImageXObject(v)
        return None

    def set_thumb(self, thumb: Any) -> None:
        if thumb is None:
            self._page.remove_item(_THUMB)
            return
        self._page.set_item(_THUMB, thumb.get_cos_object())

    def get_transition(self) -> Any:
        from pypdfbox.pdmodel.interactive.pagenavigation import PDTransition

        v = self._page.get_dictionary_object(_TRANS)
        if isinstance(v, COSDictionary):
            return PDTransition(v)
        return None

    # ---------- thread beads ----------

    def get_thread_beads(self) -> list[Any]:
        """Resolve ``/B`` into a list of :class:`PDThreadBead`.

        Returns an empty list when ``/B`` is absent. Non-dictionary entries
        are surfaced as ``None`` placeholders so the caller can preserve the
        positional alignment with the underlying array (mirrors upstream's
        defensive treatment where a malformed bead becomes a ``null`` slot).
        """
        from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead

        beads = self._page.get_dictionary_object(_BEADS)
        if not isinstance(beads, COSArray):
            return []
        result: list[Any] = []
        for i in range(beads.size()):
            entry = beads.get_object(i)
            if isinstance(entry, COSDictionary):
                result.append(PDThreadBead(entry))
            else:
                result.append(None)
        return result

    def set_thread_beads(self, beads: list[Any] | None) -> None:
        """Replace ``/B`` with an array built from ``beads``. ``None``
        removes the entry. Each item must be a :class:`PDThreadBead`."""
        from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead

        if beads is None:
            self._page.remove_item(_BEADS)
            return
        arr = COSArray()
        for bead in beads:
            if not isinstance(bead, PDThreadBead):
                raise TypeError(
                    "PDPage.set_thread_beads entries must be PDThreadBead; "
                    f"got {type(bead).__name__}"
                )
            arr.add(bead.get_cos_object())
        self._page.set_item(_BEADS, arr)

    def set_transition(self, trans: Any, duration: float | None = None) -> None:
        """Replace ``/Trans``. Pass ``None`` for ``trans`` to remove the entry.

        Mirrors upstream ``PDPage.setTransition(PDTransition)`` and
        ``PDPage.setTransition(PDTransition, float)``: when ``duration`` is
        supplied it is also written to ``/Dur`` (the maximum length of time,
        in seconds, that the page shall be displayed during presentations
        before the viewer advances automatically).
        """
        if trans is None:
            self._page.remove_item(_TRANS)
            if duration is not None:
                from pypdfbox.cos import COSFloat

                self._page.set_item(_DUR, COSFloat(float(duration)))
            return
        self._page.set_item(_TRANS, trans.get_cos_object())
        if duration is not None:
            from pypdfbox.cos import COSFloat

            self._page.set_item(_DUR, COSFloat(float(duration)))

    def get_actions(self) -> Any:
        """Return the page's additional-actions ``/AA`` wrapper.

        Mirrors upstream's auto-create behaviour (see
        ``PDPage.getActions`` line 723) — if ``/AA`` is absent the entry
        is materialised in place as an empty dictionary so the caller
        can attach trigger actions without having to wire the
        sub-dictionary first. Always returns a non-``None``
        :class:`PDPageAdditionalActions`."""
        from pypdfbox.pdmodel.interactive.action import PDPageAdditionalActions

        actions = self._page.get_dictionary_object(_AA)
        if not isinstance(actions, COSDictionary):
            actions = COSDictionary()
            self._page.set_item(_AA, actions)
        return PDPageAdditionalActions(actions)

    def set_actions(self, actions: Any) -> None:
        if actions is None:
            self._page.remove_item(_AA)
            return
        self._page.set_item(_AA, actions.get_cos_object())

    # ---------- struct parents ----------

    def get_struct_parents(self) -> int:
        """``/StructParents`` integer key into the document's structure
        parent tree. Upstream returns ``-1`` when the entry is absent
        (sentinel meaning "this page has no marked-content parents")."""
        from pypdfbox.cos import COSFloat, COSInteger

        value = self._page.get_dictionary_object(_STRUCT_PARENTS)
        if isinstance(value, COSInteger):
            return int(value.value)
        if isinstance(value, COSFloat):
            return int(value.value)
        return -1

    def set_struct_parents(self, value: int) -> None:
        from pypdfbox.cos import COSInteger

        self._page.set_item(_STRUCT_PARENTS, COSInteger.get(int(value)))

    # ---------- metadata ----------

    def get_metadata(self) -> Any:
        """Resolve ``/Metadata`` into a :class:`PDMetadata` (XMP packet
        wrapper). Returns ``None`` when ``/Metadata`` is absent or not a
        stream. Mirrors upstream ``PDPage.getMetadata``."""
        from .common.pd_metadata import PDMetadata

        value = self._page.get_dictionary_object(_METADATA)
        if isinstance(value, COSStream):
            return PDMetadata(value)
        return None

    def set_metadata(self, metadata: Any) -> None:
        """Replace ``/Metadata`` with the supplied :class:`PDMetadata`. Pass
        ``None`` to remove the entry. Mirrors upstream
        ``PDPage.setMetadata``."""
        if metadata is None:
            self._page.remove_item(_METADATA)
            return
        cos = metadata.get_cos_object() if hasattr(metadata, "get_cos_object") else metadata
        self._page.set_item(_METADATA, cos)

    # ---------- transparency group ----------

    def get_group(self) -> COSDictionary | None:
        """Return the ``/Group`` transparency-group dictionary, or ``None``
        if absent. Upstream returns a ``PDTransparencyGroupAttributes`` —
        we surface the raw COS dictionary until that wrapper lands with
        the graphics-state cluster (PRD §6.7)."""
        value = self._page.get_dictionary_object(_GROUP)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_group(self, group: Any) -> None:
        """Set ``/Group`` (transparency group attributes). Accepts a
        :class:`COSDictionary` or any object exposing ``get_cos_object()``.
        ``None`` removes the entry."""
        if group is None:
            self._page.remove_item(_GROUP)
            return
        cos = group.get_cos_object() if hasattr(group, "get_cos_object") else group
        if not isinstance(cos, COSDictionary):
            raise TypeError(
                "PDPage.set_group expected COSDictionary or wrapper; "
                f"got {type(group).__name__}"
            )
        self._page.set_item(_GROUP, cos)

    # ---------- viewports ----------

    def get_viewports(self) -> list[Any] | None:
        """Resolve ``/VP`` into a list of :class:`PDViewportDictionary`.

        Returns ``None`` when ``/VP`` is absent (mirrors upstream which
        returns ``null`` rather than an empty list — important so callers
        can distinguish "no viewports declared" from "explicitly empty
        array"). Returns an empty list when ``/VP`` is present but holds
        no dictionary entries."""
        from .interactive.measurement.pd_viewport_dictionary import (
            PDViewportDictionary,
        )

        vp = self._page.get_dictionary_object(_VP)
        if not isinstance(vp, COSArray):
            return None
        result: list[Any] = []
        for i in range(vp.size()):
            entry = vp.get_object(i)
            if isinstance(entry, COSDictionary):
                result.append(PDViewportDictionary(entry))
        return result

    def set_viewports(self, viewports: list[Any] | None) -> None:
        """Replace ``/VP`` with an array built from ``viewports``. ``None``
        removes the entry entirely (mirrors upstream's null-deletes-entry
        contract)."""
        from .interactive.measurement.pd_viewport_dictionary import (
            PDViewportDictionary,
        )

        if viewports is None:
            self._page.remove_item(_VP)
            return
        arr = COSArray()
        for vp in viewports:
            if isinstance(vp, PDViewportDictionary):
                arr.add(vp.get_cos_object())
                continue
            if isinstance(vp, COSDictionary):
                arr.add(vp)
                continue
            if hasattr(vp, "get_cos_object"):
                cos = vp.get_cos_object()
                if isinstance(cos, COSDictionary):
                    arr.add(cos)
                    continue
            raise TypeError(
                "PDPage.set_viewports entries must be PDViewportDictionary "
                f"or COSDictionary; got {type(vp).__name__}"
            )
        self._page.set_item(_VP, arr)

    # ---------- resource cache ----------

    def get_resource_cache(self) -> Any:
        """Return the resource cache associated with this page, or ``None``
        if there is none. Mirrors upstream ``PDPage.getResourceCache()``.

        This wrapper does not yet wire the ResourceCache through the page
        constructor; the accessor exists so callers porting from PDFBox
        can rely on the method being present and getting ``None`` until a
        cache is attached via :meth:`set_resource_cache`."""
        return getattr(self, "_resource_cache", None)

    def set_resource_cache(self, cache: Any) -> None:
        """Attach a :class:`PDResourceCache` to this page. Pass ``None`` to
        detach. Companion to :meth:`get_resource_cache`."""
        self._resource_cache = cache

    def remove_page_resource_from_cache(self) -> None:
        """Purge cached resources owned by this page from the attached
        :class:`PDResourceCache`.

        Mirrors upstream ``PDPage.removePageResourceFromCache()``: a no-op
        when no cache is attached; otherwise iterates every entry of the
        page's *own* (non-inherited) ``/Resources`` sub-dictionaries —
        ``/ColorSpace``, ``/ExtGState``, ``/Pattern``, ``/Properties``,
        ``/Shading``, ``/Font``, ``/XObject`` — and removes any indirect
        objects from the cache. Direct resources (those stored inline)
        are not cached so we skip them.
        """
        cache = getattr(self, "_resource_cache", None)
        if cache is None:
            return
        # Limit purge to *this page's* resources — never remove inherited
        # ancestor resources. Use direct lookup, not the inheritable walk.
        own_resources = self._page.get_dictionary_object(_RESOURCES)
        if not isinstance(own_resources, COSDictionary):
            return
        kinds_with_remover = (
            ("ColorSpace", "remove_color_space"),
            ("ExtGState", "remove_ext_state"),
            ("Pattern", "remove_pattern"),
            ("Properties", "remove_properties"),
            ("Shading", "remove_shading"),
            ("Font", "remove_font"),
            ("XObject", "remove_x_object"),
        )
        for kind, remover_name in kinds_with_remover:
            kind_dict = own_resources.get_dictionary_object(COSName.get_pdf_name(kind))
            if not isinstance(kind_dict, COSDictionary):
                continue
            remover = getattr(cache, remover_name, None)
            if remover is None:
                continue
            for entry in list(kind_dict.values()):
                # Only indirect objects are cached upstream.
                if isinstance(entry, COSObject):
                    remover(entry)

    # ---------- transition ----------

    def get_transition_effect(self) -> Any:
        """Alias for :meth:`get_transition` — matches upstream's secondary
        spelling used by the slideshow APIs."""
        return self.get_transition()

    def set_transition_effect(self, transition: Any) -> None:
        """Alias for :meth:`set_transition`."""
        self.set_transition(transition)

    # ---------- tab order ----------

    def get_tab_order(self) -> str | None:
        """Return the ``/Tabs`` value (one of ``"R"``, ``"C"``, ``"S"``,
        ``"A"``, ``"W"``) controlling the page's annotation tab order.
        Returns ``None`` when the entry is absent. Mirrors upstream
        ``PDPage.getTabOrder``."""
        return self._page.get_name(_TABS)

    def set_tab_order(self, order: str | None) -> None:
        """Set ``/Tabs``. Pass ``None`` to remove. Accepts the upstream
        constants ``"R"`` (row order), ``"C"`` (column order), ``"S"``
        (structure order, PDF 1.5+), ``"A"`` (annotations array order,
        PDF 2.0+), ``"W"`` (widget order, PDF 2.0+). We do not validate —
        upstream tolerates unknown values for forward compatibility."""
        if order is None:
            self._page.remove_item(_TABS)
            return
        self._page.set_name(_TABS, order)

    # ---------- /Dur (page display duration) ----------

    def get_duration(self) -> float | None:
        """Return ``/Dur`` — the maximum length of time, in seconds, that
        this page shall be displayed during presentations before the
        viewer automatically advances. Returns ``None`` when the entry is
        absent (no auto-advance configured).

        ``set_transition(transition, duration)`` writes this entry; the
        getter is provided so callers can read the duration back without
        going through raw COS access. There's no upstream ``getDuration``
        method, so this is a pypdfbox convenience accessor."""
        from pypdfbox.cos import COSFloat, COSInteger

        value = self._page.get_dictionary_object(_DUR)
        if isinstance(value, (COSInteger, COSFloat)):
            return float(value.value)
        return None

    def set_duration(self, duration: float | None) -> None:
        """Set ``/Dur`` directly without touching ``/Trans``. ``None``
        removes the entry. Companion to :meth:`get_duration`."""
        if duration is None:
            self._page.remove_item(_DUR)
            return
        from pypdfbox.cos import COSFloat

        self._page.set_item(_DUR, COSFloat(float(duration)))

    # ---------- presence predicates ----------
    #
    # Pythonic ``has_*`` helpers — upstream PDFBox has only ``hasContents``
    # but our codebase consistently exposes presence checks for callers who
    # want to avoid materialising the wrapper objects.

    def has_metadata(self) -> bool:
        """Return whether this page has a ``/Metadata`` XMP stream."""
        return isinstance(self._page.get_dictionary_object(_METADATA), COSStream)

    def has_thumb(self) -> bool:
        """Return whether this page has a ``/Thumb`` thumbnail stream."""
        return isinstance(self._page.get_dictionary_object(_THUMB), COSStream)

    def has_transition(self) -> bool:
        """Return whether this page has a ``/Trans`` transition dict."""
        return isinstance(self._page.get_dictionary_object(_TRANS), COSDictionary)

    def has_actions(self) -> bool:
        """Return whether this page has a non-empty ``/AA`` dict.

        This is a *read-only* probe — unlike :meth:`get_actions` it does
        **not** auto-materialise an empty ``/AA`` sub-dictionary, so it's
        safe to call on read-only inspection paths that mustn't mutate
        the page dict."""
        actions = self._page.get_dictionary_object(_AA)
        return isinstance(actions, COSDictionary) and len(actions) > 0

    def has_annotations(self) -> bool:
        """Return whether this page has a non-empty ``/Annots`` array."""
        annots = self._page.get_dictionary_object(_ANNOTS)
        return isinstance(annots, COSArray) and not annots.is_empty()

    def has_thread_beads(self) -> bool:
        """Return whether this page has a non-empty ``/B`` thread-bead array."""
        beads = self._page.get_dictionary_object(_BEADS)
        return isinstance(beads, COSArray) and not beads.is_empty()

    def has_viewports(self) -> bool:
        """Return whether this page has a ``/VP`` viewports array."""
        return isinstance(self._page.get_dictionary_object(_VP), COSArray)

    def has_group(self) -> bool:
        """Return whether this page has a ``/Group`` transparency-group dict."""
        return isinstance(self._page.get_dictionary_object(_GROUP), COSDictionary)

    def has_tab_order(self) -> bool:
        """Return whether this page has a ``/Tabs`` annotation tab-order entry."""
        return self._page.get_name(_TABS) is not None

    # ---------- equality / repr ----------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PDPage):
            return self._page is other._page
        return NotImplemented

    def __hash__(self) -> int:
        return id(self._page)

    def __repr__(self) -> str:
        return f"PDPage(media_box={self.get_media_box()!s})"


# Re-export to keep the import surface shallow in pd_page_tree.
def _unwrap_page_dict(page_or_dict: PDPage | COSDictionary | COSObject) -> COSDictionary:
    """Return the underlying ``COSDictionary`` for a PDPage, COSDictionary,
    or indirect ``COSObject`` pointing at one."""
    if isinstance(page_or_dict, PDPage):
        return page_or_dict.get_cos_object()
    if isinstance(page_or_dict, COSObject):
        resolved = page_or_dict.get_object()
        if isinstance(resolved, COSDictionary):
            return resolved
        raise TypeError(
            f"COSObject does not resolve to a COSDictionary: {type(resolved).__name__}"
        )
    if isinstance(page_or_dict, COSDictionary):
        return page_or_dict
    raise TypeError(
        f"expected PDPage, COSDictionary, or COSObject; got {type(page_or_dict).__name__}"
    )
