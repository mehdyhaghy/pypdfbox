"""Live PDFBox differential parity for ``PDInlineImage`` abbreviated-key
resolution precedence (PDF 32000-1 §8.9.7).

``PDInlineImage``'s scalar getters (``get_width`` / ``get_height`` /
``get_bits_per_component`` / ``is_stencil`` / ``get_interpolate``) read the
inline-image parameter dictionary via the two-key overloads
``COSDictionary#getInt(short, long, default)`` /
``getBoolean(short, long, default)``. Those overloads delegate to
``getDictionaryObject(firstKey, secondKey)``, which:

* resolves a ``COSNull`` first-key value to ``None`` and then falls back to the
  second (long-form) key, and
* returns the ``default`` — *without* re-consulting the long key — when the
  first key resolves to a non-null value of the wrong type.

The earlier ``contains_key``-based two-key helper short-circuited on raw key
presence, so a ``COSNull`` short value masked the long-form fallback. This
module pins the exact precedence against Apache PDFBox 3.0.7 via
``oracle/probes/InlineImageKeyResolveProbe.java`` (no input file — all cases
are constructed in-process for deterministic literals).
"""

from __future__ import annotations

from tests.oracle.harness import requires_oracle, run_probe_text


@requires_oracle
def test_inline_image_key_resolution_matches_pdfbox() -> None:
    text = run_probe_text("InlineImageKeyResolveProbe")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    got = dict(ln.split("=", 1) for ln in lines)

    # These literals are also asserted directly (oracle-free) in
    # tests/pdmodel/graphics/image/test_pd_inline_image.py.
    assert got == {
        "both_W_Width": "7",
        "only_Width": "42",
        "Wnull_Width13": "13",
        "Wnull_only": "-1",
        "Hname_Height21": "-1",
        "BPCnull_BPCfull4": "4",
        "IMnull_ImageMaskTrue": "true",
        "IMfalse_ImageMaskTrue": "false",
        "Inull_InterpolateTrue": "true",
    }
