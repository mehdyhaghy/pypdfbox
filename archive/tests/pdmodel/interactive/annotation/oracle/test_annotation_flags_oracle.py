"""Live Apache PDFBox differential parity for annotation COMMON properties.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation``

* ``PDAnnotation`` ``/F`` flag predicates — ``is_invisible`` / ``is_hidden`` /
  ``is_printed`` / ``is_no_zoom`` / ``is_no_rotate`` / ``is_no_view`` /
  ``is_read_only`` / ``is_locked`` / ``is_toggle_no_view`` /
  ``is_locked_contents``.
* ``PDBorderStyleDictionary`` (``/BS``) — ``get_width()`` / ``get_style()`` /
  ``get_dash_style()`` (dash array + phase).
* ``PDAppearanceCharacteristicsDictionary`` (``/MK``) — ``get_rotation()`` /
  ``get_border_colour()`` / ``get_background()`` component counts /
  ``get_normal_caption()``.

How it works
------------
The Java probe ``AnnotFlagsProbe`` runs in two modes:

* ``read <pdf>`` — load a PDF and print, per annotation, a canonical block:
  the ten ``/F`` flag predicates, the ``/BS`` width/style/dash, and the ``/MK``
  rotation + ``/BC`` and ``/BG`` colour-component counts + caption. ``/BS`` and
  ``/MK`` are read directly off the annotation COS dictionary so the probe is
  uniform across every subtype (matching pypdfbox's per-subclass surface).
* ``write <pdf>`` — build a one-widget PDF whose annotation sets *every* ``/F``
  bit, a ``/BS`` (width + dashed style + dash array) and an ``/MK`` (rotation +
  3-component ``/BC`` + 4-component ``/BG`` + caption), so every flag/border/MK
  branch is exercised in the comparison.

pypdfbox loads the same PDFs and builds the identical canonical block; the two
blocks are compared exactly across annotation-bearing fixtures plus the
all-bits-set built fixture.

Parity result (wave 1415)
--------------------------
Flag predicates, border style (width/style/dash/phase) and ``/MK``
(rotation + colour component counts + caption) match Apache PDFBox exactly on
every annotation of every fixture.

API-shape note (documented divergence, NOT a bug)
-------------------------------------------------
Upstream ``PDBorderStyleDictionary.getDashStyle()`` *always* returns a
non-null pattern: when ``/D`` is absent it seeds and returns the spec default
``[3]`` (and writes it back into the dictionary). pypdfbox split that into two
accessors — ``get_dash_style()`` (returns ``None`` when ``/D`` is absent, no
side effect) and ``get_dash_style_or_default()`` (the upstream-faithful one
that seeds ``[3]``). The appearance handlers use ``get_dash_style_or_default``,
so rendered borders match. This probe reads the dash array via
``get_dash_style_or_default()`` — the upstream-equivalent accessor — so the
``/BS`` dash comparison verifies genuine behavioural parity with Java's
``getDashStyle()``. Same precedent as the ``getPageLayout`` / ``getPageMode``
vs ``get_*_or_default()`` note in ``CHANGES.md``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAppearanceCharacteristicsDictionary,
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "AnnotFlagsProbe"

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures"
_ANNOT_DIR = _FIXTURES / "pdmodel" / "interactive" / "annotation"
_FORM_DIR = _FIXTURES / "pdmodel" / "interactive" / "form"

# Fixtures with rich common-property coverage: AnnotationTypes carries the full
# subtype zoo (markup + popup + square + widgets); the AcroForm fixtures carry
# widgets with /BS (width + style I/S) and /MK (rotation 0/90/180/270, /BC and
# /BG with 1/3 components, captions).
_READ_FIXTURES = [
    _ANNOT_DIR / "AnnotationTypes.pdf",
    _FORM_DIR / "AcroFormsBasicFields.pdf",
    _FORM_DIR / "AcroFormsRotation.pdf",
    _FORM_DIR / "PDFBOX-5784.pdf",
    _FORM_DIR / "PDFBOX-3656-SF1199AEG (Complete).pdf",
]

_BS: COSName = COSName.get_pdf_name("BS")
_MK: COSName = COSName.get_pdf_name("MK")


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors AnnotFlagsProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _flags_line(annot) -> str:
    def bit(flag: bool) -> int:
        return 1 if flag else 0

    return (
        "FLAGS"
        f" inv={bit(annot.is_invisible())}"
        f" hid={bit(annot.is_hidden())}"
        f" prt={bit(annot.is_printed())}"
        f" nzm={bit(annot.is_no_zoom())}"
        f" nrt={bit(annot.is_no_rotate())}"
        f" nvw={bit(annot.is_no_view())}"
        f" ro={bit(annot.is_read_only())}"
        f" lck={bit(annot.is_locked())}"
        f" tnv={bit(annot.is_toggle_no_view())}"
        f" lc={bit(annot.is_locked_contents())}"
    )


def _border_line(annot) -> str:
    cos = annot.get_cos_object()
    bs_dict = cos.get_dictionary_object(_BS)
    if not isinstance(bs_dict, COSDictionary):
        return "BS none"
    bs = PDBorderStyleDictionary(bs_dict)
    parts = [f"BS w={_canon_float(bs.get_width())}", f"s={bs.get_style()}"]
    # Upstream-faithful accessor: getDashStyle() always returns a pattern,
    # seeding the default [3] when /D is absent. pypdfbox splits this;
    # get_dash_style_or_default() is the upstream-equivalent and never returns
    # None (see module docstring API-shape note).
    dash = bs.get_dash_style_or_default()
    arr = dash.get_dash_array()
    if not arr:
        parts.append("dash=none")
    else:
        parts.append("dash=" + ",".join(_canon_float(v) for v in arr))
    parts.append(f"phase={int(dash.get_phase())}")
    return " ".join(parts)


def _mk_line(annot) -> str:
    cos = annot.get_cos_object()
    mk_dict = cos.get_dictionary_object(_MK)
    if not isinstance(mk_dict, COSDictionary):
        return "MK none"
    mk = PDAppearanceCharacteristicsDictionary(mk_dict)
    border = mk.get_border_colour()
    bg = mk.get_background()
    bc = len(border.get_components()) if border is not None else -1
    bg_n = len(bg.get_components()) if bg is not None else -1
    ca = mk.get_normal_caption()
    return f"MK r={mk.get_rotation()} bc={bc} bg={bg_n} ca={'none' if ca is None else ca}"


def _rect_str(annot) -> str:
    r = annot.get_rectangle()
    if r is None:
        return "none"
    # Canonical floats (not round()) so the sort key never diverges from Java
    # on a half-rounding boundary (Java Math.round is half-up, Python round()
    # is banker's rounding).
    return ",".join(
        _canon_float(v)
        for v in (
            r.get_lower_left_x(),
            r.get_lower_left_y(),
            r.get_upper_right_x(),
            r.get_upper_right_y(),
        )
    )


def _py_blocks(path: Path) -> str:
    """Build the same canonical, per-page-sorted block listing pypdfbox would
    emit, byte-for-byte matching AnnotFlagsProbe's read output."""
    out: list[str] = []
    doc = PDDocument.load(path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            blocks: list[str] = []
            for annot in page.get_annotations():
                subtype = annot.get_subtype() or "?"
                key = (
                    f"p{page_index} {subtype} {_rect_str(annot)}"
                    f" f{annot.get_annotation_flags()}"
                )
                block = (
                    f"ANNOT {subtype}\n"
                    f"KEY {key}\n"
                    f"{_flags_line(annot)}\n"
                    f"{_border_line(annot)}\n"
                    f"{_mk_line(annot)}\n"
                    "END\n"
                )
                blocks.append(block)
            blocks.sort()
            out.extend(blocks)
    finally:
        doc.close()
    return "".join(out)


@requires_oracle
def test_annotation_common_properties_match_pdfbox() -> None:
    """Flag predicates + /BS + /MK match Apache PDFBox exactly across every
    annotation of every annotation-bearing fixture."""
    for fixture in _READ_FIXTURES:
        assert fixture.is_file(), f"missing fixture: {fixture}"
        java = run_probe_text(_PROBE, "read", str(fixture))
        py = _py_blocks(fixture)
        assert py == java, (
            f"common-property block mismatch for {fixture.name}:\n"
            f"--- pypdfbox ---\n{py}\n--- PDFBox ---\n{java}"
        )


@requires_oracle
def test_all_flag_bits_border_and_mk_branches() -> None:
    """Built fixture sets every /F bit + a dashed /BS + a full /MK so every
    flag/border/MK branch is exercised; pypdfbox matches Apache PDFBox."""
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "annot_flags.pdf")
        run_probe_text(_PROBE, "write", out)
        java = run_probe_text(_PROBE, "read", out)
        py = _py_blocks(Path(out))
    assert py == java, (
        f"all-bits-set block mismatch:\n--- pypdfbox ---\n{py}\n"
        f"--- PDFBox ---\n{java}"
    )
    # Sanity: the built block must show every flag set and the full /BS + /MK.
    assert "inv=1 hid=1 prt=1 nzm=1 nrt=1 nvw=1 ro=1 lck=1 tnv=1 lc=1" in py
    assert "BS w=3 s=D dash=4,2 phase=0" in py
    assert "MK r=90 bc=3 bg=4 ca=Submit" in py
