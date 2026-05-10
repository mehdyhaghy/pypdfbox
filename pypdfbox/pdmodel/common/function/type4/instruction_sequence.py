"""Instruction sequence for Type 4 (PostScript calculator) functions.

Mirrors upstream
``org.apache.pdfbox.pdmodel.common.function.type4.InstructionSequence``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .execution_context import ExecutionContext


class InstructionSequence:
    """Represents an instruction sequence — a combination of values,
    operands and nested procedures.

    Each entry on the internal list is one of:

    * ``str``: an operator name (looked up against the
      :class:`Operators <pypdfbox.pdmodel.common.function.type4.Operators>`
      registry)
    * ``int`` / ``float`` / ``bool``: a literal pushed onto the stack
    * ``InstructionSequence``: a nested ``{...}`` proc, pushed as a
      first-class value (consumed by ``if`` / ``ifelse``)
    """

    def __init__(self) -> None:
        self._instructions: list[object] = []

    def get_instructions(self) -> list[object]:
        """Return the underlying instruction list.

        Not present in upstream Java (the field is private with no
        accessor). Provided for inspection / debugging — callers must
        not mutate the returned list.
        """
        return self._instructions

    def add_name(self, name: str) -> None:
        """Add a name (e.g. an operator)."""
        self._instructions.append(name)

    def add_integer(self, value: int) -> None:
        """Add an int value."""
        self._instructions.append(value)

    def add_real(self, value: float) -> None:
        """Add a real value."""
        self._instructions.append(value)

    def add_boolean(self, value: bool) -> None:
        """Add a bool value."""
        self._instructions.append(value)

    def add_proc(self, child: InstructionSequence) -> None:
        """Add a proc (sub-sequence of instructions)."""
        self._instructions.append(child)

    def execute(self, context: ExecutionContext) -> None:
        """Execute the instruction sequence.

        Mirrors upstream ``execute(ExecutionContext)``: walk the
        instruction list, dispatching name tokens against the registry
        and pushing literal/proc values onto the stack. After the walk,
        any top-level :class:`InstructionSequence` left on the stack is
        executed in turn (this lets a procedure value be called by
        simply leaving it on top).
        """
        stack = context.get_stack()
        for instruction in self._instructions:
            if isinstance(instruction, str):
                cmd = context.get_operators().get_operator(instruction)
                if cmd is not None:
                    cmd.execute(context)
                else:
                    raise NotImplementedError(
                        f"Unknown operator or name: {instruction}"
                    )
            else:
                stack.append(instruction)

        # Handles top-level procs that simply need to be executed.
        while stack and isinstance(stack[-1], InstructionSequence):
            nested = stack.pop()
            assert isinstance(nested, InstructionSequence)
            nested.execute(context)


__all__ = ["InstructionSequence"]
