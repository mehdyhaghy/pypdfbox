from __future__ import annotations

import contextlib
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
    from pypdfbox.pdmodel.common.pd_rectangle import PDRectangle
    from pypdfbox.pdmodel.graphics.color import PDColor
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
        PDTransparencyGroup,
    )
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
        PDAnnotation,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )
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
        # Initial CTM seeded by the page-renderer subclass at
        # ``init_page`` time. Mirrors upstream ``initialMatrix``.
        self._initial_matrix: Any | None = None
        # Mirrors upstream ``shouldProcessColorOperators`` — flipped to
        # ``False`` for Type3 charprocs starting with ``d1`` and for
        # uncoloured tiling patterns. The colour-operator handlers
        # consult :meth:`is_should_process_color_operators` before
        # mutating colour state.
        self._should_process_color_operators: bool = True
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
        # Graphics state stack — base engine carries an opaque sentinel
        # frame so subclasses (PDFGraphicsStreamEngine / page renderer)
        # can override :meth:`get_graphics_state` /
        # :meth:`save_graphics_state` / :meth:`restore_graphics_state`
        # without having to re-implement the dispatch surface. The base
        # engine itself never inspects the stack contents — see the
        # docstring on :meth:`get_graphics_state`.
        self._graphics_stack: list[Any] = []
        # Text matrix + text line matrix as Matrix-like objects (any type
        # the subclass cares to store; base engine treats them as opaque).
        # Distinct from the flat-list ``set_text_matrix`` notification
        # hook below — that one fires from BT/ET reset paths and is a
        # pure callback, while these accessors mirror upstream's
        # ``getTextMatrix`` / ``getTextLineMatrix`` shape used by the
        # text-extraction subclasses.
        self._text_matrix_obj: Any | None = None
        self._text_line_matrix_obj: Any | None = None

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

    def get_operator(self, name: str) -> OperatorProcessor | None:
        """Return the processor registered under ``name``, or ``None``
        when no processor handles that operator. Convenience surface
        matching the conceptual ``getOperator(opName)`` lookup that
        upstream callers often phrase via ``getOperators().get(name)``."""
        return self._operators.get(name)

    # ---------- entry points ----------

    def process_page(self, page: PDPage) -> None:
        """Walk the page's content stream(s) and dispatch every operator.

        Mirrors upstream ``processPage(PDPage)``: delegates to
        :meth:`init_page` to set up the current page / resources /
        initial matrix, then drives the parser. The
        graphics-state push/pop and full resource-stack handling that
        upstream wraps around this loop arrive in cluster #3.
        """
        self.init_page(page)
        self._is_processing_page = True
        try:
            data = page.get_contents()
            if not data:
                return
            self._process_bytes(data)
        finally:
            self._is_processing_page = False
            self._current_page = None

    def init_page(self, page: PDPage) -> None:
        """Initialize the engine for the given page.

        Mirrors upstream's private ``initPage(PDPage)``: sets the
        current-page reference, clears the graphics-state stack, seeds
        the resources from the page, and captures the page's initial
        matrix on :attr:`_initial_matrix`. Exposed as a public hook so
        the rendering subclass can override to push a typed
        ``PDGraphicsState`` onto the stack (upstream does the same via
        ``graphicsStack.push(new PDGraphicsState(page.getCropBox()))``).
        """
        if page is None:
            raise ValueError("Page cannot be null")
        self._current_page = page
        self._graphics_stack = []
        self._resources = page.get_resources()
        # ``page.getMatrix()`` upstream — we expose whatever the page's
        # ``get_matrix()`` returns when present, falling back to ``None``
        # so the base engine doesn't force materialisation of a Matrix
        # type that doesn't yet exist in pypdfbox.
        getter = getattr(page, "get_matrix", None)
        self._initial_matrix = getter() if callable(getter) else None

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
        self.increase_level()
        try:
            stream_resources = content_stream.get_resources()
            if stream_resources is not None:
                self._resources = stream_resources
            with content_stream.get_contents_for_stream_parsing() as src:
                parser = PDFStreamParser(src)
                self._dispatch_tokens(parser)
        finally:
            self._resources = prev_resources
            self.decrease_level()

    def process_child_stream(
        self,
        contents: PDContentStream,
        page: PDPage | None = None,
    ) -> None:
        """Process a nested content stream (e.g. an annotation appearance,
        an XObject, or a Type3 charproc) in the context of ``page``.
        Mirrors upstream ``processChildStream(PDContentStream, PDPage)``.

        Sets the engine's current-page context to ``page`` for the
        duration of the inner :meth:`process_stream` so the registered
        operator processors see the same :meth:`get_current_page` they
        would during a top-level :meth:`process_page` walk.
        """
        prev_page = self._current_page
        prev_is_processing = self._is_processing_page
        if page is not None:
            self._current_page = page
            self._is_processing_page = True
        try:
            self.process_stream(contents)
        finally:
            self._current_page = prev_page
            self._is_processing_page = prev_is_processing

    def _process_bytes(self, data: bytes) -> None:
        """Internal: feed raw content-stream bytes through the parser."""
        with RandomAccessReadBuffer(data) as src:
            parser = PDFStreamParser(src)
            self._dispatch_tokens(parser)

    def process_stream_operators(self, content_stream: PDContentStream) -> None:
        """Drive the parser of ``content_stream`` and dispatch each
        operator with its accumulated operands.

        Mirrors upstream's private ``processStreamOperators(PDContentStream)``.
        Exposed publicly here (as the snake_case counterpart) because the
        nested-stream entry points — :meth:`process_transparency_group`,
        :meth:`process_annotation`, the rendering subclass' Type3 path —
        all call this to re-enter dispatch after they've fenced the
        graphics stack / resources / matrix. The cluster #2 base does not
        carry the colour-operator gating for ``PDTilingPattern`` /
        Type3 ``d1`` first-operator detection — :meth:`_dispatch_tokens`
        does not yet inspect those — but the call surface matches.
        """
        with content_stream.get_contents_for_stream_parsing() as src:
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

    def increase_level(self) -> None:
        """Increase the recursive stream-processing level.

        Mirrors upstream ``PDFStreamEngine.increaseLevel``. Callers that
        process a potentially recursive stream manually can use this with
        :meth:`decrease_level` so :meth:`get_level` reflects the same state
        as the built-in :meth:`process_stream` path.
        """
        self._level += 1

    def decrease_level(self) -> None:
        """Decrease the recursive stream-processing level.

        Mirrors upstream ``PDFStreamEngine.decreaseLevel``. If called too
        many times, the level is kept at zero and an error is logged,
        matching upstream's defensive handling for unbalanced recursion
        guards.
        """
        if self._level <= 0:
            _log.error("level is below 0")
            self._level = 0
            return
        self._level -= 1

    def is_processing_page(self) -> bool:
        """``True`` while inside :meth:`process_page`. Mirrors upstream's
        ``isProcessingPage``."""
        return self._is_processing_page

    def get_initial_matrix(self) -> Any | None:
        """Return the stream's initial transformation matrix, or ``None``
        when no page has been initialised yet (cluster #2 default — the
        rendering subclass populates this in its ``init_page`` override).
        Mirrors upstream ``getInitialMatrix``."""
        return self._initial_matrix

    def set_initial_matrix(self, matrix: Any | None) -> None:
        """Set the stream's initial transformation matrix. Companion
        writer for :meth:`get_initial_matrix`. Upstream sets this through
        the private ``initPage`` path; pypdfbox exposes it as a writer so
        subclasses can populate it without re-implementing the dispatch
        surface."""
        self._initial_matrix = matrix

    def is_should_process_color_operators(self) -> bool:
        """Tells whether colour operators should be processed. Mirrors
        upstream ``isShouldProcessColorOperators``.

        Returns ``False`` in two cases that the rendering subclass /
        Type3 path flips:

        - Type3 charprocs that start with the ``d1`` operator (the glyph
          colour comes from the surrounding text-state colour, not from
          the charproc itself).
        - Uncoloured tiling patterns (the colour is supplied at paint
          time by the caller).

        The colour-operator handlers consult this before mutating colour
        state."""
        return self._should_process_color_operators

    def _set_should_process_color_operators(self, value: bool) -> None:
        """Internal setter used by the Type3 / tiling-pattern entry
        points. Not part of the public upstream surface — upstream sets
        the flag from the same private code paths."""
        self._should_process_color_operators = value

    def set_resources(self, res: PDResources) -> None:
        """Push a new resource stack frame, making ``res`` the active
        :meth:`get_resources` result. Mirrors upstream's ``setResources``
        used by form-XObject / pattern handlers to scope a nested
        resource lookup."""
        self._resources_stack.append(self._resources)
        self._resources = res

    # ---------- graphics-state stack (overridable in renderer) ----------

    def get_graphics_state(self) -> Any:
        """Return the current graphics-state frame — top of the stack.

        Mirrors upstream's ``getGraphicsState``. The base engine carries
        the stack as opaque ``Any`` entries (cluster #2 has no concrete
        ``PDGraphicsState`` class to instantiate); subclasses with a
        real graphics-state push a typed object via
        :meth:`save_graphics_state` and return it from this method.
        Returns ``None`` when the stack is empty (matches the cluster #2
        default since the base never pushes on its own)."""
        if not self._graphics_stack:
            return None
        return self._graphics_stack[-1]

    def get_graphics_stack_size(self) -> int:
        """Return the depth of the graphics-state stack. Mirrors
        upstream's ``getGraphicsStackSize``."""
        return len(self._graphics_stack)

    def save_graphics_stack(self) -> list[Any]:
        """Snapshot and reset the entire graphics-state stack.

        Mirrors upstream's ``protected final saveGraphicsStack``: returns
        the current stack so the caller can hand it to
        :meth:`restore_graphics_stack` later, and replaces the engine's
        live stack with a one-frame stack whose sole entry is a copy of
        the previously top frame (so the inner stream sees a fresh
        graphics state seeded by the outer top-of-stack).

        Used by upstream's ``processSoftMask`` /
        ``processTransparencyGroup`` / ``processType3Stream`` /
        ``processAnnotation`` paths to fence a nested stream's stack
        from the parent stream's. Cluster #2 carries the stack as opaque
        ``Any`` entries (no concrete ``PDGraphicsState`` yet); the copy
        uses ``copy.copy`` if the frame supports it, falling back to the
        same reference when it doesn't — matching the cluster-#2
        contract that the base never inspects frame contents.
        """
        import copy as _copy  # noqa: PLC0415

        saved = self._graphics_stack
        if saved:
            top = saved[-1]
            try:
                top_copy = _copy.copy(top)
            except (TypeError, ValueError):
                top_copy = top
            self._graphics_stack = [top_copy]
        else:
            self._graphics_stack = []
        return saved

    def restore_graphics_stack(self, snapshot: list[Any]) -> None:
        """Restore the entire graphics-state stack from a snapshot.

        Companion to :meth:`save_graphics_stack`; mirrors upstream's
        ``protected final restoreGraphicsStack(Deque<PDGraphicsState>)``
        verbatim — the live stack is wholesale replaced by the snapshot
        the caller previously saved.
        """
        self._graphics_stack = snapshot

    def transform(self, matrix: Any) -> None:
        """Concatenate ``matrix`` onto the current CTM. Base no-op; the
        rendering subclass overrides to multiply ``matrix`` into the
        active graphics-state CTM. Mirrors upstream's ``transform``
        (the ``cm`` operator handler delegates here)."""

    def transform_width(self, width: float) -> float:
        """Transform ``width`` through the current CTM, returning the
        scalar width in user space.

        Mirrors upstream's ``protected float transformWidth(float)``.
        Upstream computes
        ``width * sqrt((scaleX+shearX)^2 + (scaleY+shearY)^2) / sqrt(2)``
        from the active graphics-state CTM. Cluster #2 has no concrete
        CTM to consult and returns ``width`` unchanged; the rendering
        subclass overrides with the geometric form once the
        :class:`Matrix` class is in tree.
        """
        return float(width)

    def set_line_dash_pattern(self, array: COSArray, phase: int) -> None:
        """``d`` notification — base no-op.

        Mirrors upstream's ``setLineDashPattern(COSArray, int)`` which
        builds a ``PDLineDashPattern`` and stores it on the active
        graphics-state. Cluster #2 has no ``PDLineDashPattern`` /
        graphics state yet, so the base swallows the call; the rendering
        subclass overrides to materialise + store the pattern. Kept as a
        public method so the ``d`` operator handler can call back
        without reaching into private state.
        """

    # ---------- nested-stream entry points (upstream parity surface) ----------

    def process_form(self, form_xobject: PDFormXObject) -> None:
        """Process a form XObject's content stream. Convenience alias for
        :meth:`process_stream`. Mirrors upstream's ``processForm`` which
        wraps the same dispatch with a graphics-state save/restore that
        the rendering subclass overlays."""
        self.process_stream(form_xobject)

    def show_form(self, form: PDFormXObject) -> None:
        """Public ``Do``-XObject form entry point.

        Mirrors upstream's ``public void showForm(PDFormXObject)``:

        - raises ``RuntimeError`` (upstream: ``IllegalStateException``)
          when no current page is set, pointing the caller at
          :meth:`process_child_stream` instead;
        - skips empty (zero-length) streams silently — upstream wraps
          the dispatch in ``form.getCOSObject().getLength() > 0``;
        - otherwise delegates to :meth:`process_stream`.
        """
        if self._current_page is None:
            raise RuntimeError(
                "No current page, call "
                "process_child_stream(content_stream, page) instead"
            )
        cos = form.get_cos_object()
        # Empty form streams are valid but produce nothing — skip the
        # parser invocation entirely so an unfiltered ``b""`` payload
        # doesn't fall into ``_dispatch_tokens`` for no benefit.
        getter = getattr(cos, "get_length", None)
        if getter is not None:
            try:
                length = int(getter())
            except (TypeError, ValueError):
                length = 0
            if length <= 0:
                return
        self.process_stream(form)

    def show_transparency_group(self, form: PDTransparencyGroup) -> None:
        """Public transparency-group entry point.

        Mirrors upstream's ``public void showTransparencyGroup`` which
        is a thin wrapper over :meth:`process_transparency_group`.
        """
        self.process_transparency_group(form)

    def process_transparency_group(self, group: PDTransparencyGroup) -> None:
        """Process a transparency-group content stream.

        Mirrors upstream's ``protected processTransparencyGroup``: pushes
        the group's resources, fences the graphics-state stack, swaps in
        the group's matrix as the new initial matrix, clips to the group
        BBox, drives the operators via :meth:`process_stream_operators`,
        then restores. Cluster #2 has no concrete graphics state to
        mutate (blend mode, alpha constants, soft mask, CTM) so those
        upstream side-effects are deferred to the rendering subclass —
        the structural fencing and dispatch is in place.
        """
        if self._current_page is None:
            raise RuntimeError(
                "No current page, call "
                "process_child_stream(content_stream, page) instead"
            )
        parent = self.push_resources(group)
        saved_stack = self.save_graphics_stack()
        parent_matrix = self._initial_matrix
        # Upstream snapshots the CTM into ``initialMatrix`` so nested
        # streams compose against it. Without a concrete CTM we mirror
        # the structure: capture the current top-of-stack frame's matrix
        # if exposed, else just keep the parent matrix.
        gs = self.get_graphics_state()
        ctm = getattr(gs, "current_transformation_matrix", None)
        if ctm is not None:
            self._initial_matrix = ctm
        with contextlib.suppress(AttributeError, TypeError):
            # group.get_bbox() may legitimately not be defined in cluster #2
            self.clip_to_rect(group.get_bbox())
        try:
            self.process_stream_operators(group)
        finally:
            self._initial_matrix = parent_matrix
            self.restore_graphics_stack(saved_stack)
            self.pop_resources(parent)

    def process_soft_mask(self, group: PDTransparencyGroup) -> None:
        """Process a soft-mask transparency-group stream.

        Mirrors upstream's ``protected processSoftMask``: saves the
        graphics state, swaps the CTM/text matrices/colour spaces for
        the soft-mask convention (DeviceGray, soft-mask CTM), drives
        :meth:`process_transparency_group`, then restores. The cluster
        #2 base does not own a concrete graphics state — the colour /
        matrix mutations land with the rendering subclass — so the
        structural fencing (save/restore around the dispatch) is what
        stays here.
        """
        self.save_graphics_state()
        try:
            self.process_transparency_group(group)
        finally:
            self.restore_graphics_state()

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

    # ---------- annotation entry points ----------

    def show_annotation(self, annotation: PDAnnotation) -> None:
        """Public annotation entry point.

        Mirrors upstream's ``public void showAnnotation(PDAnnotation)``:
        looks up the active appearance via :meth:`get_appearance` and
        forwards to :meth:`process_annotation`. Skips silently when no
        appearance is present (an annotation with neither a normal
        appearance nor any drawing payload is a no-op for rendering).
        """
        appearance = self.get_appearance(annotation)
        if appearance is not None:
            self.process_annotation(annotation, appearance)

    def get_appearance(
        self, annotation: PDAnnotation
    ) -> PDAppearanceStream | None:
        """Return the appearance stream to process for ``annotation``.

        Mirrors upstream's ``public PDAppearanceStream getAppearance(
        PDAnnotation)`` — defaults to the annotation's normal
        appearance. Subclasses override to render a different state
        (e.g. ``hover`` / ``down``).
        """
        getter = getattr(annotation, "get_normal_appearance_stream", None)
        if getter is None:
            return None
        return getter()

    def process_annotation(
        self,
        annotation: PDAnnotation,
        appearance: PDAppearanceStream,
    ) -> None:
        """Process an annotation's appearance stream.

        Mirrors upstream's ``protected processAnnotation(PDAnnotation,
        PDAppearanceStream)``: validates the annotation rectangle and
        appearance bbox are non-zero, fences the graphics-state stack
        around :meth:`process_stream_operators`, and pushes the
        appearance's resources frame. The geometric matrix-construction
        (mapping the appearance bbox to the annotation rect) is the
        rendering-subclass concern and lands with cluster #3 — the
        cluster #2 base ships the structural fencing only.
        """
        bbox = appearance.get_bbox() if hasattr(appearance, "get_bbox") else None
        rect_getter = getattr(annotation, "get_rectangle", None)
        rect = rect_getter() if callable(rect_getter) else None
        # Upstream guard: zero-sized rect or bbox => skip
        if rect is None or bbox is None:
            return
        try:
            if rect.get_width() <= 0 or rect.get_height() <= 0:
                return
            if bbox.get_width() <= 0 or bbox.get_height() <= 0:
                return
        except (AttributeError, TypeError):
            return

        parent = self.push_resources(appearance)
        saved_stack = self.save_graphics_stack()
        parent_matrix = self._initial_matrix
        try:
            self.clip_to_rect(bbox)
            self.process_stream_operators(appearance)
        finally:
            self._initial_matrix = parent_matrix
            self.restore_graphics_stack(saved_stack)
            self.pop_resources(parent)

    # ---------- resource-stack helpers ----------

    def push_resources(
        self, content_stream: PDContentStream
    ) -> PDResources | None:
        """Push the resources of ``content_stream``, returning the prior
        frame so :meth:`pop_resources` can restore it later.

        Mirrors upstream's private ``pushResources(PDContentStream)``:

        - if the stream owns a ``/Resources`` dictionary, that becomes
          active;
        - else, the parent resources stay in place (PDFBOX-1359 — the
          PDF spec doesn't require this fall-through but Acrobat does
          it and so do we);
        - else, fall back to the current page's resources, or a fresh
          empty :class:`PDResources` if the page has none.

        Returns the previously active resources so the caller can hand
        them to :meth:`pop_resources` after the nested dispatch runs.
        """
        parent_resources = self._resources
        stream_resources = content_stream.get_resources()
        if stream_resources is not None:
            self._resources = stream_resources
        elif self._resources is not None:
            # Inherit from parent stream — see method docstring.
            pass
        else:
            page = self._current_page
            page_resources = page.get_resources() if page is not None else None
            if page_resources is None:
                from pypdfbox.pdmodel.pd_resources import (  # noqa: PLC0415
                    PDResources as _PDResources,
                )

                self._resources = _PDResources()
            else:
                self._resources = page_resources
        return parent_resources

    def pop_resources(
        self, parent_resources: PDResources | None
    ) -> None:
        """Restore the resources frame previously returned by
        :meth:`push_resources`.

        Mirrors upstream's private ``popResources(PDResources)`` —
        wholesale replaces the active frame with ``parent_resources``.
        """
        self._resources = parent_resources

    # ---------- clipping helper ----------

    def clip_to_rect(self, rectangle: PDRectangle | None) -> None:
        """Intersect the active clipping path with ``rectangle``
        transformed through the current CTM.

        Mirrors upstream's private ``clipToRect(PDRectangle)``. Cluster
        #2 has no concrete graphics-state to mutate (no clipping path,
        no real CTM) — this is a structural placeholder so the
        nested-stream entry points (:meth:`process_transparency_group`,
        :meth:`process_annotation`) can call it where upstream does.
        The rendering subclass overrides with the real intersection.
        """
        if rectangle is None:
            return
        gs = self.get_graphics_state()
        if gs is None:
            return
        clipper = getattr(gs, "intersect_clipping_path", None)
        if clipper is None:
            return
        # If the rectangle exposes a ``transform`` method (real
        # PDRectangle), feed it the current CTM so the clip path is in
        # device space; else hand the raw rectangle through.
        ctm = getattr(gs, "current_transformation_matrix", None)
        if ctm is not None and hasattr(rectangle, "transform"):
            try:
                clip_path = rectangle.transform(ctm)
            except (TypeError, AttributeError):
                clip_path = rectangle
        else:
            clip_path = rectangle
        with contextlib.suppress(TypeError, AttributeError):
            clipper(clip_path)

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

    def get_text_leading(self) -> float:
        """Return the current text leading. Cluster #2 default is 0."""
        return 0.0

    def set_word_spacing(self, spacing: float) -> None:
        """``Tw`` notification (used by the ``"`` decomposition)."""

    def set_character_spacing(self, spacing: float) -> None:
        """``Tc`` notification (used by the ``"`` decomposition)."""

    def set_horizontal_scaling(self, scaling: float) -> None:
        """``Tz`` notification — cluster #2 no-op."""

    def set_text_rendering_mode(self, mode: int) -> None:
        """``Tr`` notification — cluster #2 no-op."""

    def set_text_rise(self, rise: float) -> None:
        """``Ts`` notification — cluster #2 no-op."""

    def set_stroking_color(self, color: PDColor) -> None:
        """Device-color notification for stroking paint operators.

        Base no-op; graphics/text/rendering subclasses may store the
        supplied :class:`PDColor` in their graphics state.
        """

    def set_non_stroking_color(self, color: PDColor) -> None:
        """Device-color notification for non-stroking paint operators.

        Base no-op; graphics/text/rendering subclasses may store the
        supplied :class:`PDColor` in their graphics state.
        """

    def show_text_string(self, text: bytes) -> None:
        """``Tj`` notification — cluster #2 no-op."""

    def show_text_strings(self, array: COSArray) -> None:
        """``TJ`` notification — cluster #2 no-op. Subclasses iterate
        the array, dispatching numbers as positioning adjustments and
        strings as glyph runs."""

    def begin_marked_content_sequence(
        self, tag: COSName, properties: COSDictionary | None
    ) -> None:
        """``BMC`` / ``BDC`` notification. Base no-op — subclasses
        override (e.g. the structure-tree extractor records the tag).
        Mirrors upstream ``beginMarkedContentSequence``."""

    def end_marked_content_sequence(self) -> None:
        """``EMC`` notification. Base no-op — subclasses override.
        Mirrors upstream ``endMarkedContentSequence``."""

    def marked_content_point(
        self, tag: COSName, properties: COSDictionary | None
    ) -> None:
        """``MP`` / ``DP`` notification. Base no-op — subclasses override
        (the marked-content extractor records the point). Mirrors
        upstream ``markedContentPoint``."""

    def show_inline_image(self, inline_image: PDInlineImage) -> None:
        """``BI`` / ``ID`` / ``EI`` notification — base no-op.

        Invoked once per inline image with a fully constructed
        :class:`PDInlineImage` (the constructor has already decoded the
        filter chain). The rendering subclass overrides to delegate to
        :meth:`draw_image`. Mirrors upstream's
        ``PDFStreamEngine.showInlineImage(PDInlineImage)``.
        """

    def get_text_matrix(self) -> Any:
        """Return the current text matrix (or ``None`` outside BT/ET).

        Cluster #2 returns whatever was last passed to
        :meth:`set_text_matrix_object` — base default is ``None``. The
        ``Tj`` / ``TJ`` / ``'`` / ``"`` handlers consult this to decide
        whether a text object is currently open. Subclasses in cluster
        #3 override to return a real ``Matrix`` from the graphics-state
        text-matrix slot.

        Mirrors upstream ``PDFStreamEngine.getTextMatrix``."""
        return self._text_matrix_obj

    def set_text_matrix_object(self, matrix: Any) -> None:
        """Companion writer for :meth:`get_text_matrix` carrying a full
        ``Matrix``-like object (rather than the flat 6-element list the
        notification hook :meth:`set_text_matrix` receives). Subclasses
        with a real text-state may override; base stores opaquely.

        The split-name (``set_text_matrix_object`` vs upstream's
        ``setTextMatrix(Matrix)``) avoids colliding with the existing
        :meth:`set_text_matrix(list[float] | None)` notification hook
        — they signal different things and have different operand
        shapes."""
        self._text_matrix_obj = matrix

    def get_text_line_matrix(self) -> Any:
        """Return the current text-line matrix. Mirrors upstream's
        ``getTextLineMatrix``. Base default tracks whatever was last
        passed to :meth:`set_text_line_matrix_object`."""
        return self._text_line_matrix_obj

    def set_text_line_matrix_object(self, matrix: Any) -> None:
        """Companion writer for :meth:`get_text_line_matrix`. See
        :meth:`set_text_matrix_object` for the rationale on the
        ``_object`` suffix."""
        self._text_line_matrix_obj = matrix

    # ---------- per-glyph hooks (overridable in text + renderer) ----------

    def show_text(self, string: bytes) -> None:
        """Process ``string`` as a sequence of glyph codes through the
        currently active font, dispatching one :meth:`show_font_glyph`
        per code. Mirrors upstream ``PDFStreamEngine.showText(byte[])``.

        Cluster #2 ships a structural decode loop only: we walk the
        bytes, ask the active font (if any) to ``read_code`` from the
        stream so multi-byte fonts are honoured, and call
        :meth:`show_font_glyph` per code. When no font is set or the
        font lacks a ``read_code`` method we fall back to per-byte
        dispatch. Text-state mutation (advancing the text matrix by the
        glyph displacement, applying char/word spacing) lives in the
        rendering subclass — this base implementation is purely
        callback-driven so subclasses that don't care about glyph
        positioning can override :meth:`show_text_string` instead and
        ignore the glyph-level pipeline entirely."""
        font = self._get_active_font()
        codes: list[int]
        if font is not None and hasattr(font, "read_code"):
            codes = self._decode_codes_via_font(string, font)
        else:
            codes = list(string)
        for code in codes:
            displacement = self._glyph_displacement(font, code)
            self.show_font_glyph(self.get_text_matrix(), font, code, displacement)

    def _get_active_font(self) -> Any | None:
        """Return the font currently selected via ``Tf`` if the subclass
        tracks one (the base engine doesn't); ``None`` otherwise."""
        gs = self.get_graphics_state()
        if gs is None:
            return None
        # Probe a couple of common attribute shapes — subclasses are
        # free to override :meth:`_get_active_font` directly.
        text_state = getattr(gs, "text_state", None)
        if text_state is not None:
            return getattr(text_state, "font", None)
        return getattr(gs, "text_font", None)

    @staticmethod
    def _decode_codes_via_font(string: bytes, font: Any) -> list[int]:
        """Drive ``font.read_code`` over ``string`` until exhausted.

        ``read_code`` follows pypdfbox's uniform signature:
        ``(data, offset) -> (code, consumed)`` (composite or simple fonts).
        Older test doubles may still implement the legacy stream form
        ``read_code(buf) -> int`` — detected via ``TypeError`` and routed
        through a ``BytesIO`` shim so they keep working. Returns the list
        of codes (one per glyph)."""
        codes: list[int] = []
        offset = 0
        n = len(string)
        legacy_stream_form: bool | None = None
        legacy_buf: Any | None = None
        while offset < n:
            if legacy_stream_form is True:
                # Legacy stream-form font: stash a single BytesIO and walk
                # it via the stream-style return-int API.
                if legacy_buf is None:
                    import io as _stdio  # noqa: PLC0415

                    legacy_buf = _stdio.BytesIO(bytes(string[offset:]))
                pos = legacy_buf.tell()
                try:
                    code = font.read_code(legacy_buf)
                except (OSError, EOFError, ValueError):
                    break
                if code is None:
                    break
                if legacy_buf.tell() == pos:
                    break
                codes.append(int(code))
                offset += legacy_buf.tell() - pos
                continue
            try:
                result = font.read_code(string, offset)
            except TypeError:
                # Legacy stream-form font discovered.
                legacy_stream_form = True
                continue
            except (OSError, EOFError, ValueError):
                break
            if result is None:
                break
            # Tuple form: (code, consumed).
            if isinstance(result, tuple):
                code, consumed = result
                if consumed <= 0:
                    break
                codes.append(int(code))
                offset += consumed
            else:
                # Stream-style font that ignored the offset arg — treat
                # the return as a single-byte code at ``offset``.
                codes.append(int(result))
                offset += 1
        return codes

    @staticmethod
    def _glyph_displacement(font: Any | None, code: int) -> Any:
        """Return the advance vector for ``code`` if the font exposes
        one. Default returns ``None`` — subclasses with a real text
        state override :meth:`show_text` to use real geometry."""
        if font is None:
            return None
        getter = getattr(font, "get_displacement", None)
        if getter is None:
            return None
        try:
            return getter(code)
        except (OSError, ValueError, KeyError):
            return None

    def show_font_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        """Per-glyph hook invoked once per code by :meth:`show_text`.

        Mirrors upstream ``PDFStreamEngine.showFontGlyph(Matrix, PDFont,
        int, Vector)``. Base default: forwards to :meth:`show_glyph`,
        matching upstream's split where ``showFontGlyph`` is the
        font-aware overload and ``showGlyph`` is the
        font-and-graphics-state-aware overload that the rendering
        subclass overrides."""
        self.show_glyph(text_rendering_matrix, font, code, displacement)

    def show_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        """Most-derived per-glyph hook. Base no-op. The rendering
        subclass overrides to actually paint the glyph; the
        text-extraction subclass overrides to record the glyph + its
        position. Mirrors upstream ``showGlyph``."""

    def show_type3_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        """Per-Type3-glyph hook.

        Mirrors upstream's ``protected showType3Glyph(Matrix, PDType3Font,
        int, Vector)`` which looks up the matching ``PDType3CharProc``
        and re-enters dispatch via :meth:`process_type3_stream`. When
        ``font`` exposes a ``get_char_proc(code)`` method we follow that
        contract; otherwise the call is a no-op so subclasses without a
        Type3 font can ignore the hook.
        """
        if font is None:
            return
        getter = getattr(font, "get_char_proc", None)
        if getter is None:
            return
        try:
            charproc = getter(code)
        except (OSError, KeyError, ValueError):
            return
        if charproc is None:
            return
        self.process_type3_stream(charproc, text_rendering_matrix)

    # ---------- text-adjustment / coordinate helpers ----------

    def apply_text_adjustment(self, tx: float, ty: float) -> None:
        """Apply a TJ-style text-position adjustment.

        Mirrors upstream's ``protected applyTextAdjustment(float, float)``
        which translates the text matrix by ``(tx, ty)``. Cluster #2
        carries the text matrix as an opaque object on the engine; if
        the stored matrix exposes a ``translate`` method we delegate to
        it (matches the rendering-subclass ``Matrix.translate`` shape),
        otherwise the call is a no-op.
        """
        matrix = self.get_text_matrix()
        if matrix is None:
            return
        translator = getattr(matrix, "translate", None)
        if translator is None:
            return
        with contextlib.suppress(TypeError, ValueError):
            translator(tx, ty)

    def transformed_point(self, x: float, y: float) -> tuple[float, float]:
        """Transform a user-space point through the current CTM.

        Mirrors upstream's ``public Point2D.Float transformedPoint(float,
        float)``. The base engine has no concrete CTM; if the active
        graphics state exposes a ``current_transformation_matrix`` with
        a ``transform_point(x, y)`` method we delegate to it, else the
        point is returned unchanged. The
        :class:`PDFGraphicsStreamEngine` subclass overrides this hook
        with its own identity default; the rendering subclass overrides
        with the full CTM-aware transform.
        """
        gs = self.get_graphics_state()
        if gs is None:
            return (float(x), float(y))
        ctm = getattr(gs, "current_transformation_matrix", None)
        if ctm is None:
            return (float(x), float(y))
        transformer = getattr(ctm, "transform_point", None)
        if transformer is None:
            return (float(x), float(y))
        try:
            tx, ty = transformer(x, y)
        except (TypeError, ValueError):
            return (float(x), float(y))
        return (float(tx), float(ty))

    def get_default_font(self) -> Any:
        """Return a default font to fall back on when no font is selected.

        Mirrors upstream's private ``getDefaultFont`` which lazily
        instantiates ``PDType1Font(FontName.HELVETICA)``. The cluster #2
        base does not own a font tree to instantiate from; we return
        ``None`` and let :meth:`show_text` callers fall through to the
        per-byte dispatch path. Subclasses with the font tree available
        override to materialise the Helvetica fallback.
        """
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
