from __future__ import annotations

from abc import ABC, abstractmethod


class PDAppearanceHandler(ABC):
    """Strategy interface for annotation appearance generation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDAppearanceHandler``.

    Concrete handlers populate the annotation's ``/AP /N`` (and optionally
    ``/AP /R``, ``/AP /D``) entries by emitting PDF content operators into
    a fresh appearance stream (a Form XObject in the upstream surface;
    see :class:`PDAppearanceStream` for the lite mapping).
    """

    @abstractmethod
    def generate_normal_appearance(self) -> None:
        """Generate the normal (``/N``) appearance."""

    @abstractmethod
    def generate_rollover_appearance(self) -> None:
        """Generate the rollover (``/R``) appearance."""

    @abstractmethod
    def generate_down_appearance(self) -> None:
        """Generate the down (``/D``) appearance."""

    def generate_appearance_streams(self) -> None:
        """Generate ``/N``, ``/R``, ``/D`` in order. Mirrors upstream's
        default helper flow."""
        self.generate_normal_appearance()
        self.generate_rollover_appearance()
        self.generate_down_appearance()


__all__ = ["PDAppearanceHandler"]
