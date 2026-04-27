from __future__ import annotations

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
_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_AA: COSName = COSName.get_pdf_name("AA")
_THUMB: COSName = COSName.get_pdf_name("Thumb")
_TRANS: COSName = COSName.get_pdf_name("Trans")
_STRUCT_PARENTS: COSName = COSName.get_pdf_name("StructParents")


class PDPage:
    """
    Single PDF page wrapper. Mirrors
    ``org.apache.pdfbox.pdmodel.PDPage``.

    A page is fundamentally a ``COSDictionary`` with ``/Type /Page``
    and a handful of inheritable attributes (``/Resources``,
    ``/MediaBox``, ``/CropBox``, ``/Rotate``). PDPage resolves those
    inheritable attributes by walking the ``/Parent`` chain.
    """

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
        Mirrors upstream ``PDPageTree.getInheritableAttribute``."""
        node: COSDictionary | None = self._page
        seen: set[int] = set()
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            value = node.get_dictionary_object(key)
            if value is not None:
                return value
            parent = node.get_dictionary_object(_PARENT)
            node = parent if isinstance(parent, COSDictionary) else None
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

    def set_contents(self, stream: COSStream) -> None:
        """Replace ``/Contents`` with a single stream. Cluster #1 covers the
        single-stream variant; the array form is an upstream overload that
        will land with the contentstream cluster."""
        self._page.set_item(_CONTENTS, stream)

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
        """``/CropBox`` if present (inheritable), else ``/MediaBox``."""
        # CropBox is inheritable per spec (PDF 1.7 §14.11.2).
        value = self._get_inheritable(_CROP_BOX)
        if isinstance(value, COSArray):
            return PDRectangle.from_cos_array(value)
        return self.get_media_box()

    def set_crop_box(self, rect: PDRectangle | None) -> None:
        if rect is None:
            self._page.remove_item(_CROP_BOX)
            return
        self._page.set_item(_CROP_BOX, rect.to_cos_array())

    def get_bleed_box(self) -> PDRectangle:
        """``/BleedBox`` if present, else ``/CropBox``."""
        return self._get_box(_BLEED_BOX, fallback=self.get_crop_box())

    def set_bleed_box(self, rect: PDRectangle | None) -> None:
        if rect is None:
            self._page.remove_item(_BLEED_BOX)
            return
        self._page.set_item(_BLEED_BOX, rect.to_cos_array())

    def get_trim_box(self) -> PDRectangle:
        return self._get_box(_TRIM_BOX, fallback=self.get_crop_box())

    def set_trim_box(self, rect: PDRectangle | None) -> None:
        if rect is None:
            self._page.remove_item(_TRIM_BOX)
            return
        self._page.set_item(_TRIM_BOX, rect.to_cos_array())

    def get_art_box(self) -> PDRectangle:
        return self._get_box(_ART_BOX, fallback=self.get_crop_box())

    def set_art_box(self, rect: PDRectangle | None) -> None:
        if rect is None:
            self._page.remove_item(_ART_BOX)
            return
        self._page.set_item(_ART_BOX, rect.to_cos_array())

    # ---------- rotation / user unit ----------

    def get_rotation(self) -> int:
        """Inheritable; default 0. Normalised to 0/90/180/270 (mirrors
        upstream's modulo-360 semantics)."""
        value = self._get_inheritable(_ROTATE)
        if value is None:
            return 0
        # Both COSInteger and COSFloat are accepted upstream.
        from pypdfbox.cos import COSFloat, COSInteger

        raw: int
        if isinstance(value, COSInteger):
            raw = value.value
        elif isinstance(value, COSFloat):
            raw = int(value.value)
        else:
            return 0
        # Normalise — upstream rounds to nearest 90 and wraps.
        normalised = ((raw % 360) + 360) % 360
        # Snap to 0/90/180/270 (treat 45 → 0, 89 → 90, etc.)
        snapped = round(normalised / 90.0) * 90
        return snapped % 360

    def set_rotation(self, rotation: int) -> None:
        from pypdfbox.cos import COSInteger

        self._page.set_item(_ROTATE, COSInteger.get(int(rotation)))

    def get_user_unit(self) -> float:
        """``/UserUnit`` (PDF 1.6+). Default 1.0; upstream clamps below 1.0
        but accepts whatever the dict says — we follow."""
        from pypdfbox.cos import COSFloat, COSInteger

        value = self._page.get_dictionary_object(_USER_UNIT)
        if isinstance(value, (COSInteger, COSFloat)):
            return float(value.value)
        return 1.0

    def set_user_unit(self, unit: float) -> None:
        from pypdfbox.cos import COSFloat

        self._page.set_item(_USER_UNIT, COSFloat(float(unit)))

    # ---------- annotations ----------

    def get_annotations(self) -> list[Any]:
        """Resolve ``/Annots`` into a list of :class:`PDAnnotation`.

        Returns an empty list when ``/Annots`` is absent. Each entry is
        dispatched to the appropriate subclass via
        :meth:`PDAnnotation.create`. Non-dictionary entries (rare but
        legal under defensive parsing) are skipped.
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
            if isinstance(entry, COSDictionary):
                result.append(PDAnnotation.create(entry))
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

    def set_transition(self, trans: Any) -> None:
        if trans is None:
            self._page.remove_item(_TRANS)
            return
        self._page.set_item(_TRANS, trans.get_cos_object())

    def get_actions(self) -> Any:
        from pypdfbox.pdmodel.interactive.action import PDPageAdditionalActions

        actions = self._page.get_dictionary_object(_AA)
        if isinstance(actions, COSDictionary):
            return PDPageAdditionalActions(actions)
        return None

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
