"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``fontbox/src/test/java/org/apache/fontbox/ttf/HintingConcurrencyTest.java``.

Hammers one shared ``TrueTypeFont`` from several threads. A
system-substituted font is held in a process-wide cache, so this is how the
renderer really uses it, and the interpreter it drives is a pile of mutable
state - the storage area, the twilight zone, the post-``prep`` template, the
cached ppem - guarded only by ``GlyphHinter``'s lock.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFParser

_TTF = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "ttf"
_LIBERATION = _TTF / "LiberationSans-Regular.ttf"
THREADS = 8
ITERATIONS = 150
PPEMS = (11, 13, 16, 24)
GLYPHS = "HILEToxn"


def _parse() -> TrueTypeFont:
    return TTFParser().parse(_LIBERATION)


def _flatten(path: Any) -> list[Any]:
    return list(path.value)


def _key(glyph_index: int, ppem: int) -> int:
    return glyph_index * 1000 + ppem


def test_concurrent_hinting_matches_single_threaded_results() -> None:
    """Every thread must get exactly what a single thread would have got. Interleaving the
    ppems is the point: a ppem change re-runs the control value program and clears the storage
    area and twilight zone, so an unsynchronized hinter would let one thread wipe the state
    another is mid-way through using, and the results would drift rather than raise."""
    reference = _parse()
    lookup = reference.get_unicode_cmap_lookup()
    assert lookup is not None
    gids = [lookup.get_glyph_id(ord(c)) for c in GLYPHS]
    expected: dict[int, list[Any]] = {}
    for g, gid in enumerate(gids):
        for ppem in PPEMS:
            path = reference.get_hinted_path(gid, ppem)
            assert path is not None, f"expected '{GLYPHS[g]}' to hint at {ppem}ppem"
            expected[_key(g, ppem)] = _flatten(path)

    # a font nothing has hinted yet, so the run also races the lazy hinter creation
    shared = _parse()
    problems: list[str] = []
    problems_lock = threading.Lock()
    start = threading.Event()

    def worker(offset: int) -> None:
        # each thread walks the glyph/ppem grid from a different offset, so the threads are
        # asking for different sizes at the same moment rather than moving in lockstep
        assert start.wait(120)
        for i in range(ITERATIONS):
            g = (i + offset) % len(GLYPHS)
            ppem = PPEMS[(i + offset) % len(PPEMS)]
            actual = _flatten(shared.get_hinted_path(gids[g], ppem))
            if expected[_key(g, ppem)] != actual:
                with problems_lock:
                    problems.append(f"'{GLYPHS[g]}' at {ppem}ppem")

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [pool.submit(worker, t) for t in range(THREADS)]
        start.set()
        for future in futures:
            future.result(timeout=120)  # surfaces anything raised inside a worker
    assert not problems, f"{len(problems)} mismatched results, first: {problems[0]}"
