from __future__ import annotations

from enum import StrEnum

from pypdfbox.cos import COSDictionary, COSName

# ---------- viewer-prefs key constants (PDF 32000-1:2008 §12.2, Table 150) ----------

_HIDE_TOOLBAR: COSName = COSName.get_pdf_name("HideToolbar")
_HIDE_MENUBAR: COSName = COSName.get_pdf_name("HideMenubar")
_HIDE_WINDOWUI: COSName = COSName.get_pdf_name("HideWindowUI")
_FIT_WINDOW: COSName = COSName.get_pdf_name("FitWindow")
_CENTER_WINDOW: COSName = COSName.get_pdf_name("CenterWindow")
_DISPLAY_DOC_TITLE: COSName = COSName.get_pdf_name("DisplayDocTitle")
_NON_FULL_SCREEN_PAGE_MODE: COSName = COSName.get_pdf_name("NonFullScreenPageMode")
_DIRECTION: COSName = COSName.get_pdf_name("Direction")
_VIEW_AREA: COSName = COSName.get_pdf_name("ViewArea")
_VIEW_CLIP: COSName = COSName.get_pdf_name("ViewClip")
_PRINT_AREA: COSName = COSName.get_pdf_name("PrintArea")
_PRINT_CLIP: COSName = COSName.get_pdf_name("PrintClip")
_DUPLEX: COSName = COSName.get_pdf_name("Duplex")
_PRINT_SCALING: COSName = COSName.get_pdf_name("PrintScaling")


class PDViewerPreferences:
    """
    Wraps the catalog's ``/ViewerPreferences`` dictionary. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences``.

    Boolean accessors return PDFBox's documented defaults (``False``) when
    the entry is absent. Name-valued accessors return the spec default
    (e.g. ``CropBox`` for boundary fields, ``UseNone`` for non-full-screen
    page mode) — matching upstream signatures that bake the default in.
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

    def hide_menubar(self) -> bool:
        return self._prefs.get_boolean(_HIDE_MENUBAR, False)

    def set_hide_menubar(self, value: bool) -> None:
        self._prefs.set_boolean(_HIDE_MENUBAR, value)

    def hide_window_ui(self) -> bool:
        return self._prefs.get_boolean(_HIDE_WINDOWUI, False)

    def set_hide_window_ui(self, value: bool) -> None:
        self._prefs.set_boolean(_HIDE_WINDOWUI, value)

    def fit_window(self) -> bool:
        return self._prefs.get_boolean(_FIT_WINDOW, False)

    def set_fit_window(self, value: bool) -> None:
        self._prefs.set_boolean(_FIT_WINDOW, value)

    def center_window(self) -> bool:
        return self._prefs.get_boolean(_CENTER_WINDOW, False)

    def set_center_window(self, value: bool) -> None:
        self._prefs.set_boolean(_CENTER_WINDOW, value)

    def display_doc_title(self) -> bool:
        return self._prefs.get_boolean(_DISPLAY_DOC_TITLE, False)

    def set_display_doc_title(self, value: bool) -> None:
        self._prefs.set_boolean(_DISPLAY_DOC_TITLE, value)

    # ---------- name-valued accessors (with documented defaults) ----------

    def get_non_full_screen_page_mode(self) -> str:
        return self._prefs.get_name(
            _NON_FULL_SCREEN_PAGE_MODE,
            self.NON_FULL_SCREEN_PAGE_MODE.UseNone.value,
        ) or self.NON_FULL_SCREEN_PAGE_MODE.UseNone.value

    def set_non_full_screen_page_mode(
        self, value: NON_FULL_SCREEN_PAGE_MODE | str
    ) -> None:
        self._prefs.set_name(_NON_FULL_SCREEN_PAGE_MODE, str(value))

    def get_reading_direction(self) -> str:
        return self._prefs.get_name(
            _DIRECTION, self.READING_DIRECTION.L2R.value
        ) or self.READING_DIRECTION.L2R.value

    def set_reading_direction(self, value: READING_DIRECTION | str) -> None:
        self._prefs.set_name(_DIRECTION, str(value))

    def get_view_area(self) -> str:
        return self._prefs.get_name(
            _VIEW_AREA, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_view_area(self, value: BOUNDARY | str) -> None:
        self._prefs.set_name(_VIEW_AREA, str(value))

    def get_view_clip(self) -> str:
        return self._prefs.get_name(
            _VIEW_CLIP, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_view_clip(self, value: BOUNDARY | str) -> None:
        self._prefs.set_name(_VIEW_CLIP, str(value))

    def get_print_area(self) -> str:
        return self._prefs.get_name(
            _PRINT_AREA, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_print_area(self, value: BOUNDARY | str) -> None:
        self._prefs.set_name(_PRINT_AREA, str(value))

    def get_print_clip(self) -> str:
        return self._prefs.get_name(
            _PRINT_CLIP, self.BOUNDARY.CropBox.value
        ) or self.BOUNDARY.CropBox.value

    def set_print_clip(self, value: BOUNDARY | str) -> None:
        self._prefs.set_name(_PRINT_CLIP, str(value))

    def get_duplex(self) -> str | None:
        # Upstream returns null when /Duplex is absent (no spec default).
        return self._prefs.get_name(_DUPLEX)

    def set_duplex(self, value: DUPLEX | str) -> None:
        self._prefs.set_name(_DUPLEX, str(value))

    def get_print_scaling(self) -> str:
        return self._prefs.get_name(
            _PRINT_SCALING, self.PRINT_SCALING.AppDefault.value
        ) or self.PRINT_SCALING.AppDefault.value

    def set_print_scaling(self, value: PRINT_SCALING | str) -> None:
        self._prefs.set_name(_PRINT_SCALING, str(value))

    def __repr__(self) -> str:
        return "PDViewerPreferences(...)"


__all__ = ["PDViewerPreferences"]
