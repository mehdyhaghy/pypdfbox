"""Instruction-sequence builder for Type 4 functions.

Mirrors upstream
``org.apache.pdfbox.pdmodel.common.function.type4.InstructionSequenceBuilder``.
"""

from __future__ import annotations

import re

from .instruction_sequence import InstructionSequence
from .parser import AbstractSyntaxHandler, Parser

# PostScript number patterns ported from upstream:
#   INTEGER_PATTERN = "[\\+\\-]?\\d+"
#   REAL_PATTERN    = "\\-?\\d*\\.\\d*([Ee]\\-?\\d+)?"
_INTEGER_PATTERN = re.compile(r"[+\-]?\d+")
_REAL_PATTERN = re.compile(r"-?\d*\.\d*([Ee]-?\d+)?")
# PostScript radix literal: ``base#digits`` where ``base`` is 2..36 and
# ``digits`` are interpreted in that base (PLRM 3rd ed. §3.3.2). Closes
# the upstream TODO at InstructionSequenceBuilder.java:83 — upstream
# never implemented this in Java, but the literal form is permitted in
# the Type-4 grammar so PDF producers can (and occasionally do) emit
# values like ``8#1777`` or ``16#FFFE``.
_RADIX_PATTERN = re.compile(r"(\d+)#([0-9A-Za-z]+)")


class InstructionSequenceBuilder(AbstractSyntaxHandler):
    """Basic builder for Type 4 functions, used to build up instruction
    sequences from the syntactic elements produced by :class:`Parser`.

    Mirrors upstream ``InstructionSequenceBuilder`` (final class
    extending ``Parser.AbstractSyntaxHandler``). The Java constructor is
    private and the public entry point is the static :meth:`parse`
    factory; we follow the same shape.
    """

    def __init__(self) -> None:
        super().__init__()
        self._main_sequence = InstructionSequence()
        self._seq_stack: list[InstructionSequence] = [self._main_sequence]

    def get_instruction_sequence(self) -> InstructionSequence:
        """Return the instruction sequence built from the syntactic
        elements."""
        return self._main_sequence

    @staticmethod
    def parse(text: str) -> InstructionSequence:
        """Parse the given text into an instruction sequence representing
        a Type 4 function that can be executed.

        :param text: the Type 4 function text
        :return: the instruction sequence
        """
        builder = InstructionSequenceBuilder()
        Parser.parse(text, builder)
        return builder.get_instruction_sequence()

    def _get_current_sequence(self) -> InstructionSequence:
        return self._seq_stack[-1]

    def get_current_sequence(self) -> InstructionSequence:
        """Return the sequence currently being built (top of the stack).

        Mirrors upstream ``InstructionSequenceBuilder.getCurrentSequence``.
        """
        return self._seq_stack[-1]

    def token(self, text: str) -> None:
        """Handle a token from the parser."""
        self._handle_token(str(text))

    def _handle_token(self, token: str) -> None:
        if token == "{":
            child = InstructionSequence()
            self._get_current_sequence().add_proc(child)
            self._seq_stack.append(child)
        elif token == "}":
            self._seq_stack.pop()
        else:
            if _INTEGER_PATTERN.fullmatch(token):
                self._get_current_sequence().add_integer(self.parse_int(token))
                return

            if _REAL_PATTERN.fullmatch(token):
                self._get_current_sequence().add_real(self.parse_real(token))
                return

            # Wave 1286: closes upstream TODO at
            # InstructionSequenceBuilder.java:83. Parse PostScript radix
            # literals ``base#digits`` (e.g. ``8#1777`` is 1023, ``16#FFFE``
            # is 65534). ``base`` must be 2..36 per PLRM 3.3.2; any digit
            # outside the declared base (or a base outside 2..36) leaves
            # the token as a name, preserving the original "unknown =
            # name" fallback for malformed input.
            radix = _RADIX_PATTERN.fullmatch(token)
            if radix is not None:
                base_str, digits = radix.group(1), radix.group(2)
                try:
                    base = int(base_str)
                    if 2 <= base <= 36:
                        value = int(digits, base)
                        self._get_current_sequence().add_integer(value)
                        return
                except ValueError:
                    # Digits not valid in the declared base — fall
                    # through to the name fallback below.
                    pass

            self._get_current_sequence().add_name(token)

    @staticmethod
    def parse_int(token: str) -> int:
        """Parse a value of type ``int``.

        :param token: the token to be parsed
        :return: the parsed value
        """
        return int(token)

    @staticmethod
    def parse_real(token: str) -> float:
        """Parse a value of type ``real``.

        :param token: the token to be parsed
        :return: the parsed value
        """
        return float(token)


__all__ = ["InstructionSequenceBuilder"]
