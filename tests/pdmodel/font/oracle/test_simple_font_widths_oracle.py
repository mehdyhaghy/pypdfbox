"""Live PDFBox differential parity for the simple-font ``/Widths``-array facet.

Pins ``PDFont.getWidth(int)`` width resolution on a simple (Type1) font driven
by the *dictionary* ``/Widths`` array (PDF 32000-1 §9.2.4):

    getWidth(code) =
        /Widths[code - /FirstChar]   when /Widths is present and
                                     FirstChar <= code <= LastChar and
                                     0 <= (code - FirstChar) < len(Widths)
                                     (a null/non-numeric slot reads as 0.0)
        /FontDescriptor /MissingWidth (default 0) otherwise, when /Widths or
                                     /MissingWidth is present and a descriptor
                                     exists.

This is a different surface from the adjacent font-width oracles:

* ``test_cid_width_oracle`` drives the composite ``/W`` + ``/DW`` path.
* ``test_std14_metrics_oracle`` / ``test_font_metrics_oracle`` drive the
  Standard-14 AFM advance path.
* ``test_type1c_simple_font_oracle`` drives the embedded Type1C program width.

Every probed font here carries a ``/FontDescriptor`` ``/MissingWidth`` so the
out-of-window branch resolves to ``/MissingWidth`` and NEVER reaches the
AFM or substitute-font-program branches — keeping the surface strictly the
``/Widths`` array + ``/MissingWidth`` fallback.

The oracle output is produced by ``oracle/probes/SimpleFontWidthsProbe.java``;
the Python side builds the identical font dictionaries and reconstructs the
same line format so a divergence shows up as a single differing line. Widths
are exact table lookups (no platform-dependent floating point), so no
divergence is tolerated.

Found by this oracle (wave 1469): pypdfbox's ``PDSimpleFont.get_widths`` /
``PDFont.get_widths`` *skipped* non-numeric ``/Widths`` entries, while upstream
``COSArray.toCOSNumberFloatList`` keeps a ``None`` slot for each — so a null /
name entry in the middle of ``/Widths`` shifted every subsequent index in
pypdfbox and shortened the list (Font C below). Fixed to keep ``None`` slots.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
)
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")
_FONT_DESC = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME = COSName.get_pdf_name("FontName")
_MISSING_WIDTH = COSName.get_pdf_name("MissingWidth")


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format(Locale.ROOT, "%.4f", ...)``."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _add_descriptor(dict_: COSDictionary, name: str, missing_width: float) -> None:
    fd = COSDictionary()
    fd.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    fd.set_name(_FONT_NAME, name)
    fd.set_float(_MISSING_WIDTH, missing_width)
    dict_.set_item(_FONT_DESC, fd)


def _build_font(
    name: str,
    first_char: int,
    last_char: int,
    widths: list[float],
    missing_width: float,
) -> PDType1Font:
    dict_ = COSDictionary()
    dict_.set_item(_TYPE, _FONT)
    dict_.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    dict_.set_name(_BASE_FONT, name)
    dict_.set_int(_FIRST_CHAR, first_char)
    dict_.set_int(_LAST_CHAR, last_char)
    arr = COSArray()
    for w in widths:
        arr.add(COSFloat(w))
    dict_.set_item(_WIDTHS, arr)
    _add_descriptor(dict_, name, missing_width)
    return PDType1Font(dict_)


def _build_font_mixed() -> PDType1Font:
    """Font C: /Widths = [500, null, /X, 800, 900, 1000] over FirstChar 65."""
    dict_ = COSDictionary()
    dict_.set_item(_TYPE, _FONT)
    dict_.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    dict_.set_name(_BASE_FONT, "ProbeFontC")
    dict_.set_int(_FIRST_CHAR, 65)
    dict_.set_int(_LAST_CHAR, 70)
    arr = COSArray()
    arr.add(COSFloat(500.0))            # 65
    arr.add(COSNull.NULL)               # 66 -> null -> 0.0
    arr.add(COSName.get_pdf_name("X"))  # 67 -> non-number -> null -> 0.0
    arr.add(COSFloat(800.0))            # 68
    arr.add(COSInteger.get(900))        # 69
    arr.add(COSFloat(1000.0))           # 70
    dict_.set_item(_WIDTHS, arr)
    _add_descriptor(dict_, "ProbeFontC", 0.0)
    return PDType1Font(dict_)


def _fonts() -> list[tuple[str, PDType1Font, list[int]]]:
    """Mirror SimpleFontWidthsProbe.main's font/code list exactly."""
    return [
        (
            "A_descriptor_mw999",
            _build_font("ProbeFont", 65, 68, [500.0, 600.0, 700.0, 800.0], 999.0),
            [0, 32, 64, 65, 66, 67, 68, 69, 70, 200, 255],
        ),
        (
            "B_missingwidth_zero",
            _build_font("ProbeFont", 65, 68, [500.0, 600.0, 700.0, 800.0], 0.0),
            [0, 64, 65, 66, 67, 68, 69, 255],
        ),
        (
            "C_null_and_nonnumeric",
            _build_font_mixed(),
            [64, 65, 66, 67, 68, 69, 70, 71],
        ),
        (
            "E_first_gt_last",
            _build_font("ProbeFont", 80, 70, [111.0, 222.0, 333.0], 444.0),
            [69, 70, 75, 80, 81, 82, 90],
        ),
    ]


def _py_output() -> str:
    """Reconstruct SimpleFontWidthsProbe's output from pypdfbox, line-for-line."""
    lines: list[str] = []
    for key, font, codes in _fonts():
        dict_ = font.get_cos_object()
        first_char = dict_.get_int(_FIRST_CHAR, -1)
        last_char = dict_.get_int(_LAST_CHAR, -1)
        fd = font.get_font_descriptor()
        mw = _fmt(fd.get_missing_width()) if fd is not None else "NONE"
        widths_arr = dict_.get_dictionary_object(_WIDTHS)
        widths_len = widths_arr.size() if isinstance(widths_arr, COSArray) else 0
        lines.append(f"FONT\t{key}\t{first_char}\t{last_char}\t{mw}\t{widths_len}")
        for code in codes:
            try:
                width = _fmt(font.get_width(code))
            except Exception:
                width = "WIDTH_ERR"
            try:
                explicit = "true" if font.has_explicit_width(code) else "false"
            except Exception:
                explicit = "EXPLICIT_ERR"
            lines.append(f"WIDTH\t{key}\t{code}\t{width}\t{explicit}")
    return "\n".join(lines) + "\n"


@requires_oracle
def test_simple_font_widths_match_pdfbox() -> None:
    """Every simple-font ``/Widths`` lookup + ``/MissingWidth`` fallback +
    explicit-width predicate must match Apache PDFBox exactly.

    Pins the array window (below ``/FirstChar``, inside, above ``/LastChar``),
    the ``/MissingWidth`` fallback (default 0), null/non-numeric ``/Widths``
    slots (index alignment preserved, read back as 0.0), and the degenerate
    ``FirstChar > LastChar`` case where ``hasExplicitWidth`` is true but
    ``getWidth`` still falls back to ``/MissingWidth``.
    """
    java = run_probe_text("SimpleFontWidthsProbe").splitlines()
    py = _py_output().splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"java:\n" + "\n".join(java) + "\npy:\n" + "\n".join(py)
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "simple-font /Widths parity broken:\n" + "\n".join(diffs)


def test_widths_keep_null_slots_for_nonnumeric_entries() -> None:
    """Regression pin (no oracle needed): a null / non-numeric ``/Widths`` entry
    must keep its index slot, not be skipped.

    Mirrors upstream ``COSArray.toCOSNumberFloatList`` which appends ``None``
    for every non-``COSNumber`` entry, so ``getWidth`` reads the slot back as
    0.0 and the indices of later entries stay aligned with ``/FirstChar``.
    """
    font = _build_font_mixed()
    widths = font.get_widths()
    # Six slots preserved (500, None, None, 800, 900, 1000) — NOT collapsed to 4.
    assert len(widths) == 6
    assert widths[0] == 500.0
    assert widths[1] is None
    assert widths[2] is None
    assert widths[3] == 800.0
    assert widths[4] == 900.0
    assert widths[5] == 1000.0
    # Index alignment: code 68 (offset 3) must still resolve to 800, not 1000.
    assert font.get_width(65) == 500.0
    assert font.get_width(66) == 0.0   # null slot
    assert font.get_width(67) == 0.0   # non-numeric slot
    assert font.get_width(68) == 800.0
    assert font.get_width(69) == 900.0
    assert font.get_width(70) == 1000.0
    # The null/non-numeric slots are still "explicit" — they occupy a position
    # inside the /FirstChar..len(Widths) window.
    assert font.has_explicit_width(66)
    assert font.has_explicit_width(67)
