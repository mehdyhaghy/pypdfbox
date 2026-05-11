from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action.pd_action_javascript import (
        PDActionJavaScript,
    )


class ScriptingHandler(ABC):
    """Interface for handling JavaScript form-field events. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.ScriptingHandler``
    (upstream lines 22–58).

    Implementations are wired onto an :class:`PDAcroForm` via
    ``set_scripting_handler`` / ``get_scripting_handler`` and invoked
    by the appearance pipeline when a field declares a keyboard,
    format, validate, or calculate JavaScript action. The default
    pypdfbox engine ships without one (JavaScript execution is out of
    scope for the read/write core) — installing a handler is a
    consumer-side decision.
    """

    @abstractmethod
    def keyboard(
        self, java_script_action: PDActionJavaScript, value: str
    ) -> str:
        """Handle the field's keyboard event action. Return the
        resulting field value."""

    @abstractmethod
    def format(
        self, java_script_action: PDActionJavaScript, value: str
    ) -> str:
        """Handle the field's format event action. Return the formatted
        field value."""

    @abstractmethod
    def validate(
        self, java_script_action: PDActionJavaScript, value: str
    ) -> bool:
        """Handle the field's validate event action. Return ``True`` if
        the value is valid."""

    @abstractmethod
    def calculate(
        self, java_script_action: PDActionJavaScript, value: str
    ) -> str:
        """Handle the field's calculate event action. Return the
        calculated field value."""


__all__ = ["ScriptingHandler"]
