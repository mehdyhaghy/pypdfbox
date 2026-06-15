"""Differential TrueTypeCollection (.ttc) header-parse fuzz vs FontBox 3.0.7.

Wave 1530, Agent B. Applies the deterministic-corpus differential method to the
TTC *collection header* parse contract — the path
``TrueTypeCollection(file)`` drives when handed a (possibly malformed) ``.ttc``
container, plus the public iteration / lookup API
(``processAllFonts`` / ``getFontByName``).

A valid single-font base TTC is built once from the bundled, permissively
licensed ``LiberationSans-Regular.ttf`` via ``fontTools.ttLib.TTCollection``
(fontTools is already a pypdfbox dependency — no new dep). A fixed set of
header mutations then exercises the upstream parse contract
(``TrueTypeCollection.java`` constructor, lines 70-98):

  * wrong scaler magic (not ``ttcf``)
  * empty input / truncations before/within ``numFonts`` and the offset array
  * ``numFonts == 0`` and ``numFonts`` over the upstream 1..1024 bound
  * a ``numFonts`` whose offset array runs past EOF (short read)
  * a font offset pointing past EOF / to the header / to non-SFNT bytes
  * version 0 / version 0xFFFFFFFF (FontBox does NOT gate on the version DWORD)
  * version 2.0 with and without the trailing DSIG fields

Both engines parse the *identical* bytes and are compared on a stable
projection produced by ``oracle/probes/TrueTypeCollectionFuzzProbe.java``
(public API only — ``getFontAtIndex`` / ``numFonts`` are private upstream):

    ok=true
    numFonts=<count visited by processAllFonts, or "error" if it threw>
    names=<comma-joined postscript names visited by processAllFonts>
    getByMissing=<"true" if getFontByName("__nope__") returned None>

or the sole line ``ok=false`` on any throw from the constructor (header parse).
``_py_dump`` reproduces the same fingerprint on the pypdfbox side.

REAL BUG FIXED THIS WAVE (now pinned as an agreement case): ``version0`` /
``version_huge``. FontBox reads the 4-byte TTC version via ``read32Fixed`` and
the only decision it drives is ``version >= 2`` (consume DSIG); it never gates
on the version being one of the two canonical values, so a header carrying
``0x00000000`` / ``0xFFFFFFFF`` still parses and yields its fonts. pypdfbox
re-materialises the container for fontTools' ``TTCollection`` slicer, which
asserts ``version in (0x00010000, 0x00020000)`` and crashed. Fix:
``TrueTypeCollection._normalise_ttc_version`` rewrites the version DWORD to the
canonical value matching the DSIG decision pypdfbox already made before handing
the bytes to fontTools — so the spurious version gate FontBox does not impose
no longer leaks through.

DOCUMENTED LIBRARY-GAP DIVERGENCE (pinned BOTH sides via the ``_XFAIL`` set,
not asserted equal — the CCITT/libtiff precedent of wave 1505):
``version2_with_dsig``. Inserting the 6 trailing DSIG bytes shifts the SFNT
payload. FontBox reads ``version == 2`` → consumes the three DSIG shorts → then
the per-font offset lands on the now-misaligned payload and ``processAllFonts``
throws (numFonts=error). fontTools' ``TTCollection`` re-reads the container
with its own offset interpretation and tolerates the layout, yielding a font
with a null name. Matching FontBox here would mean abandoning fontTools'
container reader and re-deriving every per-font SFNT slice by hand off the
already-cached offsets — out of scope and against the library-first rule. The
case is characterised here and in CHANGES.md but not asserted equal.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import struct
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXDIR = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "fontbox" / "ttf"
)
_BASE_TTF = _FIXDIR / "LiberationSans-Regular.ttf"


# ---------------------------------------------------------------------------
# Build a valid single-font base TTC once from the bundled TTF. fontTools is
# already a pypdfbox dependency (library-first font decode), so this adds no
# new dep. The layout is deterministic: ``ttcf`` + version(0x10000) +
# numFonts(1) + one 4-byte offset(16) + the SFNT body.
# ---------------------------------------------------------------------------
def _build_base_ttc() -> bytes:
    if not _BASE_TTF.is_file():
        return b""
    from fontTools.ttLib import TTCollection, TTFont  # noqa: PLC0415

    collection = TTCollection()
    collection.fonts.append(TTFont(str(_BASE_TTF)))
    sink = io.BytesIO()
    collection.save(sink)
    return sink.getvalue()


_BASE = _build_base_ttc()


def _hdr(version: int, num_fonts: int, offsets: list[int], extra: bytes = b"") -> bytes:
    body = b"ttcf" + struct.pack(">I", version) + struct.pack(">I", num_fonts)
    body += b"".join(struct.pack(">I", o) for o in offsets)
    return body + extra


def _font_body() -> bytes:
    """The single SFNT payload of the base TTC (starts at offset 16)."""
    return _BASE[16:]


# ---------------------------------------------------------------------------
# deterministic mutation corpus. Each entry: (name, ttc_bytes).
# ---------------------------------------------------------------------------
def _generate_corpus() -> list[tuple[str, bytes]]:
    if not _BASE:
        return []
    payload = _font_body()
    out: list[tuple[str, bytes]] = [
        ("valid_single", _BASE),
        # -- wrong magic --------------------------------------------------
        ("wrong_magic", b"OTTO" + _BASE[4:]),
        ("magic_garbage", b"\x00\x00\x00\x00" + _BASE[4:]),
        # -- truncations --------------------------------------------------
        ("empty", b""),
        ("trunc_magic_only", b"ttcf"),
        ("trunc_no_numfonts", b"ttcf" + struct.pack(">I", 0x10000)),
        (
            "trunc_numfonts_partial",
            b"ttcf" + struct.pack(">I", 0x10000) + b"\x00\x00",
        ),
        # -- numFonts bounds ---------------------------------------------
        ("numfonts_0", _hdr(0x10000, 0, [])),
        ("numfonts_huge", _hdr(0x10000, 0x7FFFFFFF, [16])),
        (
            "numfonts_1025",
            b"ttcf" + struct.pack(">I", 0x10000) + struct.pack(">I", 1025),
        ),
        (
            "numfonts_2_offsets_short",
            b"ttcf"
            + struct.pack(">I", 0x10000)
            + struct.pack(">I", 2)
            + struct.pack(">I", 16),
        ),
        # -- bad per-font offsets ----------------------------------------
        ("offset_past_eof", _hdr(0x10000, 1, [0xFFFFFFF0]) + payload),
        ("offset_zero", _hdr(0x10000, 1, [0]) + payload),
        ("offset_into_header", _hdr(0x10000, 1, [4]) + payload),
        ("offset_to_nonttf", _hdr(0x10000, 1, [16]) + b"\x00" * 256),
        # -- version handling (FontBox does not gate on the version DWORD) -
        ("version0", _hdr(0, 1, [16]) + payload),
        ("version_huge", _hdr(0xFFFFFFFF, 1, [16]) + payload),
        ("version2_no_dsig", _hdr(0x20000, 1, [16]) + payload),
    ]
    return out


_CORPUS = _generate_corpus()
_CORPUS_IDS = [m[0] for m in _CORPUS]

# Library-gap case (DSIG bytes shift the payload; fontTools tolerates the
# layout FontBox rejects). Pinned BOTH sides below, not asserted equal.
_DSIG_SHIFTED = (
    _hdr(0x20000, 1, [22], extra=b"\x00" * 6) + _font_body() if _BASE else b""
)


# ---------------------------------------------------------------------------
# pypdfbox side: reproduce TrueTypeCollectionFuzzProbe's projection exactly.
# ---------------------------------------------------------------------------
def _py_dump(data: bytes) -> str:
    try:
        ttc = TrueTypeCollection(data)
    except Exception:
        return "ok=false\n"
    try:
        names: list[str] = []
        try:

            def _cb(font: object) -> None:
                name = font.get_name()  # type: ignore[attr-defined]
                names.append("null" if name is None else name)

            ttc.process_all_fonts(_cb)
            count = str(len(names))
        except Exception:
            count = "error"
        try:
            missing = ttc.get_font_by_name("__nope__")
            get_by_missing = "true" if missing is None else "false"
        except Exception:
            get_by_missing = "error"
        lines = [
            "ok=true",
            f"numFonts={count}",
            f"names={','.join(names)}",
            f"getByMissing={get_by_missing}",
        ]
        return "\n".join(lines) + "\n"
    finally:
        with contextlib.suppress(Exception):
            ttc.close()


def _java_dump(data: bytes) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".ttc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return run_probe_text("TrueTypeCollectionFuzzProbe", tmp)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Differential parity: every pinned mutant produces the identical projection.
# fontTools logs malformed-table warnings while re-reading corrupt containers;
# silence them so the test output stays readable (assertions use the projection
# string only, not stderr).
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.skipif(not _CORPUS, reason="base TTF fixture missing")
@pytest.mark.parametrize(("name", "mutated"), _CORPUS, ids=_CORPUS_IDS)
def test_true_type_collection_fuzz_parity(name: str, mutated: bytes) -> None:
    logging.disable(logging.WARNING)
    try:
        java = _java_dump(mutated)
        py = _py_dump(mutated)
    finally:
        logging.disable(logging.NOTSET)
    assert py == java, (
        f"divergence on TTC header mutant {name!r}:\n"
        f" java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Pinned LIBRARY-GAP divergence: DSIG-shifted v2 header. FontBox fails on the
# misaligned per-font offset; fontTools tolerates it. Pin BOTH sides so a
# future change to either engine that closes the gap (or widens it) trips here.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.skipif(not _BASE, reason="base TTF fixture missing")
def test_true_type_collection_dsig_shifted_library_gap() -> None:
    logging.disable(logging.WARNING)
    try:
        java = _java_dump(_DSIG_SHIFTED)
        py = _py_dump(_DSIG_SHIFTED)
    finally:
        logging.disable(logging.NOTSET)
    # FontBox: version 2 → consumes DSIG → per-font offset misaligned → throws.
    assert java == "ok=true\nnumFonts=error\nnames=\ngetByMissing=error\n"
    # pypdfbox via fontTools: container re-read tolerates the layout, font has
    # a null postscript name.
    assert py == "ok=true\nnumFonts=1\nnames=null\ngetByMissing=true\n"


# ---------------------------------------------------------------------------
# Sanity: the clean base parses to a non-trivial projection on pypdfbox, so a
# corpus-build regression can't silently turn every mutant into a vacuous pass.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BASE, reason="base TTF fixture missing")
def test_clean_base_projection_non_trivial() -> None:
    logging.disable(logging.WARNING)
    try:
        dump = _py_dump(_BASE)
    finally:
        logging.disable(logging.NOTSET)
    assert dump == (
        "ok=true\nnumFonts=1\nnames=LiberationSans\ngetByMissing=true\n"
    )


# ---------------------------------------------------------------------------
# Regression guard for the wave-1530 version-DWORD fix (no oracle needed):
# a header with a non-canonical version still yields its font on pypdfbox.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _BASE, reason="base TTF fixture missing")
@pytest.mark.parametrize("version", [0, 0xFFFFFFFF, 0x00030000])
def test_non_canonical_version_still_parses(version: int) -> None:
    data = _hdr(version, 1, [16]) + _font_body()
    logging.disable(logging.WARNING)
    try:
        dump = _py_dump(data)
    finally:
        logging.disable(logging.NOTSET)
    assert dump == (
        "ok=true\nnumFonts=1\nnames=LiberationSans\ngetByMissing=true\n"
    )
