from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream

from .pd_appearance_entry import PDAppearanceEntry
from .pd_appearance_stream import PDAppearanceStream

_N: COSName = COSName.get_pdf_name("N")
_R: COSName = COSName.get_pdf_name("R")
_D: COSName = COSName.get_pdf_name("D")


class PDAppearanceDictionary:
    """
    Appearance dictionary specifying how an annotation is presented
    visually on the page. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary``.

    Carries up to three entries (PDF 32000-1:2008 Table 168):

    - ``/N`` — normal appearance (required).
    - ``/R`` — rollover appearance (optional).
    - ``/D`` — down appearance (optional).

    Each entry is *either* a single appearance stream (``COSStream``) for
    the simple case, *or* a subdictionary mapping state names to
    per-state appearance streams (used by widget annotations,
    radio buttons, check boxes, etc.).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            # Upstream's no-arg constructor seeds /N with an empty
            # subdictionary because /N is required by spec.
            self._dict.set_item(_N, COSDictionary())
        else:
            if not isinstance(dictionary, COSDictionary):
                raise TypeError(
                    "PDAppearanceDictionary requires a COSDictionary or None; "
                    f"got {type(dictionary).__name__}"
                )
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- shared helpers ----------

    def _get_entry(self, key: COSName) -> PDAppearanceEntry | None:
        value = self._dict.get_dictionary_object(key)
        if isinstance(value, (COSStream, COSDictionary)):
            return PDAppearanceEntry(value)
        return None

    def _set_entry(
        self,
        key: COSName,
        entry: PDAppearanceEntry | PDAppearanceStream | COSDictionary | COSStream | None,
    ) -> None:
        if entry is None:
            self._dict.remove_item(key)
            return
        if isinstance(entry, (PDAppearanceEntry, PDAppearanceStream)):
            self._dict.set_item(key, entry.get_cos_object())
            return
        if isinstance(entry, (COSStream, COSDictionary)):
            self._dict.set_item(key, entry)
            return
        raise TypeError(
            "appearance entry must be PDAppearanceEntry, PDAppearanceStream, "
            f"COSStream, COSDictionary, or None; got {type(entry).__name__}"
        )

    # ---------- /N (normal) ----------

    def get_normal_appearance(self) -> PDAppearanceEntry | None:
        return self._get_entry(_N)

    def set_normal_appearance(
        self,
        entry: PDAppearanceEntry | PDAppearanceStream | COSDictionary | COSStream | None,
    ) -> None:
        self._set_entry(_N, entry)

    # ---------- /R (rollover) ----------

    def get_rollover_appearance(self) -> PDAppearanceEntry | None:
        """Per spec, when ``/R`` is absent the normal appearance is used —
        upstream returns ``getNormalAppearance()`` as the fallback. We
        mirror that behaviour."""
        entry = self._get_entry(_R)
        if entry is not None:
            return entry
        return self.get_normal_appearance()

    def set_rollover_appearance(
        self,
        entry: PDAppearanceEntry | PDAppearanceStream | COSDictionary | COSStream | None,
    ) -> None:
        self._set_entry(_R, entry)

    # ---------- /D (down) ----------

    def get_down_appearance(self) -> PDAppearanceEntry | None:
        """Per spec, when ``/D`` is absent the normal appearance is used —
        upstream returns ``getNormalAppearance()`` as the fallback. We
        mirror that behaviour."""
        entry = self._get_entry(_D)
        if entry is not None:
            return entry
        return self.get_normal_appearance()

    def set_down_appearance(
        self,
        entry: PDAppearanceEntry | PDAppearanceStream | COSDictionary | COSStream | None,
    ) -> None:
        self._set_entry(_D, entry)


__all__ = ["PDAppearanceDictionary"]
