from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSNumber
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import (
    Operator as _ParserOperator,
)
from pypdfbox.pdfparser.pdf_stream_parser import (
    PDFStreamParser,
)

from .operator import Operator
from .operator_processor import MissingOperandException, OperatorProcessor
from .pd_content_stream import PDContentStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

_log = logging.getLogger(__name__)


class PDFStreamEngine:
    """
    Token-driven PDF content-stream dispatcher.

    Mirrors ``org.apache.pdfbox.contentstream.PDFStreamEngine``. Cluster
    #2 ships only the dispatch surface — registry of
    :class:`OperatorProcessor` instances keyed by operator name, plus the
    walk-and-dispatch loop. The full graphics-state stack, text matrix,
    resources push/pop, clip-rect setup and inline-image handling land
    with the rendering-prep cluster (#3).

    Registered processors receive every :class:`Operator` of their name
    along with its operand list; unregistered operators fall through to
    :meth:`unsupported_operator` (default no-op, overridable).

    Engine hooks for the 9 PRD §6.7 text operators
    (:meth:`begin_text`, :meth:`end_text`, :meth:`set_font`,
    :meth:`set_text_matrix`, :meth:`move_text_position`,
    :meth:`show_text_string`, :meth:`show_text_strings`) are intentional
    no-ops here: subclasses (the upcoming text-extractor and
    page-renderer) override them. Cluster #2 uses these hooks for parity
    testing and to keep the operator handlers structural —
    operand-validation and dispatch only, no state mutation.
    """

    def __init__(self) -> None:
        self._operators: dict[str, OperatorProcessor] = {}
        # The fields below correspond to upstream private state; they are
        # carried as attributes here so cluster #3 can populate them
        # without touching the dispatch surface again. ``_resources`` is
        # the *current* resource frame; the resource stack lives in
        # ``_resources_stack`` and is pushed/popped by
        # :meth:`set_resources` / nested :meth:`process_stream`.
        self._resources: PDResources | None = None
        self._resources_stack: list[PDResources | None] = []
        self._current_page: PDPage | None = None
        self._is_processing_page: bool = False
        self._level: int = 0

    # ---------- registration ----------

    def add_operator(self, processor: OperatorProcessor) -> None:
        """Register ``processor`` keyed by its :meth:`get_name`. The
        processor is rebound to this engine via :meth:`set_context`,
        matching upstream's ``addOperator`` (which constructs each
        processor with the engine ref then puts it in the map)."""
        processor.set_context(self)
        self._operators[processor.get_name()] = processor

    def register_operator_processor(
        self, name: str, processor: OperatorProcessor
    ) -> None:
        """Register ``processor`` under an explicit ``name`` (rather than
        the processor's own :meth:`get_name`). Mirrors upstream's same-
        named convenience that accepts a custom key — useful when one
        processor handles multiple aliases."""
        processor.set_context(self)
        self._operators[name] = processor

    def get_operators(self) -> dict[str, OperatorProcessor]:
        """Return the registered-processor map (live reference, not a
        copy — matches upstream's ``getOperators``)."""
        return self._operators

    # ---------- entry points ----------

    def process_page(self, page: PDPage) -> None:
        """Walk the page's content stream(s) and dispatch every operator.

        Cluster #2 covers the dispatch path only: we pull raw bytes via
        :meth:`PDPage.get_contents`, hand them to :class:`PDFStreamParser`,
        and invoke :meth:`process_operator` on each token-run. The
        graphics-state push/pop and resource-stack handling that upstream
        wraps around this loop arrive in cluster #3.
        """
        self._current_page = page
        self._is_processing_page = True
        try:
            self._resources = page.get_resources()
            data = page.get_contents()
            if not data:
                return
            self._process_bytes(data)
        finally:
            self._is_processing_page = False
            self._current_page = None

    def process_stream(self, content_stream: PDContentStream) -> None:
        """Dispatch operators from any :class:`PDContentStream`.

        Cluster #2 uses the random-access bytes view directly; the
        graphics-state save/restore and BBox clip that upstream's private
        ``processStream`` performs around the loop are deferred to
        cluster #3. ``_level`` is bumped for the duration so nested
        ``process_form`` / ``process_tiling_pattern`` /
        ``process_type3_stream`` reflect their depth via
        :meth:`get_level`, matching upstream.
        """
        prev_resources = self._resources
        self._level += 1
        try:
            stream_resources = content_stream.get_resources()
            if stream_resources is not None:
                self._resources = stream_resources
            with content_stream.get_contents_for_stream_parsing() as src:
                parser = PDFStreamParser(src)
                self._dispatch_tokens(parser)
        finally:
            self._resources = prev_resources
            self._level -= 1

    def _process_bytes(self, data: bytes) -> None:
        """Internal: feed raw content-stream bytes through the parser."""
        with RandomAccessReadBuffer(data) as src:
            parser = PDFStreamParser(src)
            self._dispatch_tokens(parser)

    def _dispatch_tokens(self, parser: PDFStreamParser) -> None:
        """Drive the parser, accumulating operands until each operator
        token is seen, then dispatch. Mirrors upstream's
        ``processStreamOperators`` loop, sans the Type3 / tiling-pattern
        colour-operator gating which depends on classes that arrive in
        later clusters.
        """
        operands: list[COSBase] = []
        for token in parser.tokens():
            if isinstance(token, _ParserOperator):
                op = self._adopt_parser_operator(token)
                self.process_operator(op, operands)
                operands = []
            elif isinstance(token, COSBase):
                operands.append(token)
            # parse_next_token never yields anything else, but a malformed
            # stream could in principle: silently skip, matching upstream
            # which also ignores non-COSBase / non-Operator tokens.

    @staticmethod
    def _adopt_parser_operator(parser_op: _ParserOperator) -> Operator:
        """Promote a parser-internal :class:`Operator` to the canonical
        contentstream :class:`Operator` (interned, image-data preserved
        for ``BI`` / ``ID``)."""
        op = Operator.get_operator(parser_op.get_name())
        # ``BI`` / ``ID`` instances are always fresh (un-cached); safe to
        # attach the inline-image payload picked up by the parser.
        if parser_op.image_data is not None:
            op.set_image_data(parser_op.image_data)
        if parser_op.image_parameters is not None:
            op.set_image_parameters(parser_op.image_parameters)
        return op

    # ---------- dispatch ----------

    def process_operator(
        self,
        operator: Operator | str,
        operands: list[COSBase] | None,
    ) -> None:
        """Dispatch one operator. Two call shapes match upstream's pair
        of overloads: pass an :class:`Operator` (the engine's own loop
        path) or a bare ``str`` (the convenience path used by composite
        handlers like ``'`` and ``"`` to re-enter the engine).

        ``BI`` is intercepted here: the parser pre-collates ``BI`` /
        ``ID`` / ``EI`` into a single ``BI`` :class:`Operator` carrying
        both the parameter dictionary (``image_parameters``) and the raw
        image bytes (``image_data``). We construct a
        :class:`PDInlineImage` from those and forward it to the
        :meth:`show_inline_image` hook before falling through to the
        registered lite stub. Mirrors upstream
        ``BeginInlineImage.process`` which builds the inline image and
        forwards to ``PDFStreamEngine.showInlineImage``.
        """
        if operands is None:
            operands = []
        if isinstance(operator, str):
            operator = Operator.get_operator(operator)
        name = operator.get_name()
        if name == "BI":
            self._dispatch_inline_image(operator, operands)
            return
        processor = self._operators.get(name)
        if processor is not None:
            try:
                processor.process(operator, operands)
            except OSError as exc:  # IOException on the upstream side
                self.operator_exception(operator, operands, exc)
        else:
            self.unsupported_operator(operator, operands)

    def _dispatch_inline_image(
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        """Build a :class:`PDInlineImage` from the parser-collated ``BI``
        operator and forward to :meth:`show_inline_image`.

        Falls through to the lite ``BI`` stub afterwards so
        registry-level observers (e.g. parity test fixtures hooked via
        :meth:`add_operator`) still see the operator. If the parser did
        not attach a parameter dict (malformed stream) we synthesise an
        empty :class:`COSDictionary` so the PDInlineImage constructor
        receives a valid argument shape — :class:`PDInlineImage`
        validates the contents (zero-dimension images surface as
        ``get_width() == -1`` and the renderer's ``draw_image`` skips
        them).
        """
        from pypdfbox.pdmodel.graphics.image.pd_inline_image import (  # noqa: PLC0415
            PDInlineImage,
        )

        params = operator.get_image_parameters()
        if params is None:
            params = COSDictionary()
        data = operator.get_image_data()
        if data is None:
            data = b""
        try:
            image = PDInlineImage(params, data, self.get_resources())
        except OSError as exc:
            # Malformed inline image — log via the standard operator
            # exception triage and stop.
            self.operator_exception(operator, operands, exc)
            return
        try:
            self.show_inline_image(image)
        except OSError as exc:
            self.operator_exception(operator, operands, exc)
            return
        # Keep the lite-stub log path live for parity with upstream's
        # ``addOperator(BeginInlineImage)`` registration surface.
        processor = self._operators.get("BI")
        if processor is not None:
            try:
                processor.process(operator, operands)
            except OSError as exc:
                self.operator_exception(operator, operands, exc)

    def unsupported_operator(
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        """Invoked when no processor is registered for an operator.
        Default: no-op. Subclasses override (e.g. PDFTextStripper logs)."""

    def operator_exception(
        self,
        operator: Operator,
        operands: list[COSBase],
        exception: OSError,
    ) -> None:
        """Default error policy. Re-raises by default; ``MissingOperandException``
        and ``Do``-operator failures are demoted to a log line, matching
        upstream's ``operatorException`` triage. The full upstream branch
        list (MissingResourceException / EmptyGraphicsStackException /
        DataFormatException) lands with the cluster that introduces those
        exception types.
        """
        if isinstance(exception, MissingOperandException):
            _log.error("%s", exception)
            return
        if operator.get_name() == "Do":
            _log.warning("%s", exception)
            return
        raise exception

    # ---------- accessors (upstream parity surface) ----------

    def get_resources(self) -> PDResources | None:
        """Return the current resource stack top — the :class:`PDResources`
        in scope for the operator currently being processed. Mirrors
        upstream's ``getResources``."""
        return self._resources

    def get_current_page(self) -> PDPage | None:
        """Return the page currently being processed, or ``None`` outside
        of :meth:`process_page`. Mirrors upstream's ``getCurrentPage``."""
        return self._current_page

    def get_level(self) -> int:
        """Return the current nesting level of stream processing (0 at the
        outermost stream, incremented for nested form / pattern / Type3
        streams). Mirrors upstream's ``getLevel``."""
        return self._level

    def is_processing_page(self) -> bool:
        """``True`` while inside :meth:`process_page`. Mirrors upstream's
        ``isProcessingPage``."""
        return self._is_processing_page

    def set_resources(self, res: PDResources) -> None:
        """Push a new resource stack frame, making ``res`` the active
        :meth:`get_resources` result. Mirrors upstream's ``setResources``
        used by form-XObject / pattern handlers to scope a nested
        resource lookup."""
        self._resources_stack.append(self._resources)
        self._resources = res

    # ---------- nested-stream entry points (upstream parity surface) ----------

    def process_form(self, form_xobject: PDFormXObject) -> None:
        """Process a form XObject's content stream. Convenience alias for
        :meth:`process_stream`. Mirrors upstream's ``processForm`` which
        wraps the same dispatch with a graphics-state save/restore that
        the rendering subclass overlays."""
        self.process_stream(form_xobject)

    def process_tiling_pattern(
        self,
        pattern: PDContentStream,
        color: Any | None,
        color_space: Any | None,
    ) -> None:
        """Process a tiling-pattern content stream. Lite version: ignores
        ``color`` / ``color_space`` (the rendering subclass uses them to
        seed the non-stroking colour) and just drives the operators.
        Mirrors upstream's ``processTilingPattern`` signature."""
        del color, color_space  # rendering subclass consumes these
        self.process_stream(pattern)

    def process_type3_stream(
        self,
        charproc: PDContentStream,
        text_matrix: Any | None = None,
    ) -> None:
        """Process a Type3 charproc content stream. Placeholder: ignores
        ``text_matrix`` (the rendering subclass uses it to position the
        glyph) and just drives the operators. Mirrors upstream's
        ``processType3Stream``."""
        del text_matrix  # rendering subclass consumes this
        self.process_stream(charproc)

    # ---------- graphics-state hooks (overridable in renderer) ----------

    def save_graphics_state(self) -> None:
        """``q`` notification — base no-op. The rendering subclass
        overrides to push the graphics-state stack. Mirrors upstream's
        ``saveGraphicsState``."""

    def restore_graphics_state(self) -> None:
        """``Q`` notification — base no-op. The rendering subclass
        overrides to pop the graphics-state stack. Mirrors upstream's
        ``restoreGraphicsState``."""

    def transform_text(self, matrix: Any) -> None:
        """Apply ``matrix`` to the text state. Base no-op; the rendering
        subclass concatenates ``matrix`` onto the text matrix. Mirrors
        upstream's ``transformText``."""

    # ---------- engine hooks (overridable in later clusters) ----------
    #
    # The 9 PRD §6.7 operator handlers call the hooks below instead of
    # mutating engine state directly. Cluster #2 ships them as no-ops;
    # the text-extraction cluster (#7) and rendering cluster (#9)
    # override them. Keeping the handlers structural at this stage means
    # they can ship now with full operand validation and round-trip
    # parity tests, and pick up real text-state behaviour without any
    # further changes to the operator classes themselves.

    def begin_text(self) -> None:
        """``BT`` notification — cluster #2 no-op."""

    def end_text(self) -> None:
        """``ET`` notification — cluster #2 no-op."""

    def set_font(self, font_name: COSName, font_size: float) -> None:
        """``Tf`` notification — cluster #2 no-op."""

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        """``Tm`` notification (and ``BT`` / ``ET`` reset). Cluster #2
        passes the raw 6-element matrix as a flat list, or ``None`` when
        the engine is exiting a text object."""

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        """Companion to :meth:`set_text_matrix` for the text-line matrix."""

    def move_text_position(self, tx: float, ty: float) -> None:
        """``Td`` / ``TD`` notification — cluster #2 no-op."""

    def set_text_leading(self, leading: float) -> None:
        """``TL`` notification (used by the ``TD`` decomposition)."""

    def set_word_spacing(self, spacing: float) -> None:
        """``Tw`` notification (used by the ``"`` decomposition)."""

    def set_character_spacing(self, spacing: float) -> None:
        """``Tc`` notification (used by the ``"`` decomposition)."""

    def show_text_string(self, text: bytes) -> None:
        """``Tj`` notification — cluster #2 no-op."""

    def show_text_strings(self, array: COSArray) -> None:
        """``TJ`` notification — cluster #2 no-op. Subclasses iterate
        the array, dispatching numbers as positioning adjustments and
        strings as glyph runs."""

    def show_inline_image(self, inline_image: PDInlineImage) -> None:
        """``BI`` / ``ID`` / ``EI`` notification — base no-op.

        Invoked once per inline image with a fully constructed
        :class:`PDInlineImage` (the constructor has already decoded the
        filter chain). The rendering subclass overrides to delegate to
        :meth:`draw_image`. Mirrors upstream's
        ``PDFStreamEngine.showInlineImage(PDInlineImage)``.
        """

    def get_text_matrix(self) -> Any:
        """Cluster #2 always reports ``None`` (no text state). The
        ``Tj`` / ``TJ`` / ``'`` / ``"`` handlers consult this to decide
        whether a text object is currently open. Subclasses in cluster
        #3 return a real ``Matrix``."""
        return None

    # ---------- helpers used by handlers ----------

    @staticmethod
    def _require_min_operands(
        operator: Operator, operands: list[COSBase], minimum: int
    ) -> None:
        if len(operands) < minimum:
            raise MissingOperandException(operator, operands)

    @staticmethod
    def _to_float(value: COSBase) -> float | None:
        """Return ``float(value)`` for ``COSNumber``, else ``None``. The
        callers fall through silently on a None — matching upstream
        ``instanceof COSNumber`` checks that drop bad operands without
        raising."""
        if isinstance(value, COSNumber):
            return value.float_value()
        return None
