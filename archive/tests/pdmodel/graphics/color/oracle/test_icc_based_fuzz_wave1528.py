"""Live PDFBox differential fuzz parity for ``PDICCBased`` dictionary /
accessor parsing (wave 1528, agent B).

Sibling of ``oracle/probes/IccBasedFuzzProbe.java``. Where the wave-1512
``ColorSpaceFuzzProbe`` drives ``PDColorSpace.create(COSBase)`` construction at
a high level, this probe drills into the ``PDICCBased`` accessor surface for the
array form ``[/ICCBased <stream>]``: malformed ``/N``, ``/Alternate``,
``/Range``, ``/Metadata``.

It deliberately embeds NO real ICC profile bytes (or only garbage / short
bytes), so Java's ``java.awt.color.ICC_Profile`` parse fails and ``iccProfile``
stays null — putting the JVM on the same footing as pypdfbox (which carries no
AWT colour space). That isolates the *dictionary-parsing / fallback* logic from
the JVM CMM colour math.

The Java probe prints one CASE line per case in the grammar::

    CASE <name> ctor=<ERR | NOTICC class=<C> | ok nc=<n> alt=<class|NULL|ERR> \\
        range=<min:max|...|ERR|EMPTY> meta=<0|1> init=<a,b,..|ERR>>

This module rebuilds the *identical* corpus, case-for-case in the same order,
emits the identical CASE-line grammar via
``pypdfbox.pdmodel.graphics.color.PDICCBased`` (through
``PDColorSpace.create``), and asserts line-for-line parity against the live Java
oracle. Documented divergences are listed in ``_EXPECTED_DIVERGENCES`` and
pinned *both sides* (assert pypdfbox emits the pin AND that Java differs, so a
future convergence fails loudly and forces the pin's removal).

Two real parity fixes landed in this wave (see CHANGES.md "Wave 1528"):

1. **``get_alternate_color_space()`` default-by-N synthesis.** Upstream's
   accessor never returns the raw ``/Alternate``: when ``/Alternate`` is absent
   it synthesises the default alternate by component count (1 → DeviceGray,
   3 → DeviceRGB, 4 → DeviceCMYK). pypdfbox previously returned ``None``; it now
   mirrors the synthesis (staying permissive — returns ``None`` instead of
   raising — for the invalid-N path where upstream throws).
2. **``get_initial_color()`` from the alternate.** pypdfbox carries no AWT
   profile, so it always takes upstream's alternate-color-space fallback path
   (``initialColor = alternateColorSpace.getInitialColor()``). The initial
   colour's components now come from the alternate verbatim — for a DeviceCMYK
   alternate that is ``(0, 0, 0, 1)``, not all-zeros.

Remaining pinned divergence families (pre-existing design decisions):

* **create** — permissive factory contract. Upstream throws
  (``IOException``) during construction when ``/N`` ∉ {1, 3, 4} with no usable
  ``/Alternate``, when the ``/Alternate`` colour space can't be created, or when
  the array's second slot is not a stream. pypdfbox is permissive: it constructs
  and surfaces the defect later (``nc``/``init`` reflect the malformed input).
  Same family pinned by ``test_colorspace_fuzz_wave1512.py``.
* **range** — ``/Range`` numeric leniency. Upstream's ``PDRange.getMin()``
  throws on a non-numeric ``/Range`` entry (``range=ERR``); pypdfbox's
  ``to_float_array`` coerces non-numerics to ``0.0`` (``range=0.000:0.000``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders (mirror IccBasedFuzzProbe.java helpers) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _icc(
    n_val: int | None,
    body: bytes | None,
    alt: COSBase | None,
    rng: COSArray | None,
    meta: COSStream | None,
) -> COSStream:
    s = COSStream()
    if n_val is not None:
        s.set_int("N", n_val)
    if alt is not None:
        s.set_item("Alternate", alt)
    if rng is not None:
        s.set_item("Range", rng)
    if meta is not None:
        s.set_item("Metadata", meta)
    with s.create_output_stream() as os:
        if body is not None:
            os.write(body)
    return s


def _meta_stream() -> COSStream:
    s = COSStream()
    s.set_item("Type", _n("Metadata"))
    s.set_item("Subtype", _n("XML"))
    with s.create_output_stream() as os:
        os.write(b"<x:xmpmeta/>")
    return s


# ---------- CASE-line emitter (mirror IccBasedFuzzProbe.emit) ----------


def _emit(name: str, array: COSArray) -> str:
    """Build the CASE line for ``array``, mirroring the Java probe exactly."""
    sb = f"CASE {name} "
    try:
        created = PDColorSpace.create(array, None)
    except Exception:  # noqa: BLE001 — probe mirrors Java's catch(Throwable)
        return sb + "ctor=ERR"
    if not isinstance(created, PDICCBased):
        cls = "NULL" if created is None else type(created).__name__
        return sb + "ctor=NOTICC class=" + cls
    cs = created
    sb += "ctor=ok"
    try:
        nc = cs.get_number_of_components()
        sb += f" nc={nc}"
    except Exception:  # noqa: BLE001
        return sb + " nc=ERR"
    try:
        alt = cs.get_alternate_color_space()
        sb += " alt=" + ("NULL" if alt is None else type(alt).__name__)
    except Exception:  # noqa: BLE001
        sb += " alt=ERR"
    if nc <= 0:
        sb += " range=EMPTY"
    else:
        try:
            parts = []
            for i in range(nc):
                low, high = cs.get_range_for_component(i)
                parts.append(f"{low:.3f}:{high:.3f}")
            sb += " range=" + "|".join(parts)
        except Exception:  # noqa: BLE001
            sb += " range=ERR"
    try:
        sb += " meta=" + ("1" if cs.get_metadata() is not None else "0")
    except Exception:  # noqa: BLE001
        sb += " meta=ERR"
    try:
        init = cs.get_initial_color().get_components()
        sb += " init=" + ",".join(f"{c:.3f}" for c in init)
    except Exception:  # noqa: BLE001
        sb += " init=ERR"
    return sb


# ---------- the corpus (identical to IccBasedFuzzProbe.main, in order) ----


def _build_cases() -> list[tuple[str, COSArray]]:
    garbage = b"this is not an icc profile"
    short_bytes = bytes([0, 1, 2, 3])
    cases: list[tuple[str, COSArray]] = []

    def add(name: str, array: COSArray) -> None:
        cases.append((name, array))

    # ===== /N variations (no embedded profile -> iccProfile null) =====
    add("n1", _arr(_n("ICCBased"), _icc(1, None, None, None, None)))
    add("n3", _arr(_n("ICCBased"), _icc(3, None, None, None, None)))
    add("n4", _arr(_n("ICCBased"), _icc(4, None, None, None, None)))
    add("n0", _arr(_n("ICCBased"), _icc(0, None, None, None, None)))
    add("n2", _arr(_n("ICCBased"), _icc(2, None, None, None, None)))
    add("n5", _arr(_n("ICCBased"), _icc(5, None, None, None, None)))
    add("n_negative", _arr(_n("ICCBased"), _icc(-3, None, None, None, None)))
    add("n_absent", _arr(_n("ICCBased"), _icc(None, None, None, None, None)))

    # ===== /N with garbage / short profile body (still null profile) =====
    add("n3_garbage", _arr(_n("ICCBased"), _icc(3, garbage, None, None, None)))
    add("n4_garbage", _arr(_n("ICCBased"), _icc(4, garbage, None, None, None)))
    add("n3_short", _arr(_n("ICCBased"), _icc(3, short_bytes, None, None, None)))

    # ===== /Alternate present (name + array forms) =====
    add("alt_devicegray",
        _arr(_n("ICCBased"), _icc(1, None, _n("DeviceGray"), None, None)))
    add("alt_devicergb",
        _arr(_n("ICCBased"), _icc(3, None, _n("DeviceRGB"), None, None)))
    add("alt_devicecmyk",
        _arr(_n("ICCBased"), _icc(4, None, _n("DeviceCMYK"), None, None)))
    add("alt_mismatch_n3_gray",
        _arr(_n("ICCBased"), _icc(3, None, _n("DeviceGray"), None, None)))
    add("alt_array_rgb",
        _arr(_n("ICCBased"), _icc(3, None, _arr(_n("DeviceRGB")), None, None)))
    add("alt_unknown_name",
        _arr(_n("ICCBased"), _icc(3, None, _n("FooBar"), None, None)))
    add("alt_present_n2",
        _arr(_n("ICCBased"), _icc(2, None, _n("DeviceRGB"), None, None)))
    add("alt_wrong_type",
        _arr(_n("ICCBased"), _icc(3, None, COSInteger.get(7), None, None)))

    # ===== default-alternate-by-N (no /Alternate) =====
    add("default_alt_n1", _arr(_n("ICCBased"), _icc(1, None, None, None, None)))
    add("default_alt_n3", _arr(_n("ICCBased"), _icc(3, None, None, None, None)))
    add("default_alt_n4", _arr(_n("ICCBased"), _icc(4, None, None, None, None)))

    # ===== /Range corners =====
    add("range_ok_n3",
        _arr(_n("ICCBased"),
             _icc(3, None, _n("DeviceRGB"), _floats(0, 1, 0, 1, 0, 1), None)))
    add("range_custom_n3",
        _arr(_n("ICCBased"),
             _icc(3, None, _n("DeviceRGB"), _floats(-1, 2, -1, 2, -1, 2), None)))
    add("range_short_n3",
        _arr(_n("ICCBased"),
             _icc(3, None, _n("DeviceRGB"), _floats(0, 1), None)))
    add("range_empty_n3",
        _arr(_n("ICCBased"),
             _icc(3, None, _n("DeviceRGB"), COSArray(), None)))
    bad_range = COSArray()
    for _ in range(3):
        bad_range.add(_n("x"))
        bad_range.add(_n("y"))
    add("range_nonnumeric_n3",
        _arr(_n("ICCBased"), _icc(3, None, _n("DeviceRGB"), bad_range, None)))
    add("range_long_n1",
        _arr(_n("ICCBased"),
             _icc(1, None, _n("DeviceGray"), _floats(0, 1, 5, 9), None)))

    # ===== /Metadata corners =====
    add("meta_present",
        _arr(_n("ICCBased"),
             _icc(3, None, _n("DeviceRGB"), None, _meta_stream())))
    add("meta_absent",
        _arr(_n("ICCBased"), _icc(3, None, _n("DeviceRGB"), None, None)))

    # ===== empty / malformed stream body =====
    add("empty_body_n3", _arr(_n("ICCBased"), _icc(3, b"", None, None, None)))
    add("body_with_null_n1",
        _arr(_n("ICCBased"), _icc(1, bytes([0, 0, 0, 0]), None, None, None)))

    # ===== combined garbage profile + alternate fallback =====
    add("garbage_with_alt_cmyk",
        _arr(_n("ICCBased"), _icc(4, garbage, _n("DeviceCMYK"), None, None)))
    add("garbage_default_alt_n4",
        _arr(_n("ICCBased"), _icc(4, garbage, None, None, None)))

    # ===== second element not a stream =====
    add("second_not_stream", _arr(_n("ICCBased"), _n("DeviceRGB")))
    add("one_element", _arr(_n("ICCBased")))
    add("second_cosnull", _arr(_n("ICCBased"), COSNull.NULL))
    add("second_string", _arr(_n("ICCBased"), COSString("x")))

    return cases


# ---------- documented both-sides-pinned divergences ----------
#
# case name -> (pypdfbox CASE line, reason). Every entry is asserted to (a)
# match pypdfbox's emitted line exactly AND (b) differ from the Java oracle — so
# a future convergence fails the test and forces the pin's removal. Reason
# codes:
#   create -> permissive factory contract (Java throws; pypdfbox lenient)
#   range  -> /Range numeric leniency (Java PDRange throws; pypdfbox coerces 0)
_CREATE = (
    "Java PDICCBased construction throws (IOException) on invalid /N with no "
    "usable /Alternate, on an uncreatable /Alternate, or on a non-stream "
    "second slot; pypdfbox factory is permissive (constructs and surfaces the "
    "defect later) — same family as test_colorspace_fuzz_wave1512.py"
)
_RANGE = (
    "Java PDRange.getMin() throws on a non-numeric /Range entry; pypdfbox's "
    "to_float_array coerces non-numerics to 0.0 (lenient /Range read)"
)

_EXPECTED_DIVERGENCES: dict[str, tuple[str, str]] = {
    # --- permissive create contract: invalid /N, no usable alternate ---
    "n0": ("CASE n0 ctor=ok nc=0 alt=NULL range=EMPTY meta=0 init=", _CREATE),
    "n2": (
        "CASE n2 ctor=ok nc=2 alt=NULL range=0.000:1.000|0.000:1.000 meta=0 "
        "init=0.000,0.000",
        _CREATE,
    ),
    "n5": (
        "CASE n5 ctor=ok nc=5 alt=NULL "
        "range=0.000:1.000|0.000:1.000|0.000:1.000|0.000:1.000|0.000:1.000 "
        "meta=0 init=0.000,0.000,0.000,0.000,0.000",
        _CREATE,
    ),
    "n_negative": (
        "CASE n_negative ctor=ok nc=-3 alt=NULL range=EMPTY meta=0 init=",
        _CREATE,
    ),
    "n_absent": (
        "CASE n_absent ctor=ok nc=0 alt=NULL range=EMPTY meta=0 init=",
        _CREATE,
    ),
    # --- permissive create contract: uncreatable /Alternate ---
    "alt_unknown_name": (
        "CASE alt_unknown_name ctor=ok nc=3 alt=PDDeviceRGB "
        "range=0.000:1.000|0.000:1.000|0.000:1.000 meta=0 init=0.000,0.000,0.000",
        _CREATE,
    ),
    "alt_wrong_type": (
        "CASE alt_wrong_type ctor=ok nc=3 alt=PDDeviceRGB "
        "range=0.000:1.000|0.000:1.000|0.000:1.000 meta=0 init=0.000,0.000,0.000",
        _CREATE,
    ),
    # --- permissive create contract: second slot not a stream ---
    "second_not_stream": (
        "CASE second_not_stream ctor=ok nc=0 alt=NULL range=EMPTY meta=0 init=",
        _CREATE,
    ),
    "second_cosnull": (
        "CASE second_cosnull ctor=ok nc=0 alt=NULL range=EMPTY meta=0 init=",
        _CREATE,
    ),
    "second_string": (
        "CASE second_string ctor=ok nc=0 alt=NULL range=EMPTY meta=0 init=",
        _CREATE,
    ),
    # --- /Range numeric leniency ---
    "range_nonnumeric_n3": (
        "CASE range_nonnumeric_n3 ctor=ok nc=3 alt=PDDeviceRGB "
        "range=0.000:0.000|0.000:0.000|0.000:0.000 meta=0 init=0.000,0.000,0.000",
        _RANGE,
    ),
}


def _parse_probe(text: str) -> dict[str, str]:
    """Map case name -> full CASE line from the probe's stdout."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.startswith("CASE "):
            continue
        name = line.split(" ", 2)[1]
        out[name] = line
    return out


@pytest.fixture(scope="module")
def _java_lines() -> dict[str, str]:
    return _parse_probe(run_probe_text("IccBasedFuzzProbe"))


@requires_oracle
def test_corpus_count_matches(_java_lines: dict[str, str]) -> None:
    """The Java probe and the Python sibling drive the identical case set."""
    py_names = [name for name, _ in _build_cases()]
    assert len(py_names) == len(set(py_names)), "duplicate case name in corpus"
    assert set(py_names) == set(_java_lines), (
        "corpus drift: python-only="
        f"{sorted(set(py_names) - set(_java_lines))} "
        f"java-only={sorted(set(_java_lines) - set(py_names))}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "name,array", _build_cases(), ids=[c[0] for c in _build_cases()]
)
def test_icc_based_fuzz_case(
    name: str, array: COSArray, _java_lines: dict[str, str]
) -> None:
    """Each case's pypdfbox CASE line matches Java byte-for-byte, except the
    documented both-sides-pinned divergences."""
    py_line = _emit(name, array)
    java_line = _java_lines[name]

    if name in _EXPECTED_DIVERGENCES:
        pinned, reason = _EXPECTED_DIVERGENCES[name]
        assert py_line == pinned, (
            f"{name}: pypdfbox CASE line drifted from its pin.\n"
            f"  emitted: {py_line!r}\n  pinned : {pinned!r}\n  reason : {reason}"
        )
        assert py_line != java_line, (
            f"{name}: pypdfbox now matches the Java oracle — the documented "
            f"divergence ({reason}) no longer holds. Remove this pin and let "
            f"the case fall through to the exact-match assertion.\n"
            f"  java/py: {java_line!r}"
        )
        return

    assert py_line == java_line, (
        f"{name}: pypdfbox diverged from the Java oracle but is not in the "
        f"documented divergence map — this is a real parity regression.\n"
        f"  pypdfbox: {py_line!r}\n  PDFBox  : {java_line!r}"
    )
