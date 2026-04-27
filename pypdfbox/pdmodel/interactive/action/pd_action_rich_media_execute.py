from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_TA: COSName = COSName.get_pdf_name("TA")
_TI: COSName = COSName.get_pdf_name("TI")
_CMD: COSName = COSName.get_pdf_name("CMD")
_N: COSName = COSName.get_pdf_name("N")
_A: COSName = COSName.get_pdf_name("A")


class PDActionRichMediaExecute(PDAction):
    """Rich-Media Execute action. Mirrors the PDF 2.0 ``RichMediaExecute``
    action type from ISO 32000-2 §13.6.4.

    The action carries:

    * ``/TA`` — target annotation (the screen annotation hosting the rich
      media artwork the command targets);
    * ``/TI`` — (optional) target instance dictionary, identifying which
      rich-media instance inside ``/TA`` the command applies to;
    * ``/CMD`` — command dictionary with ``/N`` (command name string) and
      optional ``/A`` (arguments — any COS object, typically a single
      value or a ``COSArray`` of values).

    For convenience the inner command name and arguments are also exposed
    directly via :meth:`get_command_name` / :meth:`get_command_arguments`.

    Note: not present in upstream Apache PDFBox 3.0.x; added here for
    PDF 2.0 parity. Recorded in ``CHANGES.md``.
    """

    SUB_TYPE = "RichMediaExecute"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /TA — target annotation ----------

    def get_target_annotation(self) -> COSBase | None:
        """Return the raw ``/TA`` target-annotation entry (typically an
        indirect reference to a Screen annotation), or ``None``."""
        return self._action.get_dictionary_object(_TA)

    def set_target_annotation(self, annotation: COSBase | None) -> None:
        """Write ``/TA``. ``None`` removes the entry."""
        if annotation is None:
            self._action.remove_item(_TA)
            return
        self._action.set_item(_TA, annotation)

    # ---------- /TI — target instance ----------

    def get_target_instance(self) -> COSDictionary | None:
        """Return the ``/TI`` target-instance dictionary, or ``None``."""
        entry = self._action.get_dictionary_object(_TI)
        if isinstance(entry, COSDictionary):
            return entry
        return None

    def set_target_instance(self, instance: COSDictionary | None) -> None:
        """Write ``/TI``. ``None`` removes the entry."""
        if instance is None:
            self._action.remove_item(_TI)
            return
        self._action.set_item(_TI, instance)

    # ---------- /CMD — command dictionary ----------

    def get_command(self) -> COSDictionary | None:
        """Return the ``/CMD`` command dictionary, or ``None``."""
        entry = self._action.get_dictionary_object(_CMD)
        if isinstance(entry, COSDictionary):
            return entry
        return None

    def set_command(self, command: COSDictionary | None) -> None:
        """Write ``/CMD``. ``None`` removes the entry."""
        if command is None:
            self._action.remove_item(_CMD)
            return
        self._action.set_item(_CMD, command)

    # ---------- /CMD/N + /CMD/A convenience accessors ----------

    def get_command_name(self) -> str | None:
        """Return the ``/CMD /N`` command name string, or ``None`` when
        ``/CMD`` is absent or has no ``/N`` entry."""
        cmd = self.get_command()
        if cmd is None:
            return None
        return cmd.get_string(_N)

    def set_command_name(self, name: str | None) -> None:
        """Set ``/CMD /N``. Creates ``/CMD`` if absent. Passing ``None``
        clears the name on an existing ``/CMD`` (the dictionary itself is
        kept)."""
        cmd = self.get_command()
        if cmd is None:
            if name is None:
                return
            cmd = COSDictionary()
            self.set_command(cmd)
        cmd.set_string(_N, name)

    def get_command_arguments(self) -> COSBase | None:
        """Return the raw ``/CMD /A`` arguments entry, or ``None``."""
        cmd = self.get_command()
        if cmd is None:
            return None
        return cmd.get_dictionary_object(_A)

    def set_command_arguments(self, arguments: COSBase | None) -> None:
        """Set ``/CMD /A``. Creates ``/CMD`` if absent. Passing ``None``
        removes the ``/A`` entry from the command dictionary (the
        dictionary itself is kept)."""
        cmd = self.get_command()
        if cmd is None:
            if arguments is None:
                return
            cmd = COSDictionary()
            self.set_command(cmd)
        if arguments is None:
            cmd.remove_item(_A)
            return
        cmd.set_item(_A, arguments)


__all__ = ["PDActionRichMediaExecute"]
