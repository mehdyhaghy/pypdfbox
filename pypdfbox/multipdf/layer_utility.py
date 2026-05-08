from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

from .pdf_clone_utility import PDFCloneUtility

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_LOG = logging.getLogger(__name__)

_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]
_OC: COSName = COSName.get_pdf_name("OC")
_FLATE_DECODE: COSName = COSName.FLATE_DECODE  # type: ignore[attr-defined]
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_XOBJECT: COSName = COSName.get_pdf_name("XObject")

# Page-dict keys carried over to the form-XObject dict. Mirrors upstream's
# private ``PAGE_TO_FORM_FILTER`` set in ``LayerUtility``.
_PAGE_TO_FORM_FILTER: frozenset[str] = frozenset(
    {"Group", "LastModified", "Metadata"}
)


class LayerUtility:
    """Helpers to import pages as Form XObjects and arrange them as
    Optional Content Group (OCG) layers. Mirrors
    ``org.apache.pdfbox.multipdf.LayerUtility``.

    Should be used only on loaded documents — generated documents may
    contain unfinished parts (font subsetting, partial resource trees).

    Constructor takes the *target* :class:`PDDocument` (the one that
    receives the imported form XObjects + new layers); the import side
    accepts a separate source :class:`PDDocument`.
    """

    def __init__(self, target_doc: PDDocument) -> None:
        self._target_doc = target_doc
        self._cloner = PDFCloneUtility(target_doc)

    # ---------- accessors ----------

    def get_document(self) -> PDDocument:
        """Return the target ``PDDocument`` this utility writes into."""
        return self._target_doc

    # ---------- save/restore wrap ----------

    def wrap_in_save_restore(self, page: PDPage) -> None:
        """Wrap the page's existing ``/Contents`` in a ``q`` / ``Q`` pair so
        appended content runs in a controlled graphics state.

        Some applications emit page content without a leading save/restore
        pair, which can leak coordinate-system transformations into anything
        appended afterwards. Bracketing fixes that.
        """
        scratch = self._target_doc.get_document().scratch_file
        save_stream = COSStream(scratch)
        save_stream.set_raw_data(b"q\n")
        restore_stream = COSStream(scratch)
        restore_stream.set_raw_data(b"Q\n")

        page_dict = page.get_cos_object()
        contents = page_dict.get_dictionary_object(_CONTENTS)
        if isinstance(contents, COSStream):
            arr = COSArray()
            arr.add(save_stream)
            arr.add(contents)
            arr.add(restore_stream)
            page_dict.set_item(_CONTENTS, arr)
        elif isinstance(contents, COSArray):
            contents.add_at(0, save_stream)
            contents.add(restore_stream)
        else:
            raise OSError(
                f"Contents are unknown type: {type(contents).__name__}"
            )

    # ---------- form-import surface ----------

    def import_page_as_form(
        self, source_doc: PDDocument, page_or_index: PDPage | int
    ) -> PDFormXObject:
        """Import a page from ``source_doc`` as a :class:`PDFormXObject` so
        it can be placed (e.g. as an overlay) on a page in the target
        document. Mirrors upstream's two ``importPageAsForm`` overloads.

        You may want to call :meth:`wrap_in_save_restore` on the target
        page before invoking the form so the graphics state stays sane.
        """
        if isinstance(page_or_index, int):
            page = source_doc.get_page(page_or_index)
        elif isinstance(page_or_index, PDPage):
            page = page_or_index
        else:
            raise TypeError(
                "import_page_as_form expects a PDPage or int; got "
                f"{type(page_or_index).__name__}"
            )

        # Best-effort propagate hidden-layer config from the source doc to
        # the target's /OCProperties so visibility round-trips. Quietly
        # no-ops when the source has no /OCProperties.
        self._import_oc_properties(source_doc)

        # Build the form-body stream by re-encoding the source page's
        # decoded contents through /FlateDecode. Mirrors upstream's
        # ``new PDStream(targetDoc, page.getContents(), COSName.FLATE_DECODE)``
        # which feeds the InputStream through the filter chain at write.
        new_stream = PDStream(self._target_doc)
        with new_stream.create_output_stream(_FLATE_DECODE) as out:
            out.write(page.get_contents())
        form = PDFormXObject(new_stream.get_cos_object())

        # Clone the page's /Resources into a fresh dict for the form.
        page_resources = page.get_resources()
        form_resources = PDResources()
        self._cloner.clone_merge(page_resources, form_resources)
        form.set_resources(form_resources)

        # Carry over the small set of page-level dict entries upstream
        # transfers to the form XObject (Group, LastModified, Metadata).
        self._transfer_dict(
            page.get_cos_object(), form.get_cos_object(), _PAGE_TO_FORM_FILTER
        )

        # Compose the form's /Matrix from the page's existing matrix +
        # crop/media box offsets + rotation. Upstream uses java.awt's
        # AffineTransform; we operate directly on the 6-tuple form.
        matrix = form.get_matrix()
        media_box = page.get_media_box()
        crop_box = page.get_crop_box()
        view_box = crop_box if crop_box is not None else media_box
        rotation = page.get_rotation()

        # Translate so the form's origin matches the page's media-box
        # origin offset relative to the view box.
        matrix = _at_translate(
            matrix,
            media_box.get_lower_left_x() - view_box.get_lower_left_x(),
            media_box.get_lower_left_y() - view_box.get_lower_left_y(),
        )

        # Apply page rotation. Upstream uses quadrant rotates; we expand
        # them inline as cm-equivalent operations.
        vw = view_box.get_width()
        vh = view_box.get_height()
        if rotation == 90:
            matrix = _at_scale(matrix, vw / vh, vh / vw)
            matrix = _at_translate(matrix, 0.0, vw)
            matrix = _at_quadrant_rotate(matrix, 3)
        elif rotation == 180:
            matrix = _at_translate(matrix, vw, vh)
            matrix = _at_quadrant_rotate(matrix, 2)
        elif rotation == 270:
            matrix = _at_scale(matrix, vw / vh, vh / vw)
            matrix = _at_translate(matrix, vh, 0.0)
            matrix = _at_quadrant_rotate(matrix, 1)
        # Compensate for crop boxes not starting at 0,0.
        matrix = _at_translate(
            matrix,
            -view_box.get_lower_left_x(),
            -view_box.get_lower_left_y(),
        )
        if not _is_identity(matrix):
            form.set_matrix(matrix)

        # /BBox = the view box.
        form.set_b_box(
            PDRectangle(
                view_box.get_lower_left_x(),
                view_box.get_lower_left_y(),
                view_box.get_upper_right_x(),
                view_box.get_upper_right_y(),
            )
        )
        return form

    # ---------- layer placement ----------

    def append_form_as_layer(
        self,
        target_page: PDPage,
        form: PDFormXObject,
        transform: tuple[float, float, float, float, float, float]
        | list[float]
        | None,
        layer_name: str,
    ) -> PDOptionalContentGroup:
        """Place ``form`` over the existing content of ``target_page``
        wrapped in a marked-content section tied to a fresh OCG.

        Returns the new :class:`PDOptionalContentGroup` so callers can
        toggle its visibility through
        :class:`PDOptionalContentProperties`.

        ``transform`` is the affine matrix that controls the form's
        placement. Pass ``None`` (or the identity) to drop the form at
        the page origin. You'll typically need a non-identity transform
        when the page has a crop box that differs from its media box, or
        when scaling/positioning the overlay.

        You may want to call :meth:`wrap_in_save_restore` on the target
        page first so the graphics state is reset before the layer paints.
        """
        catalog = self._target_doc.get_document_catalog()
        oc_props = catalog.get_oc_properties()
        if oc_props is None:
            oc_props = PDOptionalContentProperties()
            catalog.set_oc_properties(oc_props)
        if oc_props.has_group(layer_name):
            raise ValueError(
                f"Optional group (layer) already exists: {layer_name}"
            )
        self._target_doc.set_version(1.5)

        # PDFBOX-4044: warn when an identity transform is paired with a
        # negative-cropbox page — the form will paint off-canvas.
        crop_box = target_page.get_crop_box()
        if (
            crop_box.get_lower_left_x() < 0 or crop_box.get_lower_left_y() < 0
        ) and _is_identity(transform):
            _LOG.warning(
                "Negative cropBox %s and identity transform may make your "
                "form invisible",
                crop_box,
            )

        layer = PDOptionalContentGroup(layer_name)
        oc_props.add_group(layer)

        a, b, c, d, e, f = _coerce_matrix(transform)
        with PDPageContentStream(
            self._target_doc,
            target_page,
            append_mode=AppendMode.APPEND,
            compress=False,
        ) as content_stream:
            content_stream.begin_marked_content_with_dict(_OC, layer)
            content_stream.save_graphics_state()
            content_stream.transform(a, b, c, d, e, f)
            content_stream.draw_form(form)
            content_stream.restore_graphics_state()
            content_stream.end_marked_content()

        return layer

    # ---------- resource-name allocation helpers ----------

    def create_overlay_x_object(
        self,
        page: PDPage,
        form: PDFormXObject,
        desired_name: str | None = None,
    ) -> COSName:
        """Register ``form`` as a Form XObject on ``page``'s resources and
        return the allocated resource name.

        When ``desired_name`` is omitted (the typical path), allocation
        falls through to :meth:`PDResources.add_x_object` which mirrors
        upstream ``createKey`` and picks ``Form0``/``Form1``/… — guaranteed
        unique within the page's ``/XObject`` subdictionary.

        When ``desired_name`` is supplied the call fails fast if the name
        is already registered on the page, mirroring upstream's behaviour
        of letting the caller specify a stable resource key for the
        overlay (handy when emitting deterministic output).
        """
        # ``PDPage.get_resources`` returns a *fresh* PDResources wrapper
        # around an unattached empty dict when /Resources is missing — so
        # we must materialise + reattach it so subsequent writes persist
        # on the page. Mirrors what upstream callers tend to do manually.
        page_dict = page.get_cos_object()
        resources_cos = page_dict.get_dictionary_object(_RESOURCES)
        if not isinstance(resources_cos, COSDictionary):
            resources_cos = COSDictionary()
            page_dict.set_item(_RESOURCES, resources_cos)
        resources = PDResources(resources_cos)

        if desired_name is None:
            return resources.add_x_object(form)
        if self.name_already_used(page, desired_name):
            raise ValueError(
                f"XObject name already used on page resources: {desired_name}"
            )
        # Manual placement under the requested key, bypassing the
        # auto-allocator. Upstream's LayerUtility doesn't expose this
        # path directly but we keep it on the helper surface for callers
        # that need stable names (e.g. deterministic regression PDFs).
        key = COSName.get_pdf_name(desired_name)
        x_object_dict = resources_cos.get_dictionary_object(_XOBJECT)
        if not isinstance(x_object_dict, COSDictionary):
            x_object_dict = COSDictionary()
            resources_cos.set_item(_XOBJECT, x_object_dict)
        x_object_dict.set_item(key, form.get_cos_object())
        return key

    @staticmethod
    def name_already_used(page: PDPage, name: str) -> bool:
        """Return ``True`` when ``name`` is already registered as an
        ``/XObject`` resource on ``page``. Used by callers who want to
        guard a custom :meth:`create_overlay_x_object` allocation.
        """
        page_dict = page.get_cos_object()
        resources_cos = page_dict.get_dictionary_object(_RESOURCES)
        if not isinstance(resources_cos, COSDictionary):
            return False
        x_object_dict = resources_cos.get_dictionary_object(_XOBJECT)
        if not isinstance(x_object_dict, COSDictionary):
            return False
        return x_object_dict.contains_key(COSName.get_pdf_name(name))

    # ---------- internal helpers ----------

    def _transfer_dict(
        self,
        org_dict: COSDictionary,
        target_dict: COSDictionary,
        keys: frozenset[str],
    ) -> None:
        for key, value in list(org_dict.entry_set()):
            if key.name in keys:
                cloned = self._cloner.clone_for_new_document(value)
                if cloned is not None:
                    target_dict.set_item(key, cloned)

    def _import_oc_properties(self, src_doc: PDDocument) -> None:
        """Copy ``/OCProperties`` from ``src_doc`` into the target catalog
        so hidden layers stay hidden after import. No-op when the source
        has no ``/OCProperties``."""
        src_catalog = src_doc.get_document_catalog()
        src_oc = src_catalog.get_oc_properties()
        if src_oc is None:
            return
        dst_catalog = self._target_doc.get_document_catalog()
        dst_oc = dst_catalog.get_oc_properties()
        if dst_oc is None:
            cloned = self._cloner.clone_for_new_document(src_oc.get_cos_object())
            if isinstance(cloned, COSDictionary):
                dst_catalog.set_oc_properties(PDOptionalContentProperties(cloned))
            return
        self._cloner.clone_merge(src_oc, dst_oc)


# ----------------------------------------------------------------------
# 6-tuple affine-transform helpers
#
# Upstream uses java.awt.geom.AffineTransform whose method names map
# 1:1 onto these helpers. We keep the math in float precision and treat
# the 6-tuple as the row-major form ``[a b c d e f]`` matching PDF's
# /Matrix entry — i.e. the matrix
#
#     | a  b  0 |
#     | c  d  0 |
#     | e  f  1 |
#
# applied as ``new = M * current`` (post-multiply, identical to
# AffineTransform.translate / scale / rotate semantics).
# ----------------------------------------------------------------------


def _at_translate(
    m: list[float], tx: float, ty: float
) -> list[float]:
    a, b, c, d, e, f = m
    return [a, b, c, d, e + a * tx + c * ty, f + b * tx + d * ty]


def _at_scale(m: list[float], sx: float, sy: float) -> list[float]:
    a, b, c, d, e, f = m
    return [a * sx, b * sx, c * sy, d * sy, e, f]


def _at_quadrant_rotate(m: list[float], n: int) -> list[float]:
    """Rotate by ``n * 90`` degrees counter-clockwise. Mirrors
    ``AffineTransform.quadrantRotate(int)`` — exact integer math, no
    float drift from sin/cos near 0/1.

    Note: PDFBox's switch picks ``quadrantRotate(3)`` for a 90deg page
    rotation, ``quadrantRotate(2)`` for 180deg, and ``quadrantRotate(1)``
    for 270deg. The values below mirror those quarter rotations exactly.
    """
    n = n % 4
    a, b, c, d, e, f = m
    if n == 0:
        return [a, b, c, d, e, f]
    if n == 1:
        # rotate 90 CCW: (a,b,c,d) -> (c,d,-a,-b)
        return [c, d, -a, -b, e, f]
    if n == 2:
        # rotate 180: (a,b,c,d) -> (-a,-b,-c,-d)
        return [-a, -b, -c, -d, e, f]
    # n == 3: rotate 270 CCW (== 90 CW): (a,b,c,d) -> (-c,-d,a,b)
    return [-c, -d, a, b, e, f]


def _is_identity(
    m: tuple[float, float, float, float, float, float]
    | list[float]
    | None,
) -> bool:
    if m is None:
        return True
    a, b, c, d, e, f = list(m)
    return (
        a == 1.0
        and b == 0.0
        and c == 0.0
        and d == 1.0
        and e == 0.0
        and f == 0.0
    )


def _coerce_matrix(
    transform: tuple[float, ...] | list[float] | None,
) -> list[float]:
    """Normalise a caller-supplied transform argument to a 6-float list.

    ``None`` → identity. Anything else must be a 6-element sequence.
    """
    if transform is None:
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    seq = list(transform)
    if len(seq) != 6:
        raise ValueError(
            f"transform expects exactly 6 numbers (a b c d e f); got {len(seq)}"
        )
    return [float(v) for v in seq]


__all__ = ["LayerUtility"]
