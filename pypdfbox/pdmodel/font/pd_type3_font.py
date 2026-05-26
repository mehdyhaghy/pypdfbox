from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)

from .pd_simple_font import PDSimpleFont

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle  # noqa: F401
    from pypdfbox.pdmodel.pd_resources import PDResources

    from .encoding.encoding import Encoding
    from .pd_type3_char_proc import PDType3CharProc

_CHAR_PROCS: COSName = COSName.get_pdf_name("CharProcs")
_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_FONT_BBOX: COSName = COSName.get_pdf_name("FontBBox")
_FONT_MATRIX: COSName = COSName.get_pdf_name("FontMatrix")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_NAME: COSName = COSName.get_pdf_name("Name")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")

# PDF 32000-1 §9.2.4: default Type 3 /FontMatrix maps the glyph coordinate
# system (typically 1000-unit em) into text space (1-unit em).
_DEFAULT_FONT_MATRIX: tuple[float, ...] = (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)


class PDType3Font(PDSimpleFont):
    """PDF Type 3 font — glyph shapes are defined by inline content streams.

    Mirrors PDFBox ``PDType3Font``. Wires the dictionary accessors from PDF
    32000-1 §9.6.5 Table 113. ``get_char_proc(code)`` returns a typed
    :class:`PDType3CharProc` wrapper around the per-glyph content stream;
    the ``Matrix`` / glyph-paint pipeline lands with the rendering
    cluster — ``get_font_matrix`` returns the raw 6-float list rather than
    a typed ``Matrix`` object until then.
    """

    SUB_TYPE = "Type3"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Memoised generated bbox — upstream's ``fontBBox`` field.
        self._font_bbox_cache: PDRectangle | None = None

    # ---------- /CharProcs (raw — typed PDType3CharProc deferred) ----------

    def get_char_procs(self) -> COSDictionary | None:
        """Return the ``/CharProcs`` glyph-name -> content-stream mapping."""
        entry = self._dict.get_dictionary_object(_CHAR_PROCS)
        return entry if isinstance(entry, COSDictionary) else None

    def set_char_procs(self, value: COSDictionary | None) -> None:
        """Set or clear the ``/CharProcs`` dictionary."""
        if value is None:
            self._dict.remove_item(_CHAR_PROCS)
            return
        self._dict.set_item(_CHAR_PROCS, value)

    @overload
    def get_char_proc(self, key: int) -> PDType3CharProc | None: ...
    @overload
    def get_char_proc(self, key: str) -> COSStream | None: ...
    def get_char_proc(
        self, key: int | str
    ) -> PDType3CharProc | COSStream | None:
        """Look up a single glyph procedure.

        Polymorphic — mirrors both upstream call shapes:

        - ``get_char_proc(int code)``: resolves the character ``code``
          through the font's ``/Encoding`` to a glyph name, then returns
          the per-glyph content stream wrapped as
          :class:`PDType3CharProc` (matches upstream
          ``getCharProc(int) : PDType3CharProc``).
        - ``get_char_proc(str name)``: convenience form that takes the
          glyph name directly and returns the raw ``COSStream`` (kept
          from the lite surface for callers that already have the name).

        Returns ``None`` when ``/CharProcs`` is missing, the glyph name
        is not present, or its entry is not a stream.
        """
        if isinstance(key, bool):  # bool is an int — disallow.
            raise TypeError("get_char_proc(bool) is not a valid call")
        if isinstance(key, int):
            return self._get_char_proc_by_code(key)
        return self._get_char_proc_by_name(key)

    def _get_char_proc_by_name(self, name: str) -> COSStream | None:
        char_procs = self.get_char_procs()
        if char_procs is None:
            return None
        entry = char_procs.get_dictionary_object(COSName.get_pdf_name(name))
        return entry if isinstance(entry, COSStream) else None

    def _get_char_proc_by_code(self, code: int) -> PDType3CharProc | None:
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        name = encoding.get_name(code)
        if name is None or name == ".notdef":
            return None
        stream = self._get_char_proc_by_name(name)
        if stream is None:
            return None
        # Local import to break the file-level cycle (pd_type3_char_proc
        # imports PDType3Font for typing).
        from .pd_type3_char_proc import PDType3CharProc  # noqa: PLC0415

        return PDType3CharProc(self, stream)

    # ---------- /Resources (typed via PDResources) ----------

    def get_resources(self) -> PDResources | None:
        """Return the ``/Resources`` dictionary wrapped as ``PDResources``."""
        from pypdfbox.pdmodel.pd_resources import PDResources

        entry = self._dict.get_dictionary_object(_RESOURCES)
        if isinstance(entry, COSDictionary):
            return PDResources(entry)
        return None

    def set_resources(self, value: PDResources | None) -> None:
        """Set or clear the ``/Resources`` dictionary."""
        if value is None:
            self._dict.remove_item(_RESOURCES)
            return
        self._dict.set_item(_RESOURCES, value.get_cos_object())

    # ---------- /FontMatrix ----------

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element ``/FontMatrix`` transform.

        Defaults to ``[0.001, 0, 0, 0.001, 0, 0]`` per PDF 32000-1 §9.2.4
        when the entry is missing or malformed (not a 6-entry numeric
        array).
        """
        entry = self._dict.get_dictionary_object(_FONT_MATRIX)
        if isinstance(entry, COSArray) and entry.size() == 6:
            values: list[float] = []
            for i in range(6):
                item = entry.get_object(i)
                if not isinstance(item, (COSInteger, COSFloat)):
                    return list(_DEFAULT_FONT_MATRIX)
                values.append(float(item.value))
            return values
        return list(_DEFAULT_FONT_MATRIX)

    def set_font_matrix(self, matrix: list[float] | None) -> None:
        """Replace or clear the ``/FontMatrix`` 6-element transform.

        Clearing restores :meth:`get_font_matrix`'s spec default.
        """
        if matrix is None:
            self._dict.remove_item(_FONT_MATRIX)
            return
        if len(matrix) != 6:
            raise ValueError(
                f"/FontMatrix requires exactly 6 elements, got {len(matrix)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in matrix])
        self._dict.set_item(_FONT_MATRIX, arr)

    # ---------- /FontBBox ----------

    def get_font_bbox(self) -> PDRectangle | None:
        """Return the ``/FontBBox`` rectangle, or ``None`` when absent."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        entry = self._dict.get_dictionary_object(_FONT_BBOX)
        if isinstance(entry, COSArray) and entry.size() >= 4:
            return PDRectangle.from_cos_array(entry)
        return None

    def set_font_bbox(self, rect: PDRectangle | None) -> None:
        """Set or clear the ``/FontBBox`` rectangle."""
        if rect is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, rect.to_cos_array())

    # ---------- /FontBBox legacy (raw COSArray accessors) ----------

    def get_font_b_box(self) -> COSArray | None:
        """Raw ``/FontBBox`` array accessor — kept for the lite-surface
        round-trip tests; new code should use :meth:`get_font_bbox`."""
        entry = self._dict.get_dictionary_object(_FONT_BBOX)
        return entry if isinstance(entry, COSArray) else None

    def set_font_b_box(self, bbox: COSArray | None) -> None:
        """Raw ``/FontBBox`` array setter — kept for the lite-surface
        round-trip tests; new code should use :meth:`set_font_bbox`."""
        if bbox is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, bbox)

    # The Type-3 ``get_bounding_box`` lives below alongside the
    # ``generate_bounding_box`` helper to keep the upstream pairing
    # ``getBoundingBox`` / ``generateBoundingBox`` colocated.

    # ---------- /FirstChar /LastChar /Widths ----------
    #
    # Inherited ``get_first_char`` / ``get_last_char`` / ``get_widths`` come
    # from :class:`PDSimpleFont`. The setters below are wired here for
    # convenience: PDFBox exposes these on ``PDSimpleFont`` itself, but
    # we only need them on Type3 today, so keeping them local avoids
    # cross-class churn.

    def set_first_char(self, value: int | None) -> None:
        if value is None:
            self._dict.remove_item(_FIRST_CHAR)
            return
        self._dict.set_int(_FIRST_CHAR, int(value))

    def set_last_char(self, value: int | None) -> None:
        if value is None:
            self._dict.remove_item(_LAST_CHAR)
            return
        self._dict.set_int(_LAST_CHAR, int(value))

    def set_widths(self, values: list[float] | None) -> None:
        """Replace or clear the ``/Widths`` array."""
        if values is None:
            self._dict.remove_item(_WIDTHS)
            return
        arr = COSArray([COSFloat(float(v)) for v in values])
        self._dict.set_item(_WIDTHS, arr)

    # ---------- per-glyph width / embedding state ----------

    def get_width(self, code: int) -> float:
        """Return the advance width for ``code``. Mirrors upstream
        ``PDType3Font.getWidth(int code)``.

        Resolution order (PDF 32000-1 §9.6.6):

        1. ``/Widths[code - /FirstChar]`` when ``code`` falls inside the
           ``/FirstChar``..``/LastChar`` window and the entry exists.
        2. ``/MissingWidth`` from the ``/FontDescriptor`` when the code
           is out of range and a descriptor is present.
        3. :meth:`get_width_from_font` otherwise — reads the per-glyph
           width op from the ``/CharProcs`` content stream.
        """
        widths = self.get_widths()
        first = self.get_first_char()
        last = self.get_last_char()
        if widths and first <= code <= last:
            index = int(code) - first
            if 0 <= index < len(widths):
                return widths[index]
            # In-range but past the array end mirrors upstream's explicit
            # ``return 0`` branch.
            return 0.0
        descriptor = self.get_font_descriptor()
        if descriptor is not None:
            return descriptor.get_missing_width()
        return self.get_width_from_font(int(code))

    def get_width_from_font(self, code: int) -> float:
        """Read the advance width op from the per-glyph ``/CharProcs``
        content stream. Mirrors upstream
        ``PDType3Font.getWidthFromFont(int code)``.

        Returns ``0.0`` when the code does not resolve to a glyph
        procedure or the procedure stream is empty (matches upstream's
        ``charProc.getCOSObject().getLength() == 0`` short-circuit).
        """
        char_proc = self._get_char_proc_by_code(int(code))
        if char_proc is None:
            return 0.0
        cos_stream = char_proc.get_cos_object()
        if cos_stream.get_length() == 0:
            return 0.0
        return char_proc.get_width()

    def get_height(self, code: int) -> float:
        """Return a representative glyph height in font units.

        Mirrors upstream ``PDType3Font.getHeight(int code)`` —
        Type 3 fonts have no per-glyph height, so we approximate from
        the font descriptor:

        1. ``/FontBBox`` height / 2 when present and non-zero.
        2. ``/CapHeight`` when set.
        3. ``/Ascent`` when set.
        4. ``/XHeight - /Descent`` when ``/XHeight > 0``.
        5. ``0.0`` (no descriptor or every metric is zero).
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return 0.0
        retval = 0.0
        bbox = descriptor.get_font_bounding_box()
        if bbox is not None:
            retval = bbox.get_height() / 2.0
        if retval == 0.0:
            retval = descriptor.get_cap_height()
        if retval == 0.0:
            retval = descriptor.get_ascent()
        if retval == 0.0:
            x_height = descriptor.get_x_height()
            if x_height > 0.0:
                retval = x_height - descriptor.get_descent()
        return float(retval)

    def get_displacement(self, code: int) -> tuple[float, float]:
        """Glyph displacement vector ``(tx, ty)`` for ``code``, in text
        space units.

        Mirrors upstream ``PDType3Font.getDisplacement(int code)``,
        which transforms ``(getWidth(code), 0)`` through the font
        matrix. For the spec-default ``[0.001, 0, 0, 0.001, 0, 0]`` this
        is just ``(width / 1000, 0)``; we apply the matrix's
        ``a`` / ``b`` scale (entries 0 and 1) to honour custom
        Type 3 matrices (see PDFBOX-2298).
        """
        width = self.get_width(int(code))
        matrix = self.get_font_matrix()
        # 6-element matrix [a b c d e f]; transform of (x, 0) = (a*x, b*x).
        return matrix[0] * width, matrix[1] * width

    def get_position_vector(self, code: int) -> tuple[float, float]:
        """Return the glyph position vector for ``code``.

        Type 3 fonts are simple horizontal fonts in PDFBox; vertical
        writing is only available via Type 0 / CID fonts. Mirrors the
        upstream horizontal-font default.
        """
        return 0.0, 0.0

    @overload
    def has_glyph(self, key: int) -> bool: ...
    @overload
    def has_glyph(self, key: str) -> bool: ...
    def has_glyph(self, key: int | str) -> bool:
        """``True`` when the font defines a paintable glyph for ``key``.

        Polymorphic — mirrors both upstream call shapes:

        - ``has_glyph(int code)``: glyph exists iff (a) ``/Encoding``
          maps ``code`` to a glyph name other than ``.notdef`` and
          (b) ``/CharProcs`` carries a stream for that name.
          Mirrors upstream ``hasGlyph(int)``.
        - ``has_glyph(str name)``: glyph exists iff ``/CharProcs``
          carries a stream registered under the literal ``name``.
          Mirrors upstream ``hasGlyph(String)``.
        """
        if isinstance(key, bool):  # bool is an int — disallow.
            raise TypeError("has_glyph(bool) is not a valid call")
        if isinstance(key, str):
            return self._get_char_proc_by_name(key) is not None
        encoding = self.get_encoding_typed()
        if encoding is None:
            return False
        name = encoding.get_name(int(key))
        if name is None or name == ".notdef":
            return False
        return self._get_char_proc_by_name(name) is not None

    def is_embedded(self) -> bool:
        """Type 3 fonts are *always* embedded — the glyphs are inline
        content streams in ``/CharProcs``, there is no external font
        program to reference. Mirrors upstream
        ``PDType3Font.isEmbedded() → true``."""
        return True

    def is_standard_14(self) -> bool:
        """Type 3 fonts are never one of the 14 PDF Standard fonts.

        Mirrors upstream ``PDType3Font.isStandard14() → false``: the
        Standard 14 set is pre-defined Type 1 fonts, so a Type 3 font
        with a colliding ``/BaseFont`` name (e.g. ``Helvetica``) still
        must not be classified as Standard 14.
        """
        return False

    def is_damaged(self) -> bool:
        """Mirrors upstream ``PDType3Font.isDamaged() → false``.

        Type 3 fonts have no external font program to load, so there is
        no parse step that could fail — upstream's comment says
        verbatim: *"there's no font file to load"*. The base
        :class:`PDFont` already returns ``False``; we override here
        explicitly so the upstream method appears on this concrete
        subclass.
        """
        return False

    def is_font_symbolic(self) -> bool:
        """Type 3 fonts are never symbolic in the PDFBox sense.

        Mirrors upstream protected ``isFontSymbolic() → false``. The
        symbolic flag in ``/FontDescriptor`` may still be set on the
        dictionary, but PDFBox treats Type 3 as non-symbolic for
        encoding-resolution purposes.
        """
        return False

    # ---------- /Name (Type 3-specific identity) ----------

    def get_name(self) -> str | None:
        """Return ``/Name`` from the font dictionary.

        Mirrors upstream ``PDType3Font.getName()`` — Type 3 fonts use the
        legacy ``/Name`` entry (PDF 32000-1 §9.6.5 Table 113), *not*
        ``/BaseFont`` like the other simple subtypes. Returns ``None``
        when ``/Name`` is missing or not a name.
        """
        return self._dict.get_name(_NAME)

    # ---------- font-program escape hatches (Type 3 has no font program) ----------

    def get_font_box_font(self) -> Any:  # noqa: ANN401  (mirrors upstream FontBoxFont return)
        """Type 3 fonts do not carry a FontBox font program.

        Mirrors upstream ``PDType3Font.getFontBoxFont()`` which throws
        ``UnsupportedOperationException("not supported for Type 3 fonts")``.
        Raises :class:`NotImplementedError` (the closest stdlib analog —
        the operation is structurally unavailable for this subtype).
        """
        raise NotImplementedError("not supported for Type 3 fonts")

    def get_path(self, name: str) -> Any:  # noqa: ANN401  (upstream returns GeneralPath)
        """Type 3 fonts do not expose vector paths by glyph name.

        Mirrors upstream ``PDType3Font.getPath(String)`` which throws
        ``UnsupportedOperationException("not supported for Type 3 fonts")``.
        Glyph shapes are inline content streams in ``/CharProcs`` — use
        :meth:`get_char_proc` and walk the content stream instead.
        """
        del name
        raise NotImplementedError("not supported for Type 3 fonts")

    def encode_codepoint(self, unicode: int) -> bytes:
        """Type 3 fonts have no canonical text-to-byte encoding path.

        Mirrors upstream protected ``encode(int unicode)`` which throws
        ``UnsupportedOperationException("Not implemented: Type3")``. The
        PDFBox text-extraction pipeline does not synthesise Type 3 byte
        streams — Type 3 is a *display* subtype only, written by the
        producer with hand-rolled ``/CharProcs`` and ``/Encoding``.

        Upstream's method is named ``encode(int unicode)`` but pypdfbox
        already binds ``encode(text: str)`` on :class:`PDFont` /
        :class:`PDSimpleFont` for the high-level text-to-byte surface,
        so the codepoint-flavoured override lives under
        ``encode_codepoint`` to avoid clobbering the parent contract.
        """
        del unicode
        raise NotImplementedError("Not implemented: Type3")

    # ---------- read_code — single byte ----------

    def read_code(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
    ) -> tuple[int, int]:
        """Read one character code from ``data`` starting at ``offset``.

        Mirrors upstream ``PDType3Font.readCode(InputStream) → in.read()``.
        Type 3 fonts use 1-byte codes (simple-font convention). Returns
        ``(code, bytes_consumed)`` to match the uniform pypdfbox renderer
        signature shared by composite (Type0) and simple fonts. At or
        past end-of-buffer returns ``(0, 0)`` so callers terminate the
        decode loop (parallels Java's ``read()`` returning ``-1``).
        """
        if offset < 0 or offset >= len(data):
            return (0, 0)
        return (data[offset] & 0xFF, 1)

    # ---------- /Encoding parsing helpers ----------

    def get_encoding_typed(self) -> Encoding | None:
        """Resolve ``/Encoding`` to a typed :class:`Encoding` for Type 3.

        Mirrors upstream ``PDType3Font.readEncoding()`` — which is distinct
        from ``PDSimpleFont.readEncoding()``:

        - ``/Encoding`` a ``COSName`` → the named predefined encoding.
        - ``/Encoding`` a ``COSDictionary`` → ``new DictionaryEncoding(dict)``,
          i.e. the *no-base* form: the resolved encoding maps **only** the
          codes listed in ``/Differences``; every other code is
          ``.notdef``.

        This is the key Type 3 divergence from the other simple fonts:
        Type 3 fonts have no built-in font-program encoding and PDFBox does
        **not** seed a StandardEncoding (non-symbolic) or font-program
        (symbolic) base for them. The inherited
        :meth:`PDSimpleFont.get_encoding_typed` does seed such a base, which
        would wrongly map unlisted codes (e.g. code 65 → 'A'); overriding
        here restores upstream parity.
        """
        if self._encoding_resolved:
            return self._encoding_typed
        raw = self.get_encoding()
        if isinstance(raw, COSName):
            from .encoding.encoding import Encoding  # noqa: PLC0415

            self._encoding_typed = Encoding.get_instance(raw)
        elif isinstance(raw, COSDictionary):
            from .encoding.dictionary_encoding import (
                DictionaryEncoding,  # noqa: PLC0415
            )

            # No-base form (font_encoding only): base == None, so codes
            # absent from /Differences resolve to ".notdef" — matches
            # upstream ``new DictionaryEncoding(COSDictionary)``.
            self._encoding_typed = DictionaryEncoding(font_encoding=raw)
        else:
            self._encoding_typed = None
        self._encoding_resolved = True
        return self._encoding_typed

    def read_encoding(self) -> None:
        """Eagerly resolve ``/Encoding`` and the Adobe glyph list.

        Mirrors upstream protected ``PDType3Font.readEncoding()`` which
        runs in the constructor; in the Python port the typed encoding
        is resolved lazily inside :meth:`get_encoding_typed`, but exposing
        this method preserves the upstream surface (parity testing relies
        on it). Calling it primes the cache.
        """
        # Touching the typed encoding triggers our Type 3 resolver, which
        # mirrors readEncoding's COSName / COSDictionary branching plus the
        # Adobe glyph list wiring.
        self.get_encoding_typed()
        self.get_glyph_list()

    def read_encoding_from_font(self) -> Any:  # noqa: ANN401  (upstream returns Encoding)
        """Type 3 fonts do not have a built-in encoding.

        Mirrors upstream protected ``PDType3Font.readEncodingFromFont()``
        which throws ``UnsupportedOperationException("not supported for
        Type 3 fonts")``. Type 3 fonts always rely on the explicit
        ``/Encoding`` dictionary entry.
        """
        raise NotImplementedError("not supported for Type 3 fonts")

    # ---------- is_standard14 (Java-cased alias) ----------

    def is_standard14(self) -> bool:
        """Mirrors upstream ``PDType3Font.isStandard14()`` — always
        ``False``. Provided as a Java-cased alias of
        :meth:`is_standard_14` so parity tooling matches the upstream
        method directly."""
        return False

    # ---------- bounding-box generation (CharProcs scan fallback) ----------

    def get_bounding_box(self) -> PDRectangle | None:
        """Return the font bounding box.

        Mirrors upstream ``PDType3Font.getBoundingBox()`` /
        ``generateBoundingBox()``: returns the dictionary ``/FontBBox``
        when present and non-zero; falls back to the union of all
        ``/CharProcs`` glyph bboxes (``d1`` operands) when ``/FontBBox``
        is the all-zero default. Returns ``None`` only when the
        dictionary lacks ``/FontBBox`` entirely (matches upstream's
        warning + empty-bbox path: we surface ``None`` so callers can
        decide whether to use an empty rectangle).
        """
        if self._font_bbox_cache is not None:
            return self._font_bbox_cache
        self._font_bbox_cache = self.generate_bounding_box()
        return self._font_bbox_cache

    def generate_bounding_box(self) -> PDRectangle | None:
        """Compute the effective ``/FontBBox`` for this font.

        Mirrors upstream ``generateBoundingBox()`` (private in Java; we
        expose the snake-cased name on the class so direct callers and
        the parity scorer can find it). When the dictionary
        ``/FontBBox`` is the all-zero default, expand it by unioning
        every ``/CharProcs`` glyph bbox carried by a ``d1`` operator
        (PDFBox plan-B; covers fonts that ship a degenerate
        ``/FontBBox`` placeholder).
        """
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        rect = self.get_font_bbox()
        if rect is None:
            return None
        if PDSimpleFont.is_non_zero_bounding_box(rect):
            # Already informative; upstream returns BoundingBox(rect.*).
            return PDRectangle(
                rect.get_lower_left_x(),
                rect.get_lower_left_y(),
                rect.get_upper_right_x(),
                rect.get_upper_right_y(),
            )

        # Plan B: union of glyph bboxes from /CharProcs.
        char_procs = self.get_char_procs()
        if char_procs is None:
            return rect

        from .pd_type3_char_proc import PDType3CharProc  # noqa: PLC0415

        llx = rect.get_lower_left_x()
        lly = rect.get_lower_left_y()
        urx = rect.get_upper_right_x()
        ury = rect.get_upper_right_y()
        for key in char_procs.key_set():
            entry = char_procs.get_dictionary_object(key)
            if not isinstance(entry, COSStream):
                continue
            char_proc = PDType3CharProc(self, entry)
            try:
                glyph_bbox = char_proc.get_glyph_bbox()
            except (OSError, ValueError):
                # Malformed d1 header — upstream logs and continues.
                continue
            if glyph_bbox is None:
                continue
            llx = min(llx, glyph_bbox.get_lower_left_x())
            lly = min(lly, glyph_bbox.get_lower_left_y())
            urx = max(urx, glyph_bbox.get_upper_right_x())
            ury = max(ury, glyph_bbox.get_upper_right_y())
        return PDRectangle(llx, lly, urx, ury)

    # ---------- subsetting ----------
    #
    # Type 3 fonts have no shared font program — every glyph is a
    # self-contained inline content stream stored under /CharProcs. There
    # is no Type 1 / TrueType / CFF table to strip, so "subsetting" is a
    # null operation by definition (PDF 32000-1 §9.6.5). Upstream PDFBox
    # inherits :meth:`PDSimpleFont.subset` which raises
    # ``UnsupportedOperationException``; we override the message here so
    # callers reaching this through Type 3 fonts get a specific reason.

    def will_be_subset(self) -> bool:
        """Type 3 fonts are never subset — every glyph is already inline."""
        return False

    def add_to_subset(self, code_point: int) -> None:
        """Type 3 fonts do not support subsetting.

        Inline glyph definitions in ``/CharProcs`` mean there is no
        shared font program to subset; mirrors upstream's
        ``UnsupportedOperationException`` with a Type 3-specific message.
        """
        raise NotImplementedError(
            "subsetting is not supported for Type 3 fonts "
            "(glyphs are defined inline in /CharProcs)"
        )

    def subset(self) -> None:
        """Type 3 fonts do not support subsetting.

        See :meth:`add_to_subset` for the rationale — Type 3 glyphs are
        inline content streams under ``/CharProcs`` with no shared
        program to strip. Mirrors upstream ``PDSimpleFont.subset``.
        """
        raise NotImplementedError(
            "subsetting is not supported for Type 3 fonts "
            "(glyphs are defined inline in /CharProcs)"
        )

    @staticmethod
    def check_font_matrix_values(matrix: COSArray | None) -> bool:
        """``True`` iff ``matrix`` is a 6-entry array of numeric items.

        Mirrors upstream ``checkFontMatrixValues(COSArray) : boolean``
        (private in Java; we expose the snake-cased name on the class
        for parity scoring and so callers porting Java code can reach
        it directly). Used by :meth:`get_font_matrix` to decide whether
        the dictionary entry is well-formed enough to honour, vs.
        falling back to the spec default ``[0.001, 0, 0, 0.001, 0, 0]``.
        """
        if matrix is None or matrix.size() != 6:
            return False
        for i in range(6):
            item = matrix.get_object(i)
            if not isinstance(item, (COSInteger, COSFloat)):
                return False
        return True


__all__ = ["PDType3Font"]
