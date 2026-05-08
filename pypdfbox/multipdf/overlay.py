from __future__ import annotations

import logging
import os
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.io import io_utils as _io_utils
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

if TYPE_CHECKING:
    from collections.abc import Mapping

_LOG = logging.getLogger(__name__)

# Resource key prefix used for the form XObject the overlay registers in
# the host page's /Resources /XObject subdictionary. Matches upstream's
# literal ``resources.add(overlayFormXObject, "OL")`` call in
# ``Overlay.overlayPage``.
_OVERLAY_KEY_PREFIX: str = "OL"
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_FLATE_DECODE: COSName = COSName.get_pdf_name("FlateDecode")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")


class Position(Enum):
    """Possible location of the overlaid pages: foreground or background.

    Mirrors ``org.apache.pdfbox.multipdf.Overlay.Position``.
    """

    FOREGROUND = "FOREGROUND"
    BACKGROUND = "BACKGROUND"

    @classmethod
    def value_of(cls, name: str) -> Position:
        """Return the ``Position`` member with the given name.

        Mirrors Java's ``Enum.valueOf(String)`` — case-sensitive lookup
        against the member name (``"FOREGROUND"`` / ``"BACKGROUND"``).
        Raises :class:`ValueError` for unknown names, just like Java's
        ``IllegalArgumentException``.
        """
        try:
            return cls[name]
        except KeyError as exc:
            raise ValueError(
                f"No Position constant with name {name!r}"
            ) from exc


class _LayoutPage:
    """Internal — stores the cached overlay-page metadata."""

    __slots__ = (
        "overlay_media_box",
        "overlay_cos_stream",
        "overlay_resources",
        "overlay_rotation",
    )

    def __init__(
        self,
        media_box: PDRectangle,
        content_stream: COSStream,
        resources: COSDictionary,
        rotation: int,
    ) -> None:
        self.overlay_media_box = media_box
        self.overlay_cos_stream = content_stream
        self.overlay_resources = resources
        self.overlay_rotation = rotation


class Overlay:
    """Adds an overlay to an existing PDF document. Mirrors
    ``org.apache.pdfbox.multipdf.Overlay``.

    Construction is parameter-less; the input document and the overlay
    documents are configured via setters before :meth:`overlay` is called:

    - :meth:`set_input_pdf` / :meth:`set_input_file` — the base document
      that receives the overlay.
    - :meth:`set_default_overlay_pdf` / :meth:`set_default_overlay_file`
      — overlay used for every page (unless a more-specific match wins).
    - :meth:`set_first_page_overlay_pdf` / :meth:`set_last_page_overlay_pdf`
      — only the first / last page of the input document.
    - :meth:`set_odd_page_overlay_pdf` / :meth:`set_even_page_overlay_pdf`
      — every odd / even input page.
    - :meth:`set_all_pages_overlay_pdf` — multi-page overlay where the
      i-th overlay page lays over the i-th (mod N) input page.
    - :meth:`set_specific_page_overlay_pdf` — explicit per-page mapping
      (1-based page number → :class:`PDDocument`); the first page of each
      mapped document is used.
    - :meth:`set_overlay_position` — :class:`Position.BACKGROUND` (default)
      paints the overlay underneath the existing page content;
      :class:`Position.FOREGROUND` paints it on top.

    Per the PDFBOX-6048 alignment note in ``CLAUDE.md``, this port uses
    the real lower-left corner of the overlay's MediaBox when computing
    the centering transform — upstream 3.0.x assumed (0, 0). PDFBox 4.0
    plans the same correction.

    Note on cloning:
    `:class:`PDFCloneUtility`` is the upstream helper used to deep-copy
    overlay resources into the input document. When that class is
    available in this package it's used directly; otherwise we fall back
    to :meth:`PDDocument._deep_copy_cos` which has equivalent semantics
    for the resource-tree shapes overlay produces.
    """

    def __init__(self) -> None:
        # Per-bucket overlay state.
        self._default_overlay_page: _LayoutPage | None = None
        self._first_page_overlay_page: _LayoutPage | None = None
        self._last_page_overlay_page: _LayoutPage | None = None
        self._odd_page_overlay_page: _LayoutPage | None = None
        self._even_page_overlay_page: _LayoutPage | None = None
        self._rotated_default_overlay_pages: dict[int, _LayoutPage] = {}

        # Documents we opened on behalf of the caller (file-path setters).
        # Closed by :meth:`close`.
        self._open_documents: list[PDDocument] = []

        # 1-based page-number → LayoutPage. Built by :meth:`overlay` from
        # the user's specific-page maps and from the all-pages overlay.
        self._specific_page_overlay_layout: dict[int, _LayoutPage] = {}
        # Explicit setter-side staging: doc/path keyed by 1-based page.
        self._specific_page_overlay_documents: dict[int, PDDocument] = {}

        self._position: Position = Position.BACKGROUND

        self._input_filename: str | None = None
        self._input_pdf: PDDocument | None = None

        self._default_overlay_filename: str | None = None
        self._default_overlay_document: PDDocument | None = None

        self._first_page_overlay_filename: str | None = None
        self._first_page_overlay_document: PDDocument | None = None

        self._last_page_overlay_filename: str | None = None
        self._last_page_overlay_document: PDDocument | None = None

        self._all_pages_overlay_filename: str | None = None
        self._all_pages_overlay_document: PDDocument | None = None

        self._odd_page_overlay_filename: str | None = None
        self._odd_page_overlay_document: PDDocument | None = None

        self._even_page_overlay_filename: str | None = None
        self._even_page_overlay_document: PDDocument | None = None

        self._number_of_overlay_pages: int = 0
        self._use_all_overlay_pages: bool = False
        self._adjust_rotation: bool = False

    # ---------- entry point ----------

    def overlay(
        self,
        specific_page_overlay_map: Mapping[int, str] | None = None,
    ) -> PDDocument:
        """Apply the configured overlays and return the input
        :class:`PDDocument` (caller is responsible for saving and closing).

        ``specific_page_overlay_map`` maps a 1-based input page number to
        a path of an overlay PDF whose first page is used. The map must
        be non-``None`` (mirrors upstream — pass ``{}`` for "no specifics").
        """
        if specific_page_overlay_map is None:
            raise ValueError(
                "Overlay.overlay requires a (possibly empty) page map"
            )
        layouts: dict[str, _LayoutPage] = {}
        self._load_pdfs()
        for page_number, path in specific_page_overlay_map.items():
            cached = layouts.get(path)
            if cached is None:
                doc = self._load_pdf(path)
                cached = self._create_layout_page_from_document(doc)
                layouts[path] = cached
                self._open_documents.append(doc)
            self._specific_page_overlay_layout[int(page_number)] = cached
        # Stage entries from setter-side document map too.
        for page_number, doc in self._specific_page_overlay_documents.items():
            self._specific_page_overlay_layout[int(page_number)] = (
                self._create_layout_page_from_document(doc)
            )
        assert self._input_pdf is not None  # guaranteed by _load_pdfs
        self._process_pages(self._input_pdf)
        return self._input_pdf

    def overlay_documents(
        self,
        specific_page_overlay_document_map: Mapping[int, PDDocument],
    ) -> PDDocument:
        """Variant of :meth:`overlay` that accepts already-loaded overlay
        :class:`PDDocument` instances rather than file paths. Mirrors
        upstream ``Overlay.overlayDocuments``."""
        self._load_pdfs()
        for page_number, doc in specific_page_overlay_document_map.items():
            if doc is not None:
                self._specific_page_overlay_layout[int(page_number)] = (
                    self._create_layout_page_from_document(doc)
                )
        for page_number, doc in self._specific_page_overlay_documents.items():
            self._specific_page_overlay_layout[int(page_number)] = (
                self._create_layout_page_from_document(doc)
            )
        assert self._input_pdf is not None
        self._process_pages(self._input_pdf)
        return self._input_pdf

    # ---------- lifecycle ----------

    def close(self) -> None:
        """Close all input documents this instance opened on the caller's
        behalf (i.e. those provided as a file path, not a PDDocument).
        Mirrors upstream's ``Closeable`` semantics."""
        import contextlib

        for doc in (
            self._default_overlay_document,
            self._first_page_overlay_document,
            self._last_page_overlay_document,
            self._all_pages_overlay_document,
            self._odd_page_overlay_document,
            self._even_page_overlay_document,
        ):
            if doc is not None:
                with contextlib.suppress(Exception):
                    doc.close()
        for doc in self._open_documents:
            with contextlib.suppress(Exception):
                doc.close()
        self._open_documents.clear()
        self._specific_page_overlay_layout.clear()
        self._rotated_default_overlay_pages.clear()

    def __enter__(self) -> Overlay:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # ---------- internal: loading ----------

    def _load_pdfs(self) -> None:
        # Upstream behaviour (Overlay.loadPDFs): when *both* a filename and
        # a PDDocument were configured for the same slot, the **filename
        # wins** — the PDF is reloaded from disk and the previously-staged
        # PDDocument is replaced. We mirror that precedence here.
        # input PDF
        if self._input_filename is not None:
            self._input_pdf = self._load_pdf(self._input_filename)
        if self._input_pdf is None:
            raise ValueError("No input document")
        # default overlay PDF
        if self._default_overlay_filename is not None:
            self._default_overlay_document = self._load_pdf(self._default_overlay_filename)
        if self._default_overlay_document is not None:
            self._default_overlay_page = self._create_layout_page_from_document(
                self._default_overlay_document
            )
        # first page overlay PDF
        if self._first_page_overlay_filename is not None:
            self._first_page_overlay_document = self._load_pdf(
                self._first_page_overlay_filename
            )
        if self._first_page_overlay_document is not None:
            self._first_page_overlay_page = self._create_layout_page_from_document(
                self._first_page_overlay_document
            )
        # last page overlay PDF
        if self._last_page_overlay_filename is not None:
            self._last_page_overlay_document = self._load_pdf(
                self._last_page_overlay_filename
            )
        if self._last_page_overlay_document is not None:
            self._last_page_overlay_page = self._create_layout_page_from_document(
                self._last_page_overlay_document
            )
        # odd pages overlay PDF
        if self._odd_page_overlay_filename is not None:
            self._odd_page_overlay_document = self._load_pdf(
                self._odd_page_overlay_filename
            )
        if self._odd_page_overlay_document is not None:
            self._odd_page_overlay_page = self._create_layout_page_from_document(
                self._odd_page_overlay_document
            )
        # even pages overlay PDF
        if self._even_page_overlay_filename is not None:
            self._even_page_overlay_document = self._load_pdf(
                self._even_page_overlay_filename
            )
        if self._even_page_overlay_document is not None:
            self._even_page_overlay_page = self._create_layout_page_from_document(
                self._even_page_overlay_document
            )
        # all pages overlay PDF
        if self._all_pages_overlay_filename is not None:
            self._all_pages_overlay_document = self._load_pdf(
                self._all_pages_overlay_filename
            )
        if self._all_pages_overlay_document is not None:
            self._specific_page_overlay_layout = self._create_page_overlay_layout_map(
                self._all_pages_overlay_document
            )
            self._use_all_overlay_pages = True
            self._number_of_overlay_pages = len(self._specific_page_overlay_layout)

    @staticmethod
    def _load_pdf(pdf_name: str | os.PathLike[str]) -> PDDocument:
        return PDDocument.load(pdf_name)

    # ---------- internal: layout-page synthesis ----------

    def _create_layout_page_from_document(self, doc: PDDocument) -> _LayoutPage:
        if doc.get_number_of_pages() == 0:
            raise ValueError("overlay document must contain at least one page")
        return self._create_layout_page(doc.get_page(0))

    def _create_layout_page(self, page: PDPage) -> _LayoutPage:
        contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
        resources = page.get_resources()
        if resources is None:
            resources = PDResources()
        return _LayoutPage(
            page.get_media_box(),
            self._create_combined_content_stream(contents),
            resources.get_cos_object(),
            page.get_rotation(),
        )

    def _create_page_overlay_layout_map(
        self, doc: PDDocument
    ) -> dict[int, _LayoutPage]:
        out: dict[int, _LayoutPage] = {}
        for i, page in enumerate(doc.get_pages()):
            out[i] = self._create_layout_page(page)
        return out

    def _create_combined_content_stream(self, contents: COSBase | None) -> COSStream:
        streams = self._create_content_stream_list(contents)
        # Concatenate the bodies into a single FlateDecode-encoded stream.
        # Use the input document's scratch file to keep memory bounded.
        assert self._input_pdf is not None
        scratch = self._input_pdf.get_document().scratch_file
        concat = COSStream(scratch)
        with concat.create_output_stream(_FLATE_DECODE) as out:
            for stream in streams:
                with stream.create_input_stream() as src:
                    _io_utils.copy(src, out)
        return concat

    @staticmethod
    def _create_content_stream_list(contents: COSBase | None) -> list[COSStream]:
        if contents is None:
            return []
        if isinstance(contents, COSStream):
            return [contents]
        out: list[COSStream] = []
        if isinstance(contents, COSArray):
            for item in contents:
                out.extend(Overlay._create_content_stream_list(item))
            return out
        if isinstance(contents, COSObject):
            return Overlay._create_content_stream_list(contents.get_object())
        raise OSError(f"Unknown content type: {type(contents).__name__}")

    # ---------- internal: per-page processing ----------

    def _process_pages(self, document: PDDocument) -> None:
        cloner = self._make_cloner(document)
        page_tree = document.get_pages()
        number_of_pages = len(page_tree)
        for i, page in enumerate(page_tree):
            page_counter = i + 1
            layout_page = self._get_layout_page(page_counter, number_of_pages)
            if layout_page is None:
                continue
            page_dict = page.get_cos_object()
            original_content = page_dict.get_dictionary_object(_CONTENTS)
            new_content_array = COSArray()
            if self._position is Position.FOREGROUND:
                new_content_array.add(self._create_stream("q\n"))
                self._add_original_content(original_content, new_content_array)
                new_content_array.add(self._create_stream("Q\n"))
                self._overlay_page(page, layout_page, new_content_array, cloner)
            elif self._position is Position.BACKGROUND:
                self._overlay_page(page, layout_page, new_content_array, cloner)
                self._add_original_content(original_content, new_content_array)
            else:
                raise OSError(f"Unknown type of position: {self._position!r}")
            page_dict.set_item(_CONTENTS, new_content_array)

    @staticmethod
    def _make_cloner(document: PDDocument) -> Any:
        """Return an object exposing ``clone_for_new_document(value)``.

        Prefers the ported :class:`PDFCloneUtility` from the same package
        when available; falls back to a thin shim around
        :meth:`PDDocument._deep_copy_cos` so this module is independently
        usable while the rest of the multipdf cluster lands.
        """
        try:
            from .pdf_clone_utility import PDFCloneUtility

            return PDFCloneUtility(document)
        except Exception:  # noqa: BLE001 — fallback path
            class _DeepCopyCloner:
                def __init__(self, dest: PDDocument) -> None:
                    self._dest = dest

                def clone_for_new_document(self, base: COSBase) -> COSBase:
                    return cast(
                        COSBase,
                        self._dest._deep_copy_cos(base, set()),  # noqa: SLF001
                    )

            return _DeepCopyCloner(document)

    @staticmethod
    def _add_original_content(
        contents: COSBase | None, content_array: COSArray
    ) -> None:
        if contents is None:
            return
        if isinstance(contents, COSStream):
            content_array.add(contents)
            return
        if isinstance(contents, COSArray):
            for entry in contents:
                content_array.add(entry)
            return
        raise OSError(f"Unknown content type: {type(contents).__name__}")

    def _overlay_page(
        self,
        page: PDPage,
        layout_page: _LayoutPage,
        array: COSArray,
        cloner: Any,
    ) -> None:
        resources = page.get_resources()
        if resources is None or not page.get_cos_object().contains_key(_RESOURCES):
            resources = PDResources()
            page.set_resources(resources)
        overlay_form = self._create_overlay_form_x_object(layout_page, cloner)
        # Mirrors upstream's literal ``resources.add(overlayFormXObject, "OL")``
        # — the registered key is allocated under the ``OL`` prefix so it
        # is observable as ``/OL0``, ``/OL1`` … in the page's /XObject
        # subdictionary. Round-trip parity test:
        # ``test_overlay_uses_ol_prefix_for_form_xobject`` exercises this.
        form_id = resources.add(
            COSName.get_pdf_name("XObject"),
            overlay_form.get_cos_object(),
            prefix=_OVERLAY_KEY_PREFIX,
        )
        array.add(self._create_overlay_stream(page, layout_page, form_id))

    def _get_layout_page(
        self, page_number: int, number_of_pages: int
    ) -> _LayoutPage | None:
        if (
            not self._use_all_overlay_pages
            and page_number in self._specific_page_overlay_layout
        ):
            return self._specific_page_overlay_layout[page_number]
        if page_number == 1 and self._first_page_overlay_page is not None:
            return self._first_page_overlay_page
        if (
            page_number == number_of_pages
            and self._last_page_overlay_page is not None
        ):
            return self._last_page_overlay_page
        if page_number % 2 == 1 and self._odd_page_overlay_page is not None:
            return self._odd_page_overlay_page
        if page_number % 2 == 0 and self._even_page_overlay_page is not None:
            return self._even_page_overlay_page
        if self._default_overlay_page is not None:
            layout = self._default_overlay_page
            if self._adjust_rotation:
                # PDFBOX-6049: consider the rotation of the document page.
                assert self._input_pdf is not None
                page = self._input_pdf.get_page(page_number - 1)
                rotation = page.get_rotation()
                if rotation != 0:
                    return self._create_adjusted_layout_page(rotation)
            return layout
        if self._use_all_overlay_pages and self._number_of_overlay_pages > 0:
            use_page_index = (page_number - 1) % self._number_of_overlay_pages
            return self._specific_page_overlay_layout.get(use_page_index)
        return None

    def _create_adjusted_layout_page(self, rotation: int) -> _LayoutPage:
        cached = self._rotated_default_overlay_pages.get(rotation)
        if cached is None:
            assert self._default_overlay_document is not None
            rotated = self._create_layout_page(
                self._default_overlay_document.get_page(0)
            )
            new_rotation = (rotated.overlay_rotation - rotation + 360) % 360
            rotated.overlay_rotation = new_rotation
            self._rotated_default_overlay_pages[rotation] = rotated
            cached = rotated
        return cached

    # ---------- internal: form XObject + stream synthesis ----------

    def _create_overlay_form_x_object(
        self, layout_page: _LayoutPage, cloner: Any
    ) -> PDFormXObject:
        # PDFormXObject expects a stream with /Type /XObject + /Subtype /Form
        # in its dictionary. The cached overlay COSStream was built from raw
        # /Contents bytes — we wrap it directly; PDFormXObject's constructor
        # stamps the Subtype if missing.
        xobj_form = PDFormXObject(layout_page.overlay_cos_stream)
        cloned = cloner.clone_for_new_document(layout_page.overlay_resources)
        if isinstance(cloned, COSDictionary):
            xobj_form.set_resources(PDResources(cloned))
        xobj_form.set_form_type(1)
        # PDFBOX-6048: use the real lower-left corner of the overlay's
        # MediaBox as the /BBox origin via ``create_retranslated_rectangle``
        # (mirrors upstream's ``createRetranslatedRectangle()`` call). The
        # real corner is reflected in the affine transform below (in
        # :meth:`_create_overlay_stream`).
        xobj_form.set_bbox(
            layout_page.overlay_media_box.create_retranslated_rectangle()
        )
        # /Matrix — apply rotation around (0,0) for non-zero overlay rotations.
        matrix = self._rotation_matrix(layout_page)
        xobj_form.set_matrix(matrix)
        return xobj_form

    @staticmethod
    def _rotation_matrix(layout_page: _LayoutPage) -> list[float]:
        """Identity matrix unless the overlay page is rotated. The upstream
        switch maps degrees → quadrant rotations; we precompute the same
        ``[a b c d e f]`` matrix entries directly.

        Rotation conventions match upstream's :class:`AffineTransform`
        with the translate-then-quadrantRotate sequence:

        - 90  → ``[0 -1 1 0 0 W]``  (translate(0, W) then 270° rotate)
        - 180 → ``[-1 0 0 -1 W H]`` (translate(W, H) then 180° rotate)
        - 270 → ``[0 1 -1 0 H 0]``  (translate(H, 0) then 90° rotate)
        """
        rotation = layout_page.overlay_rotation % 360
        w = layout_page.overlay_media_box.get_width()
        h = layout_page.overlay_media_box.get_height()
        if rotation == 90:
            return [0.0, -1.0, 1.0, 0.0, 0.0, w]
        if rotation == 180:
            return [-1.0, 0.0, 0.0, -1.0, w, h]
        if rotation == 270:
            return [0.0, 1.0, -1.0, 0.0, h, 0.0]
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def _create_overlay_stream(
        self,
        page: PDPage,
        layout_page: _LayoutPage,
        x_object_id: COSName,
    ) -> COSStream:
        # Build the small content stream that places the form XObject.
        parts: list[str] = ["q\nq\n"]
        media_box = layout_page.overlay_media_box
        if layout_page.overlay_rotation in (90, 270):
            # Swap the X and Y components of the bounding box for the
            # post-rotation centering math (mirrors the upstream rewrite).
            swapped = PDRectangle(
                media_box.get_lower_left_y(),
                media_box.get_lower_left_x(),
                media_box.get_upper_right_y(),
                media_box.get_upper_right_x(),
            )
            media_box_for_at = swapped
        else:
            media_box_for_at = media_box
        flat_matrix = self._calculate_affine_transform(page, media_box_for_at)
        for v in flat_matrix:
            parts.append(self._float_to_string(v))
            parts.append(" ")
        parts.append(" cm\n /")
        parts.append(x_object_id.get_name())
        parts.append(" Do Q\nQ\n")
        return self._create_stream("".join(parts))

    def calculate_affine_transform(
        self, page: PDPage, overlay_media_box: PDRectangle
    ) -> list[float]:
        """Public hook (mirrors upstream ``calculateAffineTransform``).

        Centers the overlay on the destination page using the **real**
        lower-left corner of the overlay's media box (PDFBOX-6048
        alignment — upstream 3.0.x assumed (0, 0)).

        Returns the 6-element flat affine matrix ``[a b c d tx ty]``.
        """
        return self._calculate_affine_transform(page, overlay_media_box)

    def _calculate_affine_transform(
        self, page: PDPage, overlay_media_box: PDRectangle
    ) -> list[float]:
        page_media_box = page.get_media_box()
        # Real lower-left corners of both boxes — PDFBOX-6048.
        page_llx = page_media_box.get_lower_left_x()
        page_lly = page_media_box.get_lower_left_y()
        overlay_llx = overlay_media_box.get_lower_left_x()
        overlay_lly = overlay_media_box.get_lower_left_y()
        h_shift = (
            (page_media_box.get_width() - overlay_media_box.get_width()) / 2.0
            + page_llx
            - overlay_llx
        )
        v_shift = (
            (page_media_box.get_height() - overlay_media_box.get_height()) / 2.0
            + page_lly
            - overlay_lly
        )
        if _LOG.isEnabledFor(logging.DEBUG):
            _LOG.debug("Overlay position: (%s,%s)", h_shift, v_shift)
        return [1.0, 0.0, 0.0, 1.0, h_shift, v_shift]

    @staticmethod
    def _float_to_string(value: float) -> str:
        """Compact decimal string — strips trailing zeros but keeps ``.0``
        on integer-valued floats. Mirrors upstream's BigDecimal-based
        formatter."""
        # Use repr-style to avoid scientific notation; then prune zeros.
        text = f"{value:.10f}".rstrip("0")
        if text.endswith("."):
            text += "0"
        return text

    def _create_stream(self, content: str) -> COSStream:
        assert self._input_pdf is not None
        scratch = self._input_pdf.get_document().scratch_file
        stream = COSStream(scratch)
        # Match upstream's "compress only when worth it" choice — short
        # marker streams stay unencoded to simplify diagnostics.
        filters: COSName | None = (
            _FLATE_DECODE if len(content) > 20 else None
        )
        with stream.create_output_stream(filters) as out:
            out.write(content.encode("latin-1"))
        return stream

    # ---------- setters ----------

    def set_overlay_position(self, overlay_position: Position) -> None:
        self._position = overlay_position

    def set_input_file(self, input_file: str) -> None:
        self._input_filename = input_file

    def set_input_pdf(self, input_pdf: PDDocument) -> None:
        self._input_pdf = input_pdf

    def get_input_file(self) -> str | None:
        return self._input_filename

    def set_default_overlay_file(self, default_overlay_file: str) -> None:
        self._default_overlay_filename = default_overlay_file

    def set_default_overlay_pdf(self, default_overlay_pdf: PDDocument) -> None:
        self._default_overlay_document = default_overlay_pdf

    def get_default_overlay_file(self) -> str | None:
        return self._default_overlay_filename

    def set_first_page_overlay_file(self, first_page_overlay_file: str) -> None:
        self._first_page_overlay_filename = first_page_overlay_file

    def set_first_page_overlay_pdf(self, first_page_overlay_pdf: PDDocument) -> None:
        self._first_page_overlay_document = first_page_overlay_pdf

    def set_last_page_overlay_file(self, last_page_overlay_file: str) -> None:
        self._last_page_overlay_filename = last_page_overlay_file

    def set_last_page_overlay_pdf(self, last_page_overlay_pdf: PDDocument) -> None:
        self._last_page_overlay_document = last_page_overlay_pdf

    def set_all_pages_overlay_file(self, all_pages_overlay_file: str) -> None:
        self._all_pages_overlay_filename = all_pages_overlay_file

    def set_all_pages_overlay_pdf(self, all_pages_overlay_pdf: PDDocument) -> None:
        self._all_pages_overlay_document = all_pages_overlay_pdf

    def set_odd_page_overlay_file(self, odd_page_overlay_file: str) -> None:
        self._odd_page_overlay_filename = odd_page_overlay_file

    def set_odd_page_overlay_pdf(self, odd_page_overlay_pdf: PDDocument) -> None:
        self._odd_page_overlay_document = odd_page_overlay_pdf

    def set_even_page_overlay_file(self, even_page_overlay_file: str) -> None:
        self._even_page_overlay_filename = even_page_overlay_file

    def set_even_page_overlay_pdf(self, even_page_overlay_pdf: PDDocument) -> None:
        self._even_page_overlay_document = even_page_overlay_pdf

    def set_specific_page_overlay_pdf(
        self, specific_page_overlay_map: Mapping[int, PDDocument]
    ) -> None:
        """Stage per-page overlay :class:`PDDocument` instances. Page numbers
        are 1-based. The first page of each mapped document is used."""
        self._specific_page_overlay_documents = dict(specific_page_overlay_map)

    def set_adjust_rotation(self, adjust_rotation: bool) -> None:
        """When ``True``, the default overlay is rotated to match the input
        page's rotation (PDFBOX-6049). Default ``False``. Only applies to
        the default overlay — specific-page overlays are assumed to have
        been authored with the destination rotation in mind."""
        self._adjust_rotation = bool(adjust_rotation)


__all__ = ["Overlay", "Position"]
