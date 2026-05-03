"""Windows launch parameters dictionary (PDF 32000-1 §12.6.4.5 Table 197).

Mirrors upstream ``org.apache.pdfbox.pdmodel.interactive.action.PDWindowsLaunchParams``.

Upstream PDFBox 3.0 only ships a typed wrapper for the ``/Win`` sub-dict of a
launch action; the (deprecated) ``/Mac`` and ``/Unix`` sub-dicts have no
dedicated typed class and are accessed as raw ``COSDictionary`` instances on
``PDActionLaunch``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_O: COSName = COSName.get_pdf_name("O")
_P: COSName = COSName.get_pdf_name("P")


class PDWindowsLaunchParams:
    """Launch parameters for Windows. Mirrors PDFBox ``PDWindowsLaunchParams``.

    Behaves as a thin typed wrapper around the underlying ``COSDictionary``.
    """

    #: The "open" operation for ``/O``.
    OPERATION_OPEN: str = "open"
    #: The "print" operation for ``/O``.
    OPERATION_PRINT: str = "print"

    def __init__(self, params: COSDictionary | None = None) -> None:
        self._params: COSDictionary = params if params is not None else COSDictionary()

    # ------------------------------------------------------------------ COSObjectable
    def get_cos_object(self) -> COSDictionary:
        """Return the backing ``COSDictionary`` (parity with upstream
        ``getCOSObject``)."""
        return self._params

    # ------------------------------------------------------------------ /F
    def get_filename(self) -> str | None:
        """Return the executable / document to launch (``/F``)."""
        return self._params.get_string(_F)

    def set_filename(self, file: str | None) -> None:
        """Set the executable / document to launch (``/F``)."""
        self._params.set_string(_F, file)

    # ------------------------------------------------------------------ /D
    def get_directory(self) -> str | None:
        """Return the working directory (``/D``)."""
        return self._params.get_string(_D)

    def set_directory(self, directory: str | None) -> None:
        """Set the working directory (``/D``)."""
        self._params.set_string(_D, directory)

    # ------------------------------------------------------------------ /O
    def get_operation(self) -> str:
        """Return the operation to perform (``/O``).

        Defaults to :pyattr:`OPERATION_OPEN` when the entry is absent — matches
        upstream ``params.getString(COSName.O, OPERATION_OPEN)``.
        """
        value = self._params.get_string(_O, self.OPERATION_OPEN)
        # ``get_string`` is typed ``str | None`` but with a non-None default it
        # always returns a string.
        assert value is not None
        return value

    def set_operation(self, op: str | None) -> None:
        """Set the operation to perform (``/O``)."""
        self._params.set_string(_O, op)

    def has_operation(self) -> bool:
        """``True`` iff ``/O`` is explicitly present in the dict.

        Distinct from :meth:`get_operation` which folds the absence case into
        the default :pyattr:`OPERATION_OPEN`. Useful when the caller needs to
        distinguish an explicit ``"open"`` from a fall-through default.
        """
        return _O in self._params

    def is_open_operation(self) -> bool:
        """``True`` iff the effective operation is :pyattr:`OPERATION_OPEN`.

        Honors the upstream ``getOperation`` default, so an absent ``/O`` entry
        also resolves to ``True`` (open is the default per Table 197).
        """
        return self.get_operation() == self.OPERATION_OPEN

    def is_print_operation(self) -> bool:
        """``True`` iff the effective operation is :pyattr:`OPERATION_PRINT`."""
        return self.get_operation() == self.OPERATION_PRINT

    # ------------------------------------------------------------------ /P
    def get_execute_param(self) -> str | None:
        """Return the parameter passed to the executable (``/P``)."""
        return self._params.get_string(_P)

    def set_execute_param(self, param: str | None) -> None:
        """Set the parameter passed to the executable (``/P``)."""
        self._params.set_string(_P, param)


__all__ = ["PDWindowsLaunchParams"]
