from __future__ import annotations

import logging
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

_LOG = logging.getLogger(__name__)

# Names referenced by PDPage. Upstream uses constants from COSName but
# many of these aren't pre-interned in our COSName module yet — we do it
# lazily here to avoid mutating the catalog from this file.
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PAGE: COSName = COSName.PAGE  # type: ignore[attr-defined]
_PAGES: COSName = COSName.PAGES  # type: ignore[attr-defined]
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

# PDFBOX-2818 box-clamp constants. The threshold is the true Java
# ``Integer.MAX_VALUE`` (2**31 - 1); the assigned clamp value is that same
# constant narrowed to a Java ``float`` (rounds up to 2147483648.0). See
# :meth:`PDPage._rect_from_cos_array`.
_INT32_MAX: float = float(2**31 - 1)
_INT32_MAX_FLOAT32: float = 2147483648.0


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
        resource_cache: Any = None,
    ) -> None:
        # Constructor shapes matching upstream:
        #   PDPage()                       -> blank Letter page
        #   PDPage(media_box)              -> blank page with custom MediaBox
        #   PDPage(cos_dictionary)         -> wrap an existing page dict
        #   PDPage(cos_dictionary, cache)  -> wrap with resource cache
        #     (mirrors upstream's package-private constructor used by
        #     ``PDPageTree`` to thread the cache during page enumeration —
        #     see PDPage.java line 116).
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
        # Always set the attribute so :meth:`get_resource_cache` doesn't have
        # to fall back to ``getattr`` with a default — keeps the read path
        # symmetric with upstream's instance field.
        self._resource_cache = resource_cache
        self._page_resources: PDResources | None = None

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._page

    # ---------- inheritable resolution ----------

    def _get_inheritable(self, key: COSName) -> COSBase | None:
        """Walk this page's ``/Parent`` chain looking for ``key``.
        Mirrors upstream ``PDPageTree.getInheritableAttribute`` exactly
        (PDFBox 3.0.7, ``PDPageTree.java`` line 114)::

            COSBase value = node.getDictionaryObject(key);
            if (value != null) return value;
            COSDictionary parent =
                node.getCOSDictionary(COSName.PARENT, COSName.P);
            if (parent != null
                    && COSName.PAGES.equals(parent.getCOSName(COSName.TYPE))) {
                return getInheritableAttribute(parent, key, visited);
            }
            return null;

        Upstream PDFBox accepts ``/P`` as a legacy alias for ``/Parent``
        and — crucially — only ascends to the parent when the parent's
        ``/Type`` is ``/Pages``. A ``/Parent`` that is missing, not a
        dictionary, or whose ``/Type`` is anything other than ``/Pages``
        terminates the walk (the attribute is reported as unset rather than
        inherited from a non-page-tree ancestor). The ``visited`` set guards
        the self-referential-parent cycle upstream defends against.
        """
        node: COSDictionary | None = self._page
        seen: set[int] = set()
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            value = node.get_dictionary_object(key)
            if value is not None:
                return value
            parent = node.get_cos_dictionary(_PARENT)
            if parent is None:
                parent = node.get_cos_dictionary(_P)
            # Upstream only recurses when the parent is a /Pages node.
            is_pages = parent is not None and parent.get_cos_name(_TYPE) is _PAGES
            node = parent if is_pages else None
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
        pages into and out of intermediate nodes.

        Upstream's page-tree code also accepts ``/P`` as a legacy short-form
        parent key. Keep this accessor aligned with the inheritable walk so
        malformed/older producer output can still be traversed consistently.
        """
        parent = self._page.get_dictionary_object(_PARENT)
        if not isinstance(parent, COSDictionary):
            parent = self._page.get_dictionary_object(_P)
        if isinstance(parent, COSDictionary):
            return parent
        return None

    # ---------- resources ----------

    def get_resources(self) -> PDResources | None:
        """Resolve ``/Resources`` walking parents, or ``None`` if absent
        everywhere.

        The page's resource cache is threaded through to the returned
        wrapper, matching PDFBox's ``new PDResources(resources, resourceCache)``
        path so indirect resource wrappers can be reused.

        Mirrors upstream ``PDPage.getResources()`` (PDFBox 3.0.7,
        ``PDPage.java``)::

            COSDictionary resources = (COSDictionary)
                PDPageTree.getInheritableAttribute(page, COSName.RESOURCES);
            if (resources != null) {
                return new PDResources(resources, resourceCache);
            }
            return null;

        Strict-null contract restored in wave 1491 (was an empty-bag wrapper
        from wave 1454). Callers that need the "create-and-attach if absent"
        behaviour use :meth:`get_or_create_resources` instead — that is the
        ``page.getResources() == null ? new PDResources() : ...`` idiom
        upstream call-sites spell out inline.
        """
        if self._page_resources is None:
            resolved = self._get_inheritable(_RESOURCES)
            if isinstance(resolved, COSDictionary):
                self._page_resources = PDResources(
                    resolved, resource_cache=self.get_resource_cache()
                )
        return self._page_resources

    def get_or_create_resources(self) -> PDResources:
        """Return the page's resolved :class:`PDResources`, materialising and
        back-writing an empty one onto this page when neither the page nor any
        ancestor ``/Pages`` node carries ``/Resources``.

        This is **not** an upstream method — upstream call-sites spell the
        idiom inline as::

            PDResources resources = page.getResources();
            if (resources == null) {
                resources = new PDResources();
                page.setResources(resources);
            }

        pypdfbox factors that recurring pattern into a single helper so the
        many internal callers that need a guaranteed-non-null resource bag
        don't each re-implement the create-and-attach dance (and so
        :meth:`get_resources` can keep upstream's strict-null contract).
        """
        resources = self.get_resources()
        if resources is None:
            resources = PDResources(resource_cache=self.get_resource_cache())
            self.set_resources(resources)
        return resources

    def set_resources(self, resources: PDResources | COSDictionary | None) -> None:
        if resources is None:
            self._page_resources = None
            self._page.remove_item(_RESOURCES)
            return
        if isinstance(resources, PDResources):
            self._page_resources = resources
            cos = resources.get_cos_object()
        else:
            self._page_resources = PDResources(
                resources, resource_cache=self.get_resource_cache()
            )
            cos = resources
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

    def clear_contents(self) -> None:
        """Remove the ``/Contents`` entry."""
        self._page.remove_item(_CONTENTS)

    def set_contents(
        self,
        stream: COSStream | list[COSStream] | COSArray | Any | None,
    ) -> None:
        """Replace ``/Contents``.

        Accepts:

        - ``None`` — remove the entry entirely.
        - a single :class:`COSStream` — written verbatim (single-stream form).
        - a single stream wrapper such as :class:`PDStream` — unwrapped to its
          ``COSStream`` and written in single-stream form.
        - a ``list`` of streams or stream wrappers, or :class:`COSArray` of
          streams — written as the array form. Mirrors upstream's
          ``setContents(List<PDStream>)`` overload.
        """
        if stream is None:
            self.clear_contents()
            return
        if isinstance(stream, COSStream):
            self._page.set_item(_CONTENTS, stream)
            return
        # COSArray check precedes the wrapper-via-`get_cos_object` branch
        # because COSBase now provides ``get_cos_object`` returning ``self``,
        # so COSArray would otherwise be misidentified as a stream wrapper.
        if isinstance(stream, COSArray):
            self._page.set_item(_CONTENTS, stream)
            return
        if hasattr(stream, "get_cos_object"):
            cos = stream.get_cos_object()
            if isinstance(cos, COSStream):
                self._page.set_item(_CONTENTS, cos)
                return
            raise TypeError(
                "PDPage.set_contents expected stream wrapper to wrap a "
                f"COSStream; got {type(cos).__name__}"
            )
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
            "PDPage.set_contents expected None, COSStream, COSArray, stream wrapper, or "
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

        Mirrors upstream ``PDPage.getMatrix()`` exactly: returns the
        identity transform as a six-number list (same shape used by
        :class:`PDFormXObject.get_matrix` and
        :class:`PDAbstractPattern.get_matrix`). Upstream's ``// todo:
        take into account user-space unit redefinition as scale?``
        comment flags this as a known divergence from "what a
        rendering-time matrix would ideally be" — but PDF 32000-1
        §14.10.4 (``/UserUnit``) makes the unit redefinition a viewer
        concern (a per-page scale applied *outside* the content stream's
        own CTM), and applying it inside this matrix would over-scale
        every consumer that already composes ``/UserUnit`` separately
        (the renderer reads :meth:`get_user_unit` directly when it
        builds the page viewport). The known-good fix is therefore to
        match upstream's identity-only behaviour; callers that want the
        scaled form should compose ``Matrix.get_scale_instance(unit,
        unit)`` themselves against :meth:`get_user_unit`.
        """
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    # ---------- boxes ----------

    @staticmethod
    def _rect_from_cos_array(array: COSArray) -> PDRectangle:
        """Upstream-faithful ``new PDRectangle(COSArray)`` conversion.

        Mirrors PDFBox 3.0.7 ``PDRectangle(COSArray)`` (``PDRectangle.java``
        line 143) — which is intentionally LENIENT and never throws on a
        malformed box array::

            float[] values = Arrays.copyOf(array.toFloatArray(), 4);
            // huge-magnitude clamp to ±Integer.MAX_VALUE
            // then min/max-normalise the two corners

        ``COSArray.toFloatArray`` maps every non-``COSNumber`` entry to
        ``0`` and ``Arrays.copyOf(..., 4)`` truncates a too-long array and
        zero-pads a too-short one. So a 2-entry, non-numeric, or oversized
        ``/MediaBox`` resolves to a real rectangle (with zeros filling the
        gaps) rather than raising.

        As of wave 1524 the shared :meth:`PDRectangle.from_cos_array` is itself
        upstream-faithful (it formerly raised on arity ``< 4`` or a non-numeric
        entry — see CHANGES.md wave 1524). This private helper predates that fix
        and is now behaviourally identical apart from a hair-thin clamp-threshold
        edge (it thresholds at ``2**31 - 1`` rather than the float-rounded
        ``2147483648.0``); it is kept as a named seam for the page-box accessors.
        """
        from pypdfbox.cos import COSFloat, COSInteger

        n = array.size()
        vals: list[float] = []
        for i in range(4):
            if i < n:
                entry = array.get_object(i)
                # COSArray.toFloatArray maps a non-number entry to 0.
                v = (
                    float(entry.value)
                    if isinstance(entry, (COSInteger, COSFloat))
                    else 0.0
                )
            else:
                # Arrays.copyOf zero-pads a short array.
                v = 0.0
            # PDFBOX-2818 huge-magnitude clamp. Upstream compares against
            # Integer.MAX_VALUE (2**31 - 1) but ASSIGNS ``(float)
            # Integer.MAX_VALUE`` — which, once narrowed to a Java float,
            # rounds UP to 2147483648.0. We mirror both: threshold at the
            # true int ceiling, clamp to the float32-rounded constant so a
            # huge box reads byte-identically to PDFBox.
            if abs(v) > _INT32_MAX:
                v = _INT32_MAX_FLOAT32 if v > 0 else -_INT32_MAX_FLOAT32
            vals.append(v)
        x0, y0, x1, y1 = vals
        return PDRectangle(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def _get_box(self, key: COSName, fallback: PDRectangle | None = None) -> PDRectangle:
        value = self._get_inheritable(key) if key is _MEDIA_BOX else (
            self._page.get_dictionary_object(key)
        )
        if isinstance(value, COSArray):
            return self._rect_from_cos_array(value)
        if fallback is not None:
            return fallback
        # MediaBox absent everywhere — upstream defaults to U.S. Letter.
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def clip_to_media_box(self, box: PDRectangle) -> PDRectangle:
        """Clip ``box`` to the resolved media-box bounds.

        Mirrors upstream ``PDPage.clipToMediaBox(PDRectangle)`` (private
        upstream, exposed publicly here so tools that need the same
        clipping projection — e.g. annotation-flattening utilities — can
        reuse it without reimplementing the snap rules).

        Any portion of the supplied rectangle that extends past the media
        box is trimmed in place (lower-left snaps up, upper-right snaps
        down). Used internally by the crop/bleed/trim/art accessors so an
        oversized box never reports coordinates outside the page's
        printable surface.
        """
        media = self.get_media_box()
        return PDRectangle(
            max(media.lower_left_x, box.lower_left_x),
            max(media.lower_left_y, box.lower_left_y),
            min(media.upper_right_x, box.upper_right_x),
            min(media.upper_right_y, box.upper_right_y),
        )

    # Internal alias — kept so the existing private-name call sites in
    # this file (and any external callers that adopted the leading-underscore
    # spelling early) continue to resolve unchanged.
    _clip_to_media_box = clip_to_media_box

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
            return self._clip_to_media_box(self._rect_from_cos_array(value))
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
            return self._clip_to_media_box(self._rect_from_cos_array(value))
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
            return self._clip_to_media_box(self._rect_from_cos_array(value))
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
            return self._clip_to_media_box(self._rect_from_cos_array(value))
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

        Returns an empty list when ``/Annots`` is absent or not an array.
        Each non-``null`` entry is dispatched to the appropriate subclass
        via :meth:`PDAnnotation.create_annotation`. Mirroring upstream's
        ``getAnnotations`` loop (PDFBox 3.0.8, PDFBOX-6206), ``null`` array
        members are skipped (``if (item == null) continue;``) and a member
        that ``createAnnotation`` rejects (upstream throws
        ``IOException("Error: Unknown annotation type ...")`` for a
        non-dictionary — pypdfbox's ``PDAnnotation.create_annotation``
        raises :class:`OSError` for the same case) is logged and skipped
        instead of failing the whole call. Before 3.0.8 one malformed
        annotation aborted ``getAnnotations`` for the entire page.

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
            # PDFBOX-6206 (3.0.8): a malformed /Annots member no longer
            # fails the whole call — upstream wraps createAnnotation in
            # try/catch(IOException), logs, and skips the bad entry.
            # ``create_annotation`` is the OSError-raising mirror of
            # ``createAnnotation`` (OSError ↔ IOException).
            try:
                created = PDAnnotation.create_annotation(entry)
            except OSError as exc:
                _LOG.error(str(exc), exc_info=exc)
                continue
            if annotation_filter is None or annotation_filter(created):
                result.append(created)
        return result

    def set_annotations(self, annotations: list[Any] | None) -> None:
        """Replace ``/Annots`` with a fresh array built from ``annotations``.

        ``None`` removes the entry. Each item must be a
        :class:`PDAnnotation` (we read its underlying ``COSDictionary``).
        """
        if annotations is None:
            self.clear_annotations()
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

    def add_annotation(self, annotation: Any) -> None:
        """Append ``annotation`` to the page's ``/Annots`` array.

        Creates the array if it doesn't exist. ``annotation`` must be a
        :class:`PDAnnotation` — we append its underlying COS dictionary.
        Provided because callers reach for the upstream Java idiom
        ``page.getAnnotations().add(widget)``, which doesn't persist
        here: :meth:`get_annotations` returns a fresh snapshot list each
        call.
        """
        from .interactive.annotation import PDAnnotation

        if not isinstance(annotation, PDAnnotation):
            raise TypeError(
                "PDPage.add_annotation expects a PDAnnotation; "
                f"got {type(annotation).__name__}"
            )
        existing = self._page.get_dictionary_object(_ANNOTS)
        if isinstance(existing, COSArray):
            existing.add(annotation.get_cos_object())
            return
        arr = COSArray()
        arr.add(annotation.get_cos_object())
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
            self.clear_thumb()
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
            self.clear_thread_beads()
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
            self.clear_transition()
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
            self.clear_actions()
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
            self.clear_metadata()
            return
        cos = metadata.get_cos_object() if hasattr(metadata, "get_cos_object") else metadata
        self._page.set_item(_METADATA, cos)

    # ---------- transparency group ----------

    def get_group(self) -> COSDictionary | None:
        """Return the ``/Group`` transparency-group dictionary, or ``None``
        if absent or malformed.

        Upstream returns a ``PDTransparencyGroupAttributes``. This accessor
        preserves the established local raw-COS return type; callers that
        need the typed graphics wrapper can wrap the returned dictionary.
        """
        value = self._page.get_dictionary_object(_GROUP)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_group(self, group: Any) -> None:
        """Set ``/Group`` (transparency group attributes). Accepts a
        :class:`COSDictionary` or any object exposing ``get_cos_object()``.
        ``None`` removes the entry."""
        if group is None:
            self.clear_group()
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
            self.clear_viewports()
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

        The cache is set either via the ``resource_cache`` constructor arg
        (mirroring upstream's package-private ``PDPage(COSDictionary,
        ResourceCache)``) or explicitly via :meth:`set_resource_cache`."""
        return self._resource_cache

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
        cache = self._resource_cache
        if cache is None:
            return
        # Limit purge to *this page's* resources — never remove inherited
        # ancestor resources. Use direct lookup, not the inheritable walk.
        own_resources = self._page.get_dictionary_object(_RESOURCES)
        if not isinstance(own_resources, COSDictionary):
            return
        self.remove_resources(own_resources)

    def remove_resources(self, resources: COSDictionary | None) -> None:
        """Remove every cached entry referenced by ``resources`` from the
        attached :class:`PDResourceCache`.

        Mirrors upstream ``PDPage.removeResources(COSDictionary)`` (private
        upstream — see PDPage.java line 136). Exposed publicly here so the
        recursive XForm-resource purge stays callable from
        :meth:`remove_page_resource_from_cache` without leaking through a
        leading-underscore name.

        ``None`` and non-dictionary inputs are no-ops, matching upstream's
        early-return guard. Indirect entries (``COSObject``) are forwarded
        to the cache's typed remover; direct entries (inline COS values)
        are not cached upstream and are silently skipped.
        """
        if resources is None or not isinstance(resources, COSDictionary):
            return
        cache = self._resource_cache
        if cache is None:
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
            kind_dict = resources.get_dictionary_object(COSName.get_pdf_name(kind))
            if not isinstance(kind_dict, COSDictionary):
                continue
            remover = getattr(cache, remover_name, None)
            if remover is None:
                continue
            for entry in list(kind_dict.values()):
                # Only indirect objects are cached upstream.
                if isinstance(entry, COSObject):
                    remover(entry)

    def get_indirect_resource_objects(
        self,
        page_resources: COSDictionary,
        kind: COSName,
    ) -> list[COSObject]:
        """Return the indirect (``COSObject``) entries of one resource
        sub-dictionary.

        Mirrors upstream ``PDPage.getIndirectResourceObjects(COSDictionary,
        COSName)`` (private upstream — see PDPage.java line 192). Exposed
        publicly so callers writing custom cache-purge logic can reuse the
        same filter without reimplementing the indirect-vs-direct split.

        Returns an empty list when the named sub-dictionary is absent or
        not a dictionary. Direct entries (inline COS values) are filtered
        out because PDFBox only caches indirect references.
        """
        if not isinstance(page_resources, COSDictionary):
            return []
        sub = page_resources.get_dictionary_object(kind)
        if not isinstance(sub, COSDictionary):
            return []
        return [entry for entry in sub.values() if isinstance(entry, COSObject)]

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
            self.clear_tab_order()
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
            self.clear_duration()
            return
        from pypdfbox.cos import COSFloat

        self._page.set_item(_DUR, COSFloat(float(duration)))

    # ---------- presence predicates ----------
    #
    # Pythonic ``has_*`` helpers — upstream PDFBox has only ``hasContents``
    # but our codebase consistently exposes cheap direct key-presence checks
    # for callers who want to avoid resolving malformed COS objects or
    # materialising wrapper objects.

    def has_metadata(self) -> bool:
        """Return whether this page has a direct ``/Metadata`` entry."""
        return self._page.contains_key(_METADATA)

    def has_thumb(self) -> bool:
        """Return whether this page has a direct ``/Thumb`` entry."""
        return self._page.contains_key(_THUMB)

    def has_transition(self) -> bool:
        """Return whether this page has a direct ``/Trans`` entry."""
        return self._page.contains_key(_TRANS)

    def has_actions(self) -> bool:
        """Return whether this page has a direct ``/AA`` entry.

        This is a *read-only* probe — unlike :meth:`get_actions` it does
        **not** auto-materialise an empty ``/AA`` sub-dictionary, so it's
        safe to call on read-only inspection paths that must not mutate
        the page dict."""
        return self._page.contains_key(_AA)

    def has_annotations(self) -> bool:
        """Return whether this page has a direct ``/Annots`` entry."""
        return self._page.contains_key(_ANNOTS)

    def has_thread_beads(self) -> bool:
        """Return whether this page has a direct ``/B`` thread-bead entry."""
        return self._page.contains_key(_BEADS)

    def has_viewports(self) -> bool:
        """Return whether this page has a direct ``/VP`` entry."""
        return self._page.contains_key(_VP)

    def has_group(self) -> bool:
        """Return whether this page has a direct ``/Group`` entry."""
        return self._page.contains_key(_GROUP)

    def has_tab_order(self) -> bool:
        """Return whether this page has a direct ``/Tabs`` entry."""
        return self._page.contains_key(_TABS)

    def has_duration(self) -> bool:
        """Return whether this page has a direct ``/Dur`` entry."""
        return self._page.contains_key(_DUR)

    # ---------- clear helpers ----------

    def clear_metadata(self) -> None:
        """Remove the ``/Metadata`` entry."""
        self._page.remove_item(_METADATA)

    def clear_thumb(self) -> None:
        """Remove the ``/Thumb`` entry."""
        self._page.remove_item(_THUMB)

    def clear_transition(self) -> None:
        """Remove the ``/Trans`` entry."""
        self._page.remove_item(_TRANS)

    def clear_actions(self) -> None:
        """Remove the ``/AA`` entry."""
        self._page.remove_item(_AA)

    def clear_annotations(self) -> None:
        """Remove the ``/Annots`` entry."""
        self._page.remove_item(_ANNOTS)

    def clear_thread_beads(self) -> None:
        """Remove the ``/B`` thread-beads entry."""
        self._page.remove_item(_BEADS)

    def clear_viewports(self) -> None:
        """Remove the ``/VP`` viewports entry."""
        self._page.remove_item(_VP)

    def clear_group(self) -> None:
        """Remove the ``/Group`` entry."""
        self._page.remove_item(_GROUP)

    def clear_tab_order(self) -> None:
        """Remove the ``/Tabs`` entry."""
        self._page.remove_item(_TABS)

    def clear_duration(self) -> None:
        """Remove the ``/Dur`` entry."""
        self._page.remove_item(_DUR)

    # ---------- equality / repr ----------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PDPage):
            return self._page is other._page
        return NotImplemented

    def __hash__(self) -> int:
        return id(self._page)

    def __repr__(self) -> str:
        return f"PDPage(media_box={self.get_media_box()!s})"

    def equals(self, other: object) -> bool:
        """Snake_case mirror of upstream ``PDPage.equals(Object)`` —
        delegates to :meth:`__eq__` so ``page.equals(other)`` and
        ``page == other`` always agree.

        Upstream defines equality as identity over the underlying page
        ``COSDictionary`` (see PDPage.java line 838); we keep the same
        semantics — two ``PDPage`` wrappers are equal iff they wrap the
        same dictionary instance.
        """
        return self.__eq__(other) is True

    def hash_code(self) -> int:
        """Snake_case mirror of upstream ``PDPage.hashCode()`` —
        delegates to :meth:`__hash__`. Provided so callers porting from
        PDFBox can use the upstream spelling directly without reaching
        for the Python builtin ``hash()``.
        """
        return self.__hash__()


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
