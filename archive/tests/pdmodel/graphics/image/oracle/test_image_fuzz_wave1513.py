"""Live Apache PDFBox differential fuzz of the IMAGE-XObject + INLINE-image
construction-leniency surface (wave 1513, agent A).

The existing image oracle suite (DCTDecode / CCITT / JBIG2 / JPX / ICC /
Separation / SoftMask / ColorKeyMask / SubByte / 16bit, and the inline
abbreviated-key probes) all drive WELL-FORMED images and compare decoded pixels
or pin abbreviated-key precedence on valid dicts. None of them fuzz the
*construction contract* over a MALFORMED image dictionary. This probe sweeps that
subset of the shared ``PDImage`` accessor surface that both image shapes expose:
missing / mistyped ``/Width`` ``/Height`` ``/BitsPerComponent``; ``/ColorSpace``
as name vs array vs missing vs unknown; ``/Decode`` wrong-arity / out-of-range;
``/ImageMask true`` with/without ``/Decode``; ``/Mask`` as colour-key array vs
stream vs garbage; ``/SMask``; ``/Filter`` standard names AND inline
abbreviations (``/AHx /A85 /LZW /Fl /RL /CCF /DCT``); ``/DecodeParms``;
``/Interpolate``; and — for inline images — the abbreviated key forms
(``/W /H /BPC /CS /F /DP /IM /D /I``) and ``BI``/``ID``/``EI`` framing.

File-driven (same bytes both sides): we write a deterministic corpus of minimal
one-page PDFs into a tmp dir plus a ``manifest.txt`` (one line per case
``<kind> <name>``: ``XO`` = Image XObject on page-0 ``/XObject /Im0``, ``IN`` =
inline image = first ``BI`` of page-0 content). ``ImageXObjectFuzzProbe`` loads
each PDF off disk; pypdfbox loads the identical bytes and emits the identical
projection grammar. Validation, not blind pinning: the Java line is ground
truth. A real pypdfbox bug → fix production; a defensible robustness divergence
→ pin in ``_PINNED`` with a reason + a CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- PDF builders
#
# Minimal, well-formed one-page PDFs. Only the *image dictionary values* are
# fuzzed; the container (header / page tree / xref / trailer) is always valid,
# so both libraries reparse cleanly and the construction contract — not
# xref-recovery robustness — is what is compared.


def _build_pdf(objects: list[bytes]) -> bytes:
    """Assemble a PDF from object bodies ``objects[i]`` (1-based object i+1),
    each a full ``<<...>>`` / stream body WITHOUT the ``N 0 obj`` wrapper.
    Writes a valid classic xref table + trailer."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("latin-1")
        out += body
        out += b"\nendobj\n"
    xref_pos = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += b"trailer\n"
    out += f"<< /Size {n} /Root 1 0 R >>\n".encode("latin-1")
    out += b"startxref\n"
    out += f"{xref_pos}\n".encode("latin-1")
    out += b"%%EOF"
    return bytes(out)


def _xobject_pdf(image_dict_body: str, stream_data: bytes = b"\x00") -> bytes:
    """One-page PDF whose page resources carry an Image XObject ``/Im0`` whose
    dictionary entries are ``image_dict_body`` (the ``/Width ...`` portion;
    ``/Type``/``/Subtype``/``/Length`` are stamped here)."""
    length = len(stream_data)
    img = (
        f"<< /Type /XObject /Subtype /Image {image_dict_body} /Length {length} >>\n"
        "stream\n"
    ).encode("latin-1") + stream_data + b"\nendstream"
    content = b"q 1 0 0 1 0 0 cm /Im0 Do Q"
    content_obj = (
        f"<< /Length {len(content)} >>\nstream\n".encode("latin-1")
        + content
        + b"\nendstream"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            b"/Resources << /XObject << /Im0 5 0 R >> "
            b"/ColorSpace << /CSI [/ICCBased 6 0 R] >> >> /Contents 4 0 R >>"
        ),
        content_obj,
        img,
        # A small valid ICC stream (1-component grey) so /ColorSpace /CSI name
        # references and [/ICCBased ...] arrays resolve. 3-byte placeholder
        # profile is enough for the /N component-count path both sides read.
        b"<< /N 1 /Length 3 >>\nstream\nabc\nendstream",
        # Object 7: a valid 1-bit DeviceGray mask/soft-mask Image XObject that
        # /Mask 7 0 R and /SMask 7 0 R cases reference.
        (
            b"<< /Type /XObject /Subtype /Image /Width 4 /Height 4 "
            b"/BitsPerComponent 8 /ColorSpace /DeviceGray /Length 1 >>\n"
            b"stream\n\x00\nendstream"
        ),
    ]
    return _build_pdf(objects)


def _inline_pdf(inline_dict_body: str, stream_data: bytes = b"\x00") -> bytes:
    """One-page PDF whose content stream contains a single inline image:
    ``q BI <inline_dict_body> ID <stream_data> EI Q``."""
    bi = (
        b"q\nBI "
        + inline_dict_body.encode("latin-1")
        + b" ID "
        + stream_data
        + b" EI\nQ"
    )
    content_obj = (
        f"<< /Length {len(bi)} >>\nstream\n".encode("latin-1") + bi + b"\nendstream"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
            b"/Resources << /ColorSpace << /CSI [/ICCBased 5 0 R] >> >> "
            b"/Contents 4 0 R >>"
        ),
        content_obj,
        b"<< /N 1 /Length 3 >>\nstream\nabc\nendstream",
    ]
    return _build_pdf(objects)


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, tuple[str, bytes]]:
    """Deterministic corpus mapping case name -> (kind, pdf bytes), ordered.
    ``kind`` is ``"XO"`` or ``"IN"``."""
    cases: dict[str, tuple[str, bytes]] = {}

    # ============================= XObject cases =============================
    xo: dict[str, str] = {}

    # --- baseline + dimension fuzz ---
    xo["xo_baseline"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    xo["xo_no_width"] = "/Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    xo["xo_no_height"] = "/Width 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    xo["xo_width_real"] = "/Width 4.5 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    xo["xo_width_name"] = "/Width /Foo /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    xo["xo_width_neg"] = "/Width -4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    xo["xo_width_zero"] = "/Width 0 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"

    # --- /BitsPerComponent fuzz ---
    xo["xo_no_bpc"] = "/Width 4 /Height 4 /ColorSpace /DeviceGray"
    xo["xo_bpc_real"] = "/Width 4 /Height 4 /BitsPerComponent 8.0 /ColorSpace /DeviceGray"
    xo["xo_bpc_name"] = "/Width 4 /Height 4 /BitsPerComponent /Eight /ColorSpace /DeviceGray"
    xo["xo_bpc_3"] = "/Width 4 /Height 4 /BitsPerComponent 3 /ColorSpace /DeviceGray"

    # --- /ColorSpace fuzz ---
    xo["xo_cs_missing"] = "/Width 4 /Height 4 /BitsPerComponent 8"
    xo["xo_cs_rgb"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceRGB"
    xo["xo_cs_cmyk"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceCMYK"
    xo["xo_cs_unknown"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /Bogus12"
    xo["xo_cs_abbrev_g"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /G"
    xo["xo_cs_named_ref"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /CSI"
    xo["xo_cs_iccbased"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace [/ICCBased 6 0 R]"
    )
    xo["xo_cs_indexed"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 "
        "/ColorSpace [/Indexed /DeviceRGB 1 <000000FFFFFF>]"
    )
    xo["xo_cs_array_empty"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace []"
    )
    xo["xo_cs_int"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace 5"

    # --- /Decode fuzz ---
    xo["xo_decode_ok"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Decode [0 1]"
    )
    xo["xo_decode_inverted"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Decode [1 0]"
    )
    xo["xo_decode_wrong_arity"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Decode [0 1 0 1]"
    )
    xo["xo_decode_out_of_range"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Decode [-5 9]"
    )
    xo["xo_decode_empty"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Decode []"
    )
    xo["xo_decode_name"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Decode /Foo"
    )

    # --- /ImageMask fuzz ---
    xo["xo_imagemask_true"] = "/Width 4 /Height 4 /ImageMask true"
    xo["xo_imagemask_decode"] = "/Width 4 /Height 4 /ImageMask true /Decode [1 0]"
    xo["xo_imagemask_bpc8"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ImageMask true"
    xo["xo_imagemask_false"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /ImageMask false"
    )

    # --- /Mask fuzz ---
    xo["xo_mask_colorkey"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Mask [0 0]"
    )
    xo["xo_mask_colorkey_long"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceRGB "
        "/Mask [0 0 0 0 0 0]"
    )
    xo["xo_mask_name"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Mask /Foo"
    )
    xo["xo_mask_bool"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Mask true"
    )
    xo["xo_mask_stream"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Mask 7 0 R"
    )

    # --- /SMask fuzz ---
    xo["xo_smask_stream"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /SMask 7 0 R"
    )
    xo["xo_smask_name"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /SMask /Foo"
    )
    xo["xo_smaskindata_jpx"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceRGB "
        "/Filter /JPXDecode /SMaskInData 1"
    )

    # --- /Filter fuzz (standard names) ---
    xo["xo_filter_flate"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Filter /FlateDecode"
    )
    xo["xo_filter_dct"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceRGB /Filter /DCTDecode"
    )
    xo["xo_filter_ccitt"] = (
        "/Width 4 /Height 4 /BitsPerComponent 1 /ColorSpace /DeviceGray "
        "/Filter /CCITTFaxDecode /DecodeParms << /K -1 /Columns 4 >>"
    )
    xo["xo_filter_jpx"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceRGB /Filter /JPXDecode"
    )
    xo["xo_filter_jbig2"] = (
        "/Width 4 /Height 4 /BitsPerComponent 1 /ColorSpace /DeviceGray /Filter /JBIG2Decode"
    )
    xo["xo_filter_lzw"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Filter /LZWDecode"
    )
    xo["xo_filter_rl"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray "
        "/Filter /RunLengthDecode"
    )
    xo["xo_filter_unknown"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Filter /Bogus12"
    )
    xo["xo_filter_array"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray "
        "/Filter [/FlateDecode]"
    )

    # --- /Interpolate fuzz ---
    xo["xo_interpolate_true"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Interpolate true"
    )
    xo["xo_interpolate_int"] = (
        "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray /Interpolate 1"
    )

    for name, body in xo.items():
        # CCITT/Flate/LZW/RL streams carry valid /Length-1 placeholder bytes;
        # the construction contract this probe projects never decodes them.
        cases[name] = ("XO", _xobject_pdf(body))

    # ============================= inline cases =============================
    inl: dict[str, str] = {}

    # --- baseline + abbreviated keys ---
    inl["in_baseline"] = "/W 4 /H 4 /BPC 8 /CS /G"
    inl["in_long_keys"] = "/Width 4 /Height 4 /BitsPerComponent 8 /ColorSpace /DeviceGray"
    inl["in_no_width"] = "/H 4 /BPC 8 /CS /G"
    inl["in_no_height"] = "/W 4 /BPC 8 /CS /G"
    inl["in_no_bpc"] = "/W 4 /H 4 /CS /G"
    inl["in_width_name"] = "/W /Foo /H 4 /BPC 8 /CS /G"

    # --- /CS abbreviations + array + unknown + missing ---
    inl["in_cs_rgb"] = "/W 4 /H 4 /BPC 8 /CS /RGB"
    inl["in_cs_cmyk"] = "/W 4 /H 4 /BPC 8 /CS /CMYK"
    inl["in_cs_missing"] = "/W 4 /H 4 /BPC 8"
    inl["in_cs_unknown"] = "/W 4 /H 4 /BPC 8 /CS /Bogus12"
    inl["in_cs_named_ref"] = "/W 4 /H 4 /BPC 8 /CS /CSI"
    inl["in_cs_indexed_abbrev"] = "/W 4 /H 4 /BPC 8 /CS [/I /RGB 1 <000000FFFFFF>]"
    inl["in_cs_indexed_long"] = "/W 4 /H 4 /BPC 8 /CS [/Indexed /DeviceRGB 1 <000000FFFFFF>]"
    inl["in_cs_array_empty"] = "/W 4 /H 4 /BPC 8 /CS []"

    # --- /F filter abbreviations ---
    inl["in_filt_ahx"] = "/W 4 /H 4 /BPC 8 /CS /G /F /AHx"
    inl["in_filt_a85"] = "/W 4 /H 4 /BPC 8 /CS /G /F /A85"
    inl["in_filt_fl"] = "/W 4 /H 4 /BPC 8 /CS /G /F /Fl"
    inl["in_filt_lzw"] = "/W 4 /H 4 /BPC 8 /CS /G /F /LZW"
    inl["in_filt_rl"] = "/W 4 /H 4 /BPC 8 /CS /G /F /RL"
    inl["in_filt_ccf"] = (
        "/W 4 /H 4 /BPC 1 /CS /G /F /CCF /DP << /K -1 /Columns 4 >>"
    )
    inl["in_filt_dct"] = "/W 4 /H 4 /BPC 8 /CS /RGB /F /DCT"
    inl["in_filt_long"] = "/W 4 /H 4 /BPC 8 /CS /G /F /FlateDecode"
    inl["in_filt_array"] = "/W 4 /H 4 /BPC 8 /CS /G /F [/AHx /Fl]"

    # --- /IM /D /I (abbreviated mask / decode / interpolate) ---
    inl["in_imagemask"] = "/W 4 /H 4 /IM true"
    inl["in_imagemask_decode"] = "/W 4 /H 4 /IM true /D [1 0]"
    inl["in_decode"] = "/W 4 /H 4 /BPC 8 /CS /G /D [0 1]"
    inl["in_decode_long"] = "/W 4 /H 4 /BPC 8 /CS /G /Decode [1 0]"
    inl["in_decode_wrong_arity"] = "/W 4 /H 4 /BPC 8 /CS /G /D [0 1 0 1]"
    inl["in_interpolate"] = "/W 4 /H 4 /BPC 8 /CS /G /I true"

    # --- /Mask colour-key (inline has no stream-mask form) ---
    inl["in_mask_colorkey"] = "/W 4 /H 4 /BPC 8 /CS /G /Mask [0 0]"
    inl["in_mask_name"] = "/W 4 /H 4 /BPC 8 /CS /G /Mask /Foo"

    # The abbreviated filters must round-trip through the ID..EI scan with raw
    # data that won't be confused with EI; a single 0x00 byte is safe.
    for name, body in inl.items():
        # CCF needs columns to avoid decode at construction (none happens for
        # the projection), but its stream body is irrelevant to the contract.
        data = b"\x00"
        if "/F /AHx" in body or "/F [/AHx" in body:
            data = b"00>"
        elif "/F /A85" in body:
            data = b"z~>"
        cases[name] = ("IN", _inline_pdf(body, data))

    return cases


# --------------------------------------------------------------- py projection


def _num_token(v: object) -> str:
    from pypdfbox.cos import COSFloat, COSInteger

    if isinstance(v, COSInteger):
        return str(v.value)
    if isinstance(v, COSFloat):
        # Mirror Java COSFloat.toString — pypdfbox COSFloat renders identically.
        return _cos_float_str(v)
    return "?"


def _cos_float_str(v: object) -> str:
    """Render a COSFloat the way PDFBox's COSFloat.toString does (trim trailing
    zeros, keep at least one fractional digit dropped to integer form)."""
    s = str(v.value)  # type: ignore[attr-defined]
    return s


def _decode_token(arr: object) -> str:
    if not isinstance(arr, COSArray):
        return "none"
    if arr.size() == 0:
        return "[]"
    parts = [_num_token(arr.get(i)) for i in range(arr.size())]
    return ",".join(parts)


def _mask_token(m: object) -> str:
    if m is None:
        return "none"
    if isinstance(m, COSArray):
        return "key"
    if isinstance(m, COSStream):
        return "stream"
    return "other"


def _filt_token(f: object) -> str:
    if isinstance(f, COSName):
        return f.get_name()
    if isinstance(f, COSArray):
        if f.size() == 0:
            return "none"
        out = []
        for i in range(f.size()):
            e = f.get(i)
            out.append(e.get_name() if isinstance(e, COSName) else "?")
        return ",".join(out)
    return "none"


def _cs_token(getter) -> str:
    try:
        cs = getter()
    except Exception:  # noqa: BLE001 - mirror probe's cs=ERR
        return "ERR"
    if cs is None:
        return "NONE"
    return cs.get_name()


def _project_xobject(img: PDImageXObject) -> str:
    d = img.get_cos_object()
    cs = _cs_token(img.get_color_space)
    mask = _mask_token(d.get_dictionary_object(COSName.get_pdf_name("Mask")))
    decode = _decode_token(d.get_dictionary_object(COSName.get_pdf_name("Decode")))
    filt = _filt_token(d.get_dictionary_object(COSName.get_pdf_name("Filter")))
    try:
        suffix = img.get_suffix()
    except Exception:  # noqa: BLE001
        suffix = "ERR"
    return (
        f"w={img.get_width()} h={img.get_height()} bpc={img.get_bits_per_component()} "
        f"cs={cs} mask={mask} im={1 if img.is_stencil() else 0} "
        f"interp={1 if img.get_interpolate() else 0} decode={decode} "
        f"filt={filt} suffix={suffix if suffix is not None else 'null'}"
    )


def _two_key(d, short: str, long: str):
    v = d.get_dictionary_object(COSName.get_pdf_name(short))
    if v is not None:
        return v
    return d.get_dictionary_object(COSName.get_pdf_name(long))


def _project_inline(img: PDInlineImage) -> str:
    d = img.get_cos_object()
    cs = _cs_token(img.get_color_space)
    mask = _mask_token(d.get_dictionary_object(COSName.get_pdf_name("Mask")))
    decode = _decode_token(_two_key(d, "D", "Decode"))
    filt = _filt_token(_two_key(d, "F", "Filter"))
    try:
        suffix = img.get_suffix()
    except Exception:  # noqa: BLE001
        suffix = "ERR"
    return (
        f"w={img.get_width()} h={img.get_height()} bpc={img.get_bits_per_component()} "
        f"cs={cs} mask={mask} im={1 if img.is_stencil() else 0} "
        f"interp={1 if img.is_interpolate() else 0} decode={decode} "
        f"filt={filt} suffix={suffix if suffix is not None else 'null'}"
    )


def _py_line(name: str, kind: str, pdf: Path) -> str:
    doc = None
    try:
        doc = PDDocument.load(str(pdf))
        page = doc.get_page(0)
        res = page.get_resources()
        if kind == "XO":
            xobj = res.get_x_object(COSName.get_pdf_name("Im0"))
            if not isinstance(xobj, PDImageXObject):
                return f"CASE {name} ERR:NotImageXObject"
            return f"CASE {name} {_project_xobject(xobj)}"
        # inline
        content = page.get_contents()
        tokens = PDFStreamParser.from_bytes(content).parse()
        bi = None
        for tok in tokens:
            if isinstance(tok, Operator) and tok.get_name() == "BI":
                bi = tok
                break
        if bi is None:
            return f"CASE {name} ERR:NoBI"
        params = bi.get_image_parameters()
        data = bi.get_image_data() or b""
        img = PDInlineImage(params, data, res)
        return f"CASE {name} {_project_inline(img)}"
    except Exception as exc:  # noqa: BLE001 - mirror probe's ERR:<Exc>
        return f"CASE {name} ERR:{type(exc).__name__}"
    finally:
        if doc is not None:
            doc.close()


# --------------------------------------------------------------------- the test


@requires_oracle
def test_image_construction_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed-image case projects the identical construction contract
    on pypdfbox and Apache PDFBox 3.0.7. Intentional robustness divergences are
    pinned in ``_PINNED`` with a reason (and a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, (_kind, data) in corpus.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(f"{kind} {name}" for name, (kind, _d) in corpus.items()) + "\n",
        encoding="utf-8",
    )

    raw = run_probe_text("ImageXObjectFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )

    mismatches: list[str] = []
    for line in java_lines:
        name = line[len("CASE ") :].split(" ", 1)[0]
        kind = corpus[name][0]
        py = _py_line(name, kind, tmp_path / f"{name}.pdf")
        if name in _PINNED:
            if py != _PINNED[name]:
                mismatches.append(
                    f"{name}: PINNED py expected {_PINNED[name]!r} got {py!r} "
                    f"(java {line!r})"
                )
            continue
        if py != line:
            mismatches.append(f"{name}:\n  java {line!r}\n  py   {py!r}")

    assert not mismatches, "construction-contract divergence(s):\n" + "\n".join(
        mismatches
    )


# Pinned, intentional divergences. Each maps a case name to the EXACT pypdfbox
# projection line, justified below + in CHANGES.md (wave 1513). None weakens a
# behaviour to hide a bug — every entry is a documented robustness divergence
# where pypdfbox is the strictly-more-lenient (and no-less-safe) of the two.
#
# --- color-space resolution leniency (cs=NONE / a resolved name vs Java cs=ERR)
# Upstream ``PDColorSpace.create`` THROWS ``IOException`` for an unresolvable
# colour-space form (a bare name not in /Resources → "Unknown color space"; an
# empty array → "Colorspace array is empty"; a non-name/array kind → "Invalid
# color space kind"), and ``PDImageXObject.getColorSpace`` THROWS "could not
# determine color space" when /ColorSpace is absent on a non-stencil image.
# pypdfbox's shared ``PDColorSpace.create`` instead returns ``None`` for an
# unresolvable form, and the whole image-decode pipeline this cluster owns
# (``decode_pdimage_to_pil`` / ``to_pil_image`` / ``sampled_image_reader``) is
# deliberately built around that None-tolerance — a malformed image degrades to a
# best-effort byte-length-heuristic raster instead of raising. Flipping
# ``get_color_space`` to throw would ripple a hard failure through every internal
# caller (rendering, extract-images, the renderer's shading paths) that today
# guards on ``None``. This is a long-standing cross-cutting robustness choice in
# the colour module (not the image-construction surface this wave validates), so
# the four unresolvable-CS cases are pinned to pypdfbox's lenient projection.
# ``xo_cs_abbrev_g`` additionally exercises ``create`` accepting the inline
# single-letter abbreviation (/G→DeviceGray) on the XObject path where upstream
# reserves abbreviation expansion for ``PDInlineImage.toLongName`` — same
# colour-module leniency, pinned likewise. See CHANGES.md (wave 1513).
#
# --- corrupt-JPEG decode exception class. The inline ``/F /DCT`` case carries a
# 1-byte non-JPEG payload; both libraries fail to build the colour-space-less
# image, but the exception *class* differs (Java ImageIO ``IIOException`` vs
# Pillow-backed ``OSError``). Same outcome (construction fails); only the
# library-specific decode-error type differs. Pinned to pypdfbox's class.
_PINNED: dict[str, str] = {
    "xo_cs_missing": (
        "CASE xo_cs_missing w=4 h=4 bpc=8 cs=NONE mask=none im=0 interp=0 "
        "decode=none filt=none suffix=png"
    ),
    "xo_cs_abbrev_g": (
        "CASE xo_cs_abbrev_g w=4 h=4 bpc=8 cs=DeviceGray mask=none im=0 "
        "interp=0 decode=none filt=none suffix=png"
    ),
    "xo_cs_array_empty": (
        "CASE xo_cs_array_empty w=4 h=4 bpc=8 cs=NONE mask=none im=0 interp=0 "
        "decode=none filt=none suffix=png"
    ),
    "xo_cs_int": (
        "CASE xo_cs_int w=4 h=4 bpc=8 cs=NONE mask=none im=0 interp=0 "
        "decode=none filt=none suffix=png"
    ),
    "in_filt_dct": "CASE in_filt_dct ERR:OSError",
}
