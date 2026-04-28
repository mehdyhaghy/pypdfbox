from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSStream

from ..pd_appearance_content_stream import PDAppearanceContentStream
from ..pd_appearance_dictionary import PDAppearanceDictionary
from ..pd_appearance_stream import PDAppearanceStream
from .pd_appearance_handler import PDAppearanceHandler

if TYPE_CHECKING:
    from ...pd_document import PDDocument
    from ...pd_rectangle import PDRectangle
    from ..pd_annotation import PDAnnotation


_TYPE: COSName = COSName.get_pdf_name("Type")
_X_OBJECT: COSName = COSName.get_pdf_name("XObject")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_FORM: COSName = COSName.get_pdf_name("Form")
_FORM_TYPE: COSName = COSName.get_pdf_name("FormType")
_BBOX: COSName = COSName.get_pdf_name("BBox")


class PDAbstractAppearanceHandler(PDAppearanceHandler):
    """Generic base for annotation appearance handlers. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDAbstractAppearanceHandler``.

    Concrete subclasses implement ``generate_normal_appearance`` (and
    optionally rollover/down). The base provides the appearance-stream
    plumbing (allocate the Form XObject body, ensure ``/AP`` is wired,
    open a writer) plus a few small geometry helpers that get reused
    across handlers.

    Lite scope: ``draw_style`` (line endings), ``CloudyBorder`` and
    ``setOpacity`` (via ``/ExtGState``) are not ported; the lite
    appearance stream surface doesn't yet extend ``PDFormXObject`` (see
    :class:`PDAppearanceStream`) so the upstream ``setGraphicsStateParameters``
    helper would have nowhere to register the GS dictionary. ``CHANGES.md``
    tracks the deviation. Constant opacity is therefore burned into the
    color at write time by the concrete handlers when needed.
    """

    def __init__(
        self,
        annotation: "PDAnnotation",
        document: "PDDocument | None" = None,
    ) -> None:
        self._annotation = annotation
        self._document = document

    # ---------- accessors ----------

    def get_annotation(self) -> "PDAnnotation":
        return self._annotation

    def get_document(self) -> "PDDocument | None":
        return self._document

    def get_rectangle(self) -> "PDRectangle | None":
        return self._annotation.get_rectangle()

    # ---------- appearance allocation ----------

    def create_cos_stream(self) -> COSStream:
        """Allocate a fresh ``COSStream`` for an appearance body. Upstream
        routes through ``PDDocument.getDocument().createCOSStream()`` when
        a document is available so the new stream gets registered with
        the COSDocument; the lite port falls back to a bare ``COSStream``
        when ``document`` is ``None``."""
        if self._document is not None:
            cos_doc = self._document.get_document()
            create = getattr(cos_doc, "create_cos_stream", None)
            if create is not None:
                return create()
        return COSStream()

    def get_appearance(self) -> PDAppearanceDictionary:
        """Return the annotation's ``/AP`` dictionary, creating one if
        absent (and writing it back on the annotation). Mirrors upstream's
        ``getAppearance``."""
        existing = self._annotation.get_appearance_dictionary()
        if existing is not None:
            return existing
        ap = PDAppearanceDictionary()
        self._annotation.set_appearance_dictionary(ap)
        return ap

    def get_normal_appearance_stream(self) -> PDAppearanceStream:
        """Return the (single-stream) ``/AP /N`` appearance, creating a
        fresh one when ``/N`` is absent or is a state subdictionary.

        The returned stream has ``/Type /XObject /Subtype /Form
        /FormType 1 /BBox <annotation rect>`` set so it is a valid Form
        XObject even before the lite-scope ``PDAppearanceStream`` grows
        full ``PDFormXObject`` support.
        """
        ap = self.get_appearance()
        entry = ap.get_normal_appearance()
        if entry is not None and entry.is_stream():
            stream = entry.get_appearance_stream()
            assert stream is not None
            return stream
        # Either /N is absent or it's a state subdictionary — replace it
        # with a fresh single-stream appearance.
        cos_stream = self.create_cos_stream()
        cos_stream.set_item(_TYPE, _X_OBJECT)
        cos_stream.set_item(_SUBTYPE, _FORM)
        cos_stream.set_int(_FORM_TYPE, 1)
        rect = self.get_rectangle()
        if rect is not None:
            cos_stream.set_item(_BBOX, rect.to_cos_array())
        appearance_stream = PDAppearanceStream(cos_stream)
        ap.set_normal_appearance(appearance_stream)
        return appearance_stream

    def get_normal_appearance_as_content_stream(
        self, compress: bool = False
    ) -> PDAppearanceContentStream:
        """Open a writer over the ``/AP /N`` appearance stream. Caller is
        responsible for ``close()`` (use ``with``)."""
        appearance = self.get_normal_appearance_stream()
        return PDAppearanceContentStream(appearance, compress=compress)

    # ---------- geometry helpers ----------

    @staticmethod
    def get_padded_rectangle(
        rectangle: "PDRectangle", padding: float
    ) -> "PDRectangle":
        from ...pd_rectangle import PDRectangle

        return PDRectangle(
            rectangle.get_lower_left_x() + padding,
            rectangle.get_lower_left_y() + padding,
            rectangle.get_width() - 2 * padding,
            rectangle.get_height() - 2 * padding,
        )

    @staticmethod
    def add_rect_differences(
        rectangle: "PDRectangle", differences: list[float] | None
    ) -> "PDRectangle":
        if differences is None or len(differences) != 4:
            return rectangle
        from ...pd_rectangle import PDRectangle

        return PDRectangle(
            rectangle.get_lower_left_x() - differences[0],
            rectangle.get_lower_left_y() - differences[1],
            rectangle.get_width() + differences[0] + differences[2],
            rectangle.get_height() + differences[1] + differences[3],
        )

    @staticmethod
    def apply_rect_differences(
        rectangle: "PDRectangle", differences: list[float] | None
    ) -> "PDRectangle":
        if differences is None or len(differences) != 4:
            return rectangle
        from ...pd_rectangle import PDRectangle

        return PDRectangle(
            rectangle.get_lower_left_x() + differences[0],
            rectangle.get_lower_left_y() + differences[1],
            rectangle.get_width() - differences[0] - differences[2],
            rectangle.get_height() - differences[1] - differences[3],
        )

    # ---------- color helper ----------

    @staticmethod
    def _color_components_from_annotation(
        annotation: "PDAnnotation",
    ) -> list[float] | None:
        """Read /C off the annotation as raw float components. Returns
        ``None`` when /C is absent or empty."""
        color = annotation.get_color()
        if color is None or color.size() == 0:
            return None
        return color.to_float_array()

    @staticmethod
    def _components_to_rgb(components: list[float]) -> tuple[float, float, float]:
        """Best-effort conversion of /C components to RGB. The annotation
        ``/C`` array uses DeviceGray (1), DeviceRGB (3), or DeviceCMYK (4)
        per PDF 32000-1:2008 §12.5.3."""
        if len(components) == 1:
            g = max(0.0, min(1.0, float(components[0])))
            return (g, g, g)
        if len(components) >= 3 and len(components) != 4:
            return (
                max(0.0, min(1.0, float(components[0]))),
                max(0.0, min(1.0, float(components[1]))),
                max(0.0, min(1.0, float(components[2]))),
            )
        if len(components) == 4:
            c, m, y, k = (float(v) for v in components[:4])
            r = (1.0 - c) * (1.0 - k)
            g = (1.0 - m) * (1.0 - k)
            b = (1.0 - y) * (1.0 - k)
            return (
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
            )
        return (0.0, 0.0, 0.0)

    # ---------- default no-ops ----------

    def generate_normal_appearance(self) -> None:  # pragma: no cover - abstract default
        return None

    def generate_rollover_appearance(self) -> None:
        # Most upstream subclasses no-op rollover.
        return None

    def generate_down_appearance(self) -> None:
        # Most upstream subclasses no-op down.
        return None


__all__ = ["PDAbstractAppearanceHandler"]
