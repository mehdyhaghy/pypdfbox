from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")


class PDActionImportData(PDAction):
    """ImportData action. Mirrors PDFBox ``PDActionImportData`` lite surface.

    PDF 32000-1 §12.7.5.4. The action only has a single spec entry:
    ``/F`` — a file specification of an FDF/XFDF/XML form-data file. pypdfbox
    layers a small set of typed convenience accessors (``get_url`` /
    ``get_file_path`` / ``has_file`` / ``is_valid``) on top of the upstream
    raw ``get_file`` / ``set_file`` surface so callers don't have to
    re-classify the COS form themselves."""

    SUB_TYPE = "ImportData"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /F (file specification) ----------

    def get_file(self) -> PDFileSpecification | None:
        """Return ``/F`` typed as a :class:`PDFileSpecification` (simple or
        complex form), or ``None`` when ``/F`` is absent. Mirrors upstream
        ``getFile()``."""
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(self, file_spec: PDFileSpecification | COSBase | str | bytes | None) -> None:
        """Set ``/F``. Accepts a :class:`PDFileSpecification`, a raw
        ``COSBase``, a ``str``/``bytes`` URL or path (stored as a simple
        ``COSString`` form), or ``None`` to remove the entry."""
        if file_spec is None:
            self._action.remove_item(_F)
            return
        if isinstance(file_spec, PDFileSpecification):
            self._action.set_item(_F, file_spec.get_cos_object())
            return
        if isinstance(file_spec, (str, bytes)):
            self._action.set_string(_F, file_spec)
            return
        self._action.set_item(_F, file_spec)

    # ---------- /F string convenience ----------

    def get_file_path(self) -> str | None:
        """Return ``/F`` as a plain string when stored in simple
        (``COSString``) form, or by reading ``/F`` from a complex file
        specification. Returns ``None`` when no path/URL can be derived
        (entry absent or non-string complex spec without ``/F``).

        Convenience over the typed :meth:`get_file` for callers that
        only want the underlying path/URL string."""
        raw = self._action.get_dictionary_object(_F)
        if raw is None:
            return None
        if isinstance(raw, COSString):
            return raw.get_string()
        if not isinstance(raw, COSDictionary):
            return None
        fs = PDFileSpecification.create_fs(raw)
        if fs is None:
            return None
        return fs.get_file()

    def get_url(self) -> str | None:
        """Alias for :meth:`get_file_path`. Mirrors the convenience accessor
        on :class:`PDActionSubmitForm` for the common case of ImportData
        actions targeting a URL — PDF 32000-1 §12.7.5.4 lets ``/F`` reference
        any file specification, including a network URL."""
        return self.get_file_path()

    def set_url(self, value: str | None) -> None:
        """Store ``/F`` as a simple ``COSString`` URL, or remove ``/F`` when
        ``value`` is ``None``. Counterpart of :meth:`get_url` mirroring the
        :class:`PDActionSubmitForm` convenience surface."""
        if value is None:
            self._action.remove_item(_F)
            return
        self._action.set_string(_F, value)

    # ---------- predicates ----------

    def has_file(self) -> bool:
        """``True`` when ``/F`` is present on the underlying dictionary,
        regardless of its COS form (string or complex spec). Lets callers
        branch on file-presence without paying the cost of constructing
        a :class:`PDFileSpecification` wrapper."""
        return self._action.get_dictionary_object(_F) is not None

    def clear_file(self) -> None:
        """Remove ``/F`` from the underlying dictionary. After this call
        :meth:`get_file`, :meth:`get_file_path`, and :meth:`get_url`
        return ``None``."""
        self._action.remove_item(_F)

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"ImportData"``). Useful as a sanity check after
        round-tripping through :meth:`PDAction.create` or when constructing
        the wrapper around a hand-built :class:`COSDictionary`."""
        return self.get_sub_type() == self.SUB_TYPE


__all__ = ["PDActionImportData"]
