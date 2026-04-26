from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSName, COSNumber
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
    from pypdfbox.pdmodel.pd_page import PDPage

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
        # without touching the dispatch surface again.
        self._resources: Any | None = None
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
        cluster #3.
        """
        prev_resources = self._resources
        try:
            self._resources = content_stream.get_resources()
            with content_stream.get_contents_for_stream_parsing() as src:
                parser = PDFStreamParser(src)
                self._dispatch_tokens(parser)
        finally:
            self._resources = prev_resources

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
        """
        if operands is None:
            operands = []
        if isinstance(operator, str):
            operator = Operator.get_operator(operator)
        name = operator.get_name()
        processor = self._operators.get(name)
        if processor is not None:
            try:
                processor.process(operator, operands)
            except OSError as exc:  # IOException on the upstream side
                self.operator_exception(operator, operands, exc)
        else:
            self.unsupported_operator(operator, operands)

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
