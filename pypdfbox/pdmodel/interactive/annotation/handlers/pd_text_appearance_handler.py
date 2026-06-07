from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pypdfbox.cos import COSName
from pypdfbox.util.matrix import Matrix

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ....pd_rectangle import PDRectangle
    from ..pd_annotation import PDAnnotation
    from ..pd_annotation_text import PDAnnotationText
    from ..pd_appearance_content_stream import PDAppearanceContentStream


_SUPPORTED_NAMES = frozenset(
    {
        "Note",
        "Insert",
        "Cross",
        "Help",
        "Circle",
        "Paragraph",
        "NewParagraph",
        "Check",
        "Star",
        "RightArrow",
        "RightPointer",
        "CrossHairs",
        "UpArrow",
        "UpLeftArrow",
        "Comment",
        "Key",
    }
)


# ---------------------------------------------------------------------------
# Standard-14 glyph outlines used by drawHelp / drawParagraph / drawNewParagraph.
#
# Upstream extracts these via ``Standard14Fonts.getGlyphPath(fontName, glyph)``
# and walks the resulting ``GeneralPath`` with ``addPath``. pypdfbox has not
# ported Standard14 glyph-path extraction, so we embed the exact upstream glyph
# outlines (canonical to 3 decimals — matching the operand precision Apache
# PDFBox emits) as pre-flattened ``(op, coords)`` paths. Quadratic segments are
# already cubic in the source outlines. Coordinates are in the font's 1000-unit
# em; the draw helpers apply the upstream scale/translate ``cm`` before emitting.
# ---------------------------------------------------------------------------

_GLYPH_QUESTION: list[tuple[str, tuple[float, ...]]] = [
    ("M", (778, 544)),
    ("C", (770, 518.667, 765.667, 479.333, 765, 426)),
    ("L", (495, 426)),
    ("C", (499, 538.667, 509.667, 616.333, 527, 659)),
    ("C", (544.333, 702.333, 589, 752, 661, 808)),
    ("L", (734, 865)),
    ("C", (758, 883, 777.333, 902.667, 792, 924)),
    ("C", (818.667, 960.667, 832, 1001, 832, 1045)),
    ("C", (832, 1095.667, 817.333, 1141.667, 788, 1183)),
    ("C", (758, 1225, 703.667, 1246, 625, 1246)),
    ("C", (547.667, 1246, 493, 1220.333, 461, 1169)),
    ("C", (428.333, 1117.667, 412, 1064.333, 412, 1009)),
    ("L", (123, 1009)),
    ("C", (131, 1199, 197.333, 1333.667, 322, 1413)),
    ("C", (400.667, 1463.667, 497.333, 1489, 612, 1489)),
    ("C", (762.667, 1489, 887.667, 1453, 987, 1381)),
    ("C", (1087, 1309, 1137, 1202.333, 1137, 1061)),
    ("C", (1137, 974.333, 1115.333, 901.333, 1072, 842)),
    ("C", (1046.667, 806, 998, 760, 926, 704)),
    ("L", (855, 649)),
    ("C", (816.333, 619, 790.667, 584, 778, 544)),
    ("H", ()),
    ("M", (786, 0)),
    ("L", (488, 0)),
    ("L", (488, 289)),
    ("L", (786, 289)),
    ("L", (786, 0)),
    ("H", ()),
]

_GLYPH_PARAGRAPH: list[tuple[str, tuple[float, ...]]] = [
    ("M", (940, -363)),
    ("L", (793, -363)),
    ("L", (793, 1353)),
    ("L", (562, 1353)),
    ("L", (562, -363)),
    ("L", (415, -363)),
    ("L", (415, 526)),
    ("C", (273, 528, 166.667, 577.333, 96, 674)),
    ("C", (24.667, 771.333, -11, 878.333, -11, 995)),
    ("C", (-11, 1093.667, 13, 1181.667, 61, 1259)),
    ("C", (147.667, 1399, 290.333, 1469, 489, 1469)),
    ("L", (1065, 1469)),
    ("L", (1065, 1353)),
    ("L", (940, 1353)),
    ("L", (940, -363)),
    ("H", ()),
]

_GLYPH_N: list[tuple[str, tuple[float, ...]]] = [
    ("M", (1348, 0)),
    ("L", (1040, 0)),
    ("L", (438, 1047)),
    ("L", (438, 0)),
    ("L", (151, 0)),
    ("L", (151, 1474)),
    ("L", (474, 1474)),
    ("L", (1061, 445)),
    ("L", (1061, 1474)),
    ("L", (1348, 1474)),
    ("L", (1348, 0)),
    ("H", ()),
]

_GLYPH_P: list[tuple[str, tuple[float, ...]]] = [
    ("M", (782, 530)),
    ("L", (469, 530)),
    ("L", (469, 0)),
    ("L", (163, 0)),
    ("L", (163, 1474)),
    ("L", (805, 1474)),
    ("C", (953, 1474, 1071, 1436, 1159, 1360)),
    ("C", (1247, 1284, 1291, 1166.333, 1291, 1007)),
    ("C", (1291, 833, 1247, 710, 1159, 638)),
    ("C", (1071, 566, 945.333, 530, 782, 530)),
    ("H", ()),
    ("M", (926, 837)),
    ("C", (966, 872.333, 986, 928.333, 986, 1005)),
    ("C", (986, 1081.667, 966, 1136.333, 926, 1169)),
    ("C", (885.333, 1201.667, 828.667, 1218, 756, 1218)),
    ("L", (469, 1218)),
    ("L", (469, 784)),
    ("L", (756, 784)),
    ("C", (828.667, 784, 885.333, 801.667, 926, 837)),
    ("H", ()),
]

# ---------------------------------------------------------------------------
# ZapfDingbats / Symbol glyph outlines used by drawZapf / drawCrossHairs.
#
# Upstream extracts these via ``Standard14Fonts.getGlyphPath(fontName, glyph)``
# (ZapfDingbats for Cross/Star/Check/RightPointer, Symbol for CrossHairs) and
# walks the resulting ``GeneralPath`` with ``addPath``. pypdfbox has not ported
# Standard14 glyph-path extraction, so we embed the exact upstream glyph
# outlines as pre-flattened ``(op, coords)`` paths. Coordinates are in the
# font's own units (ZapfDingbats / Symbol use a 1/2048 em fontMatrix); the draw
# helpers apply the upstream fontMatrix-derived scale/translate ``cm`` before
# emitting. All operands are canonical to 3 decimals — matching what Apache
# PDFBox 3.0.7 emits when it flattens these paths.
# ---------------------------------------------------------------------------

# ZapfDingbats "a22" — ✖ heavy multiplication X (Cross icon).
_GLYPH_ZAPF_CROSS: list[tuple[str, tuple[float, ...]]] = [
    ("M", (1493, 344)),
    ("L", (1149, 0)),
    ("L", (778, 371)),
    ("L", (408, 0)),
    ("L", (63, 344)),
    ("L", (434, 715)),
    ("L", (63, 1083)),
    ("L", (410, 1430)),
    ("L", (778, 1061)),
    ("L", (1147, 1430)),
    ("L", (1493, 1083)),
    ("L", (1122, 715)),
    ("L", (1493, 344)),
    ("H", ()),
]

# ZapfDingbats "a35" — ★ black star (Star icon).
_GLYPH_ZAPF_STAR: list[tuple[str, tuple[float, ...]]] = [
    ("M", (1606, 883)),
    ("L", (1130, 537)),
    ("L", (1313, -25)),
    ("L", (836, 322)),
    ("L", (358, -25)),
    ("L", (541, 537)),
    ("L", (66, 883)),
    ("L", (653, 883)),
    ("L", (836, 1442)),
    ("L", (1018, 883)),
    ("L", (1606, 883)),
    ("H", ()),
]

# ZapfDingbats "a20" — ✔ heavy check mark (Check icon).
_GLYPH_ZAPF_CHECK: list[tuple[str, tuple[float, ...]]] = [
    ("M", (1663, 1300)),
    ("C", (1663, 1222, 1627.667, 1146, 1557, 1072)),
    ("L", (1546, 1061)),
    ("L", (928, 410)),
    ("C", (796.667, 272, 685, 165.333, 593, 90)),
    ("C", (500.333, 14.667, 435, -23, 397, -23)),
    ("C", (357, -23, 307.333, -4.333, 248, 33)),
    ("C", (188.667, 71, 150.333, 110, 133, 150)),
    ("C", (118.333, 183.333, 104.667, 254, 92, 362)),
    ("C", (78.667, 470, 72, 587, 72, 713)),
    ("C", (72, 781.667, 100.667, 845, 158, 903)),
    ("C", (215.333, 961.667, 278.667, 991, 348, 991)),
    ("C", (414, 991, 453.333, 930.667, 466, 810)),
    ("C", (467.333, 796, 468.333, 785.667, 469, 779)),
    ("C", (479.667, 686.333, 492, 621.667, 506, 585)),
    ("C", (520, 548.333, 539, 530, 563, 530)),
    ("C", (573, 530, 591.667, 540.667, 619, 562)),
    ("C", (646.333, 584, 679, 613.667, 717, 651)),
    ("L", (1352, 1280)),
    ("C", (1405.333, 1333.333, 1453, 1373.667, 1495, 1401)),
    ("C", (1537, 1428.333, 1572.667, 1442, 1602, 1442)),
    ("C", (1624, 1442, 1639.667, 1433.667, 1649, 1417)),
    ("C", (1658.333, 1400.333, 1663, 1372.333, 1663, 1333)),
    ("L", (1663, 1300)),
    ("H", ()),
]

# ZapfDingbats "a174" — ➤ three-d top-lighted rightwards arrowhead
# (RightPointer icon).
_GLYPH_ZAPF_RIGHT_POINTER: list[tuple[str, tuple[float, ...]]] = [
    ("M", (1806, 709)),
    ("L", (72, 8)),
    ("L", (492, 709)),
    ("L", (72, 1409)),
    ("L", (1806, 709)),
    ("H", ()),
]

# Symbol "circleplus" — ⊕ circled plus (CrossHairs icon).
_GLYPH_SYMBOL_CIRCLE_PLUS: list[tuple[str, tuple[float, ...]]] = [
    ("M", (731, 555)),
    ("L", (309, 555)),
    ("L", (309, 668)),
    ("L", (731, 668)),
    ("L", (731, 1087)),
    ("L", (844, 1087)),
    ("L", (844, 668)),
    ("L", (1264, 668)),
    ("L", (1264, 555)),
    ("L", (844, 555)),
    ("L", (844, 135)),
    ("L", (731, 135)),
    ("L", (731, 555)),
    ("H", ()),
    ("M", (786, 1266)),
    ("C", (697.333, 1266, 613.333, 1249.667, 534, 1217)),
    ("C", (454, 1183.667, 383.333, 1135.667, 322, 1073)),
    ("C", (261.333, 1012.333, 214.667, 942.333, 182, 863)),
    ("C", (149.333, 783, 133, 698.667, 133, 610)),
    ("C", (133, 537.333, 144, 467.667, 166, 401)),
    ("C", (188.667, 334.333, 222, 272.333, 266, 215)),
    ("C", (328.667, 133, 405.667, 69.333, 497, 24)),
    ("C", (588.333, -22, 684.667, -45, 786, -45)),
    ("C", (872.667, -45, 956.333, -28.333, 1037, 5)),
    ("C", (1117.667, 39, 1189, 87.333, 1251, 150)),
    ("C", (1312.333, 211.333, 1359.333, 281.667, 1392, 361)),
    ("C", (1425.333, 440.333, 1442, 523.333, 1442, 610)),
    ("C", (1442, 697.333, 1425.333, 780.667, 1392, 860)),
    ("C", (1358.667, 940, 1311, 1011, 1249, 1073)),
    ("C", (1187, 1135, 1116.333, 1182.667, 1037, 1216)),
    ("C", (957.667, 1249.333, 874, 1266, 786, 1266)),
    ("H", ()),
    ("M", (37, 610)),
    ("C", (37, 709.333, 56, 805, 94, 897)),
    ("C", (132, 989.667, 186, 1071, 256, 1141)),
    ("C", (326.667, 1212.333, 407, 1266.667, 497, 1304)),
    ("C", (587.667, 1341.333, 684, 1360, 786, 1360)),
    ("C", (869.333, 1360, 950, 1347, 1028, 1321)),
    ("C", (1106, 1294.333, 1177.667, 1256, 1243, 1206)),
    ("C", (1336.333, 1134.667, 1408.333, 1047, 1459, 943)),
    ("C", (1510.333, 839, 1536, 728, 1536, 610)),
    ("C", (1536, 527.333, 1523, 447.333, 1497, 370)),
    ("C", (1471, 292.667, 1432.667, 221.333, 1382, 156)),
    ("C", (1310, 62, 1222, -10.667, 1118, -62)),
    ("C", (1014, -113.333, 903.333, -139, 786, -139)),
    ("C", (686.667, -139, 591.333, -120, 500, -82)),
    ("C", (408.667, -44, 327.333, 10.667, 256, 82)),
    ("C", (185.333, 152.667, 131.333, 233.333, 94, 324)),
    ("C", (56, 415.333, 37, 510.667, 37, 610)),
    ("H", ()),
]

# ZapfDingbats / Symbol shared fontMatrix scale (1/2048 — a TrueType-derived
# em, the value Apache PDFBox reads from the Standard-14 font's fontMatrix).
_ZAPF_FONT_MATRIX_SCALE = 0.00048828125


def _apply_matrix(cs: PDAppearanceContentStream, matrix: Matrix) -> None:
    """Emit the ``cm`` operator with the six components of ``matrix``.

    Required because the runtime ``PDAppearanceContentStream.transform``
    method (inherited from :class:`PDPageContentStream`) takes six
    explicit floats, not a :class:`Matrix` instance — whereas upstream's
    Java equivalent accepts the Matrix directly.
    """
    cs.transform(
        matrix.get_scale_x(),
        matrix.get_shear_y(),
        matrix.get_shear_x(),
        matrix.get_scale_y(),
        matrix.get_translate_x(),
        matrix.get_translate_y(),
    )


def _apply_translucent_white_fill(cs: PDAppearanceContentStream) -> None:
    """Helper that paints a translucent white "halo" via an ext-gstate.

    Used by drawCircles / drawHelp / drawParagraph / drawRightArrow to
    paint the inner circle background with 60% alpha. Mirrors the
    inline ``PDExtendedGraphicsState`` setup in upstream's draw helpers.
    """
    # Import lazily to avoid a circular dependency at module import.
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    gs = PDExtendedGraphicsState()
    gs.set_alpha_source_flag(False)
    gs.set_stroking_alpha_constant(0.6)
    gs.set_non_stroking_alpha_constant(0.6)
    gs.set_blend_mode(BlendMode.NORMAL)
    cs.set_graphics_state_parameters(gs)


class PDTextAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a text (sticky-note) annotation.
    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDTextAppearanceHandler``.

    Each ``/Name`` value (``Note``, ``Help``, ``Insert``, etc.) dispatches
    to a private ``_draw_*`` helper that emits a small icon path
    (~20-300 content-stream operators). The implementations are direct
    line-by-line ports of the upstream Java drawing code. Glyph-based
    icons (``Cross``, ``Star``, ``Check``, ``RightPointer``,
    ``CrossHairs``, ``Help``, ``Paragraph``, ``NewParagraph``) embed the
    exact upstream Standard-14 glyph outlines (since
    :class:`Standard14Fonts` glyph-path extraction is not yet ported) and
    drive them through :meth:`add_path` under the upstream fontMatrix
    scale — byte-identical to Apache PDFBox. See ``CHANGES.md``.
    """

    SUPPORTED_NAMES: frozenset[str] = _SUPPORTED_NAMES

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        """Mirrors upstream ``generateNormalAppearance``
        (PDTextAppearanceHandler.java:82)."""
        from ..pd_annotation_text import PDAnnotationText

        annotation = self.get_annotation()
        if not isinstance(annotation, PDAnnotationText):
            return
        name = annotation.get_name()
        if name not in _SUPPORTED_NAMES:
            return
        with self.get_normal_appearance_as_content_stream() as cs:
            bg_components = self._color_components_from_annotation(annotation)
            if bg_components is None:
                # White when /C is absent (PDTextAppearanceHandler.java:96):
                # upstream calls setNonStrokingColor(1f) → the gray shorthand
                # ``1 g``. A one-element list routes to that same shorthand.
                cs.set_non_stroking_color([1.0])
            else:
                # Upstream passes the full PDColor to setNonStrokingColor, which
                # emits ``/DeviceRGB cs r g b sc`` (colour-space + ``cs`` +
                # components + ``sc``), never the device shorthand ``rg``/``g``/
                # ``k``. Wrap the raw /C components so the operand stream matches.
                cs.set_non_stroking_color(
                    self._pd_color_from_components(bg_components)
                )
            # Stroking color stays the PDF default (black).
            self.set_opacity(cs, annotation.get_constant_opacity())
            dispatch = {
                PDAnnotationText.NAME_NOTE: self._draw_note,
                PDAnnotationText.NAME_CROSS: self._draw_cross,
                PDAnnotationText.NAME_CIRCLE: self._draw_circles,
                PDAnnotationText.NAME_INSERT: self._draw_insert,
                PDAnnotationText.NAME_HELP: self._draw_help,
                PDAnnotationText.NAME_PARAGRAPH: self._draw_paragraph,
                PDAnnotationText.NAME_NEW_PARAGRAPH: self._draw_new_paragraph,
                PDAnnotationText.NAME_STAR: self._draw_star,
                PDAnnotationText.NAME_CHECK: self._draw_check,
                PDAnnotationText.NAME_RIGHT_ARROW: self._draw_right_arrow,
                PDAnnotationText.NAME_RIGHT_POINTER: self._draw_right_pointer,
                PDAnnotationText.NAME_CROSS_HAIRS: self._draw_cross_hairs,
                PDAnnotationText.NAME_UP_ARROW: self._draw_up_arrow,
                PDAnnotationText.NAME_UP_LEFT_ARROW: self._draw_up_left_arrow,
                PDAnnotationText.NAME_COMMENT: self._draw_comment,
                PDAnnotationText.NAME_KEY: self._draw_key,
            }
            painter = dispatch.get(name)
            if painter is not None:  # pragma: no branch - _SUPPORTED_NAMES mirrors dispatch keys
                painter(annotation, cs)

    # ------------------------------------------------------------------
    # bbox / rectangle adjustment helper
    # ------------------------------------------------------------------

    def _adjust_rect_and_bbox(
        self, annotation: PDAnnotationText, width: float, height: float
    ) -> PDRectangle:
        """Mirrors upstream's private ``adjustRectAndBBox``
        (PDTextAppearanceHandler.java:166)."""
        from ....pd_rectangle import PDRectangle

        rect = self.get_rectangle()
        if rect is not None and not annotation.is_no_zoom():
            rect.set_upper_right_x(rect.get_lower_left_x() + width)
            rect.set_lower_left_y(rect.get_upper_right_y() - height)
            annotation.set_rectangle(rect)
        if not annotation.get_cos_object().contains_key(COSName.get_pdf_name("F")):
            # Mirror Adobe — set NoRotate + NoZoom when /F is absent.
            # pypdfbox's renderer does not honour these flags, but the
            # flags are still written so the file is byte-similar.
            annotation.set_no_rotate(True)
            annotation.set_no_zoom(True)
        bbox = PDRectangle.from_width_height(width, height)
        normal_stream = annotation.get_normal_appearance_stream()
        if normal_stream is not None:
            normal_stream.set_bbox(bbox)
        return bbox

    # ------------------------------------------------------------------
    # public parity surface — mirrors upstream's private helpers under
    # their upstream snake_case names so the parity script counts them.
    # ------------------------------------------------------------------

    def adjust_rect_and_b_box(
        self, annotation: PDAnnotationText, width: float, height: float
    ) -> PDRectangle:
        """Mirrors upstream's ``adjustRectAndBBox``
        (PDTextAppearanceHandler.java:166)."""
        return self._adjust_rect_and_bbox(annotation, width, height)

    def add_path(
        self,
        cs: PDAppearanceContentStream,
        path: list[tuple[str, tuple[float, ...]]],
    ) -> None:
        """Mirrors upstream's private ``addPath``
        (PDTextAppearanceHandler.java:617).

        Upstream walks a ``java.awt.geom.GeneralPath`` via a
        ``PathIterator`` and emits ``m`` / ``l`` / ``c`` / ``h`` content
        stream operators per segment. We accept a pre-flattened list of
        ``(operator, coords)`` tuples — quadratic Beziers must already
        be converted to cubic. Operators: ``"M"`` move, ``"L"`` line,
        ``"C"`` cubic (6 coords), ``"H"`` close.
        """
        for op, coords in path:
            if op == "M":
                cs.move_to(coords[0], coords[1])
            elif op == "L":
                cs.line_to(coords[0], coords[1])
            elif op == "C":
                cs.curve_to(
                    coords[0],
                    coords[1],
                    coords[2],
                    coords[3],
                    coords[4],
                    coords[5],
                )
            elif op == "H":
                cs.close_path()

    def draw_note(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawNote``
        (PDTextAppearanceHandler.java:194)."""
        self._draw_note(annotation, cs)

    def draw_circles(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawCircles``
        (PDTextAppearanceHandler.java:228)."""
        self._draw_circles(annotation, cs)

    def draw_insert(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawInsert``
        (PDTextAppearanceHandler.java:262)."""
        self._draw_insert(annotation, cs)

    def draw_cross_hairs(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawCrossHairs``
        (PDTextAppearanceHandler.java:295)."""
        self._draw_cross_hairs(annotation, cs)

    def draw_help(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawHelp``
        (PDTextAppearanceHandler.java:336)."""
        self._draw_help(annotation, cs)

    def draw_comment(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawComment``
        (PDTextAppearanceHandler.java:380)."""
        self._draw_comment(annotation, cs)

    def draw_key(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawKey``
        (PDTextAppearanceHandler.java:441)."""
        self._draw_key(annotation, cs)

    def draw_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawParagraph``
        (PDTextAppearanceHandler.java:487)."""
        self._draw_paragraph(annotation, cs)

    def draw_new_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawNewParagraph``
        (PDTextAppearanceHandler.java:535)."""
        self._draw_new_paragraph(annotation, cs)

    def draw_right_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawRightArrow``
        (PDTextAppearanceHandler.java:560)."""
        self._draw_right_arrow(annotation, cs)

    def draw_up_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawUpArrow``
        (PDTextAppearanceHandler.java:576)."""
        self._draw_up_arrow(annotation, cs)

    def draw_up_left_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream's ``drawUpLeftArrow``
        (PDTextAppearanceHandler.java:584)."""
        self._draw_up_left_arrow(annotation, cs)

    def draw_zapf(
        self,
        annotation: PDAnnotationText,
        cs: PDAppearanceContentStream,
        by: float,
        ty: float,
        glyph_name: str,
    ) -> None:
        """Mirrors upstream's private ``drawZapf``
        (PDTextAppearanceHandler.java:592)."""
        self._draw_zapf(annotation, cs, by, ty, glyph_name)

    # ------------------------------------------------------------------
    # glyph painters
    # ------------------------------------------------------------------

    def _draw_note(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawNote`` (PDTextAppearanceHandler.java:194).
        The Note glyph is the spec default (a notebook icon)."""
        bbox = self._adjust_rect_and_bbox(annotation, 18.0, 20.0)
        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.61)  # value from Adobe
        width = bbox.get_width()
        height = bbox.get_height()
        cs.add_rect(1.0, 1.0, width - 2.0, height - 2.0)
        for k in (2, 3, 4, 5):
            cs.move_to(width / 4, height / 7 * k)
            cs.line_to(width * 3 / 4 - 1.0, height / 7 * k)
        cs.fill_and_stroke()

    def _draw_circles(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawCircles`` (PDTextAppearanceHandler.java:228).
        Two overlapping circles painted via Bezier curves."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)

        small_r = 6.36
        large_r = 9.756

        # adjustments because the bottom of the circle is flat
        _apply_matrix(cs, Matrix.get_scale_instance(0.95, 0.95))
        _apply_matrix(cs, Matrix.get_translate_instance(0.0, 0.5))

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        width = bbox.get_width() / 2
        height = bbox.get_height() / 2
        self.draw_circle(cs, width, height, small_r)
        cs.fill()
        cs.restore_graphics_state()

        cs.set_line_width(0.59)  # value from Adobe
        self.draw_circle(cs, width, height, small_r)
        self.draw_circle2(cs, width, height, large_r)
        cs.fill_and_stroke()

    def _draw_insert(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawInsert`` (PDTextAppearanceHandler.java:262).
        Caret-style downward triangle."""
        bbox = self._adjust_rect_and_bbox(annotation, 17.0, 20.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(0)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe
        cs.move_to(bbox.get_width() / 2 - 1.0, bbox.get_height() - 2.0)
        cs.line_to(1.0, 1.0)
        cs.line_to(bbox.get_width() - 2.0, 1.0)
        cs.close_and_fill_and_stroke()

    def _draw_cross(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 19, 0, "a22")``
        (PDTextAppearanceHandler.java:111). Renders a thick X."""
        self._draw_zapf(annotation, cs, 19.0, 0.0, "a22")

    def _draw_help(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawHelp`` (PDTextAppearanceHandler.java:280).
        Circle with the Helvetica-Bold ``question`` glyph centered inside."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill()
        cs.restore_graphics_state()

        # Helvetica-Bold "question" glyph path, scaled into the circle.
        cs.save_graphics_state()
        _apply_matrix(
            cs,
            Matrix.get_scale_instance(
                0.001 * min_dim / 2.25, 0.001 * min_dim / 2.25
            ),
        )
        _apply_matrix(cs, Matrix.get_translate_instance(500.0, 375.0))
        self.add_path(cs, _GLYPH_QUESTION)
        cs.restore_graphics_state()

        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill_and_stroke()

    def _draw_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawParagraph`` (PDTextAppearanceHandler.java:320).
        Helvetica ``paragraph`` (pilcrow) glyph centered in a circle."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill()
        cs.restore_graphics_state()

        # Helvetica "paragraph" glyph path, scaled into the circle.
        cs.save_graphics_state()
        _apply_matrix(
            cs,
            Matrix.get_scale_instance(
                0.001 * min_dim / 3.0, 0.001 * min_dim / 3.0
            ),
        )
        _apply_matrix(cs, Matrix.get_translate_instance(850.0, 900.0))
        self.add_path(cs, _GLYPH_PARAGRAPH)
        cs.restore_graphics_state()
        cs.fill_and_stroke()

        self.draw_circle(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.stroke()

    def _draw_new_paragraph(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawNewParagraph`` (PDTextAppearanceHandler.java:362).
        Triangle marker above the Helvetica-Bold ``N`` / ``P`` glyph pair."""
        self._adjust_rect_and_bbox(annotation, 13.0, 20.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(0)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        # Small triangle — exact coordinates from Adobe (upstream lines 374-376).
        cs.move_to(6.4995, 20.0)
        cs.line_to(0.295, 7.287)
        cs.line_to(12.705, 7.287)
        cs.close_and_fill_and_stroke()

        # Helvetica-Bold "N" then "P" glyph paths, scaled and translated.
        _apply_matrix(cs, Matrix.get_scale_instance(0.004, 0.004))
        _apply_matrix(cs, Matrix.get_translate_instance(200.0, 0.0))
        self.add_path(cs, _GLYPH_N)
        _apply_matrix(cs, Matrix.get_translate_instance(1300.0, 0.0))
        self.add_path(cs, _GLYPH_P)
        cs.fill()

    def _draw_star(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 19, 0, "a35")``
        (PDTextAppearanceHandler.java:129)."""
        self._draw_zapf(annotation, cs, 19.0, 0.0, "a35")

    def _draw_check(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 19, 50, "a20")``
        (PDTextAppearanceHandler.java:132)."""
        self._draw_zapf(annotation, cs, 19.0, 50.0, "a20")

    def _draw_right_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawRightArrow`` (PDTextAppearanceHandler.java:458).
        Right-pointing arrow inside a circle."""
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        self.draw_circle2(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill()
        cs.restore_graphics_state()

        cs.save_graphics_state()
        cs.move_to(8.0, 17.5)
        cs.line_to(8.0, 13.5)
        cs.line_to(3.0, 13.5)
        cs.line_to(3.0, 6.5)
        cs.line_to(8.0, 6.5)
        cs.line_to(8.0, 2.5)
        cs.line_to(18.0, 10.0)
        cs.close_path()
        cs.restore_graphics_state()
        # surprisingly, this one not counterclockwise.
        self.draw_circle(cs, min_dim / 2, min_dim / 2, min_dim / 2 - 1.0)
        cs.fill_and_stroke()

    def _draw_right_pointer(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawZapf(... 17, 50, "a174")``
        (PDTextAppearanceHandler.java:138)."""
        self._draw_zapf(annotation, cs, 17.0, 50.0, "a174")

    def _draw_cross_hairs(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawCrossHairs`` (PDTextAppearanceHandler.java:390).

        Upstream draws the ``circleplus`` glyph from the Symbol Type1 font
        via ``Standard14Fonts.getGlyphPath`` and walks it with ``addPath``.
        pypdfbox has not ported Standard14 glyph-path extraction, so we
        drive the exact pre-flattened Symbol glyph outline through
        :meth:`add_path` under the upstream fontMatrix-derived
        scale/translate ``cm`` — byte-identical to Apache PDFBox 3.0.7.
        """
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, 20.0)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(0)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.61)  # value from Adobe

        # Upstream computes the scale via the Symbol fontMatrix
        # (1/2048, 1/2048) multiplied by 1.3333.
        scale = _ZAPF_FONT_MATRIX_SCALE * min_dim * 1.3333
        _apply_matrix(cs, Matrix.get_scale_instance(scale, scale))
        _apply_matrix(cs, Matrix.get_translate_instance(0.0, 50.0))
        self.add_path(cs, _GLYPH_SYMBOL_CIRCLE_PLUS)
        cs.fill_and_stroke()

    def _draw_up_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawUpArrow`` (PDTextAppearanceHandler.java:416).
        Upward-pointing chunky arrow."""
        self._adjust_rect_and_bbox(annotation, 17.0, 20.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        cs.move_to(1.0, 7.0)
        cs.line_to(5.0, 7.0)
        cs.line_to(5.0, 1.0)
        cs.line_to(12.0, 1.0)
        cs.line_to(12.0, 7.0)
        cs.line_to(16.0, 7.0)
        cs.line_to(8.5, 19.0)
        cs.close_and_fill_and_stroke()

    def _draw_up_left_arrow(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawUpLeftArrow`` (PDTextAppearanceHandler.java:436).
        Same shape as the up arrow rotated 45° counter-clockwise."""
        self._adjust_rect_and_bbox(annotation, 17.0, 17.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        _apply_matrix(cs, Matrix.get_rotate_instance(math.radians(45.0), 8.0, -4.0))

        cs.move_to(1.0, 7.0)
        cs.line_to(5.0, 7.0)
        cs.line_to(5.0, 1.0)
        cs.line_to(12.0, 1.0)
        cs.line_to(12.0, 7.0)
        cs.line_to(16.0, 7.0)
        cs.line_to(8.5, 19.0)
        cs.close_and_fill_and_stroke()

    def _draw_comment(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawComment`` (PDTextAppearanceHandler.java:499).
        Speech bubble icon — gathered from Font Awesome's ``comment.svg``."""
        self._adjust_rect_and_bbox(annotation, 18.0, 18.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(200.0)

        # Adobe first fills a white rectangle with CA ca 0.6, so do we.
        cs.save_graphics_state()
        cs.set_line_width(1.0)
        _apply_translucent_white_fill(cs)
        cs.set_non_stroking_color([1.0])
        cs.add_rect(0.3, 0.3, 18.0 - 0.6, 18.0 - 0.6)
        cs.fill()
        cs.restore_graphics_state()

        _apply_matrix(cs, Matrix.get_scale_instance(0.003, 0.003))
        _apply_matrix(cs, Matrix.get_translate_instance(500.0, -300.0))

        # Outer shape gathered from Font Awesome's comment.svg.
        cs.move_to(2549.0, 5269.0)
        cs.curve_to(1307.0, 5269.0, 300.0, 4451.0, 300.0, 3441.0)
        cs.curve_to(300.0, 3023.0, 474.0, 2640.0, 764.0, 2331.0)
        cs.curve_to(633.0, 1985.0, 361.0, 1691.0, 357.0, 1688.0)
        cs.curve_to(299.0, 1626.0, 283.0, 1537.0, 316.0, 1459.0)
        cs.curve_to(350.0, 1382.0, 426.0, 1332.0, 510.0, 1332.0)
        cs.curve_to(1051.0, 1332.0, 1477.0, 1558.0, 1733.0, 1739.0)
        cs.curve_to(1987.0, 1659.0, 2261.0, 1613.0, 2549.0, 1613.0)
        cs.curve_to(3792.0, 1613.0, 4799.0, 2431.0, 4799.0, 3441.0)
        cs.curve_to(4799.0, 4451.0, 3792.0, 5269.0, 2549.0, 5269.0)
        cs.close_path()

        # Donut effect — can't use addRect, see upstream comment.
        cs.move_to(0.3 / 0.003 - 500.0, 0.3 / 0.003 + 300.0)
        cs.line_to(0.3 / 0.003 - 500.0, 0.3 / 0.003 + 300.0 + 17.4 / 0.003)
        cs.line_to(
            0.3 / 0.003 - 500.0 + 17.4 / 0.003,
            0.3 / 0.003 + 300.0 + 17.4 / 0.003,
        )
        cs.line_to(0.3 / 0.003 - 500.0 + 17.4 / 0.003, 0.3 / 0.003 + 300.0)

        cs.close_and_fill_and_stroke()

    def _draw_key(
        self, annotation: PDAnnotationText, cs: PDAppearanceContentStream
    ) -> None:
        """Mirrors upstream ``drawKey`` (PDTextAppearanceHandler.java:549).
        Key icon — gathered from Font Awesome's ``key.svg``."""
        self._adjust_rect_and_bbox(annotation, 13.0, 18.0)

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(200.0)

        _apply_matrix(cs, Matrix.get_scale_instance(0.003, 0.003))
        _apply_matrix(cs, Matrix.get_rotate_instance(math.radians(45.0), 2500.0, -800.0))

        # Shape from Font Awesome's key.svg.
        cs.move_to(4799.0, 4004.0)
        cs.curve_to(4799.0, 3149.0, 4107.0, 2457.0, 3253.0, 2457.0)
        cs.curve_to(3154.0, 2457.0, 3058.0, 2466.0, 2964.0, 2484.0)
        cs.line_to(2753.0, 2246.0)
        cs.curve_to(2713.0, 2201.0, 2656.0, 2175.0, 2595.0, 2175.0)
        cs.line_to(2268.0, 2175.0)
        cs.line_to(2268.0, 1824.0)
        cs.curve_to(2268.0, 1707.0, 2174.0, 1613.0, 2057.0, 1613.0)
        cs.line_to(1706.0, 1613.0)
        cs.line_to(1706.0, 1261.0)
        cs.curve_to(1706.0, 1145.0, 1611.0, 1050.0, 1495.0, 1050.0)
        cs.line_to(510.0, 1050.0)
        cs.curve_to(394.0, 1050.0, 300.0, 1145.0, 300.0, 1261.0)
        cs.line_to(300.0, 1947.0)
        cs.curve_to(300.0, 2003.0, 322.0, 2057.0, 361.0, 2097.0)
        cs.line_to(1783.0, 3519.0)
        cs.curve_to(1733.0, 3671.0, 1706.0, 3834.0, 1706.0, 4004.0)
        cs.curve_to(1706.0, 4858.0, 2398.0, 5550.0, 3253.0, 5550.0)
        cs.curve_to(4109.0, 5550.0, 4799.0, 4860.0, 4799.0, 4004.0)
        cs.close_path()
        cs.move_to(3253.0, 4425.0)
        cs.curve_to(3253.0, 4192.0, 3441.0, 4004.0, 3674.0, 4004.0)
        cs.curve_to(3907.0, 4004.0, 4096.0, 4192.0, 4096.0, 4425.0)
        cs.curve_to(4096.0, 4658.0, 3907.0, 4847.0, 3674.0, 4847.0)
        cs.curve_to(3441.0, 4847.0, 3253.0, 4658.0, 3253.0, 4425.0)
        cs.fill_and_stroke()

    def _draw_zapf(
        self,
        annotation: PDAnnotationText,
        cs: PDAppearanceContentStream,
        by: float,
        ty: float,
        glyph_name: str,
    ) -> None:
        """Mirrors upstream's private ``drawZapf``
        (PDTextAppearanceHandler.java:592).

        Upstream extracts the named glyph path from the ZapfDingbats Type1
        font via ``Standard14Fonts.getGlyphPath`` and walks it with
        ``addPath``. pypdfbox has not ported Standard14 glyph-path
        extraction, so we drive the exact pre-flattened upstream glyph
        outline through :meth:`add_path` under the upstream fontMatrix-derived
        scale/translate ``cm`` — byte-identical to Apache PDFBox 3.0.7.
        """
        bbox = self._adjust_rect_and_bbox(annotation, 20.0, by)
        min_dim = min(bbox.get_width(), bbox.get_height())

        cs.set_miter_limit(4.0)
        cs.set_line_join_style(1)
        cs.set_line_cap_style(0)
        cs.set_line_width(0.59)  # value from Adobe

        # Upstream computes the scale via the ZapfDingbats fontMatrix
        # (1/2048, 1/2048) divided by 0.8.
        scale = _ZAPF_FONT_MATRIX_SCALE * min_dim / 0.8
        _apply_matrix(cs, Matrix.get_scale_instance(scale, scale))
        _apply_matrix(cs, Matrix.get_translate_instance(0.0, ty))

        glyph = {
            "a22": _GLYPH_ZAPF_CROSS,
            "a35": _GLYPH_ZAPF_STAR,
            "a20": _GLYPH_ZAPF_CHECK,
            "a174": _GLYPH_ZAPF_RIGHT_POINTER,
        }[glyph_name]
        self.add_path(cs, glyph)
        cs.fill_and_stroke()

    def generate_rollover_appearance(self) -> None:
        # No rollover appearance (PDTextAppearanceHandler.java:670)
        return None

    def generate_down_appearance(self) -> None:
        # No down appearance (PDTextAppearanceHandler.java:676)
        return None


__all__ = ["PDTextAppearanceHandler"]
