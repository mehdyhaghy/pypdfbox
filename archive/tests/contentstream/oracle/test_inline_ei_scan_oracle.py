"""Live PDFBox differential parity for inline-image ``ID...EI`` length scan.

Targets the EI-terminator detection in the binary ``ID``...``EI`` scan — the
tricky part of inline-image (BI/ID/EI) parsing. After ``ID `` the parser reads
the raw binary image data until it finds ``EI`` followed by whitespace AND not
followed by binary data (``hasNoFollowingBinData``). A literal ``E I`` byte
pair *inside* the payload must NOT terminate the segment prematurely; only the
real terminator does.

We craft byte buffers where ``EI`` appears mid-stream as a false terminator
(followed by binary control bytes, a high byte > 0x7F, or an over-long
non-operator token) and verify pypdfbox's ``PDFStreamParser`` extracts the
exact same image-data length / bytes as Apache PDFBox's ``PDFStreamParser`` via
the ``InlineEiScanProbe`` Java oracle.

Canonical block grammar (must match ``oracle/probes/InlineEiScanProbe.java``)::

    IMGLEN:<len>          extracted inline-image byte length
    IMGSHA:<sha1>         SHA-1 of the extracted bytes (lower-hex)
    IMGHEAD:<hex>         first up to 16 bytes, lower-hex
    IMGTAIL:<hex>         last up to 16 bytes, lower-hex
    OPS:<n>               total token count (post-EI resync sanity)
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# Inline-image parameter dict + ``ID `` prefix common to every case.
# /W /H /BPC /CS are nominal; the EI-scan heuristic is byte-driven and does
# NOT consult the declared dimensions in PDFBox 3.0.x (it scans for a valid
# EI<sep> terminator), so the payloads below need not match W*H*BPC.
_BI = b"q BI /W 4 /H 4 /BPC 8 /CS /G ID "


def _case_real_ei_then_q() -> bytes:
    # Simplest real terminator: binary bytes, then EI followed by ' Q'.
    payload = bytes([0x00, 0x10, 0x7F, 0x05, 0x20, 0x41, 0x42, 0x43])
    return _BI + payload + b"EI Q\n"


def _case_false_ei_high_byte() -> bytes:
    # 'E' 'I' then a high byte (> 0x7F) -> hasNoFollowingBinData is false
    # (binary), so this EI must be skipped. Real EI follows later + ' Q'.
    payload = bytes([0x01, 0x45, 0x49, 0xFF, 0x02, 0x03, 0x10])
    return _BI + payload + b"EI Q\n"


def _case_false_ei_then_space_then_binary() -> bytes:
    # 'E' 'I' <space> then a control byte (< 0x09, != 0) -> binary.
    payload = bytes([0x45, 0x49, 0x20, 0x01, 0x02, 0x45, 0x49, 0x20, 0x77])
    return _BI + payload + b"EI Q\n"


def _case_false_ei_long_token() -> bytes:
    # 'E' 'I' <space> then a > 3-char non-operator token, non-number, with
    # 10 ASCII bytes available -> PDFBOX-3742 long-operator rule rejects it
    # as binary, so this EI is skipped.
    payload = b"\x05\x06EI ABCDEFGH \x07"
    return _BI + payload + b"EI Q\n"


def _case_false_ei_then_q_is_real() -> bytes:
    # 'E' 'I' <space> 'Q' -> Q is an accepted following operator, so this is
    # treated as the REAL terminator (the heuristic stops here). Verifies we
    # don't over-scan past a legitimate EI.
    payload = bytes([0x10, 0x20, 0x30])
    return _BI + payload + b"EI Q\n"


def _case_false_ei_then_number_is_real() -> bytes:
    # 'E' 'I' <space> '123' -> a number is accepted (PDFBOX-5957), so this is
    # the real terminator.
    payload = bytes([0x40, 0x41, 0x42])
    return _BI + payload + b"EI 123 w\n"


def _case_real_ei_at_eof() -> bytes:
    # EI at the very end of the buffer (no trailing separator). Upstream's
    # loop terminates via the isEOF guard; the trailing 'E' 'I' are NOT
    # written into the image data.
    payload = bytes([0x00, 0x11, 0x22, 0x33])
    return _BI + payload + b"EI"


def _case_embedded_ei_in_long_binary() -> bytes:
    # Several false 'E' 'I' pairs embedded in a longer binary blob, each
    # followed by binary, then the real EI + ' Q'.
    payload = (
        bytes([0x80, 0x45, 0x49, 0x90])
        + bytes([0x45, 0x49, 0x01])
        + bytes([0x45, 0x49, 0xFE, 0x00, 0x7F])
    )
    return _BI + payload + b"EI Q\n"


def _case_ei_followed_by_emc() -> bytes:
    # PDFBOX-2376: EMC is an accepted following operator.
    payload = bytes([0x12, 0x34, 0x56])
    return _BI + payload + b"EI EMC\n"


def _case_ei_followed_by_s() -> bytes:
    # PDFBOX-3784: S is an accepted following operator.
    payload = bytes([0x09, 0x0A, 0x0D, 0x20])
    return _BI + payload + b"EI S\n"


_CASES = {
    "real_ei_then_q": _case_real_ei_then_q(),
    "false_ei_high_byte": _case_false_ei_high_byte(),
    "false_ei_then_space_then_binary": _case_false_ei_then_space_then_binary(),
    "false_ei_long_token": _case_false_ei_long_token(),
    "ei_then_q_real": _case_false_ei_then_q_is_real(),
    "ei_then_number_real": _case_false_ei_then_number_is_real(),
    "real_ei_at_eof": _case_real_ei_at_eof(),
    "embedded_ei_in_long_binary": _case_embedded_ei_in_long_binary(),
    "ei_then_emc": _case_ei_followed_by_emc(),
    "ei_then_s": _case_ei_followed_by_s(),
}


def _pypdfbox_blocks(data: bytes) -> str:
    parser = PDFStreamParser.from_bytes(data)
    tokens = parser.parse()
    out: list[str] = []
    for tok in tokens:
        if isinstance(tok, Operator):
            img = tok.get_image_data()
            if img is not None and tok.get_name() == "ID":
                sha = hashlib.sha1(img).hexdigest()  # noqa: S324 - parity hash
                out.append(f"IMGLEN:{len(img)}")
                out.append(f"IMGSHA:{sha}")
                out.append(f"IMGHEAD:{img[:16].hex()}")
                out.append(f"IMGTAIL:{img[-16:].hex()}")
    out.append(f"OPS:{len(tokens)}")
    return "".join(line + "\n" for line in out)


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_inline_ei_scan_matches_pdfbox(name: str) -> None:
    data = _CASES[name]
    with tempfile.NamedTemporaryFile(
        suffix=".cs", delete=False
    ) as handle:
        handle.write(data)
        tmp_path = handle.name
    try:
        java = run_probe_text("InlineEiScanProbe", tmp_path)
        py = _pypdfbox_blocks(data)
        assert py == java
    finally:
        Path(tmp_path).unlink()
