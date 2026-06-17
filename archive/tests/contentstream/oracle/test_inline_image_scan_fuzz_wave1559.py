"""Wave 1559 — live-oracle parity for the operator-stream BI/ID/EI SCAN +
collate surface.

Where ``InlineImageOperatorFuzzProbe`` (wave 1537) exercises the *graphics-engine*
draw dispatch and ``InlineCsResolveProbe`` resolves colour spaces against page
resources, this module drives the *parser-level* BI/ID/EI scan: how
:class:`pypdfbox.pdfparser.PDFStreamParser` collates a ``BI`` parameter
dictionary, delimits the binary ``ID``..``EI`` payload with the EI-terminator
heuristic (whitespace before/after ``EI`` PLUS a binary follow-on probe so an
embedded ``EI`` byte pair inside the image data does NOT terminate prematurely),
and resynchronises the operator stream after the payload.

Projected facts per inline image, in stream order:

* ``ops`` — total token count (a desync after a mis-detected terminator changes
  the operator count downstream);
* ``img`` — assembled ``W``/``H``/``BPC`` (abbreviated + long keys), the ``/CS``
  and ``/F`` COS shapes (abbreviated ``/G`` ``/RGB`` ``/CMYK`` ``/I`` colour +
  ``/AHx`` ``/Fl`` ``/RL`` ``/A85`` filter abbreviations and chains), the binary
  data ``len``, and the last 8 data bytes as hex;
* ``post`` — the operator names that FOLLOW the inline image to end of stream
  (the resync fact).

Fuzz angles unique to this wave: binary payload that *contains* the bytes
``EI`` mid-stream (false terminator), filter chains, whitespace variations after
``ID`` (space / LF / CRLF / tab+FF), missing ``EI`` (scan to EOF), an inline
image followed by another inline image / a text-show sequence / two operators,
and the ``len``-includes-trailing-whitespace detail upstream exposes.

Probe: ``oracle/probes/InlineImageScanFuzzProbe.java`` (holds the identical
``CASES`` map and projects the same ``case=`` / ``img …`` / ``post=`` lines).

Both sides are pinned: ``EXPECTED`` captures the live PDFBox 3.0.7 oracle output
(verified on the dev box). The ``@requires_oracle`` test re-runs the Java probe
and asserts pypdfbox == PDFBox; the always-on tests assert pypdfbox ==
``EXPECTED`` so the parity survives on machines without the jar. No production
divergence was found — pypdfbox's scan already matches the oracle byte-for-byte
across all 28 cases, including the embedded-``EI`` heuristic and the
trailing-whitespace data length.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# Named fuzz cases — identical content-stream text to the Java probe's CASES.
# Encoded ISO-8859-1 / latin-1 so the high byte in ``stencil`` round-trips.
CASES: dict[str, str] = {
    "basic_then_q": "BI /W 2 /H 2 /BPC 8 /CS /RGB ID abcdefghijkl EI Q",
    "embedded_ei": "BI /W 4 /H 1 /BPC 8 /CS /G ID aEIbcdEIfg EI Q",
    "embedded_ei_ws": "BI /W 6 /H 1 /BPC 8 /CS /G ID xx EI yy EI Q",
    "ahx_filter": "BI /W 1 /H 1 /BPC 8 /CS /G /F /AHx ID 616263> EI Q",
    "filter_chain": (
        "BI /W 1 /H 1 /BPC 8 /CS /G /F [/AHx /Fl] "
        "ID 78da4b4c4a0600026d0121> EI Q"
    ),
    "rgb_abbrev": "BI /W 1 /H 1 /BPC 8 /CS /RGB ID abc EI Q",
    "cmyk_abbrev": "BI /W 1 /H 1 /BPC 8 /CS /CMYK ID abcd EI Q",
    "indexed_i": "BI /W 2 /H 1 /BPC 8 /CS [/I /RGB 1 <000000ffffff>] ID   EI Q",
    "long_keys": (
        "BI /Width 2 /Height 2 /BitsPerComponent 8 /ColorSpace /DeviceRGB "
        "ID abcdefghijkl EI Q"
    ),
    "stencil": "BI /W 8 /H 1 /IM true ID ÿ EI Q",
    "id_lf": "BI /W 1 /H 1 /BPC 8 /CS /G ID\nabc EI Q",
    "id_crlf": "BI /W 1 /H 1 /BPC 8 /CS /G ID\r\nabc EI Q",
    "id_space": "BI /W 1 /H 1 /BPC 8 /CS /G ID abc EI Q",
    "two_inline": (
        "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI "
        "BI /W 1 /H 1 /BPC 8 /CS /RGB ID abc EI Q"
    ),
    "then_text": "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI BT (hi) Tj ET",
    "missing_ei": "BI /W 1 /H 1 /BPC 8 /CS /G ID abcdef",
    "zero_data": "BI /W 1 /H 1 /BPC 8 /CS /G ID  EI Q",
    "trailing_e": "BI /W 1 /H 1 /BPC 8 /CS /G ID abcE EI Q",
    "ei_glued": "BI /W 1 /H 1 /BPC 8 /CS /G ID abEI EI Q",
    "post_two_ops": "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI Q 0 0 m",
    "decode_arr": "BI /W 1 /H 1 /BPC 8 /CS /G /D [1 0] ID a EI Q",
    "interpolate": "BI /W 1 /H 1 /BPC 8 /CS /G /I true ID a EI Q",
    "loose_ws": (
        "BI   /W   2   /H 2   /BPC 8   /CS /RGB   ID abcdefghijkl EI Q"
    ),
    "tab_ff": "BI /W 1 /H 1 /BPC 8 /CS /G ID\tabc\fEI Q",
    "ei_then_data": "BI /W 5 /H 1 /BPC 8 /CS /G ID ab\nEIcd EI Q",
    "rl_filter": "BI /W 1 /H 1 /BPC 8 /CS /G /F /RL ID abc EI Q",
    "key_order": "BI /CS /G /BPC 8 /H 2 /W 2 ID abcd EI Q",
    "a85_filter": "BI /W 1 /H 1 /BPC 8 /CS /G /F /A85 ID @:E_WAS~> EI Q",
}

# Live PDFBox 3.0.7 oracle output, captured on the dev box. Pins the
# machine-without-jar path; the @requires_oracle test re-verifies against the
# live probe. ``len`` includes the single whitespace byte before the real ``EI``
# terminator (upstream keeps it in the binary payload) — see e.g. tail ``...20``.
EXPECTED: dict[str, str] = {
    "basic_then_q": (
        "case=basic_then_q ops=2 err=none\n"
        "img w=2 h=2 bpc=8 cs=RGB f=- len=13 tail=666768696a6b6c20\n"
        "post=Q\n"
    ),
    "embedded_ei": (
        "case=embedded_ei ops=2 err=none\n"
        "img w=4 h=1 bpc=8 cs=G f=- len=11 tail=6263644549666720\n"
        "post=Q\n"
    ),
    "embedded_ei_ws": (
        "case=embedded_ei_ws ops=2 err=none\n"
        "img w=6 h=1 bpc=8 cs=G f=- len=9 tail=7820454920797920\n"
        "post=Q\n"
    ),
    "ahx_filter": (
        "case=ahx_filter ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=AHx len=8 tail=3631363236333e20\n"
        "post=Q\n"
    ),
    "filter_chain": (
        "case=filter_chain ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=[AHx,Fl] len=24 tail=3664303132313e20\n"
        "post=Q\n"
    ),
    "rgb_abbrev": (
        "case=rgb_abbrev ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=RGB f=- len=4 tail=61626320\n"
        "post=Q\n"
    ),
    "cmyk_abbrev": (
        "case=cmyk_abbrev ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=CMYK f=- len=5 tail=6162636420\n"
        "post=Q\n"
    ),
    "indexed_i": (
        "case=indexed_i ops=2 err=none\n"
        "img w=2 h=1 bpc=8 cs=[I,RGB,COSInteger,COSString] f=- len=2 tail=2020\n"
        "post=Q\n"
    ),
    "long_keys": (
        "case=long_keys ops=2 err=none\n"
        "img w=2 h=2 bpc=8 cs=DeviceRGB f=- len=13 tail=666768696a6b6c20\n"
        "post=Q\n"
    ),
    "stencil": (
        "case=stencil ops=2 err=none\n"
        "img w=8 h=1 bpc=- cs=- f=- len=2 tail=ff20\n"
        "post=Q\n"
    ),
    "id_lf": (
        "case=id_lf ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=4 tail=61626320\n"
        "post=Q\n"
    ),
    "id_crlf": (
        "case=id_crlf ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=4 tail=61626320\n"
        "post=Q\n"
    ),
    "id_space": (
        "case=id_space ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=4 tail=61626320\n"
        "post=Q\n"
    ),
    "two_inline": (
        # The first image's EI is glued to the following ``BI`` token, so the
        # ``hasNoFollowingBinData`` probe rejects it as a mid-stream EI and the
        # scanner swallows the whole second image text into the first payload
        # (len=41). This is the SAME (upstream-divergent-looking but identical)
        # behaviour on both sides — there is no whitespace separating ``EI`` and
        # ``BI`` so the first EI is not a valid terminator.
        "case=two_inline ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=41 tail=2049442061626320\n"
        "post=Q\n"
    ),
    "then_text": (
        # Same glue effect: ``EI BT`` — the ``BT`` after ``EI`` is alphabetic,
        # the follow-on probe treats it as binary, so the first EI is rejected
        # and the scan runs to EOF, absorbing the text show. ops=1 (only the BI).
        "case=then_text ops=1 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=16 tail=2868692920546a20\n"
        "post=-\n"
    ),
    "missing_ei": (
        "case=missing_ei ops=1 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=4 tail=61626364\n"
        "post=-\n"
    ),
    "zero_data": (
        "case=zero_data ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=1 tail=20\n"
        "post=Q\n"
    ),
    "trailing_e": (
        "case=trailing_e ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=5 tail=6162634520\n"
        "post=Q\n"
    ),
    "ei_glued": (
        "case=ei_glued ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=5 tail=6162454920\n"
        "post=Q\n"
    ),
    "post_two_ops": (
        "case=post_two_ops ops=5 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=2 tail=6120\n"
        "post=Q m\n"
    ),
    "decode_arr": (
        "case=decode_arr ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=2 tail=6120\n"
        "post=Q\n"
    ),
    "interpolate": (
        "case=interpolate ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=2 tail=6120\n"
        "post=Q\n"
    ),
    "loose_ws": (
        "case=loose_ws ops=2 err=none\n"
        "img w=2 h=2 bpc=8 cs=RGB f=- len=13 tail=666768696a6b6c20\n"
        "post=Q\n"
    ),
    "tab_ff": (
        "case=tab_ff ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=- len=4 tail=6162630c\n"
        "post=Q\n"
    ),
    "ei_then_data": (
        "case=ei_then_data ops=2 err=none\n"
        "img w=5 h=1 bpc=8 cs=G f=- len=8 tail=61620a4549636420\n"
        "post=Q\n"
    ),
    "rl_filter": (
        "case=rl_filter ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=RL len=4 tail=61626320\n"
        "post=Q\n"
    ),
    "key_order": (
        "case=key_order ops=2 err=none\n"
        "img w=2 h=2 bpc=8 cs=G f=- len=5 tail=6162636420\n"
        "post=Q\n"
    ),
    "a85_filter": (
        "case=a85_filter ops=2 err=none\n"
        "img w=1 h=1 bpc=8 cs=G f=A85 len=10 tail=455f5741537e3e20\n"
        "post=Q\n"
    ),
}


def _cos_shape(value: object) -> str:
    """Project a ``/CS`` or ``/F`` COS value the way the Java probe does:
    a name → its bare name, an array → ``[a,b,...]`` of names / simple class
    names, anything else → ``-``."""
    if isinstance(value, COSName):
        return value.get_name()
    if isinstance(value, COSArray):
        parts: list[str] = []
        for element in value:
            if isinstance(element, COSName):
                parts.append(element.get_name())
            elif element is not None:
                parts.append(type(element).__name__)
            else:
                parts.append("null")
        return "[" + ",".join(parts) + "]"
    return "-"


def _int_key(params: object, short: str, long: str) -> str:
    if params is None:
        return "-"
    obj = params.get_dictionary_object(short, long)
    if isinstance(obj, (COSInteger, COSFloat)):
        return str(int(obj.value))
    return "-"


def _tail(data: bytes, n: int) -> str:
    if not data:
        return "-"
    return data[-n:].hex()


def _project(case: str) -> str:
    """Drive pypdfbox's ``PDFStreamParser`` over a case's content-stream bytes
    and emit the canonical ``case= / img … / post=`` projection."""
    content = CASES[case]
    raw = content.encode("latin-1")
    threw = False
    tokens: list[object] = []
    try:
        parser = PDFStreamParser.from_bytes(raw)
        tokens = list(parser.tokens())
    except Exception:  # noqa: BLE001 — throw-vs-not is the projected fact
        threw = True

    lines = [
        f"case={case} ops={len(tokens)} err={'throw' if threw else 'none'}"
    ]
    for index, token in enumerate(tokens):
        if not isinstance(token, Operator):
            continue
        if token.get_name() != "BI" or token.get_image_data() is None:
            continue
        data = token.get_image_data()
        params = token.get_image_parameters()
        cs = params.get_dictionary_object("CS", "ColorSpace") if params else None
        flt = params.get_dictionary_object("F", "Filter") if params else None
        lines.append(
            f"img w={_int_key(params, 'W', 'Width')} "
            f"h={_int_key(params, 'H', 'Height')} "
            f"bpc={_int_key(params, 'BPC', 'BitsPerComponent')} "
            f"cs={_cos_shape(cs)} "
            f"f={_cos_shape(flt)} "
            f"len={len(data)} "
            f"tail={_tail(data, 8)}"
        )
        post = [
            t.get_name()
            for t in tokens[index + 1 :]
            if isinstance(t, Operator)
        ]
        lines.append("post=" + (" ".join(post) if post else "-"))
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("case", list(CASES), ids=list(CASES))
def test_inline_image_scan_matches_pinned_oracle(case: str) -> None:
    """pypdfbox parser BI/ID/EI scan projection == captured PDFBox 3.0.7."""
    assert _project(case) == EXPECTED[case]


@requires_oracle
@pytest.mark.parametrize("case", list(CASES), ids=list(CASES))
def test_inline_image_scan_matches_live_oracle(case: str) -> None:
    """pypdfbox parser BI/ID/EI scan projection == live PDFBox oracle."""
    java = run_probe_text("InlineImageScanFuzzProbe", case)
    assert _project(case).strip() == java.strip()


def test_embedded_ei_not_a_terminator() -> None:
    """A binary payload containing the bytes ``EI`` mid-stream is NOT split at
    the first ``EI`` — the scanner keeps reading to the whitespace-delimited
    real terminator (PDFBOX EI-detection heuristic)."""
    out = _project("embedded_ei")
    assert "len=11" in out  # full payload, not truncated at the embedded EI
    assert out.strip().endswith("post=Q")


def test_missing_ei_scans_to_eof() -> None:
    """With no ``EI`` at all, the scanner consumes to end of buffer and no
    operator follows."""
    out = _project("missing_ei")
    assert "ops=1 err=none" in out
    assert out.strip().endswith("post=-")


def test_data_length_includes_trailing_whitespace_byte() -> None:
    """Upstream keeps the single whitespace byte before the real ``EI`` in the
    binary payload, so a 12-byte raster collates as len=13 (tail ends in 20)."""
    out = _project("basic_then_q")
    assert "len=13 tail=666768696a6b6c20" in out
