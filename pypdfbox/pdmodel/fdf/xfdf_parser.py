"""XFDF (XML Forms Data Format) ingest helpers.

Mirrors the XFDF parsing scaffolding spread across upstream
``org.apache.pdfbox.pdmodel.fdf`` — specifically the ``Element``-taking
constructors of ``FDFCatalog``, ``FDFDictionary``, ``FDFField`` and
``FDFAnnotation``. Upstream uses ``org.w3c.dom`` directly; pypdfbox
delegates to :class:`pypdfbox.util.xml_util.XMLUtil`, which returns a
:mod:`xml.dom.minidom` document, so the walkers here consume minidom
``Element`` nodes.

The annotation factory dispatches by XFDF tag name (``text``, ``caret``,
``freetext``, ``fileattachment``, ``circle``, ``square``, ``polygon``,
``polyline``, ``line``, ``ink``, ``stamp``, ``highlight``, ``underline``,
``strikeout``, ``squiggly``) — matching the switch table in
``FDFDictionary.FDFDictionary(Element)`` (Java lines 137-217).
"""

from __future__ import annotations

import contextlib
import logging
from xml.dom.minidom import Element, Node

from pypdfbox.cos import COSArray, COSString
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)

from .fdf_annotation import FDFAnnotation
from .fdf_field import FDFField

logger = logging.getLogger(__name__)


def _child_elements(parent: Element) -> list[Element]:
    """Return direct ``Element`` children of ``parent`` (ignoring text /
    comment nodes). Mirrors the ``instanceof Element`` filter used by
    upstream ``FDFDictionary.FDFDictionary(Element)``.
    """
    out: list[Element] = []
    for child in parent.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            out.append(child)  # type: ignore[arg-type]
    return out


def _node_text(node: Element) -> str:
    """Return the concatenated text-node children of ``node``.

    Mirrors upstream ``XMLUtil.getNodeValue(Element)`` — used to extract
    the inner text of ``<value>`` and ``<value-richtext>`` elements.
    """
    parts: list[str] = []
    for child in node.childNodes:
        if child.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
            parts.append(child.nodeValue or "")
    return "".join(parts)


def populate_field_from_xfdf(field: FDFField, element: Element) -> None:
    """Populate ``field`` from an XFDF ``<field>`` element.

    Mirrors upstream ``FDFField.FDFField(Element)`` (Java lines 75-108):

    - ``name`` attribute → ``setPartialFieldName``
    - ``<value>`` child → ``setValue``
    - ``<value-richtext>`` child → ``setRichText`` (as ``COSString``)
    - nested ``<field>`` children → ``setKids`` (recursive)
    """
    name = element.getAttribute("name") or ""
    field.set_partial_field_name(name)

    kids: list[FDFField] = []
    for child in _child_elements(element):
        tag = child.tagName
        if tag == "value":
            field.set_value(_node_text(child))
        elif tag == "value-richtext":
            field.set_rich_text(COSString(_node_text(child)))
        elif tag == "field":
            kid = FDFField()
            populate_field_from_xfdf(kid, child)
            kids.append(kid)
    if kids:
        field.set_kids(kids)


def build_annotation_from_xfdf(element: Element) -> FDFAnnotation | None:
    """Build an :class:`FDFAnnotation` subclass from an XFDF annotation
    element. The element tag selects the subtype; ``None`` is returned
    for unknown / unsupported tags.

    Mirrors the switch table in ``FDFDictionary.FDFDictionary(Element)``
    (Java lines 150-207). Subtype-specific initialisation (vertices,
    fringe, callout, …) is delegated to the matching ``init_*`` helpers
    on the subclass (added in prior waves specifically so the XFDF
    pipeline could wire them in here).
    """
    # Locally import the concrete subclasses so this module doesn't form
    # an import cycle through the ``__init__`` re-exports.
    from .fdf_annotation_caret import FDFAnnotationCaret
    from .fdf_annotation_circle import FDFAnnotationCircle
    from .fdf_annotation_file_attachment import FDFAnnotationFileAttachment
    from .fdf_annotation_free_text import FDFAnnotationFreeText
    from .fdf_annotation_ink import FDFAnnotationInk
    from .fdf_annotation_line import FDFAnnotationLine
    from .fdf_annotation_polygon import FDFAnnotationPolygon
    from .fdf_annotation_polyline import FDFAnnotationPolyline
    from .fdf_annotation_square import FDFAnnotationSquare
    from .fdf_annotation_stamp import FDFAnnotationStamp
    from .fdf_annotation_text import FDFAnnotationText
    from .fdf_annotation_text_markup import FDFAnnotationTextMarkup

    tag = element.tagName
    annot: FDFAnnotation
    if tag == "text":
        annot = FDFAnnotationText()
    elif tag == "caret":
        annot = FDFAnnotationCaret()
    elif tag == "freetext":
        annot = FDFAnnotationFreeText()
    elif tag == "fileattachment":
        annot = FDFAnnotationFileAttachment()
    elif tag == "circle":
        annot = FDFAnnotationCircle()
    elif tag == "square":
        annot = FDFAnnotationSquare()
    elif tag == "polygon":
        annot = FDFAnnotationPolygon()
    elif tag == "polyline":
        annot = FDFAnnotationPolyline()
    elif tag == "line":
        annot = FDFAnnotationLine()
    elif tag == "ink":
        annot = FDFAnnotationInk()
    elif tag == "stamp":
        annot = FDFAnnotationStamp()
    elif tag in ("highlight", "underline", "strikeout", "squiggly"):
        annot = FDFAnnotationTextMarkup()
        # Upstream sets the /Subtype via subclass constructors; map the
        # tag name to the canonical PDF subtype here.
        annot.set_subtype(
            {
                "highlight": "Highlight",
                "underline": "Underline",
                "strikeout": "StrikeOut",
                "squiggly": "Squiggly",
            }[tag]
        )
    else:
        logger.warning("Unknown or unsupported XFDF annotation type %r", tag)
        return None

    _populate_annotation_base(annot, element)
    _populate_annotation_subtype(annot, element)
    return annot


def _populate_annotation_base(annot: FDFAnnotation, element: Element) -> None:
    """Apply the attributes shared by every FDF annotation (page, rect,
    color, flags, name, title, subject, creation date, opacity,
    contents, contents-richtext).

    Mirrors the body of ``FDFAnnotation.FDFAnnotation(Element)`` (Java
    lines 130-308) — kept lenient: missing optional attributes are
    skipped silently instead of raising, so a partial XFDF still
    round-trips through ingest.
    """
    page = element.getAttribute("page")
    if page:
        try:
            annot.set_page(int(page))
        except ValueError:
            logger.warning("XFDF annotation has non-integer 'page' %r", page)

    color = element.getAttribute("color")
    if color and len(color) == 7 and color[0] == "#":
        try:
            cv = int(color[1:7], 16)
            r = ((cv >> 16) & 0xFF) / 255.0
            g = ((cv >> 8) & 0xFF) / 255.0
            b = (cv & 0xFF) / 255.0
            annot.set_color((r, g, b))
        except ValueError:
            pass

    date = element.getAttribute("date")
    if date:
        annot.set_date(date)

    flags = element.getAttribute("flags")
    if flags:
        flag_map = {
            "invisible": annot.set_invisible,
            "hidden": annot.set_hidden,
            "print": annot.set_printed,
            "nozoom": annot.set_no_zoom,
            "norotate": annot.set_no_rotate,
            "noview": annot.set_no_view,
            "readonly": annot.set_read_only,
            "locked": annot.set_locked,
            "togglenoview": annot.set_toggle_no_view,
        }
        for token in flags.split(","):
            token = token.strip()
            setter = flag_map.get(token)
            if setter is not None:
                setter(True)

    name_attr = element.getAttribute("name")
    if name_attr:
        annot.set_name(name_attr)

    rect = element.getAttribute("rect")
    if rect:
        try:
            values = annot.parse_rectangle_attributes(
                rect, "Error: wrong amount of numbers in attribute 'rect'"
            )
            annot.set_rectangle(
                (values[0], values[1], values[2], values[3])
            )
        except OSError:
            pass

    title = element.getAttribute("title")
    if title:
        annot.set_title(title)

    creation_date = element.getAttribute("creationdate")
    if creation_date:
        annot.set_creation_date(creation_date)

    opacity = element.getAttribute("opacity")
    if opacity:
        with contextlib.suppress(ValueError):
            annot.set_opacity(float(opacity))

    subject = element.getAttribute("subject")
    if subject:
        annot.set_subject(subject)

    intent = element.getAttribute("intent")
    if not intent:
        # qoppa/Adobe accept the all-caps spelling; mirror upstream.
        intent = element.getAttribute("IT")
    if intent:
        annot.set_intent(intent)

    # contents (plain text child element)
    for child in _child_elements(element):
        if child.tagName == "contents":
            annot.set_contents(_node_text(child))
        elif child.tagName == "contents-richtext":
            inner = FDFAnnotation.rich_contents_to_string(child, root=True)
            annot.set_rich_contents(inner)
            # Upstream also stamps plain /Contents with the stripped text.
            annot.set_contents(_node_text(child).strip())


def _populate_annotation_subtype(annot: FDFAnnotation, element: Element) -> None:
    """Apply subtype-specific XFDF attributes by delegating to the
    ``init_*`` helpers already on each annotation subclass.

    The helpers were added in prior waves (1273, 1278, 1281) specifically
    so this ingest path could wire them in without duplicating the
    parsing logic.
    """
    # Polygon / polyline: ``vertices`` attribute.
    init_vertices = getattr(annot, "init_vertices", None)
    if callable(init_vertices):
        vertices = element.getAttribute("vertices")
        if vertices:
            with contextlib.suppress(OSError):
                init_vertices(vertices)

    # Polyline + Line: ``head`` / ``tail`` / ``interior-color`` via init_styles.
    init_styles = getattr(annot, "init_styles", None)
    if callable(init_styles):
        head = element.getAttribute("head") or None
        tail = element.getAttribute("tail") or None
        ic = element.getAttribute("interior-color") or None
        if head or tail or ic:
            init_styles(head=head, tail=tail, interior_color=ic)

    # Caret / Circle / Square / FreeText: ``fringe`` attribute.
    init_fringe = getattr(annot, "init_fringe", None)
    if callable(init_fringe):
        fringe = element.getAttribute("fringe")
        if fringe:
            with contextlib.suppress(OSError):
                init_fringe(fringe)

    # FreeText: ``callout`` attribute.
    init_callout = getattr(annot, "init_callout", None)
    if callable(init_callout):
        callout = element.getAttribute("callout")
        if callout:
            with contextlib.suppress(OSError):
                init_callout(callout)


def populate_fdf_dictionary_from_xfdf(fdf_dict: object, element: Element) -> None:
    """Populate an :class:`FDFDictionary` from an XFDF ``<xfdf>`` element.

    Mirrors ``FDFDictionary.FDFDictionary(Element)`` (Java lines 74-223):
    walks the immediate ``<f>``, ``<ids>``, ``<fields>``, and ``<annots>``
    children and populates the matching dictionary entries.

    The ``fdf_dict`` parameter is typed as ``object`` to avoid an import
    cycle through :mod:`pypdfbox.pdmodel.fdf.fdf_dictionary`; callers
    pass a real :class:`FDFDictionary`.
    """
    # Local import to keep this module free of an import cycle.
    from .fdf_dictionary import FDFDictionary

    assert isinstance(fdf_dict, FDFDictionary)
    for child in _child_elements(element):
        tag = child.tagName
        if tag == "f":
            fs = PDSimpleFileSpecification()
            fs.set_file(child.getAttribute("href"))
            fdf_dict.set_file(fs)
        elif tag == "ids":
            ids = COSArray()
            original = child.getAttribute("original")
            modified = child.getAttribute("modified")
            try:
                if original:
                    ids.add(COSString.parse_hex(original))
            except (OSError, ValueError):
                logger.warning(
                    "Error parsing ID entry for attribute 'original' [%s]. "
                    "ID entry ignored.",
                    original,
                )
            try:
                if modified:
                    ids.add(COSString.parse_hex(modified))
            except (OSError, ValueError):
                logger.warning(
                    "Error parsing ID entry for attribute 'modified' [%s]. "
                    "ID entry ignored.",
                    modified,
                )
            if len(ids) > 0:
                fdf_dict.set_id(ids)
        elif tag == "fields":
            field_list: list[FDFField] = []
            for f in _child_elements(child):
                if f.tagName == "field":
                    fdf_field = FDFField()
                    try:
                        populate_field_from_xfdf(fdf_field, f)
                        field_list.append(fdf_field)
                    except OSError as exc:
                        logger.warning(
                            "Error parsing field entry. Field ignored. (%s)", exc
                        )
            fdf_dict.set_fields(field_list)
        elif tag == "annots":
            annot_list: list[FDFAnnotation] = []
            for a in _child_elements(child):
                try:
                    built = build_annotation_from_xfdf(a)
                    if built is not None:
                        annot_list.append(built)
                except OSError as exc:
                    logger.warning(
                        "Error parsing annotation %r. Annotation ignored. (%s)",
                        a.tagName,
                        exc,
                    )
            fdf_dict.set_annotations(annot_list)


__all__ = [
    "build_annotation_from_xfdf",
    "populate_fdf_dictionary_from_xfdf",
    "populate_field_from_xfdf",
]
