from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNumber, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent

from .pdf_text_stripper import PDFTextStripper, _TextState
from .text_position import TextPosition

if TYPE_CHECKING:
    from pypdfbox.cos import COSBase
    from pypdfbox.pdmodel import PDPage


class PDFMarkedContentExtractor(PDFTextStripper):
    """Stream engine that extracts marked-content sequences and groups
    text by their containing BMC/BDC tag. Mirrors
    ``org.apache.pdfbox.text.PDFMarkedContentExtractor``.

    Walks the page's content stream tokens, tracking BMC/BDC/EMC
    nesting, and bucketing every emitted :class:`TextPosition` into the
    currently open :class:`PDMarkedContent`. Top-level sequences are
    accumulated in :meth:`get_marked_contents`; nested sequences are
    attached to their parent via :meth:`PDMarkedContent.add_marked_content`.

    Optionally suppresses duplicate overlapping text (same character
    rendered at the same coordinates with a tolerance derived from the
    glyph width) — used by Word-style fake-bold output.
    """

    def __init__(self, encoding: str | None = None) -> None:
        super().__init__()
        del encoding  # upstream applies encoding-specific output conversion;
        # pypdfbox decodes via /ToUnicode + /Differences, so the parameter
        # is accepted for API parity but unused.
        self._suppress_duplicate_overlapping_text: bool = True
        self._marked_contents: list[PDMarkedContent] = []
        self._current_marked_contents: deque[PDMarkedContent] = deque()
        self._character_list_mapping: dict[str, list[TextPosition]] = {}

    # ---------- configuration accessors ----------

    def is_suppress_duplicate_overlapping_text(self) -> bool:
        return self._suppress_duplicate_overlapping_text

    def set_suppress_duplicate_overlapping_text(self, value: bool) -> None:
        self._suppress_duplicate_overlapping_text = bool(value)

    # ---------- marked-content callbacks ----------

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        marked_content = PDMarkedContent.create(tag, properties)
        if not self._current_marked_contents:
            self._marked_contents.append(marked_content)
        else:
            current = self._current_marked_contents[-1]
            if current is not None:
                current.add_marked_content(marked_content)
        self._current_marked_contents.append(marked_content)

    def end_marked_content_sequence(self) -> None:
        if self._current_marked_contents:
            self._current_marked_contents.pop()

    def marked_content_point(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        # Upstream comment: "Nothing happens here yet. If you know
        # anything useful that should happen, please tell us."
        del tag, properties

    def xobject(self, xobject: Any) -> None:
        if self._current_marked_contents:
            self._current_marked_contents[-1].add_x_object(xobject)

    # ---------- text-position hook ----------

    def process_text_position(self, text: TextPosition) -> None:
        """Bucket ``text`` into the currently open marked-content
        sequence, optionally suppressing overlapping duplicates.

        Mirrors upstream's ``processTextPosition``: a per-character
        deduplication map keyed on the decoded glyph; we add the glyph
        to whichever bucket is on top of the marked-content stack.
        """
        show_character = True
        if self._suppress_duplicate_overlapping_text:
            show_character = False
            text_character = text.get_unicode()
            text_x = text.get_x()
            text_y = text.get_y()
            same_text_characters = self._character_list_mapping.setdefault(
                text_character, []
            )
            suppress_character = False
            char_count = max(1, len(text_character))
            tolerance = (text.get_width() / char_count) / 3.0
            for same in same_text_characters:
                char_character = same.get_unicode()
                char_x = same.get_x()
                char_y = same.get_y()
                if (
                    char_character is not None
                    and self._within(char_x, text_x, tolerance)
                    and self._within(char_y, text_y, tolerance)
                ):
                    suppress_character = True
                    break
            if not suppress_character:
                same_text_characters.append(text)
                show_character = True

        if show_character and self._current_marked_contents:
            self._current_marked_contents[-1].add_text(text)

    @staticmethod
    def _within(first: float, second: float, variance: float) -> bool:
        return first - variance < second < first + variance

    # ---------- accessors ----------

    def get_marked_contents(self) -> list[PDMarkedContent]:
        return self._marked_contents

    # ---------- driver ----------

    def process_page(self, page: PDPage) -> str:
        """Walk the page content stream, dispatching BMC/BDC/EMC and
        text-emitting operators. Marked-content callbacks fire as the
        sequences open and close; emitted ``TextPosition`` objects flow
        through :meth:`process_text_position` for bucketing.

        Returns the empty string — the extractor is interested in
        marked-content grouping, not flat text. Use
        :meth:`get_marked_contents` to inspect the result.
        """
        self._current_marked_contents.clear()
        self._character_list_mapping.clear()
        body = page.get_contents()
        if not body:
            return ""
        self._active_page = page
        self._cmap_cache = {}
        self._font_cache = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        try:
            self._extract_marked(body)
        finally:
            self._active_page = None
            self._active_cmap = None
            self._active_font = None
            self._active_avg_advance = None
        return ""

    def _extract_marked(self, body: bytes) -> None:
        state = _TextState()
        operands: list[COSBase] = []
        with RandomAccessReadBuffer(body) as src:
            parser = PDFStreamParser(src)
            for token in parser.tokens():
                if isinstance(token, Operator):
                    self._dispatch_marked(token.get_name(), operands, state)
                    operands = []
                else:
                    operands.append(token)

    def _dispatch_marked(
        self,
        op: str,
        operands: list[COSBase],
        state: _TextState,
    ) -> None:
        if op == "BMC":
            # Upstream ``BeginMarkedContentSequence.process`` scans the whole
            # operand list and keeps the *last* ``COSName`` (any leading
            # non-name junk is skipped), so ``1 (x) /Artifact BMC`` opens the
            # ``/Artifact`` sequence. Mirror ``_props.extract_tag`` here
            # rather than taking ``operands[0]``.
            tag = self._last_cos_name(operands)
            self.begin_marked_content_sequence(tag, None)
            return
        if op == "BDC":
            # Unlike BMC, the tag is the *first* operand: the property
            # operand of the ``/Name`` form is itself a ``COSName`` and must
            # not be mistaken for the tag. When the property list cannot be
            # resolved to a dictionary (unknown ``/Name``, wrong type, no
            # resources) upstream ``BeginMarkedContentSequenceWithProperties``
            # returns *without* opening a sequence (``propDict == null``) — so
            # no marked-content node is pushed (and EMC balance is preserved
            # because the unwritten content stream's EMC will still pop the
            # parent, matching upstream which simply skips the open here).
            tag = operands[0] if operands and isinstance(operands[0], COSName) else None
            if tag is None:
                return
            properties = self._resolve_bdc_properties(operands)
            if properties is None:
                return
            self.begin_marked_content_sequence(tag, properties)
            return
        if op == "EMC":
            self.end_marked_content_sequence()
            return
        if op == "MP":
            tag = self._last_cos_name(operands)
            self.marked_content_point(tag, None)
            return
        if op == "DP":
            # Same tag/property semantics as BDC: tag is ``operands[0]``;
            # an unresolved property list means upstream
            # ``MarkedContentPointWithProperties`` returns without notifying
            # the engine.
            tag = operands[0] if operands and isinstance(operands[0], COSName) else None
            if tag is None:
                return
            properties = self._resolve_bdc_properties(operands)
            if properties is None:
                return
            self.marked_content_point(tag, properties)
            return

        # Text-emitting operators reuse the parent's text-state machine
        # but route emitted ``TextPosition``s through our hook instead of
        # appending to a flat positions list.
        if op in {"BT", "ET", "Tf", "TL", "Td", "TD", "Tm", "T*",
                  "Tc", "Tw"}:
            self._dispatch(op, operands, state, [])
            return
        if op in {"Tj", "TJ", "'", '"'}:
            sink: list[TextPosition] = []
            self._dispatch(op, operands, state, sink)
            for tp in sink:
                self.process_text_position(tp)
            return

    def _resolve_bdc_properties(
        self,
        operands: list[COSBase],
    ) -> COSDictionary | None:
        """``BDC`` / ``DP`` carry either an inline property dictionary or
        a ``COSName`` referencing the page resources' ``/Properties``
        subdictionary. Inline dictionary wins; otherwise we resolve the
        name through the active page's resources.
        """
        if len(operands) < 2:
            return None
        prop = operands[1]
        if isinstance(prop, COSDictionary):
            return prop
        if isinstance(prop, COSName) and self._active_page is not None:
            try:
                resources = self._active_page.get_resources()
                pl = (
                    resources.get_property_list(prop)
                    if resources is not None
                    else None
                )
                if pl is not None:
                    return pl.get_cos_object()
            except Exception:  # noqa: BLE001 — defensive: malformed resources
                return None
        return None


__all__ = [
    "PDFMarkedContentExtractor",
    # Re-exported for the rare caller that wants to type-annotate the
    # operand list passed to ``begin_marked_content_sequence``.
    "COSArray",
    "COSNumber",
    "COSString",
]
