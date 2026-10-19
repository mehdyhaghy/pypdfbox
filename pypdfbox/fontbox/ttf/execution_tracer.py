"""A toggleable execution tracer for the TrueType interpreter.

When attached to a :class:`TrueTypeInterpreter` it emits one line per executed
instruction, just before the instruction runs, in a format deliberately close
to FreeType's ``FT2_DEBUG=ttinterp`` output::

    <pc>  <MNEMONIC>  # <top of stack first>

The program counter and the operand stack are what matter for diffing:
feeding the same glyph through this tracer and through FreeType and aligning
the two traces by instruction index pinpoints the first instruction where
control flow or an operand value diverges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from pypdfbox.fontbox.ttf.execution_context import ExecutionContext

# Number of top-of-stack operands to print, matching FreeType's trace window.
_STACK_WINDOW = 8


def _build_mnemonics() -> list[str]:
    m = [f"INS_{i:02X}" for i in range(256)]
    names = {
        # axis-variant vector setters: [y] for the even (0) code, [x] for the odd (1) code
        0x00: "SVTCA[y]",
        0x01: "SVTCA[x]",
        0x02: "SPVTCA[y]",
        0x03: "SPVTCA[x]",
        0x04: "SFVTCA[y]",
        0x05: "SFVTCA[x]",
        0x06: "SPVTL[||]",
        0x07: "SPVTL[+]",
        0x08: "SFVTL[||]",
        0x09: "SFVTL[+]",
        0x0A: "SPVFS",
        0x0B: "SFVFS",
        0x0C: "GPV",
        0x0D: "GFV",
        0x0E: "SFVTPV",
        0x0F: "ISECT",
        0x10: "SRP0",
        0x11: "SRP1",
        0x12: "SRP2",
        0x13: "SZP0",
        0x14: "SZP1",
        0x15: "SZP2",
        0x16: "SZPS",
        0x17: "SLOOP",
        0x18: "RTG",
        0x19: "RTHG",
        0x1A: "SMD",
        0x1B: "ELSE",
        0x1C: "JMPR",
        0x1D: "SCVTCI",
        0x1E: "SSWCI",
        0x1F: "SSW",
        0x20: "DUP",
        0x21: "POP",
        0x22: "CLEAR",
        0x23: "SWAP",
        0x24: "DEPTH",
        0x25: "CINDEX",
        0x26: "MINDEX",
        0x27: "ALIGNPTS",
        0x29: "UTP",
        0x2A: "LOOPCALL",
        0x2B: "CALL",
        0x2C: "FDEF",
        0x2D: "ENDF",
        0x2E: "MDAP[nr]",
        0x2F: "MDAP[rnd]",
        0x30: "IUP[y]",
        0x31: "IUP[x]",
        0x32: "SHP[rp2]",
        0x33: "SHP[rp1]",
        0x34: "SHC[rp2]",
        0x35: "SHC[rp1]",
        0x36: "SHZ[rp2]",
        0x37: "SHZ[rp1]",
        0x38: "SHPIX",
        0x39: "IP",
        0x3A: "MSIRP[nr]",
        0x3B: "MSIRP[rp0]",
        0x3C: "ALIGNRP",
        0x3D: "RTDG",
        0x3E: "MIAP[nr]",
        0x3F: "MIAP[rnd]",
        0x40: "NPUSHB",
        0x41: "NPUSHW",
        0x42: "WS",
        0x43: "RS",
        0x44: "WCVTP",
        0x45: "RCVT",
        0x46: "GC[cur]",
        0x47: "GC[org]",
        0x48: "SCFS",
        0x49: "MD[grid]",
        0x4A: "MD[org]",
        0x4B: "MPPEM",
        0x4C: "MPS",
        0x4D: "FLIPON",
        0x4E: "FLIPOFF",
        0x4F: "DEBUG",
        0x50: "LT",
        0x51: "LTEQ",
        0x52: "GT",
        0x53: "GTEQ",
        0x54: "EQ",
        0x55: "NEQ",
        0x56: "ODD",
        0x57: "EVEN",
        0x58: "IF",
        0x59: "EIF",
        0x5A: "AND",
        0x5B: "OR",
        0x5C: "NOT",
        0x5D: "DELTAP1",
        0x5E: "SDB",
        0x5F: "SDS",
        0x60: "ADD",
        0x61: "SUB",
        0x62: "DIV",
        0x63: "MUL",
        0x64: "ABS",
        0x65: "NEG",
        0x66: "FLOOR",
        0x67: "CEILING",
        0x70: "WCVTF",
        0x71: "DELTAP2",
        0x72: "DELTAP3",
        0x73: "DELTAC1",
        0x74: "DELTAC2",
        0x75: "DELTAC3",
        0x76: "SROUND",
        0x77: "S45ROUND",
        0x78: "JROT",
        0x79: "JROF",
        0x7A: "ROFF",
        0x7C: "RUTG",
        0x7D: "RDTG",
        0x7E: "SANGW",
        0x7F: "AA",
        0x80: "FLIPPT",
        0x81: "FLIPRGON",
        0x82: "FLIPRGOFF",
        0x85: "SCANCTRL",
        0x86: "SDPVTL[||]",
        0x87: "SDPVTL[+]",
        0x88: "GETINFO",
        0x89: "IDEF",
        0x8A: "ROLL",
        0x8B: "MAX",
        0x8C: "MIN",
        0x8D: "SCANTYPE",
        0x8E: "INSTCTRL",
    }
    for opcode, name in names.items():
        m[opcode] = name
    for k in range(4):
        m[0x68 + k] = f"ROUND[{k}]"
        m[0x6C + k] = f"NROUND[{k}]"
    for k in range(8):
        m[0xB0 + k] = f"PUSHB[{k + 1}]"
        m[0xB8 + k] = f"PUSHW[{k + 1}]"
    for op in range(0xC0, 0xE0):
        m[op] = f"MDRP[{op & 0x1F:x}]"
    for op in range(0xE0, 0x100):
        m[op] = f"MIRP[{op & 0x1F:x}]"
    return m


_MNEMONICS = _build_mnemonics()


class ExecutionTracer:
    """Mirrors upstream package-private ``ExecutionTracer``; ``out`` is a text stream."""

    __slots__ = ("_out", "_trace_point")

    def __init__(self, out: TextIO, trace_point: int = -1) -> None:
        """``trace_point`` is a glyph-zone point whose current coordinate is appended to each line.

        That localizes silent point-position divergence; -1 omits it.
        """
        self._out = out
        self._trace_point = trace_point

    @staticmethod
    def mnemonic(opcode: int) -> str:
        """Returns the mnemonic for an opcode value 0-255."""
        return _MNEMONICS[opcode & 0xFF]

    def trace(self, pc: int, opcode: int, ctx: ExecutionContext) -> None:
        """Emits a trace line for the instruction about to execute (its stack is sampled)."""
        parts = [f"{pc:06d}  {_MNEMONICS[opcode & 0xFF]:<11s}"]
        trace_point = self._trace_point
        if trace_point >= 0:
            zone = ctx.get_glyph_zone()
            if zone is not None and trace_point < zone.get_point_count():
                parts.append(
                    f" P{trace_point}=({zone.get_current_x()[trace_point]},"
                    f"{zone.get_current_y()[trace_point]})"
                )
        parts.append(" #")
        # top of stack first, matching FreeType's ttinterp window
        window = min(_STACK_WINDOW, ctx.get_stack_depth())
        for k in range(window):
            parts.append(f" {ctx.peek(k)}")
        print("".join(parts), file=self._out)


__all__ = ["ExecutionTracer"]
