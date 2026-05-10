"""Type 4 (PostScript calculator) function infrastructure.

Mirrors upstream Java package
``org.apache.pdfbox.pdmodel.common.function.type4``. Each Java source file
has a Python module of the same snake-case name in this subpackage.

The high-level entry point is :class:`InstructionSequenceBuilder`:

>>> seq = InstructionSequenceBuilder.parse("3 4 add 2 sub")
>>> ctx = ExecutionContext(Operators())
>>> seq.execute(ctx)
>>> ctx.get_stack()
[5]

Note: the canonical Type-4 evaluator used by
:class:`pypdfbox.pdmodel.common.function.PDFunctionType4` is the inline
stack machine in :mod:`pypdfbox.pdmodel.common.function.pd_function_type4`.
This subpackage exposes the same machinery in PDFBox's class shape so
porting code/tests against ``org.apache.pdfbox.pdmodel.common.function.type4``
finds the expected names.
"""

from __future__ import annotations

from .execution_context import ExecutionContext
from .instruction_sequence import InstructionSequence
from .instruction_sequence_builder import InstructionSequenceBuilder
from .operator import Operator
from .operators import Operators
from .parser import Parser

__all__ = [
    "ExecutionContext",
    "InstructionSequence",
    "InstructionSequenceBuilder",
    "Operator",
    "Operators",
    "Parser",
]
