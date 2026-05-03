from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .pd_action import PDAction

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread import PDThread
    from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread_bead import (
        PDThreadBead,
    )

_B: COSName = COSName.get_pdf_name("B")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_F: COSName = COSName.get_pdf_name("F")


class PDActionThread(PDAction):
    """Thread action. Mirrors PDFBox ``PDActionThread`` lite surface.

    PDF 32000-1 §12.6.4.7. The ``/D`` entry identifies the thread to jump
    to and may be (a) a thread dictionary, (b) an integer index into the
    document's threads array, or (c) a text string matching a thread's
    ``/I /Title`` entry. The ``/B`` entry identifies the bead within the
    thread and may be (a) a bead dictionary or (b) an integer bead index.
    pypdfbox layers typed accessors on top of the upstream raw-COS getters
    while keeping ``get_d``/``set_d`` and ``get_b``/``set_b`` for parity.
    """

    SUB_TYPE = "Thread"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /F (file containing the thread) ----------
    # Optional; defaults to the current document.
    def get_file(self) -> PDFileSpecification | None:
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(self, file_spec: PDFileSpecification | COSBase | str | bytes | None) -> None:
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

    # ---------- /D (thread destination) ----------

    def get_thread(self) -> COSBase | None:
        """Return the raw ``/D`` value: thread dict, integer index, or
        text-string title. Mirrors upstream ``getD()``."""
        return self._action.get_dictionary_object(_D)

    def set_thread(
        self,
        thread: PDThread | COSBase | int | str | None,
    ) -> None:
        """Replace ``/D``. Accepts a :class:`PDThread` (stores its
        underlying ``COSDictionary``), a raw ``COSBase``, a Python ``int``
        (stored as ``COSInteger`` thread-index), a ``str`` (stored as
        ``COSString`` thread title), or ``None`` to remove the entry."""
        if thread is None:
            self._action.remove_item(_D)
            return
        # Avoid the circular import that PDThread→PDActionThread would
        # introduce; use a runtime import like the parent factory does.
        from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread import (
            PDThread as _PDThread,
        )
        if isinstance(thread, _PDThread):
            self._action.set_item(_D, thread.get_cos_object())
            return
        # bool is an int subclass — guard so callers don't accidentally
        # store True/False as a thread index.
        if isinstance(thread, bool):
            raise TypeError("set_thread does not accept bool")
        if isinstance(thread, int):
            self._action.set_item(_D, COSInteger.get(thread))
            return
        if isinstance(thread, str):
            self._action.set_string(_D, thread)
            return
        self._action.set_item(_D, thread)

    def get_thread_typed(self) -> PDThread | None:
        """Return ``/D`` as a typed :class:`PDThread` when ``/D`` is a
        thread dictionary; ``None`` otherwise (including the integer-index
        and string-title forms — use :meth:`get_thread_index` /
        :meth:`get_thread_title` for those)."""
        entry = self._action.get_dictionary_object(_D)
        if isinstance(entry, COSDictionary):
            from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread import (
                PDThread as _PDThread,
            )
            return _PDThread(entry)
        return None

    def get_thread_index(self) -> int | None:
        """Return ``/D`` as a 0-based integer index when stored in
        integer form; ``None`` otherwise."""
        entry = self._action.get_dictionary_object(_D)
        if isinstance(entry, COSInteger):
            return entry.value
        return None

    def get_thread_title(self) -> str | None:
        """Return ``/D`` as a thread-title string when stored in
        text-string form; ``None`` otherwise."""
        entry = self._action.get_dictionary_object(_D)
        if isinstance(entry, COSString):
            return entry.get_string()
        return None

    # Back-compat aliases mirroring the historical ``get_d``/``set_d`` surface.
    def get_d(self) -> COSBase | None:
        return self.get_thread()

    def set_d(self, thread: COSBase | None) -> None:
        # Preserve the historical raw-COS contract: callers who reached
        # for ``set_d`` always passed a COSBase, never a PDThread/int/str.
        if thread is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, thread)

    # ---------- /B (bead within the thread) ----------

    def get_bead(self) -> COSBase | None:
        """Return the raw ``/B`` value: bead dict or integer bead index.
        Mirrors upstream ``getB()``."""
        return self._action.get_dictionary_object(_B)

    def set_bead(
        self,
        bead: PDThreadBead | COSBase | int | None,
    ) -> None:
        """Replace ``/B``. Accepts a :class:`PDThreadBead` (stores its
        underlying ``COSDictionary``), a raw ``COSBase``, a Python ``int``
        (stored as ``COSInteger`` bead-index), or ``None`` to remove the
        entry."""
        if bead is None:
            self._action.remove_item(_B)
            return
        from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread_bead import (
            PDThreadBead as _PDThreadBead,
        )
        if isinstance(bead, _PDThreadBead):
            self._action.set_item(_B, bead.get_cos_object())
            return
        if isinstance(bead, bool):
            raise TypeError("set_bead does not accept bool")
        if isinstance(bead, int):
            self._action.set_item(_B, COSInteger.get(bead))
            return
        self._action.set_item(_B, bead)

    def get_bead_typed(self) -> PDThreadBead | None:
        """Return ``/B`` as a typed :class:`PDThreadBead` when ``/B`` is
        a bead dictionary; ``None`` otherwise (including the integer-index
        form — use :meth:`get_bead_index` for that)."""
        entry = self._action.get_dictionary_object(_B)
        if isinstance(entry, COSDictionary):
            from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread_bead import (
                PDThreadBead as _PDThreadBead,
            )
            return _PDThreadBead(entry)
        return None

    def get_bead_index(self) -> int | None:
        """Return ``/B`` as a 0-based integer bead index when stored in
        integer form; ``None`` otherwise."""
        entry = self._action.get_dictionary_object(_B)
        if isinstance(entry, COSInteger):
            return entry.value
        return None

    # Back-compat aliases mirroring the historical ``get_b``/``set_b`` surface.
    def get_b(self) -> COSBase | None:
        return self.get_bead()

    def set_b(self, bead: COSBase | None) -> None:
        # Preserve the historical raw-COS contract; see ``set_d``.
        if bead is None:
            self._action.remove_item(_B)
            return
        self._action.set_item(_B, bead)


__all__ = ["PDActionThread"]
