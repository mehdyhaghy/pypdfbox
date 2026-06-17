"""Live Apache PDFBox differential fuzz of the IMAGE-XObject metadata-accessor
construction contract, built IN MEMORY (wave 1546, agent B).

Complements the file-driven ``ImageXObjectFuzzProbe`` / ``test_image_fuzz_wave1513``
(which loads malformed PDFs off disk and projects a coarse one-line summary).
This probe builds each ``PDImageXObject`` programmatically over a fuzzed
``COSStream`` — no file round-trip, no parser/xref involvement — and projects the
FINER accessor surface wave 1513 did not exercise:

* ``get_color_key_mask()`` decoded ``int`` list (not just the key/stream/other
  bucket) over array / float-array / stream / name ``/Mask`` forms;
* ``get_decode_array()`` raw array incl. wrong-arity, empty, non-numeric, and
  not-an-array ``/Decode``;
* ``get_mask()`` stream vs none + ``get_soft_mask()`` over a non-stream
  ``/SMask`` (name / array);
* ``get_struct_parent()`` default / value;
* ``get_suffix()`` across the full filter matrix incl. JBIG2 and an unsupported
  (ASCII85-only) filter that maps to ``None``;
* ``get_bits_per_component()`` stencil-forcing to 1 regardless of the dict entry
  and the no-validation passthrough of bpc 0 / 3;
* ``/Width`` ``/Height`` 0 / negative / missing / float / name.

The Java probe (``oracle/probes/ImageXObjectMetaFuzzProbe.java``) emits one line
per case; pypdfbox reproduces the same projection and the two are compared
token-by-token. Validation, not blind pinning: the Java line is ground truth. A
real pypdfbox bug -> fix production; a defensible robustness divergence -> pin in
``_PINNED`` with a reason + a CHANGES.md row.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- COS helpers


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _ints(*xs: int) -> COSArray:
    a = COSArray()
    for x in xs:
        a.add(COSInteger.get(x))
    return a


def _floats(*xs: float) -> COSArray:
    a = COSArray()
    for x in xs:
        a.add(COSFloat(float(x)))
    return a


def _image_stream(data: bytes = b"\x00" * 64) -> COSStream:
    s = COSStream()
    s.set_item(_name("Type"), _name("XObject"))
    s.set_item(_name("Subtype"), _name("Image"))
    with s.create_output_stream() as out:
        out.write(data)
    return s


def _xobj(cos: COSStream) -> PDImageXObject:
    return PDImageXObject(PDStream(cos), None)


# --------------------------------------------------------------- projection


def _cs_token(img: PDImageXObject) -> str:
    try:
        cs = img.get_color_space()
    except Exception:  # noqa: BLE001 - mirror Java's broad catch -> ERR
        return "ERR"
    return "NONE" if cs is None else cs.get_name()


def _array_token(arr: COSArray | None) -> str:
    """Comma-joined numeric/canonical token for a /Decode COSArray (matches the
    Java side after normalisation in :func:`_normalise_java`)."""
    if arr is None:
        return "none"
    if len(arr) == 0:
        return "[]"
    parts = []
    for item in arr:
        if isinstance(item, COSInteger):
            parts.append(str(item.value))
        elif isinstance(item, COSFloat):
            parts.append(_num(item.value))
        else:
            parts.append("?")
    return ",".join(parts)


def _ckey_token(img: PDImageXObject) -> str:
    vals = img.get_color_key_mask()
    if vals is None:
        return "none"
    if len(vals) == 0:
        return "[]"
    return ",".join(str(int(v)) for v in vals)


def _mask_token(img: PDImageXObject) -> str:
    try:
        m = img.get_mask()
    except Exception:  # noqa: BLE001
        return "ERR"
    return "none" if m is None else "stream"


def _smask_token(img: PDImageXObject) -> str:
    try:
        m = img.get_soft_mask()
    except Exception:  # noqa: BLE001
        return "ERR"
    return "none" if m is None else "stream"


def _num(value: float) -> str:
    """Canonical numeric token: ``4.5`` -> ``4.5``, ``1.0`` -> ``1.0``."""
    return repr(float(value))


def _project(name: str, img: PDImageXObject) -> str:
    suffix = img.get_suffix()
    return (
        f"CASE {name}"
        f" w={img.get_width()}"
        f" h={img.get_height()}"
        f" bpc={img.get_bits_per_component()}"
        f" im={'1' if img.is_stencil() else '0'}"
        f" cs={_cs_token(img)}"
        f" decode={_array_token(img.get_decode_array())}"
        f" ckey={_ckey_token(img)}"
        f" mask={_mask_token(img)}"
        f" smask={_smask_token(img)}"
        f" sp={img.get_struct_parent()}"
        f" suffix={'null' if suffix is None else suffix}"
    )


def _suffix_case(name: str, filter_name: COSName | None) -> str:
    cos = _image_stream(b"\x00")
    cos.set_int(_name("Width"), 4)
    cos.set_int(_name("Height"), 4)
    cos.set_int(_name("BitsPerComponent"), 8)
    cos.set_item(_name("ColorSpace"), _name("DeviceGray"))
    if filter_name is not None:
        cos.set_item(COSName.FILTER, filter_name)
    img = _xobj(cos)
    suffix = img.get_suffix()
    return f"CASE {name} suffix={'null' if suffix is None else suffix}"


# --------------------------------------------------------------- case corpus
#
# Each builder returns (name, line). Order is identical to the Java probe's
# main() so the captured oracle text lines up case-for-case.


def _build_cases() -> list[str]:
    lines: list[str] = []

    def full(name: str, cos: COSStream) -> None:
        lines.append(_project(name, _xobj(cos)))

    # ---- /Width /Height fuzz ----
    full("wh_missing", _image_stream())

    c = _image_stream()
    c.set_int(_name("Width"), 0)
    c.set_int(_name("Height"), 0)
    full("wh_zero", c)

    c = _image_stream()
    c.set_int(_name("Width"), -4)
    c.set_int(_name("Height"), -4)
    full("wh_negative", c)

    c = _image_stream()
    c.set_item(_name("Width"), COSFloat(4.5))
    c.set_item(_name("Height"), COSFloat(4.5))
    full("wh_float", c)

    c = _image_stream()
    c.set_item(_name("Width"), _name("x"))
    full("w_name", c)

    # ---- /BitsPerComponent fuzz ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 16)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    full("bpc_16", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 3)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    full("bpc_3", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 0)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    full("bpc_0", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BPC"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    full("bpc_short_alias", c)

    # ---- /ImageMask stencil forcing ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_item(_name("ImageMask"), COSBoolean.TRUE)
    full("imagemask_true_no_bpc", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_item(_name("ImageMask"), COSBoolean.TRUE)
    c.set_int(_name("BitsPerComponent"), 8)
    full("imagemask_true_bpc8", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_item(_name("ImageMask"), COSBoolean.FALSE)
    c.set_int(_name("BitsPerComponent"), 1)
    full("imagemask_false", c)

    # ---- /ColorSpace fuzz ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceRGB"))
    full("cs_devicergb", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("Bogus"))
    full("cs_unknown_name", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    full("cs_missing", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_item(_name("ImageMask"), COSBoolean.TRUE)
    full("cs_missing_stencil", c)

    # ---- /Decode fuzz ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Decode"), _floats(0.0, 1.0))
    full("decode_normal", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Decode"), _floats(1.0, 0.0))
    full("decode_reversed", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceRGB"))
    c.set_item(_name("Decode"), _floats(0.0, 1.0))
    full("decode_wrong_arity", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Decode"), COSArray())
    full("decode_empty", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    mixed = COSArray()
    mixed.add(COSInteger.get(0))
    mixed.add(_name("oops"))
    c.set_item(_name("Decode"), mixed)
    full("decode_nonnumeric", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Decode"), _name("notarray"))
    full("decode_not_array", c)

    # ---- /Mask fuzz ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Mask"), _ints(0, 5))
    full("mask_colorkey", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Mask"), _ints(0, 5, 0, 5, 0, 5))
    full("mask_colorkey_rgb", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Mask"), _floats(0.0, 5.0))
    full("mask_colorkey_float", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Mask"), _image_stream(b"\x00"))
    full("mask_stream", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Mask"), _name("garbage"))
    full("mask_name", c)

    # ---- /SMask fuzz ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("SMask"), _image_stream(b"\x00"))
    full("smask_stream", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("SMask"), _ints(0, 5))
    full("smask_array", c)

    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("SMask"), _name("nope"))
    full("smask_name", c)

    # ---- /Interpolate fuzz ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_item(_name("Interpolate"), COSInteger.get(1))
    full("interp_int", c)

    # ---- /StructParent ----
    c = _image_stream()
    c.set_int(_name("Width"), 4)
    c.set_int(_name("Height"), 4)
    c.set_int(_name("BitsPerComponent"), 8)
    c.set_item(_name("ColorSpace"), _name("DeviceGray"))
    c.set_int(_name("StructParent"), 7)
    full("structparent_7", c)

    # ---- /Suffix across filter matrix ----
    lines.append(_suffix_case("suffix_no_filter", None))
    lines.append(_suffix_case("suffix_flate", _name("FlateDecode")))
    lines.append(_suffix_case("suffix_lzw", _name("LZWDecode")))
    lines.append(_suffix_case("suffix_runlength", _name("RunLengthDecode")))
    lines.append(_suffix_case("suffix_dct", _name("DCTDecode")))
    lines.append(_suffix_case("suffix_jpx", _name("JPXDecode")))
    lines.append(_suffix_case("suffix_ccitt", _name("CCITTFaxDecode")))
    lines.append(_suffix_case("suffix_jbig2", _name("JBIG2Decode")))
    lines.append(_suffix_case("suffix_ascii85", _name("ASCII85Decode")))

    return lines


# --------------------------------------------------------------- divergences
#
# {case_name: (python_token_overrides_applied_to_oracle_line)}. Each entry maps
# a token KEY to the value pypdfbox emits where it DEFENSIBLY diverges from the
# Java oracle, so the oracle's raw line is rewritten to pypdfbox's contract
# before comparison. Every entry carries a one-line justification.

_PINNED: dict[str, dict[str, str]] = {
    # getColorSpace(): Java raises IOException ("missing colorspace" /
    # "unknown colorspace name") for a non-stencil image with absent or
    # unresolvable /ColorSpace -> the probe catches it as cs=ERR. pypdfbox
    # returns None (cs=NONE) rather than raising, matching the rest of the
    # image cluster's lenient accessor contract (a None colour space lets the
    # raster fall through to the byte-length heuristic in decode). Pinned.
    "cs_missing": {"cs": "NONE"},
    "cs_unknown_name": {"cs": "NONE"},
    "imagemask_false": {"cs": "NONE"},
    # /Width /Height /BitsPerComponent absent -> w/h/bpc = -1; getColorSpace()
    # then sees no colour space and (non-stencil) raises in Java but returns
    # None in pypdfbox. Same divergence family as above.
    "wh_missing": {"cs": "NONE"},
    "wh_zero": {"cs": "NONE"},
    "wh_negative": {"cs": "NONE"},
    "wh_float": {"cs": "NONE"},
    "w_name": {"cs": "NONE"},
}


def _normalise_java(line: str) -> str:
    """Rewrite a Java oracle line into pypdfbox's canonical token form.

    * ``COSFloat{0.0}`` -> ``0.0`` and ``COSInteger{...}`` -> the int so the
      ``decode=`` token matches :func:`_array_token`.
    * Apply any :data:`_PINNED` per-case token overrides (defensible
      divergences).
    """
    # Canonicalise COSFloat / COSInteger renderings inside the decode token.
    out = line.replace("COSFloat{", "").replace("COSInteger{", "")
    out = out.replace("}", "")
    if not out.startswith("CASE "):
        return out
    name = out.split(" ", 2)[1]
    overrides = _PINNED.get(name)
    if not overrides:
        return out
    tokens = out.split(" ")
    for i, tok in enumerate(tokens):
        if "=" in tok:
            key = tok.split("=", 1)[0]
            if key in overrides:
                tokens[i] = f"{key}={overrides[key]}"
    return " ".join(tokens)


@requires_oracle
def test_image_xobject_metadata_matches_pdfbox() -> None:
    raw = run_probe_text("ImageXObjectMetaFuzzProbe").strip().splitlines()
    java_lines = [_normalise_java(line.strip()) for line in raw if line.strip().startswith("CASE ")]
    py_lines = _build_cases()
    assert len(py_lines) == len(java_lines), (
        f"case count mismatch: py={len(py_lines)} java={len(java_lines)}"
    )
    for py_line, java_line in zip(py_lines, java_lines, strict=True):
        assert py_line == java_line


def test_case_corpus_is_self_consistent() -> None:
    """Oracle-free guard: the corpus builds without error and pins the
    documented divergences. Runs everywhere (no java/javac needed)."""
    lines = _build_cases()
    by_name = {line.split(" ", 2)[1]: line for line in lines}

    # cs=NONE divergence is the pypdfbox contract (Java raises).
    assert "cs=NONE" in by_name["cs_missing"]
    assert "cs=NONE" in by_name["cs_unknown_name"]
    assert "cs=NONE" in by_name["imagemask_false"]

    # Stencil forces bpc=1 regardless of the /BitsPerComponent entry.
    assert "bpc=1" in by_name["imagemask_true_bpc8"]
    assert "im=1" in by_name["imagemask_true_bpc8"]

    # No bpc validation: 0 and 3 pass through untouched (matches Java).
    assert "bpc=3" in by_name["bpc_3"]
    assert "bpc=0" in by_name["bpc_0"]

    # /BPC short alias resolves.
    assert "bpc=8" in by_name["bpc_short_alias"]

    # /Width 4.5 truncates to 4 (get_int -> int_value), matching Java.
    assert "w=4 h=4" in by_name["wh_float"]

    # Color-key vs stencil /Mask: array -> ckey, stream -> mask=stream.
    assert "ckey=0,5" in by_name["mask_colorkey"]
    assert "mask=stream" in by_name["mask_stream"]
    assert "ckey=none mask=none" in by_name["mask_name"]

    # /SMask only a stream is a soft mask; array/name -> none.
    assert "smask=stream" in by_name["smask_stream"]
    assert "smask=none" in by_name["smask_array"]
    assert "smask=none" in by_name["smask_name"]

    # Non-numeric /Decode still surfaces the raw array (get_decode_array).
    assert "decode=0,?" in by_name["decode_nonnumeric"]
    assert "decode=none" in by_name["decode_not_array"]

    # Suffix matrix.
    assert by_name["suffix_dct"].endswith("suffix=jpg")
    assert by_name["suffix_jpx"].endswith("suffix=jpx")
    assert by_name["suffix_ccitt"].endswith("suffix=tiff")
    assert by_name["suffix_jbig2"].endswith("suffix=jb2")
    assert by_name["suffix_flate"].endswith("suffix=png")
    assert by_name["suffix_ascii85"].endswith("suffix=null")
