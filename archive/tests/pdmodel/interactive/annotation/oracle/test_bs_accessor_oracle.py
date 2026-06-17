"""Live Apache PDFBox differential parity for the PDBorderStyleDictionary
(``/BS``) TYPED ACCESSOR DEFAULTS.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation``
:class:`PDBorderStyleDictionary` — the exact ``get_width()`` / ``get_style()``
/ dash-array defaults Apache PDFBox 3.0.7 exposes when each ``/W`` / ``/S`` /
``/D`` key is present vs. absent.

This is narrower and more default-focused than ``BorderStyleProbe`` (which
round-trips a built four-annotation fixture): here every interesting branch of
the three getters is exercised in isolation on a hand-built ``COSDictionary``,
so a divergence in a single default value is pinpointed.

Defaulting facts verified against the oracle (PDF 32000-1 §12.5.4 / Table 166)
-----------------------------------------------------------------------------
* ``getWidth()``:
  - empty dict (no ``/W``)            -> ``1`` (``getFloat(W, 1f)``)
  - ``/W 0``                           -> ``0`` (no border)
  - ``/W 2.5``                         -> ``2.5``
  - ``/W`` as a ``COSName`` (Adobe quirk) -> ``0`` (contradicts spec; PDFBox
    returns 0). pypdfbox replicates this in :meth:`get_width`.
* ``getStyle()``:
  - empty dict (no ``/S``)             -> ``"S"`` (``getNameAsString(S, "S")``)
  - ``/S /D``                          -> ``"D"``
* ``getDashStyle()`` — the upstream method is a MUTATING accessor: when ``/D``
  is absent it seeds ``[3]`` into the dict and returns the typed pattern (never
  null). pypdfbox faithfully maps this to
  :meth:`PDBorderStyleDictionary.get_dash_style_or_default` (the appearance
  handlers call that one). pypdfbox additionally exposes a non-mutating
  :meth:`get_dash_style` that returns ``None`` for an absent ``/D`` — a
  documented pypdfbox-only convenience with NO upstream equivalent, asserted
  here to stay None / side-effect-free.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "BsAccessorProbe"

_W: COSName = COSName.get_pdf_name("W")
_D: COSName = COSName.get_pdf_name("D")


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _floats(arr) -> str:
    if not arr:
        return "none"
    return ",".join(_canon_float(v) for v in arr)


def _empty() -> PDBorderStyleDictionary:
    return PDBorderStyleDictionary(COSDictionary())


def _py_facts() -> str:
    sb: list[str] = []

    # ---- get_width() ----
    sb.append(f"width_empty={_canon_float(_empty().get_width())}")

    w0 = _empty()
    w0.set_width(0)
    sb.append(f"width_zero={_canon_float(w0.get_width())}")

    w25 = _empty()
    w25.get_cos_object().set_item(_W, COSFloat(2.5))
    sb.append(f"width_2p5={_canon_float(w25.get_width())}")

    wname = _empty()
    wname.get_cos_object().set_item(_W, COSName.get_pdf_name("Foo"))
    sb.append(f"width_name={_canon_float(wname.get_width())}")

    # ---- get_style() ----
    sb.append(f"style_empty={_empty().get_style()}")

    sd = _empty()
    sd.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    sb.append(f"style_dashed={sd.get_style()}")

    # ---- getDashStyle() (mutating) -> get_dash_style_or_default ----
    d_empty = _empty()
    pattern = d_empty.get_dash_style_or_default()
    # upstream getDashStyle() never returns null here; pypdfbox's
    # get_dash_style_or_default mirrors that ("false").
    sb.append(f"dash_empty_null={str(pattern is None).lower()}")
    sb.append(f"dash_empty_arr={_floats(pattern.get_dash_array())}")
    seeded = d_empty.get_cos_object().get_dictionary_object(_D)
    sb.append(
        "dash_empty_seeded="
        + (
            _floats(seeded.to_float_array())
            if isinstance(seeded, COSArray)
            else "none"
        )
    )

    d_present = _empty()
    arr = COSArray()
    arr.add(COSInteger.get(4))
    arr.add(COSInteger.get(2))
    d_present.get_cos_object().set_item(_D, arr)
    sb.append(f"dash_present_arr={_floats(d_present.get_dash_style().get_dash_array())}")

    return "\n".join(sb) + "\n"


@requires_oracle
def test_bs_accessor_defaults_match_pdfbox() -> None:
    """Every ``/BS`` typed-accessor default (``get_width`` / ``get_style`` /
    the mutating dash accessor) matches Apache PDFBox 3.0.7 exactly."""
    java = run_probe_text(_PROBE, "facts")
    py = _py_facts()
    assert py == java, (
        f"BS accessor-default mismatch:\n--- pypdfbox ---\n{py}\n"
        f"--- PDFBox ---\n{java}"
    )
    # Sanity: pin the load-bearing defaults so a regression is legible.
    assert "width_empty=1" in py  # absent /W -> 1
    assert "width_name=0" in py  # /W as a name -> 0 (Adobe quirk)
    assert "style_empty=S" in py  # absent /S -> "S"
    assert "dash_empty_null=false" in py  # getDashStyle never null
    assert "dash_empty_seeded=3" in py  # absent /D seeds [3] into the dict


def test_get_dash_style_is_non_mutating_pypdfbox_extension() -> None:
    """``get_dash_style`` (the pypdfbox-only non-mutating convenience, NO
    upstream equivalent) returns ``None`` for an absent ``/D`` and does NOT
    seed the dict — the side-effect-free counterpart to the upstream-faithful
    ``get_dash_style_or_default``."""
    bs = _empty()
    assert bs.get_dash_style() is None
    # No /D was seeded by the read.
    assert bs.get_cos_object().get_dictionary_object(_D) is None
