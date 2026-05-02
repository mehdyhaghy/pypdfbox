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

    DIRECTION_L2R: str = "L2R"
    DIRECTION_R2L: str = "R2L"

    PRINT_SCALING_NONE: str = "None"
    PRINT_SCALING_APPDEFAULT: str = "AppDefault"

    DUPLEX_SIMPLEX: str = "Simplex"
    DUPLEX_DUPLEX_FLIP_SHORT_EDGE: str = "DuplexFlipShortEdge"
    DUPLEX_DUPLEX_FLIP_LONG_EDGE: str = "DuplexFlipLongEdge"

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

    def __repr__(self) -> str:
        return "PDViewerPreferences(...)"


__all__ = ["PDViewerPreferences"]
