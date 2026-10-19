"""Live PDFBox differential for the GSUB data projection and GSUB workers.

``GlyphSubstitutionTable.get_gsub_data()`` must pick the language from the
font's script list the way upstream ``GlyphSubstitutionDataExtractor`` does
(first ``Language`` with a script tag present), and build each feature's
glyph-run -> substitute map from the actual single / alternate / ligature
lookups. ``get_gsub_data(tag)`` builds the same maps for one script with
the language left ``UNSPECIFIED``. ``GsubWorkerFactory`` then picks the
worker from that language, and ``PDPageContentStream.show_text`` with an
embedded ``PDType0Font`` writes the worker's substituted glyph ids.

The ``GsubDataProbe`` Java oracle prints the same facts with Apache PDFBox
3.0.8; this module computes them with pypdfbox and compares line by line.
Fonts: the LiberationSans-Regular fixture plus every bundled
``pypdfbox/resources/ttf`` font (Arimo, Tinos, Cousine, DejaVuSans), which
covers a LATIN font without ``liga`` (Liberation / Arimo / Tinos), one with
real ligatures (DejaVuSans) and one with no supported language (Cousine,
``hebr`` only -> ``NO_DATA_FOUND``).

Line grammar (must match ``archive/oracle/probes/GsubDataProbe.java``)::

    font \\t default \\t LANGUAGE \\t script \\t sorted,features
    font \\t default \\t NO_DATA_FOUND
    font \\t default.map.FEATURE \\t entryCount \\t sha256
    font \\t script.TAG ... / script.TAG.map.FEATURE ...
    font \\t worker \\t WorkerSimpleName | NONE
    font \\t gids_in \\t ids / gids_out \\t ids
    font \\t content \\t HEX
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.gsub.gsub_worker_factory import GsubWorkerFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO = Path(__file__).resolve().parents[3]
_FONTS = [
    _REPO / "tests" / "fixtures" / "fontbox" / "ttf" / "LiberationSans-Regular.ttf",
    _REPO / "pypdfbox" / "resources" / "ttf" / "DejaVuSans.ttf",
    *sorted((_REPO / "pypdfbox" / "resources" / "ttf").glob("[ACT]*.ttf")),
]
_TEXT = "fi fl office ffi Hello"


def _dump(lines: list[str], font: str, label: str, data: Any) -> None:
    if data is None:
        lines.append(f"{font}\t{label}\tNULL")
        return
    if data is GsubData.NO_DATA_FOUND:
        lines.append(f"{font}\t{label}\tNO_DATA_FOUND")
        return
    features = sorted(data.get_supported_features())
    lines.append(
        f"{font}\t{label}\t{data.get_language().name}\t"
        f"{data.get_active_script_name()}\t{','.join(features)}"
    )
    for feature in features:
        sf = data.get_feature(feature)
        keys = sorted(sf.get_all_glyph_ids_for_substitution())
        ser = "".join(
            ",".join(str(g) for g in key) + f">{sf.get_replacement_for_glyphs(list(key))};"
            for key in keys
        )
        digest = hashlib.sha256(ser.encode("utf-8")).hexdigest()
        lines.append(f"{font}\t{label}.map.{feature}\t{len(keys)}\t{digest}")


def _content(path: Path) -> str:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType0Font.load(doc, str(path))
        cs = PDPageContentStream(doc, page)
        try:
            cs.begin_text()
            cs.set_font(font, 12)
            cs.show_text(_TEXT)
            cs.end_text()
        finally:
            cs.close()
        return page.get_contents().hex().upper()
    finally:
        doc.close()


def _python_lines() -> list[str]:
    lines: list[str] = []
    for path in _FONTS:
        font = path.name
        ttf = TrueTypeFont.from_bytes(path.read_bytes())
        try:
            data = ttf.get_gsub_data()
            _dump(lines, font, "default", data)
            gsub = ttf.get_gsub()
            if gsub is not None:
                for tag in sorted(gsub.get_supported_script_tags()):
                    _dump(lines, font, f"script.{tag}", gsub.get_gsub_data(tag))
            cmap = ttf.get_unicode_cmap_lookup()
            gids = [cmap.get_glyph_id(ord(c)) for c in _TEXT]
            if data is GsubData.NO_DATA_FOUND:
                lines.append(f"{font}\tworker\tNONE")
            else:
                worker = GsubWorkerFactory().get_gsub_worker(cmap, data)
                lines.append(f"{font}\tworker\t{type(worker).__name__}")
                lines.append(f"{font}\tgids_in\t{' '.join(map(str, gids))}")
                out = worker.apply_transforms(list(gids))
                lines.append(f"{font}\tgids_out\t{' '.join(map(str, out))}")
        finally:
            ttf.close()
        lines.append(f"{font}\tcontent\t{_content(path)}")
    return lines


def _key(line: str) -> str:
    font, label, _rest = line.split("\t", 2)
    return f"{font}\t{label}"


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    out = run_probe_text("GsubDataProbe", *(str(p) for p in _FONTS))
    return {_key(line): line for line in out.splitlines() if line}


@pytest.fixture(scope="module")
def python_lines() -> dict[str, str]:
    return {_key(line): line for line in _python_lines()}


@requires_oracle
def test_same_line_keys(java_lines: dict[str, str], python_lines: dict[str, str]) -> None:
    assert sorted(python_lines) == sorted(java_lines)


@requires_oracle
@pytest.mark.parametrize("font", [p.name for p in _FONTS])
def test_gsub_data_matches_pdfbox(
    font: str, java_lines: dict[str, str], python_lines: dict[str, str]
) -> None:
    prefix = f"{font}\t"
    java = sorted(v for k, v in java_lines.items() if k.startswith(prefix))
    python = sorted(v for k, v in python_lines.items() if k.startswith(prefix))
    assert java, f"probe emitted no line for {font}"
    assert python == java
