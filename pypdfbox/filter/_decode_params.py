"""Shared ``/DecodeParms`` resolution for the per-filter decode path.

Both ``FlateDecode`` and ``LZWDecode`` need to pull their effective
``/DecodeParms`` (predictor geometry, ``EarlyChange``, …) out of the
parameters they are handed. Upstream PDFBox routes this through
``org.apache.pdfbox.filter.Filter#getDecodeParams(COSDictionary, int)``
which **consults the ``/Filter`` entry** to validate the shape per ISO
32000-1 §7.3.8.2:

* single ``/Filter`` name + dict ``/DecodeParms`` → that dict;
* array ``/Filter`` + array ``/DecodeParms`` → ``arr[index]`` if it is a
  dictionary, else an empty dictionary;
* any mismatch (notably an **array ``/Filter`` paired with a single dict
  ``/DecodeParms``**, or a single name paired with an array) → an empty
  dictionary. Upstream never applies a lone dict to a multi-filter chain.

The earlier pypdfbox per-filter resolver ignored ``/Filter`` entirely and
returned a single dict ``/DecodeParms`` for *every* filter index, so a
chain such as ``[/ASCIIHexDecode /FlateDecode]`` carrying one dict would
wrongly apply that dict's predictor to FlateDecode where upstream applies
none — a behavioural divergence that garbles the decode (wave 1572).

This resolver mirrors upstream while preserving one pypdfbox-specific
convenience that the rest of the codebase relies on: when neither a
``/Filter`` entry nor a ``/DecodeParms`` / ``/DP`` entry is present, the
parameters dictionary is treated as the decode-params dictionary itself.
That lets callers invoke a codec directly with a flat predictor dict
(``flate.decode(enc, dec, predictor_dict)``) without wrapping it in a
synthetic stream dictionary.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

_F = COSName.get_pdf_name("F")
_FILTER = COSName.get_pdf_name("Filter")
_DP = COSName.get_pdf_name("DP")
_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")


def resolve_decode_params(
    parameters: COSDictionary | None, index: int
) -> COSDictionary:
    """Return the effective ``/DecodeParms`` for the filter at ``index``.

    See module docstring for the full shape table. Returns a fresh empty
    ``COSDictionary`` on any malformed / mismatched shape so the calling
    codec falls back to its defaults exactly as upstream does.
    """
    if parameters is None:
        return COSDictionary()

    filter_obj = parameters.get_dictionary_object(_F, _FILTER)
    # Upstream resolves ``getDictionaryObject(DECODE_PARMS, DP)`` —
    # ``/DecodeParms`` (long form) takes precedence, falling back to the
    # ``/DP`` abbreviation when the long key is absent.
    params_obj = parameters.get_dictionary_object(_DECODE_PARMS, _DP)

    if isinstance(filter_obj, COSArray):
        # Multi-filter chain. Upstream pairs an array /Filter ONLY with an
        # array /DecodeParms; a single dict (or any non-array) must NOT be
        # applied to a filter in the chain — that is the divergence wave
        # 1572 fixes. Resolve the parallel entry, else an empty dict.
        if isinstance(params_obj, COSArray) and index < params_obj.size():
            try:
                entry = params_obj.get_object(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
        return COSDictionary()

    # Single filter (a /Filter name, OR no /Filter at all — the latter is
    # the pypdfbox direct-codec convenience where a caller hands the codec
    # a flat stream/params dict without wrapping it in a synthetic stream).
    if isinstance(params_obj, COSDictionary):
        # Single filter + dict params → that dict.
        return params_obj
    if isinstance(params_obj, COSArray):
        # Single filter + array params: upstream treats this as a mismatch
        # and returns empty. But a direct-codec caller with no /Filter may
        # still index a parallel array, so honour the indexed entry when no
        # /Filter is present; with a /Filter name it is a true mismatch.
        if filter_obj is None and index < params_obj.size():
            try:
                entry = params_obj.get_object(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
        return COSDictionary()

    if filter_obj is None and params_obj is None:
        # pypdfbox convenience: no /Filter and no /DecodeParms means the
        # caller passed a flat predictor dict directly to the codec.
        return parameters

    # Remaining shapes (a /Filter name with non-dict, non-array params)
    # are malformed; upstream returns an empty dictionary.
    return COSDictionary()
