"""Live PDFBox differential parity for the TrueType ``name`` table accessors
(``oracle/probes/NameTableProbe.java``).

The OpenType ``name`` table holds localized name records keyed by
``(nid, platformID, encodingID, languageID)``. Apache PDFBox 3.0.7 exposes:

* :meth:`NamingTable.get_name_records` — every record in read order.
* :meth:`NamingTable.get_name(nid, plat, enc, lang)` — the 4-arg lookup
  PDFBox uses internally (Microsoft Unicode BMP en-US, Mac-Roman English,
  Unicode-platform 2.0 BMP).
* :meth:`NamingTable.get_font_family` / ``get_font_sub_family`` /
  ``get_post_script_name`` — the priority-resolved family / sub-family /
  PostScript name. NID 6 (PostScript name) is the high-value case because
  ``PDFontDescriptor.get_font_name`` reads it.

Two surfaces are exercised against the live oracle:

1. **Record decode** — every record's decoded string must match PDFBox's,
   verifying UTF-16BE decode for platform-3 records (Windows-Unicode-BMP)
   and Mac-Roman decode for platform-1 records (NameRecord platform=1).
2. **Priority lookup** — the 4-arg ``get_name`` lookup for the three
   canonical (platform, encoding, language) tuples PDFBox itself queries,
   plus the three priority-resolved accessors.

Fonts used (both carry a rich ``name`` table with parallel
``(plat=1, enc=0, lang=0)`` Mac-Roman and ``(plat=3, enc=1, lang=1033)``
Windows-Unicode-BMP records covering NIDs 0..14):

* ``LiberationSans-Regular`` — 30 records, NIDs 0..14.
* ``DejaVuSans`` — 26 records, NIDs 0..6, 8, 11, 13, 14, 16, 17 (missing
  NID 7 covers the absent-record / NULL lookup case).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.name_record import NameRecord
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

# Mirror the probe's tuples exactly.
_TUPLES = [
    (
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
    ),
    (
        NameRecord.PLATFORM_MACINTOSH,
        NameRecord.ENCODING_MACINTOSH_ROMAN,
        NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
    ),
    (
        NameRecord.PLATFORM_UNICODE,
        NameRecord.ENCODING_UNICODE_2_0_BMP,
        NameRecord.LANGUAGE_UNICODE,
    ),
]


def _escape(s: str) -> str:
    """Reproduce the probe's tab / CR / LF / backslash escape (probe lines 99-115).

    Keeps records on a single line so the canonical line order is stable for
    multi-line copyright strings.
    """
    return (
        s.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _pypdfbox_lines(path: Path) -> list[str]:
    """Reproduce the probe's canonical output from pypdfbox.

    Closes the font program in a ``finally`` so the source-file handle never
    leaks (Windows would otherwise lock the bundled resource).
    """
    ttf = TrueTypeFont.from_bytes(path.read_bytes())
    try:
        naming = ttf.get_naming()
        records = list(naming.get_name_records()) if naming is not None else []
        records.sort(
            key=lambda r: (
                r.get_name_id(),
                r.get_platform_id(),
                r.get_platform_encoding_id(),
                r.get_language_id(),
            )
        )
        lines = [f"COUNT\t{len(records)}"]
        for r in records:
            s = r.get_string()
            lines.append(
                f"RECORD\t{r.get_name_id()}\t{r.get_platform_id()}\t"
                f"{r.get_platform_encoding_id()}\t{r.get_language_id()}\t"
                f"{'NULL' if s is None else _escape(s)}"
            )
        for nid in range(9):
            for plat, enc, lang in _TUPLES:
                s = None if naming is None else naming.get_name(nid, plat, enc, lang)
                lines.append(
                    f"LOOKUP\t{nid}\t{plat}\t{enc}\t{lang}\t"
                    f"{'NULL' if s is None else _escape(s)}"
                )
        family = None if naming is None else naming.get_font_family()
        subfamily = None if naming is None else naming.get_font_sub_family()
        psname = None if naming is None else naming.get_post_script_name()
        lines.append(f"FAMILY\t{'NULL' if family is None else _escape(family)}")
        lines.append(
            f"SUBFAMILY\t{'NULL' if subfamily is None else _escape(subfamily)}"
        )
        lines.append(f"PSNAME\t{'NULL' if psname is None else _escape(psname)}")
        return lines
    finally:
        ttf.close()


def _assert_parity(java: list[str], py: list[str], label: str) -> None:
    assert len(java) == len(py), (
        f"line-count mismatch for {label}: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(java, py, strict=True))
        if a != b
    ]
    assert not diffs, f"name-table parity broken for {label}:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    "font",
    ["LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
    ids=["liberation_sans", "dejavu_sans"],
)
def test_name_table_records_and_lookup_match_pdfbox(font: str) -> None:
    """All name records and the 4-arg priority lookup per (NID, plat, enc,
    lang) tuple must match Apache PDFBox 3.0.7 for a bundled TTF with a rich
    name table (Mac-Roman + Windows-Unicode-BMP records covering NIDs 0..8).

    Verifies:
      * UTF-16BE decode of platform-3 records.
      * Mac-Roman decode of platform-1 records.
      * 4-arg ``get_name`` lookup map keyed correctly on each (plat, enc,
        lang) slot — including the unobserved (0, 3, 0) Unicode-platform
        slot which returns NULL on both bundled fonts.
      * Priority-resolved family / sub-family / PostScript name (the NID 6
        PostScript-name case is the one ``PDFontDescriptor.get_font_name``
        reads).
    """
    path = _TTF_DIR / font
    java = run_probe_text("NameTableProbe", str(path)).splitlines()
    py = _pypdfbox_lines(path)
    _assert_parity(java, py, font)


@requires_oracle
@pytest.mark.parametrize(
    "font",
    ["LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
    ids=["liberation_sans", "dejavu_sans"],
)
def test_postscript_name_nid6_matches_pdfbox(font: str) -> None:
    """NID 6 (PostScript name) — the value ``PDFontDescriptor.get_font_name``
    reads — must match PDFBox's priority-resolved ``getPostScriptName()``.

    Pulled out of the parametrised parity test because a regression in the
    NID 6 selection (wrong priority, wrong UTF-16BE decode) is the highest-
    impact name-table bug: it propagates to every embedded font's
    ``/FontName`` in the PDF output.
    """
    path = _TTF_DIR / font
    java_lines = run_probe_text("NameTableProbe", str(path)).splitlines()
    java_ps = next(
        line.split("\t", 1)[1] for line in java_lines if line.startswith("PSNAME\t")
    )
    ttf = TrueTypeFont.from_bytes(path.read_bytes())
    try:
        naming = ttf.get_naming()
        assert naming is not None
        py_ps = naming.get_post_script_name()
    finally:
        ttf.close()
    assert (py_ps if py_ps is not None else "NULL") == java_ps
