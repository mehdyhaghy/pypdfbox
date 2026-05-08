from __future__ import annotations

import datetime as _dt
from collections.abc import Sequence
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form.pd_transparency_group_attributes import (
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache

_FORM: COSName = COSName.get_pdf_name("Form")
_FORMTYPE: COSName = COSName.get_pdf_name("FormType")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")
_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]
_STRUCT_PARENTS: COSName = COSName.get_pdf_name("StructParents")
_GROUP: COSName = COSName.get_pdf_name("Group")
_REF: COSName = COSName.get_pdf_name("Ref")
_OC: COSName = COSName.get_pdf_name("OC")
_OPI: COSName = COSName.get_pdf_name("OPI")
_METADATA: COSName = COSName.METADATA  # type: ignore[attr-defined]
_PIECE_INFO: COSName = COSName.get_pdf_name("PieceInfo")
_LAST_MODIFIED: COSName = COSName.get_pdf_name("LastModified")
_NAME: COSName = COSName.get_pdf_name("Name")


class PDFormXObject(PDXObject):
    """
    Form XObject — reusable graphics container. Mirrors
    ``org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject``.

    Has ``/Subtype /Form`` and the form-specific entries:

    - ``/FormType``  — int (currently always 1).
    - ``/BBox``      — bounding box rectangle (required).
    - ``/Matrix``    — transformation matrix [a b c d e f] (optional;
      defaults to identity per PDF §8.10).
    - ``/Resources`` — local resource dict (optional; falls back to the
      page's resources at use-time).
    """

    # The fixed ``/Subtype`` value for a Form XObject. Mirrors upstream's
    # use of ``COSName.FORM`` for ``/Subtype`` checks; exposing the value
    # as a class constant lets call sites identify form X-Objects without
    # re-deriving the name (parallel to ``SUBTYPE_IMAGE`` on the image
    # cluster).
    SUBTYPE: str = "Form"

    def __init__(
        self,
        stream: PDStream | COSStream | PDDocument,
        cache: PDResourceCache | None = None,
    ) -> None:
        # Local import — PDDocument pulls in PDPage / PDResources which
        # themselves depend on this module at construction time.
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        if isinstance(stream, PDDocument):
            # Mirrors upstream ``PDFormXObject(PDDocument)`` — create a
            # blank form-XObject stream owned by the document for writing.
            stream = PDStream(stream)
        super().__init__(stream, _FORM)
        # Mirror upstream: lazily-resolved cached typed group attributes.
        self._group_attributes: PDTransparencyGroupAttributes | None = None
        # Mirrors upstream's ``private final ResourceCache cache`` — when
        # set, ``get_resources()`` threads it through to the new
        # ``PDResources`` so font/X-object look-ups hit the cache.
        self._cache: PDResourceCache | None = cache

    # ---------- /FormType ----------

    def get_form_type(self) -> int:
        """``/FormType`` (default 1 — the only defined value)."""
        return self.get_cos_object().get_int(_FORMTYPE, 1)

    def set_form_type(self, form_type: int) -> None:
        self.get_cos_object().set_int(_FORMTYPE, int(form_type))

    # ---------- /BBox ----------

    def get_b_box(self) -> PDRectangle | None:
        """``/BBox``. Returns ``None`` when absent (matches upstream)."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_BBOX)
        if isinstance(value, COSArray):
            return PDRectangle.from_cos_array(value)
        return None

    # PDFBox spells it ``getBBox`` — keep both forms for camelCase fidelity
    # (PDFBox developers will type ``get_b_box`` after the case-conversion
    # rule, but the two-word form ``get_bbox`` is what most port tests use).
    def get_bbox(self) -> PDRectangle | None:
        return self.get_b_box()

    def set_b_box(self, bbox: PDRectangle | None) -> None:
        cos = self.get_cos_object()
        if bbox is None:
            cos.remove_item(_BBOX)
        else:
            cos.set_item(_BBOX, bbox.to_cos_array())

    def set_bbox(self, bbox: PDRectangle | None) -> None:
        self.set_b_box(bbox)

    # ---------- /Matrix ----------

    def get_matrix(self) -> list[float]:
        """``/Matrix`` as a 6-tuple ``[a, b, c, d, e, f]``. Defaults to the
        identity matrix ``[1, 0, 0, 1, 0, 0]`` per PDF §8.10. Mirrors
        upstream's ``Matrix.createMatrix(...)`` semantics on the array form
        (a typed ``Matrix`` class lands with the rendering cluster):
        the identity matrix is returned when ``/Matrix`` is absent, when
        it is not a ``COSArray``, when its size is less than 6, or when
        any of the first six entries is not a numeric COS object."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_MATRIX)
        if isinstance(value, COSArray) and value.size() >= 6:
            out: list[float] = []
            for i in range(6):
                entry = value.get_object(i)
                if isinstance(entry, (COSInteger, COSFloat)):
                    out.append(float(entry.value))
                else:
                    # Match upstream Matrix.createMatrix: any non-numeric
                    # entry collapses to identity (graceful degradation
                    # rather than a hard error).
                    return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
            return out
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def set_matrix(self, values: Sequence[float] | COSArray | None) -> None:
        cos = self.get_cos_object()
        if values is None:
            cos.remove_item(_MATRIX)
            return
        if isinstance(values, COSArray):
            cos.set_item(_MATRIX, values)
            return
        if len(values) != 6:
            raise ValueError(
                f"/Matrix expects exactly 6 numbers (a b c d e f); got {len(values)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in values])
        cos.set_item(_MATRIX, arr)

    # ---------- /Resources ----------

    def get_resources(self) -> PDResources | None:
        """``/Resources`` if present, else ``None``. Note: when the key is
        present but the value isn't a dictionary, upstream returns an empty
        ``PDResources`` (PDFBOX-4372 — guards against a self-reference where
        the form refers to itself). We mirror that.

        When this form was constructed with a :class:`PDResourceCache`,
        the cache is threaded through to the returned :class:`PDResources`
        — matching upstream ``new PDResources(resources, cache)``."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_RESOURCES)
        if isinstance(value, COSDictionary):
            return PDResources(value, resource_cache=self._cache)
        if cos.contains_key(_RESOURCES):
            return PDResources()
        return None

    def set_resources(self, resources: PDResources | COSDictionary | None) -> None:
        cos = self.get_cos_object()
        if resources is None:
            cos.remove_item(_RESOURCES)
            return
        target = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        cos.set_item(_RESOURCES, target)

    # ---------- /StructParents ----------

    def get_struct_parents(self) -> int:
        """``/StructParents`` integer key into the structure-parents
        number tree. Defaults to ``-1`` when absent (matches upstream)."""
        return self.get_cos_object().get_int(_STRUCT_PARENTS, -1)

    def set_struct_parents(self, value: int) -> None:
        self.get_cos_object().set_int(_STRUCT_PARENTS, int(value))

    # Backward-compatibility singular aliases. PDFBox's PDFormXObject uses
    # the plural ``/StructParents`` key (forms reference a *list* of
    # marked-content sequences via the structure-parent tree), but call
    # sites that share code paths with PDImageXObject / PDAnnotation
    # — which use the singular ``getStructParent()`` form — sometimes
    # reach for the singular spelling. Mirror it through to the plural
    # accessor so either form compiles.
    def get_struct_parent(self) -> int:
        """Singular alias of :meth:`get_struct_parents`. The underlying
        PDF key is still ``/StructParents`` (plural) — this exists only
        to match the spelling used by PDImageXObject / PDAnnotation
        sibling APIs."""
        return self.get_struct_parents()

    def set_struct_parent(self, value: int) -> None:
        """Singular alias of :meth:`set_struct_parents`."""
        self.set_struct_parents(value)

    # ---------- /OC (optional content) ----------

    def get_oc(self) -> PDPropertyList | None:
        """``/OC`` typed property list (PDOptionalContentGroup or
        PDOptionalContentMembershipDictionary). Returns ``None`` when
        absent or of an unrecognised type."""
        value = self.get_cos_object().get_dictionary_object(_OC)
        if isinstance(value, COSDictionary):
            return PDPropertyList.create(value)
        return None

    def set_oc(self, value: PDPropertyList | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_OC)
            return
        cos.set_item(_OC, value.get_cos_object())

    # ---------- /Group ----------

    def get_group(self) -> COSDictionary | None:
        """Raw ``/Group`` transparency-group dictionary, or ``None``."""
        value = self.get_cos_object().get_dictionary_object(_GROUP)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_group(self, value: COSDictionary | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_GROUP)
            self._group_attributes = None
            return
        cos.set_item(_GROUP, value)
        # Drop the typed cache — caller passed a raw dict that may not be
        # the cached object.
        self._group_attributes = None

    # Typed /Group access mirroring upstream ``getGroup() /
    # setGroup(PDTransparencyGroupAttributes)``. The earlier raw form
    # above is kept for backward compatibility with call sites that
    # already store/retrieve the dictionary directly.

    def get_group_attributes(self) -> PDTransparencyGroupAttributes | None:
        """Typed ``/Group`` transparency-group attributes, or ``None``
        when no ``/Group`` entry exists. Mirrors upstream
        ``getGroup()`` (which returns ``PDTransparencyGroupAttributes``).
        Lazily wraps and caches the underlying dictionary."""
        if self._group_attributes is not None:
            return self._group_attributes
        value = self.get_cos_object().get_dictionary_object(_GROUP)
        if isinstance(value, COSDictionary):
            self._group_attributes = PDTransparencyGroupAttributes(value)
            return self._group_attributes
        return None

    def set_group_attributes(
        self, group: PDTransparencyGroupAttributes | None
    ) -> None:
        """Set the typed transparency-group attributes. Mirrors upstream
        ``setGroup(PDTransparencyGroupAttributes)``. ``None`` clears the
        ``/Group`` entry."""
        cos = self.get_cos_object()
        if group is None:
            cos.remove_item(_GROUP)
            self._group_attributes = None
            return
        cos.set_item(_GROUP, group.get_cos_object())
        self._group_attributes = group

    # ---------- /Ref ----------

    def get_ref(self) -> COSDictionary | None:
        """Raw ``/Ref`` reference dictionary, or ``None``."""
        value = self.get_cos_object().get_dictionary_object(_REF)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_ref(self, value: COSDictionary | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_REF)
            return
        cos.set_item(_REF, value)

    # ---------- /PieceInfo ----------

    def get_piece_info(self) -> COSDictionary | None:
        """Raw ``/PieceInfo`` page-piece dictionary, or ``None``. Mirrors
        upstream ``getPieceInfo()`` (PDF §14.5)."""
        value = self.get_cos_object().get_dictionary_object(_PIECE_INFO)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_piece_info(self, value: COSDictionary | None) -> None:
        """Mirror of upstream ``setPieceInfo(COSDictionary)``."""
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_PIECE_INFO)
            return
        cos.set_item(_PIECE_INFO, value)

    # Backward-compatibility aliases — earlier ports used the all-lowercase
    # form. Keep both spellings live so existing call sites and the parity
    # tests do not regress.
    def get_pieceinfo(self) -> COSDictionary | None:
        return self.get_piece_info()

    def set_pieceinfo(self, value: COSDictionary | None) -> None:
        self.set_piece_info(value)

    # ---------- /OPI ----------

    def get_opi(self) -> COSDictionary | None:
        """Raw ``/OPI`` Open Prepress Interface dictionary, or ``None``
        when absent. Mirrors PDF 32000-1 §14.11.7 — ``/OPI`` carries
        version-keyed sub-dictionaries (``/1.3`` and/or ``/2.0``) used
        by prepress workflows to substitute high-resolution image data.

        Upstream PDFBox does not expose a typed ``/OPI`` accessor on
        ``PDFormXObject`` (the entry is rare in modern PDFs), but the
        key is recognised in PDF 32000-1 Table 95 and we provide a raw
        accessor so callers can introspect ``/OPI`` without re-deriving
        the name."""
        value = self.get_cos_object().get_dictionary_object(_OPI)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_opi(self, value: COSDictionary | None) -> None:
        """Set or clear ``/OPI``. ``None`` removes the entry."""
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_OPI)
            return
        cos.set_item(_OPI, value)

    # ---------- /LastModified ----------

    def get_last_modified(self) -> _dt.datetime | None:
        """``/LastModified`` PDF date string parsed to ``datetime``;
        ``None`` when absent or unparseable."""
        # Local import avoids a top-level cycle through pd_document_information.
        from pypdfbox.pdmodel.pd_document_information import (  # noqa: PLC0415
            _parse_pdf_date,
        )

        raw = self.get_cos_object().get_string(_LAST_MODIFIED)
        return _parse_pdf_date(raw) if raw is not None else None

    def set_last_modified(self, value: _dt.datetime | None) -> None:
        from pypdfbox.pdmodel.pd_document_information import (  # noqa: PLC0415
            _format_pdf_date,
        )

        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_LAST_MODIFIED)
            return
        cos.set_item(_LAST_MODIFIED, COSString(_format_pdf_date(value)))

    # ---------- /Name ----------

    def get_name(self) -> str | None:
        """``/Name`` (a /Name object — deprecated since PDF 1.2 but still
        appears in the wild). ``None`` when absent."""
        return self.get_cos_object().get_name(_NAME)

    def set_name(self, value: str | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_NAME)
            return
        cos.set_name(_NAME, value)

    # ---------- PDContentStream interface ----------
    #
    # ``PDFormXObject`` implements ``PDContentStream`` upstream. The five
    # methods below — ``get_content_stream`` / ``get_contents`` /
    # ``get_contents_for_random_access`` / ``get_resources`` / ``get_bbox`` /
    # ``get_matrix`` — give the content-stream parser a stable handle on
    # the form's body without forcing callers to thread :class:`PDStream`
    # through the API. ``get_resources`` and ``get_bbox`` and ``get_matrix``
    # are already defined above; the remaining three are added here.

    def get_content_stream(self) -> PDStream:
        """The underlying :class:`PDStream` carrying the form's content
        stream bytes. Mirrors upstream ``getContentStream()``."""
        return self.get_stream()

    def get_contents(self) -> BinaryIO:
        """Decoded content-stream bytes as a readable stream. Mirrors
        upstream ``getContents()`` (which returns ``InputStream``).
        Equivalent to ``self.get_stream().create_input_stream()``."""
        return self.get_stream().create_input_stream()

    def get_contents_for_random_access(self) -> RandomAccessRead:
        """Random-access view of the decoded content-stream bytes. Mirrors
        upstream ``getContentsForRandomAccess()``. The bytes are read
        eagerly and wrapped in :class:`RandomAccessReadBuffer` — content
        streams are bounded so this stays cheap."""
        # Local import avoids a top-level cycle through the io package
        # which itself imports PDF model types in a few places.
        from pypdfbox.io.random_access_read_buffer import (  # noqa: PLC0415
            RandomAccessReadBuffer,
        )

        with self.get_stream().create_input_stream() as src:
            data = src.read()
        return RandomAccessReadBuffer.from_bytes(data)

    def get_contents_for_stream_parsing(self) -> RandomAccessRead:
        """Random-access view of the decoded content-stream bytes for the
        PDF stream parser. Mirrors upstream
        ``PDContentStream.getContentsForStreamParsing()`` (the interface
        default delegates to ``getContentsForRandomAccess()``). Forms have
        a single content stream so we do the same delegation that
        :class:`PDPage` does."""
        return self.get_contents_for_random_access()

    # ---------- /OC aliases ----------
    #
    # Upstream spells the optional-content accessor ``getOptionalContent``
    # (and ``setOptionalContent``); the snake_case translation is
    # ``get_optional_content``. The earlier two-letter form ``get_oc`` is
    # the one wired into call sites; both spellings stay live.

    def get_optional_content(self) -> PDPropertyList | None:
        """``/OC`` typed property list. Mirrors upstream
        ``getOptionalContent()``. Alias of :meth:`get_oc`."""
        return self.get_oc()

    def set_optional_content(self, value: PDPropertyList | None) -> None:
        """Set ``/OC`` typed property list. Mirrors upstream
        ``setOptionalContent(PDPropertyList)``. Alias of :meth:`set_oc`."""
        self.set_oc(value)

    # ---------- predicate helpers ----------
    #
    # These ``has_*`` helpers don't appear on upstream PDFormXObject (Java
    # callers use ``getX() != null``), but they are the established
    # pypdfbox idiom on sibling classes (``PDPage.has_group``,
    # ``PDViewportDictionary.has_b_box``, ``PDType3CharProc.has_resources``)
    # and let call-sites avoid an extra Optional-style indirection.
    #
    # All of them check the underlying COS dict shape — not just key
    # presence — so a key that exists but holds the wrong type returns
    # ``False`` (matching the typed getters which all return ``None`` in
    # that case).

    def has_b_box(self) -> bool:
        """Return ``True`` when ``/BBox`` is present and a ``COSArray``."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_BBOX), COSArray
        )

    def has_bbox(self) -> bool:
        """Alias of :meth:`has_b_box` matching the two-word ``get_bbox``
        spelling."""
        return self.has_b_box()

    def has_matrix(self) -> bool:
        """Return ``True`` when ``/Matrix`` is present and a ``COSArray``
        of size 6 or more — i.e. when :meth:`get_matrix` will return the
        stored value rather than the identity default."""
        value = self.get_cos_object().get_dictionary_object(_MATRIX)
        if not isinstance(value, COSArray) or value.size() < 6:
            return False
        return all(
            isinstance(value.get_object(i), (COSInteger, COSFloat))
            for i in range(6)
        )

    def has_resources(self) -> bool:
        """Return ``True`` when ``/Resources`` is present (regardless of
        whether the value is a real dictionary or the broken
        self-reference shape PDFBOX-4372 covers)."""
        return self.get_cos_object().contains_key(_RESOURCES)

    def has_group(self) -> bool:
        """Return ``True`` when ``/Group`` is present and a
        ``COSDictionary``."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_GROUP), COSDictionary
        )

    def has_ref(self) -> bool:
        """Return ``True`` when ``/Ref`` is present and a
        ``COSDictionary``."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_REF), COSDictionary
        )

    def has_oc(self) -> bool:
        """Return ``True`` when ``/OC`` (optional content) is present and
        a ``COSDictionary``."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_OC), COSDictionary
        )

    def has_optional_content(self) -> bool:
        """Alias of :meth:`has_oc` — long-form spelling matching upstream
        ``getOptionalContent``."""
        return self.has_oc()

    def has_piece_info(self) -> bool:
        """Return ``True`` when ``/PieceInfo`` is present and a
        ``COSDictionary``."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_PIECE_INFO),
            COSDictionary,
        )

    def has_pieceinfo(self) -> bool:
        """Lowercase alias of :meth:`has_piece_info`, mirroring the
        ``get_pieceinfo``/``set_pieceinfo`` legacy spelling kept live for
        backward compatibility."""
        return self.has_piece_info()

    def has_last_modified(self) -> bool:
        """Return ``True`` when ``/LastModified`` is present (as a
        string)."""
        return self.get_cos_object().get_string(_LAST_MODIFIED) is not None

    def has_name(self) -> bool:
        """Return ``True`` when the legacy ``/Name`` entry is present."""
        return self.get_cos_object().get_name(_NAME) is not None

    def has_struct_parents(self) -> bool:
        """Return ``True`` when ``/StructParents`` is present — i.e. this
        form participates in the structure-parents number tree."""
        return self.get_cos_object().contains_key(_STRUCT_PARENTS)

    def has_form_type(self) -> bool:
        """Return ``True`` when ``/FormType`` is explicitly present.
        :meth:`get_form_type` defaults to ``1`` when absent, so this is
        the way to tell an explicit ``1`` from the implicit default."""
        return self.get_cos_object().contains_key(_FORMTYPE)

    def has_opi(self) -> bool:
        """Return ``True`` when ``/OPI`` is present and a
        ``COSDictionary`` (the only valid form per PDF 32000-1
        §14.11.7)."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_OPI), COSDictionary
        )

    def has_metadata(self) -> bool:
        """Return ``True`` when ``/Metadata`` is present and a
        ``COSStream`` — i.e. :meth:`get_metadata` (inherited from
        :class:`PDXObject`) will return a typed ``PDMetadata`` rather
        than ``None``."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_METADATA), COSStream
        )
