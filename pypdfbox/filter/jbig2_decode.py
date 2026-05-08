from __future__ import annotations

import io
from typing import BinaryIO, Final

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSStream

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# ISO 32000-1 §7.4.7 JBIG2Decode parameter keys.
_JBIG2_GLOBALS: Final[str] = "JBIG2Globals"


def _resolve_decode_params(parameters: COSDictionary | None, index: int) -> COSDictionary:
    """Resolve effective ``/DecodeParms`` for the filter at ``index``.

    Mirrors the convention used by :mod:`ccitt_fax_decode` /
    :mod:`flate_decode`: the ``parameters`` argument is the *stream
    dictionary*, from which we pull ``/DecodeParms`` (single dict or
    array indexed by filter position). Missing entries return an empty
    dict so callers can use ``get_dictionary_object`` defaults
    uniformly. Falls back to ``parameters`` itself when the caller
    handed us the decode-params dict directly (this is how the
    hand-written tests invoke the filter).
    """
    if parameters is None:
        return COSDictionary()
    for key in ("DecodeParms", "DP"):
        params = parameters.get_dictionary_object(key)
        if isinstance(params, COSDictionary):
            return params
        if isinstance(params, COSArray):
            try:
                entry = params.get(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
            return COSDictionary()
    return parameters


def _read_globals_bytes(decode_params: COSDictionary) -> bytes:
    """Pull and decode the ``/JBIG2Globals`` stream, if present.

    The globals entry is itself a content stream (may carry its own
    ``/Filter`` chain — typically ``/FlateDecode``). ``COSStream.to_byte_array``
    runs the chain so we get the raw global-segment bytes the JBIG2
    codec expects to see prepended to the per-image segments.
    """
    globals_obj = decode_params.get_dictionary_object(_JBIG2_GLOBALS)
    if globals_obj is None:
        return b""
    if not isinstance(globals_obj, COSStream):
        # Spec permits only a stream here; defend against malformed
        # input by treating anything else as no globals rather than
        # crashing the whole image decode.
        return b""
    return globals_obj.to_byte_array()


class JBIG2Decode(Filter):
    """``/JBIG2Decode`` filter (ISO 32000-1 §7.4.7).

    Decodes a JBIG2 (ITU-T T.88) bilevel image stream by delegating to
    the Rust-backed ``jbig2_parser`` library, whose ``parse_jbig2``
    entrypoint returns a PNG-encoded buffer that we re-decode through
    Pillow to recover raw bilevel sample bytes.

    JBIG2 is bilevel by definition (one bit per pixel, packed MSB-first
    into bytes) so the decoded output and the surfaced parameters are
    fixed at ``/BitsPerComponent = 1`` and ``/ColorComponents = 1``.
    Geometry (``/Width``, ``/Height``) is intrinsic to the codestream
    and surfaced via ``DecodeResult.parameters`` so callers can patch
    the image XObject when those entries are absent.

    Per spec the only ``/DecodeParms`` entry is ``/JBIG2Globals``: a
    stream containing shared symbol / page dictionaries. When present,
    its decoded bytes are prepended to the per-image stream before
    handoff. Decoder-only — there is no PDF producer use case for
    JBIG2 in pypdfbox.

    Mirrors `org.apache.pdfbox.filter.JBIG2Filter`.
    """

    #: ``/JBIG2Globals`` parameter key per ISO 32000-1 §7.4.7. Exposed
    #: as a class attribute so callers reaching for the upstream
    #: ``COSName.JBIG2_GLOBALS`` reference site land on a stable name.
    JBIG2_GLOBALS: Final[str] = _JBIG2_GLOBALS

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        # Lazy import: ``jbig2_parser`` ships with a Rust extension and
        # we don't want every filter import to drag it in until a JBIG2
        # stream is actually decoded.
        import jbig2_parser  # type: ignore[import-untyped]

        decode_params = _resolve_decode_params(parameters, index)
        globals_bytes = _read_globals_bytes(decode_params)

        encoded_bytes = encoded.read()
        out_params = parameters if parameters is not None else COSDictionary()
        if not encoded_bytes and not globals_bytes:
            return DecodeResult(parameters=out_params, bytes_written=0)

        # Per ISO 32000-1 §7.4.7 the globals segments must logically
        # precede the per-image segments. The codestream is a sequence
        # of self-delimiting JBIG2 segments, so naive concatenation is
        # the canonical way to feed both halves to a decoder that
        # accepts a single buffer.
        jbig2_input = globals_bytes + encoded_bytes

        try:
            png_bytes = jbig2_parser.parse_jbig2(jbig2_input)
        except Exception as exc:
            raise OSError(f"JBIG2Decode: jbig2_parser decode failed: {exc}") from exc

        try:
            with Image.open(io.BytesIO(png_bytes)) as image:
                bilevel = image if image.mode == "1" else image.convert("1")
                bilevel.load()
                samples = bilevel.tobytes()
                width, height = bilevel.size
        except Exception as exc:
            raise OSError(
                f"JBIG2Decode: post-decode PNG handoff failed: {exc}"
            ) from exc

        bytes_written = decoded.write(samples)

        out_params.set_int("Width", width)
        out_params.set_int("Height", height)
        # JBIG2 is bilevel by ITU-T T.88 definition.
        out_params.set_int("BitsPerComponent", 1)
        out_params.set_int("ColorComponents", 1)
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        raise NotImplementedError(
            "JBIG2Decode.encode is not implemented (decode-only)"
        )


# PDF spec defines NO short-name abbreviation for /JBIG2Decode
# (ISO 32000-1 §7.4.2 Table 6) — register only the long name.
FilterFactory.register("JBIG2Decode", JBIG2Decode())
