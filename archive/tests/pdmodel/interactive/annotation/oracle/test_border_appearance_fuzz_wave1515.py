"""Differential fuzz audit for the annotation border-style (``/BS``) and
appearance-characteristics (``/MK``) dictionaries vs Apache PDFBox 3.0.7
(wave 1515, agent E).

Complements the well-formed border-style / MK oracle suites
(``test_border_style_oracle``, ``test_bs_accessor_oracle``,
``test_widget_icon_oracle``) — none of which exercise the MALFORMED subset this
audit targets:

* :class:`PDBorderStyleDictionary` ``/BS``: ``/W`` width as a number / missing /
  negative / a real / a name (Adobe quirk: a name ``/W`` reads as 0) / a string;
  ``/S`` style enum (``S``/``D``/``B``/``I``/``U``/unknown/missing/as a string →
  default ``S``); ``/D`` dash array (well-formed / empty / non-numeric / missing
  / a single number / a name instead of an array);
* :class:`PDAppearanceCharacteristicsDictionary` ``/MK``: ``/R`` rotation
  (multiple of 90 / non-multiple / negative / a real / missing / a name);
  ``/BC`` border colour and ``/BG`` background colour arrays with 0/1/3/4
  components (→ DeviceGray / DeviceRGB / DeviceCMYK, empty = no colour) and a
  wrong-type (name / number) entry; ``/CA`` normal caption (string / name /
  missing); the ``/MK`` dict altogether missing.

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case (a single Widget annotation on the page whose ``/BS`` and ``/MK``
sub-dicts are the mutated dictionaries) plus a ``manifest.txt`` into a tmp dir.
The Java probe (``oracle/probes/BorderAppearanceFuzzProbe.java``) loads each
``<case>.pdf`` and projects a stable framed line; this module reads the exact
same files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> bs_w=<n|ERR:X> bs_s=<style|ERR:X> bs_d=<floats|none|empty|ERR:X>
        mk_r=<n|ERR:X> mk_bc=<comp-count|none|ERR:X> mk_bg=<comp-count|none|ERR:X>
        mk_ca=<caption|none|ERR:X>

Java is ground truth: a real divergence is a production fix in the border-style
/ appearance-characteristics classes under
``pypdfbox/pdmodel/interactive/annotation/``; a defensible divergence is pinned
in ``_PINNED`` (both-sides) with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _nums(*vals: float) -> COSArray:
    return _arr(*[COSFloat(float(v)) for v in vals])


def _ints(*vals: int) -> COSArray:
    return _arr(*[COSInteger.get(int(v)) for v in vals])


def _widget(bs: COSBase | None, mk: COSBase | None) -> COSDictionary:
    """A minimal /Subtype /Widget annotation dict carrying ``/BS`` and ``/MK``
    (when provided). /Rect keeps the annotation legal."""
    w = COSDictionary()
    w.set_item(_N("Type"), _N("Annot"))
    w.set_item(_N("Subtype"), _N("Widget"))
    w.set_item(_N("Rect"), _nums(0, 0, 100, 20))
    if bs is not None:
        w.set_item(_N("BS"), bs)
    if mk is not None:
        w.set_item(_N("MK"), mk)
    return w


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSDictionary]:
    """Each case is a Widget annotation dict; ``/BS`` and ``/MK`` carry the
    mutated sub-dictionaries."""
    c: dict[str, COSDictionary] = {}

    # ---- baseline: well-formed /BS and /MK ----
    bs = COSDictionary()
    bs.set_item(_N("Type"), _N("Border"))
    bs.set_int(_N("W"), 2)
    bs.set_item(_N("S"), _N("D"))
    bs.set_item(_N("D"), _nums(3, 2))
    mk = COSDictionary()
    mk.set_int(_N("R"), 90)
    mk.set_item(_N("BC"), _nums(1, 0, 0))
    mk.set_item(_N("BG"), _nums(0.5))
    mk.set_string(_N("CA"), "OK")
    c["baseline"] = _widget(bs, mk)

    # ===================== /BS — /W width =====================

    def _bs(width: COSBase | None = None) -> COSDictionary:
        d = COSDictionary()
        if width is not None:
            d.set_item(_N("W"), width)
        return d

    c["bs_w_int"] = _widget(_bs(COSInteger.get(3)), None)
    c["bs_w_zero"] = _widget(_bs(COSInteger.get(0)), None)
    c["bs_w_negative"] = _widget(_bs(COSInteger.get(-2)), None)
    c["bs_w_real"] = _widget(_bs(COSFloat(1.5)), None)
    c["bs_w_missing"] = _widget(_bs(None), None)
    c["bs_w_name"] = _widget(_bs(_N("Foo")), None)
    c["bs_w_string"] = _widget(_bs(COSString("3")), None)
    c["bs_w_array"] = _widget(_bs(_nums(1, 2)), None)

    # ===================== /BS — /S style =====================

    def _bs_s(style: COSBase | None) -> COSDictionary:
        d = COSDictionary()
        if style is not None:
            d.set_item(_N("S"), style)
        return d

    c["bs_s_solid"] = _widget(_bs_s(_N("S")), None)
    c["bs_s_dashed"] = _widget(_bs_s(_N("D")), None)
    c["bs_s_beveled"] = _widget(_bs_s(_N("B")), None)
    c["bs_s_inset"] = _widget(_bs_s(_N("I")), None)
    c["bs_s_underline"] = _widget(_bs_s(_N("U")), None)
    c["bs_s_unknown"] = _widget(_bs_s(_N("Z")), None)
    c["bs_s_missing"] = _widget(_bs_s(None), None)
    c["bs_s_string"] = _widget(_bs_s(COSString("D")), None)
    c["bs_s_number"] = _widget(_bs_s(COSInteger.get(1)), None)

    # ===================== /BS — /D dash array =====================

    def _bs_d(dash: COSBase | None) -> COSDictionary:
        d = COSDictionary()
        d.set_item(_N("S"), _N("D"))
        if dash is not None:
            d.set_item(_N("D"), dash)
        return d

    c["bs_d_normal"] = _widget(_bs_d(_nums(3, 2)), None)
    c["bs_d_single"] = _widget(_bs_d(_nums(4)), None)
    c["bs_d_empty"] = _widget(_bs_d(COSArray()), None)
    c["bs_d_ints"] = _widget(_bs_d(_ints(3, 1)), None)
    c["bs_d_nonnumeric"] = _widget(_bs_d(_arr(_N("x"), COSString("y"))), None)
    c["bs_d_mixed"] = _widget(_bs_d(_arr(COSFloat(2.0), _N("x"))), None)
    c["bs_d_missing"] = _widget(_bs_d(None), None)
    c["bs_d_name"] = _widget(_bs_d(_N("NotArray")), None)
    c["bs_d_number"] = _widget(_bs_d(COSInteger.get(5)), None)

    # ---- /BS missing entirely ----
    c["bs_missing"] = _widget(None, COSDictionary())
    # ---- /BS present but empty (all defaults) ----
    c["bs_empty"] = _widget(COSDictionary(), None)

    # ===================== /MK — /R rotation =====================

    def _mk_r(rot: COSBase | None) -> COSDictionary:
        d = COSDictionary()
        if rot is not None:
            d.set_item(_N("R"), rot)
        return d

    c["mk_r_90"] = _widget(None, _mk_r(COSInteger.get(90)))
    c["mk_r_180"] = _widget(None, _mk_r(COSInteger.get(180)))
    c["mk_r_270"] = _widget(None, _mk_r(COSInteger.get(270)))
    c["mk_r_360"] = _widget(None, _mk_r(COSInteger.get(360)))
    c["mk_r_45"] = _widget(None, _mk_r(COSInteger.get(45)))
    c["mk_r_negative"] = _widget(None, _mk_r(COSInteger.get(-90)))
    c["mk_r_real"] = _widget(None, _mk_r(COSFloat(90.5)))
    c["mk_r_missing"] = _widget(None, _mk_r(None))
    c["mk_r_name"] = _widget(None, _mk_r(_N("Foo")))

    # ===================== /MK — /BC border colour =====================

    def _mk_bc(bc: COSBase | None) -> COSDictionary:
        d = COSDictionary()
        if bc is not None:
            d.set_item(_N("BC"), bc)
        return d

    c["mk_bc_gray"] = _widget(None, _mk_bc(_nums(0.5)))
    c["mk_bc_rgb"] = _widget(None, _mk_bc(_nums(1, 0, 0)))
    c["mk_bc_cmyk"] = _widget(None, _mk_bc(_nums(0, 0, 0, 1)))
    c["mk_bc_empty"] = _widget(None, _mk_bc(COSArray()))
    c["mk_bc_two"] = _widget(None, _mk_bc(_nums(1, 0)))
    c["mk_bc_five"] = _widget(None, _mk_bc(_nums(1, 0, 0, 0, 0)))
    c["mk_bc_missing"] = _widget(None, _mk_bc(None))
    c["mk_bc_name"] = _widget(None, _mk_bc(_N("Red")))
    c["mk_bc_number"] = _widget(None, _mk_bc(COSInteger.get(3)))

    # ===================== /MK — /BG background colour =====================

    def _mk_bg(bg: COSBase | None) -> COSDictionary:
        d = COSDictionary()
        if bg is not None:
            d.set_item(_N("BG"), bg)
        return d

    c["mk_bg_gray"] = _widget(None, _mk_bg(_nums(0.25)))
    c["mk_bg_rgb"] = _widget(None, _mk_bg(_nums(0, 1, 0)))
    c["mk_bg_cmyk"] = _widget(None, _mk_bg(_nums(0, 0, 0, 0.5)))
    c["mk_bg_empty"] = _widget(None, _mk_bg(COSArray()))
    c["mk_bg_two"] = _widget(None, _mk_bg(_nums(1, 0)))
    c["mk_bg_missing"] = _widget(None, _mk_bg(None))
    c["mk_bg_name"] = _widget(None, _mk_bg(_N("Green")))

    # ===================== /MK — /CA normal caption =====================

    def _mk_ca(ca: COSBase | None) -> COSDictionary:
        d = COSDictionary()
        if ca is not None:
            d.set_item(_N("CA"), ca)
        return d

    c["mk_ca_string"] = _widget(None, _mk_ca(COSString("Submit")))
    c["mk_ca_empty"] = _widget(None, _mk_ca(COSString("")))
    c["mk_ca_name"] = _widget(None, _mk_ca(_N("Submit")))
    c["mk_ca_number"] = _widget(None, _mk_ca(COSInteger.get(7)))
    c["mk_ca_missing"] = _widget(None, _mk_ca(None))

    # ---- /MK missing entirely ----
    c["mk_missing"] = _widget(COSDictionary(), None)
    # ---- /MK present but empty (all defaults) ----
    c["mk_empty"] = _widget(None, COSDictionary())

    return c


# --------------------------------------------------------------------- corpus io


def _write_case_pdf(path: Path, widget: COSDictionary) -> None:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        annots = COSArray()
        annots.add(widget)
        page.get_cos_object().set_item(_N("Annots"), annots)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _num(d: float) -> str:
    """Match the Java probe's ``num``: integral floats print without ``.0``."""
    if d == int(d):
        return str(int(d))
    return repr(float(d))


def _bs_width_cell(bs) -> str:  # type: ignore[no-untyped-def]
    try:
        return _num(bs.get_width())
    except Exception as e:  # noqa: BLE001 - contract probe
        return f"ERR:{type(e).__name__}"


def _bs_style_cell(bs) -> str:  # type: ignore[no-untyped-def]
    try:
        s = bs.get_style()
        return "none" if s is None else s
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def _bs_dash_cell(bs) -> str:  # type: ignore[no-untyped-def]
    # Java's ``PDBorderStyleDictionary.getDashStyle()`` SEEDS the default
    # ``[3]`` dash array when ``/D`` is absent / not an array, so it never
    # returns null for a present /BS. pypdfbox splits the two behaviours:
    # ``get_dash_style()`` returns None for absent (extra non-upstream
    # convenience), and ``get_dash_style_or_default()`` is the byte-for-byte
    # mirror of upstream's seeding getter. Probe the latter.
    try:
        d = bs.get_dash_style_or_default()
        if d is None:
            return "none"
        arr = d.get_dash_array()
        if not arr:
            return "empty"
        return "|".join(_num(v) for v in arr)
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def _mk_rotation_cell(mk) -> str:  # type: ignore[no-untyped-def]
    try:
        return str(mk.get_rotation())
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def _color_cell(getter) -> str:  # type: ignore[no-untyped-def]
    try:
        c = getter()
        if c is None:
            return "none"
        comps = c.get_components()
        return str(0 if comps is None else len(comps))
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def _mk_caption_cell(mk) -> str:  # type: ignore[no-untyped-def]
    try:
        s = mk.get_normal_caption()
        return "none" if s is None else s
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001
        return prefix + f"LOAD:{type(e).__name__}"
    try:
        page = doc.get_page(0)
        annots = page.get_annotations()
        widget = annots[0]
        assert isinstance(widget, PDAnnotationWidget), type(widget).__name__

        bs = widget.get_border_style()
        if bs is None:
            bs_part = "bs_w=NOBS bs_s=NOBS bs_d=NOBS"
        else:
            bs_part = (
                f"bs_w={_bs_width_cell(bs)} bs_s={_bs_style_cell(bs)} "
                f"bs_d={_bs_dash_cell(bs)}"
            )

        mk = widget.get_appearance_characteristics()
        if mk is None:
            mk_part = "mk_r=NOMK mk_bc=NOMK mk_bg=NOMK mk_ca=NOMK"
        else:
            mk_part = (
                f"mk_r={_mk_rotation_cell(mk)} "
                f"mk_bc={_color_cell(mk.get_border_colour)} "
                f"mk_bg={_color_cell(mk.get_background)} "
                f"mk_ca={_mk_caption_cell(mk)}"
            )
        return prefix + f"{bs_part} {mk_part}"
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
#
# Populated empirically against the live oracle. Each entry is a defensible
# divergence pinned both-sides with a matching CHANGES.md row.
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_border_appearance_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed ``/BS`` / ``/MK`` dict resolves (or fails to resolve)
    identically on pypdfbox and Apache PDFBox 3.0.7: same width / style / dash,
    same rotation, same colour component counts, same caption. Divergences are
    pinned explicitly in ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, widget in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", widget)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("BorderAppearanceFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, (
        "border-style / appearance-characteristics fuzz divergences:\n"
        + "\n".join(mismatches)
    )
