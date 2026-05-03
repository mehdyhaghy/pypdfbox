from __future__ import annotations

from enum import StrEnum

from pypdfbox.cos import COSArray, COSDictionary, COSName

# ---------- viewer-prefs key constants (PDF 32000-1:2008 §12.2, Table 150) ----------

_HIDE_TOOLBAR: COSName = COSName.get_pdf_name("HideToolbar")
_HIDE_MENUBAR: COSName = COSName.get_pdf_name("HideMenubar")
_HIDE_WINDOWUI: COSName = COSName.get_pdf_name("HideWindowUI")
_FIT_WINDOW: COSName = COSName.get_pdf_name("FitWindow")
_CENTER_WINDOW: COSName = COSName.get_pdf_name("CenterWindow")
_DISPLAY_DOC_TITLE: COSName = COSName.get_pdf_name("DisplayDocTitle")
_PICK_TRAY_BY_PDF_SIZE: COSName = COSName.get_pdf_name("PickTrayByPDFSize")
_NON_FULL_SCREEN_PAGE_MODE: COSName = COSName.get_pdf_name("NonFullScreenPageMode")
_DIRECTION: COSName = COSName.get_pdf_name("Direction")
_VIEW_AREA: COSName = COSName.get_pdf_name("ViewArea")
_VIEW_CLIP: COSName = COSName.get_pdf_name("ViewClip")
_PRINT_AREA: COSName = COSName.get_pdf_name("PrintArea")
_PRINT_CLIP: COSName = COSName.get_pdf_name("PrintClip")
_DUPLEX: COSName = COSName.get_pdf_name("Duplex")
_PRINT_SCALING: COSName = COSName.get_pdf_name("PrintScaling")
_NUM_COPIES: COSName = COSName.get_pdf_name("NumCopies")
_PRINT_PAGE_RANGE: COSName = COSName.get_pdf_name("PrintPageRange")
_ENFORCE: COSName = COSName.get_pdf_name("Enforce")


class PDViewerPreferences:
    """
    Wraps the catalog's ``/ViewerPreferences`` dictionary. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences``.

    Boolean accessors return PDFBox's documented defaults (``False``) when
    the entry is absent. Name-valued accessors return the spec default
    (e.g. ``CropBox`` for boundary fields, ``UseNone`` for non-full-screen
    page mode) — matching upstream signatures that bake the default in.

    PDF 2.0 (32000-2) and PDF 32000-1 Table 150 entries beyond what
    upstream PDFBox 3.0 exposes (``PickTrayByPDFSize``, ``NumCopies``,
    ``PrintPageRange``, ``Enforce``) are surfaced here as enrichment.
    """

    # ---------- nested enumerations (mirror upstream's Java enums) ----------

    class NON_FULL_SCREEN_PAGE_MODE(StrEnum):
        UseNone = "UseNone"
        UseOutlines = "UseOutlines"
        UseThumbs = "UseThumbs"
        UseOC = "UseOC"

    class READING_DIRECTION(StrEnum):
        L2R = "L2R"
        R2L = "R2L"

    class BOUNDARY(StrEnum):
        MediaBox = "MediaBox"
        CropBox = "CropBox"
        BleedBox = "BleedBox"
        TrimBox = "TrimBox"
        ArtBox = "ArtBox"

    class DUPLEX(StrEnum):
        Simplex = "Simplex"
        DuplexFlipShortEdge = "DuplexFlipShortEdge"
        DuplexFlipLongEdge = "DuplexFlipLongEdge"

    class PRINT_SCALING(StrEnum):
        None_ = "None"  # ``None`` is reserved in Python; expose under ``None_``.
        AppDefault = "AppDefault"

    # ---------- class-level string constants (mirror upstream PDFBox) ----------
    # Upstream exposes these alongside the nested enums for callers that prefer
    # plain string constants. Values are the exact /Name token strings written
    # to the PDF dictionary (PDF 32000-1 §12.2 Table 150).

    NON_FS_USE_NONE: str = "UseNone"
    NON_FS_USE_OUTLINES: str = "UseOutlines"
    NON_FS_USE_THUMBS: str = "UseThumbs"
    NON_FS_USE_OC: str = "UseOC"

    # Long-form upstream-style aliases for ``/NonFullScreenPageMode`` tokens.
    # Mirror upstream's verbose constant naming style for callers porting
    # from Java code that references the long-form names.
    NON_FULL_SCREEN_PAGE_MODE_USE_NONE: str = "UseNone"
    NON_FULL_SCREEN_PAGE_MODE_USE_OUTLINES: str = "UseOutlines"
    NON_FULL_SCREEN_PAGE_MODE_USE_THUMBS: str = "UseThumbs"
    NON_FULL_SCREEN_PAGE_MODE_USE_OC: str = "UseOC"

    DIRECTION_L2R: str = "L2R"
    DIRECTION_R2L: str = "R2L"

    # Long-form upstream-style aliases for ``/Direction`` tokens.
    READING_DIRECTION_L2R: str = "L2R"
    READING_DIRECTION_R2L: str = "R2L"

    PRINT_SCALING_NONE: str = "None"
    PRINT_SCALING_APPDEFAULT: str = "AppDefault"
    # Underscored alias mirroring upstream's two-word ``AppDefault``.
    PRINT_SCALING_APP_DEFAULT: str = "AppDefault"

    DUPLEX_SIMPLEX: str = "Simplex"
    DUPLEX_DUPLEX_FLIP_SHORT_EDGE: str = "DuplexFlipShortEdge"
    DUPLEX_DUPLEX_FLIP_LONG_EDGE: str = "DuplexFlipLongEdge"
    # Short-form aliases (drop the redundant ``DUPLEX_DUPLEX_`` prefix on
    # the flip variants — easier on the eyes when callers chain enum-style
    # lookups but still want the plain string token).
    DUPLEX_FLIP_SHORT_EDGE: str = "DuplexFlipShortEdge"
    DUPLEX_FLIP_LONG_EDGE: str = "DuplexFlipLongEdge"

    BOUNDARY_MEDIA_BOX: str = "MediaBox"
    BOUNDARY_CROP_BOX: str = "CropBox"
    BOUNDARY_BLEED_BOX: str = "BleedBox"
    BOUNDARY_TRIM_BOX: str = "TrimBox"
    BOUNDARY_ART_BOX: str = "ArtBox"

    # ---------- construction ----------

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        self._prefs = dict_ if dict_ is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._prefs

    # ---------- boolean flags ----------

    def hide_toolbar(self) -> bool:
        return self._prefs.get_boolean(_HIDE_TOOLBAR, False)

    def set_hide_toolbar(self, value: bool) -> None:
        self._prefs.set_boolean(_HIDE_TOOLBAR, value)

    # Upstream-named accessor (``isHideToolbar`` → ``is_hide_toolbar``).
    def is_hide_toolbar(self) -> bool:
        return self.hide_toolbar()

    # Upstream-named accessor (``getHideToolbar`` → ``get_hide_toolbar``).
    def get_hide_toolbar(self) -> bool:
        return self.hide_toolbar()

    def hide_menubar(self) -> bool:
        return self._prefs.get_boolean(_HIDE_MENUBAR, False)

    def set_hide_menubar(self, value: bool) -> None:
        self._prefs.set_boolean(_HIDE_MENUBAR, value)

    def is_hide_menubar(self) -> bool:
        return self.hide_menubar()

    def get_hide_menubar(self) -> bool:
        return self.hide_menubar()

    def hide_window_ui(self) -> bool:
        return self._prefs.get_boolean(_HIDE_WINDOWUI, False)

    def set_hide_window_ui(self, value: bool) -> None:
        self._prefs.set_boolean(_HIDE_WINDOWUI, value)

    def is_hide_window_ui(self) -> bool:
        return self.hide_window_ui()

    def get_hide_window_ui(self) -> bool:
        return self.hide_window_ui()

    def fit_window(self) -> bool:
        return self._prefs.get_boolean(_FIT_WINDOW, False)

    def set_fit_window(self, value: bool) -> None:
        self._prefs.set_boolean(_FIT_WINDOW, value)

    def is_fit_window(self) -> bool:
        return self.fit_window()

    def get_fit_window(self) -> bool:
        return self.fit_window()

    def center_window(self) -> bool:
        return self._prefs.get_boolean(_CENTER_WINDOW, False)

    def set_center_window(self, value: bool) -> None:
        self._prefs.set_boolean(_CENTER_WINDOW, value)

    def is_center_window(self) -> bool:
        return self.center_window()

    def get_center_window(self) -> bool:
        return self.center_window()

    def display_doc_title(self) -> bool:
        return self._prefs.get_boolean(_DISPLAY_DOC_TITLE, False)

    def set_display_doc_title(self, value: bool) -> None:
        self._prefs.set_boolean(_DISPLAY_DOC_TITLE, value)

    def is_display_doc_title(self) -> bool:
        return self.display_doc_title()

    def get_display_doc_title(self) -> bool:
        return self.display_doc_title()

    def pick_tray_by_pdf_size(self) -> bool:
        return self._prefs.get_boolean(_PICK_TRAY_BY_PDF_SIZE, False)

    def set_pick_tray_by_pdf_size(self, value: bool) -> None:
        self._prefs.set_boolean(_PICK_TRAY_BY_PDF_SIZE, value)

    def is_pick_tray_by_pdf_size(self) -> bool:
        return self.pick_tray_by_pdf_size()

    def get_pick_tray_by_pdf_size(self) -> bool:
        return self.pick_tray_by_pdf_size()

    # ---------- name-valued accessors (with documented defaults) ----------

    def get_non_full_screen_page_mode(self) -> str:
        return self._prefs.get_name(
            _NON_FULL_SCREEN_PAGE_MODE,
            self.NON_FULL_SCREEN_PAGE_MODE.UseNone.value,
        ) or self.NON_FULL_SCREEN_PAGE_MODE.UseNone.value

    def set_non_full_screen_page_mode(
        self, value: NON_FULL_SCREEN_PAGE_MODE | str | None
    ) -> None:
        if value is None:
            self._prefs.remove_item(_NON_FULL_SCREEN_PAGE_MODE)
        else:
            self._prefs.set_name(_NON_FULL_SCREEN_PAGE_MODE, str(value))

    def get_reading_direction(self) -> str:
        return self._prefs.get_name(
            _DIRECTION, self.READING_DIRECTION.L2R.value
        ) or self.READING_DIRECTION.L2R.value

    def set_reading_direction(
        self, value: READING_DIRECTION | str | None
    ) -> None:
        if value is None:
            self._prefs.remove_item(_DIRECTION)
        else:
            self._prefs.set_name(_DIRECTION, str(value))

    # Upstream-named accessors (``getDirection`` / ``setDirection``).
    def get_direction(self) -> str:
        return self.get_reading_direction()

    def set_direction(self, value: READING_DIRECTION | str | None) -> None:
        self.set_reading_direction(value)

    def get_view_area(self) -> str:
        return self._prefs.get_name(
            _VIEW_AREA, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_view_area(self, value: BOUNDARY | str | None) -> None:
        if value is None:
            self._prefs.remove_item(_VIEW_AREA)
        else:
            self._prefs.set_name(_VIEW_AREA, str(value))

    def get_view_clip(self) -> str:
        return self._prefs.get_name(
            _VIEW_CLIP, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_view_clip(self, value: BOUNDARY | str | None) -> None:
        if value is None:
            self._prefs.remove_item(_VIEW_CLIP)
        else:
            self._prefs.set_name(_VIEW_CLIP, str(value))

    def get_print_area(self) -> str:
        return self._prefs.get_name(
            _PRINT_AREA, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_print_area(self, value: BOUNDARY | str | None) -> None:
        if value is None:
            self._prefs.remove_item(_PRINT_AREA)
        else:
            self._prefs.set_name(_PRINT_AREA, str(value))

    def get_print_clip(self) -> str:
        return self._prefs.get_name(
            _PRINT_CLIP, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_print_clip(self, value: BOUNDARY | str | None) -> None:
        if value is None:
            self._prefs.remove_item(_PRINT_CLIP)
        else:
            self._prefs.set_name(_PRINT_CLIP, str(value))

    def get_duplex(self) -> str | None:
        # Upstream returns null when /Duplex is absent (no spec default).
        return self._prefs.get_name(_DUPLEX)

    def set_duplex(self, value: DUPLEX | str | None) -> None:
        if value is None:
            self._prefs.remove_item(_DUPLEX)
        else:
            self._prefs.set_name(_DUPLEX, str(value))

    def get_print_scaling(self) -> str:
        return self._prefs.get_name(
            _PRINT_SCALING, self.PRINT_SCALING.AppDefault.value
        ) or self.PRINT_SCALING.AppDefault.value

    def set_print_scaling(self, value: PRINT_SCALING | str | None) -> None:
        if value is None:
            self._prefs.remove_item(_PRINT_SCALING)
        else:
            self._prefs.set_name(_PRINT_SCALING, str(value))

    # ---------- numeric / array accessors (PDF 32000-1 / 32000-2 enrichment) ----------

    def get_num_copies(self) -> int:
        # PDF 32000-1 Table 150: default value is 1.
        v = self._prefs.get_int(_NUM_COPIES, 1)
        return v if v >= 1 else 1

    def get_num_copies_raw(self) -> int | None:
        """Return the raw ``/NumCopies`` integer (no clamping, no spec
        default). Returns ``None`` when the entry is absent. Useful when a
        caller wants to detect malformed producer values that
        ``get_num_copies`` would otherwise hide behind the ``1`` clamp."""
        if not self._prefs.contains_key(_NUM_COPIES):
            return None
        return self._prefs.get_int(_NUM_COPIES, 1)

    def set_num_copies(self, value: int | None) -> None:
        if value is None:
            self._prefs.remove_item(_NUM_COPIES)
            return
        self._prefs.set_int(_NUM_COPIES, value)

    def get_print_page_range(self) -> COSArray | None:
        """Raw ``/PrintPageRange`` array — pairs of 1-based page numbers
        (start, end). Returns ``None`` when absent."""
        v = self._prefs.get_dictionary_object(_PRINT_PAGE_RANGE)
        return v if isinstance(v, COSArray) else None

    def set_print_page_range(self, value: COSArray | None) -> None:
        if value is None:
            self._prefs.remove_item(_PRINT_PAGE_RANGE)
        else:
            self._prefs.set_item(_PRINT_PAGE_RANGE, value)

    def get_print_page_range_pairs(self) -> list[tuple[int, int]]:
        """Decode ``/PrintPageRange`` as a list of ``(start, end)`` 1-based
        page-number pairs. Returns an empty list when the entry is absent or
        contains an odd number of elements (per PDF 32000-2 §12.4.4: invalid
        ranges shall be ignored)."""
        arr = self.get_print_page_range()
        if arr is None:
            return []
        n = arr.size()
        if n % 2 != 0:
            return []
        out: list[tuple[int, int]] = []
        for i in range(0, n, 2):
            out.append((arr.get_int(i), arr.get_int(i + 1)))
        return out

    def set_print_page_range_pairs(
        self, pairs: list[tuple[int, int]] | None
    ) -> None:
        """Encode a list of ``(start, end)`` 1-based page-number pairs into
        ``/PrintPageRange``. Passing ``None`` or an empty list removes the
        entry."""
        if not pairs:
            self._prefs.remove_item(_PRINT_PAGE_RANGE)
            return
        flat: list[int] = []
        for start, end in pairs:
            flat.append(int(start))
            flat.append(int(end))
        self._prefs.set_item(_PRINT_PAGE_RANGE, COSArray.of_cos_integers(flat))

    def get_enforce(self) -> COSArray | None:
        """Raw ``/Enforce`` array (PDF 2.0 Table 150) — names of viewer
        preferences that shall be enforced. Returns ``None`` when absent."""
        v = self._prefs.get_dictionary_object(_ENFORCE)
        return v if isinstance(v, COSArray) else None

    def set_enforce(self, value: COSArray | None) -> None:
        if value is None:
            self._prefs.remove_item(_ENFORCE)
        else:
            self._prefs.set_item(_ENFORCE, value)

    def get_enforce_names(self) -> list[str]:
        """Decode ``/Enforce`` as a list of viewer-preference name tokens
        (PDF 32000-2 §12.4.4 Table 152). Returns an empty list when the
        entry is absent. Non-name entries inside the array are skipped."""
        arr = self.get_enforce()
        if arr is None:
            return []
        out: list[str] = []
        for i in range(arr.size()):
            name = arr.get_name(i)
            if name is not None:
                out.append(name)
        return out

    def set_enforce_names(self, names: list[str] | None) -> None:
        """Encode a list of viewer-preference name tokens into ``/Enforce``.
        Passing ``None`` or an empty list removes the entry."""
        if not names:
            self._prefs.remove_item(_ENFORCE)
            return
        self._prefs.set_item(_ENFORCE, COSArray.of_cos_names(names))

    # ---------- typed enum-returning accessors (companions to the string
    # getters; mirror upstream's Java enums but as a typed view). Return
    # ``None`` when the stored token is not a recognized enum member, so
    # callers can defensively handle producer-written non-standard values.

    def get_non_full_screen_page_mode_enum(
        self,
    ) -> "PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE | None":
        """Return ``/NonFullScreenPageMode`` decoded as a
        :class:`NON_FULL_SCREEN_PAGE_MODE` enum. Returns the spec default
        ``UseNone`` when absent, and ``None`` when the stored token is not
        one of the four enum members."""
        try:
            return PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE(
                self.get_non_full_screen_page_mode()
            )
        except ValueError:
            return None

    def get_reading_direction_enum(
        self,
    ) -> "PDViewerPreferences.READING_DIRECTION | None":
        """Return ``/Direction`` decoded as a :class:`READING_DIRECTION`
        enum. Returns the spec default ``L2R`` when absent, and ``None``
        when the stored token is not a recognized enum member."""
        try:
            return PDViewerPreferences.READING_DIRECTION(
                self.get_reading_direction()
            )
        except ValueError:
            return None

    def get_view_area_enum(self) -> "PDViewerPreferences.BOUNDARY | None":
        """Return ``/ViewArea`` decoded as a :class:`BOUNDARY` enum. Returns
        the spec default ``CropBox`` when absent, and ``None`` when the
        stored token is not a recognized enum member."""
        try:
            return PDViewerPreferences.BOUNDARY(self.get_view_area())
        except ValueError:
            return None

    def get_view_clip_enum(self) -> "PDViewerPreferences.BOUNDARY | None":
        """Return ``/ViewClip`` decoded as a :class:`BOUNDARY` enum. Returns
        the spec default ``CropBox`` when absent, and ``None`` when the
        stored token is not a recognized enum member."""
        try:
            return PDViewerPreferences.BOUNDARY(self.get_view_clip())
        except ValueError:
            return None

    def get_print_area_enum(self) -> "PDViewerPreferences.BOUNDARY | None":
        """Return ``/PrintArea`` decoded as a :class:`BOUNDARY` enum.
        Returns the spec default ``CropBox`` when absent, and ``None``
        when the stored token is not a recognized enum member."""
        try:
            return PDViewerPreferences.BOUNDARY(self.get_print_area())
        except ValueError:
            return None

    def get_print_clip_enum(self) -> "PDViewerPreferences.BOUNDARY | None":
        """Return ``/PrintClip`` decoded as a :class:`BOUNDARY` enum.
        Returns the spec default ``CropBox`` when absent, and ``None``
        when the stored token is not a recognized enum member."""
        try:
            return PDViewerPreferences.BOUNDARY(self.get_print_clip())
        except ValueError:
            return None

    def get_duplex_enum(self) -> "PDViewerPreferences.DUPLEX | None":
        """Return ``/Duplex`` decoded as a :class:`DUPLEX` enum. Returns
        ``None`` when ``/Duplex`` is absent (no spec default per PDF
        32000-1 Table 150) or when the stored token is not a recognized
        enum member."""
        raw = self.get_duplex()
        if raw is None:
            return None
        try:
            return PDViewerPreferences.DUPLEX(raw)
        except ValueError:
            return None

    def get_print_scaling_enum(
        self,
    ) -> "PDViewerPreferences.PRINT_SCALING | None":
        """Return ``/PrintScaling`` decoded as a :class:`PRINT_SCALING`
        enum. Returns the spec default ``AppDefault`` when absent, and
        ``None`` when the stored token is not a recognized enum member."""
        try:
            return PDViewerPreferences.PRINT_SCALING(self.get_print_scaling())
        except ValueError:
            return None

    # ---------- predicate helpers (``has_*``) ----------
    # Distinguish "entry absent (getter falls back to spec default)" from
    # "entry explicitly written to the spec-default value". Useful when a
    # writer wants to round-trip a producer's exact dictionary without
    # introducing redundant entries, or when validation needs to reason
    # over what was *stated* vs what was *defaulted*.

    def has_non_full_screen_page_mode(self) -> bool:
        return self._prefs.contains_key(_NON_FULL_SCREEN_PAGE_MODE)

    def has_direction(self) -> bool:
        return self._prefs.contains_key(_DIRECTION)

    def has_view_area(self) -> bool:
        return self._prefs.contains_key(_VIEW_AREA)

    def has_view_clip(self) -> bool:
        return self._prefs.contains_key(_VIEW_CLIP)

    def has_print_area(self) -> bool:
        return self._prefs.contains_key(_PRINT_AREA)

    def has_print_clip(self) -> bool:
        return self._prefs.contains_key(_PRINT_CLIP)

    def has_duplex(self) -> bool:
        return self._prefs.contains_key(_DUPLEX)

    def has_print_scaling(self) -> bool:
        return self._prefs.contains_key(_PRINT_SCALING)

    def has_num_copies(self) -> bool:
        return self._prefs.contains_key(_NUM_COPIES)

    def has_print_page_range(self) -> bool:
        return self._prefs.contains_key(_PRINT_PAGE_RANGE)

    def has_enforce(self) -> bool:
        return self._prefs.contains_key(_ENFORCE)

    # ---------- /Enforce element-level helpers (PDF 32000-2 §12.4.4) ----------

    def is_enforced(self, name: str) -> bool:
        """Return ``True`` if ``name`` appears as a name token in
        ``/Enforce``. Mirrors PDF 32000-2 §12.4.4: a viewer-preference key
        listed here shall be enforced by conforming readers."""
        return name in self.get_enforce_names()

    def add_enforce_name(self, name: str) -> None:
        """Append ``name`` to ``/Enforce``. Idempotent: if ``name`` is
        already present, the array is unchanged. Creates ``/Enforce`` when
        absent."""
        names = self.get_enforce_names()
        if name in names:
            return
        names.append(name)
        self.set_enforce_names(names)

    def remove_enforce_name(self, name: str) -> bool:
        """Remove the first occurrence of ``name`` from ``/Enforce``.
        Returns ``True`` if removed, ``False`` if not present. When the
        last entry is removed, ``/Enforce`` itself is dropped — keeping
        the dictionary minimal."""
        names = self.get_enforce_names()
        if name not in names:
            return False
        names.remove(name)
        self.set_enforce_names(names if names else None)
        return True

    # ---------- /PrintPageRange element-level helper ----------

    def add_print_page_range_pair(self, start: int, end: int) -> None:
        """Append a single ``(start, end)`` 1-based page-number pair to
        ``/PrintPageRange``. Creates the entry when absent."""
        pairs = self.get_print_page_range_pairs()
        pairs.append((int(start), int(end)))
        self.set_print_page_range_pairs(pairs)

    # ---------- token-equivalence predicates ----------
    # Convenience boolean accessors that wrap the name-valued getters and
    # compare against the spec's recognized tokens. Useful when a caller
    # only needs to branch on a single value rather than pull the full
    # string back. All predicates honor PDFBox's documented spec defaults
    # (e.g. ``/Direction`` defaults to ``L2R`` when absent).

    def is_print_scaling_none(self) -> bool:
        """Return ``True`` iff ``/PrintScaling`` is ``None`` (no scaling)."""
        return self.get_print_scaling() == self.PRINT_SCALING.None_.value

    def is_print_scaling_app_default(self) -> bool:
        """Return ``True`` iff ``/PrintScaling`` is ``AppDefault`` (the spec
        default — also returned when the entry is absent)."""
        return self.get_print_scaling() == self.PRINT_SCALING.AppDefault.value

    def is_simplex(self) -> bool:
        """Return ``True`` iff ``/Duplex`` is ``Simplex``. ``False`` when
        ``/Duplex`` is absent — there is no spec default per PDF 32000-1
        Table 150."""
        return self.get_duplex() == self.DUPLEX.Simplex.value

    def is_duplex_flip_short_edge(self) -> bool:
        """Return ``True`` iff ``/Duplex`` is ``DuplexFlipShortEdge``."""
        return self.get_duplex() == self.DUPLEX.DuplexFlipShortEdge.value

    def is_duplex_flip_long_edge(self) -> bool:
        """Return ``True`` iff ``/Duplex`` is ``DuplexFlipLongEdge``."""
        return self.get_duplex() == self.DUPLEX.DuplexFlipLongEdge.value

    def is_left_to_right(self) -> bool:
        """Return ``True`` iff ``/Direction`` is ``L2R`` (the spec default
        — also returned when the entry is absent)."""
        return self.get_reading_direction() == self.READING_DIRECTION.L2R.value

    def is_right_to_left(self) -> bool:
        """Return ``True`` iff ``/Direction`` is ``R2L``."""
        return self.get_reading_direction() == self.READING_DIRECTION.R2L.value

    # ---------- clear-entry helpers ----------
    # Sugar for callers that want to drop an entry without having to call
    # the typed setter with ``None``. Behaviorally identical to passing
    # ``None`` to the corresponding setter.

    def clear_enforce(self) -> None:
        """Remove ``/Enforce`` entirely (PDF 2.0 Table 150). No-op when
        already absent."""
        self._prefs.remove_item(_ENFORCE)

    def clear_print_page_range(self) -> None:
        """Remove ``/PrintPageRange`` entirely. No-op when already absent."""
        self._prefs.remove_item(_PRINT_PAGE_RANGE)

    def clear_num_copies(self) -> None:
        """Remove ``/NumCopies`` entirely (the getter then falls back to
        the spec default of 1). No-op when already absent."""
        self._prefs.remove_item(_NUM_COPIES)

    # ---------- count helpers ----------

    def enforce_count(self) -> int:
        """Return the number of name tokens in ``/Enforce``. Returns ``0``
        when the entry is absent or empty."""
        return len(self.get_enforce_names())

    def get_print_page_range_pair_count(self) -> int:
        """Return the number of ``(start, end)`` pairs encoded in
        ``/PrintPageRange``. Returns ``0`` when the entry is absent or
        contains an odd number of elements (per PDF 32000-2 §12.4.4 such
        ranges are invalid and shall be ignored)."""
        return len(self.get_print_page_range_pairs())

    def is_valid_print_page_range(self) -> bool:
        """Return ``True`` iff ``/PrintPageRange`` is structurally valid
        per PDF 32000-2 §12.4.4: an even-length array of integer pairs,
        each pair non-decreasing (``start <= end``). Returns ``True`` when
        the entry is absent (a missing array is trivially valid)."""
        arr = self.get_print_page_range()
        if arr is None:
            return True
        n = arr.size()
        if n == 0 or n % 2 != 0:
            return n == 0
        for i in range(0, n, 2):
            start = arr.get_int(i)
            end = arr.get_int(i + 1)
            if start <= 0 or end <= 0 or start > end:
                return False
        return True

    # ---------- bulk /Enforce mutator ----------

    def add_enforce_names(self, names) -> None:
        """Append each name in ``names`` to ``/Enforce`` (idempotent per
        name — duplicates are skipped). Creates ``/Enforce`` when absent.
        ``names`` may be any iterable of strings."""
        existing = self.get_enforce_names()
        seen = set(existing)
        out = list(existing)
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
        if out != existing:
            self.set_enforce_names(out)

    def __repr__(self) -> str:
        return "PDViewerPreferences(...)"


__all__ = ["PDViewerPreferences"]
