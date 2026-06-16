"""Live PDFBox DIFFERENTIAL-FUZZ parity for the ICCBased + Indexed + device
colour-space surfaces (wave 1550, agent E).

Sibling of ``oracle/probes/IccIndexedColorFuzzProbe.java``. Where the wave-1528
``IccBasedFuzzProbe`` drilled the ``/N``/``/Alternate``/``/Range``/``/Metadata``
*accessor* surface, and ``IndexedRoundProbe``/``IndexedStreamProbe`` exercised
``PDIndexed.toRGB`` index rounding/clamp on DeviceRGB / DeviceCMYK bases, this
probe attacks angles those did NOT cover:

* **ICCBased** with NO embedded profile (Java's AWT ``ICC_Profile`` parse stays
  null, matching pypdfbox which carries no AWT colour space): project
  ``getNumberOfComponents``, ``getInitialColor`` components, and a single
  ``toRGB`` routed through the alternate colour space.
* **Indexed** construction over malformed ``/hival`` (negative, huge, non-int
  name, COSNull) and malformed ``/lookup`` (string vs stream, too short / too
  long / COSNull / empty); project ``toRGB`` over a wide index sweep (including
  out-of-range indices) so the clamp-to-``actualMaxIndex`` and lookup-shrink
  behaviour is in the trace. Bases: DeviceGray (1 byte/entry), DeviceRGB (3),
  DeviceCMYK (4), ICCBased-with-DeviceRGB-alternate (3).
* **device** DeviceGray/RGB/CMYK ``getNumberOfComponents``, ``getInitialColor``,
  ``toRGB`` at interior points.

The corpus is rebuilt case-for-case in the same order on the pypdfbox side, the
identical line grammar is emitted, and every line is asserted against the live
Java oracle — except the documented divergences, which are pinned BOTH SIDES
(assert pypdfbox emits the pin AND that Java differs, so a future convergence
fails loudly).

Two divergence families show up here, both pre-existing design decisions:

1. **CMM** — any ``toRGB`` that bottoms out in Java's ``PDDeviceCMYK`` routes
   through the bundled ``CGATS001Compat-v2-micro`` ICC profile + the JVM colour
   management module (a known XYZ→sRGB delta). pypdfbox uses the textbook
   subtractive approximation ``r=(1-c)(1-k)`` etc. The probe emits a
   ``CMM_MARKER`` token for the two pure-DeviceCMYK device cases; the ICCBased
   and Indexed cases whose alternate / base is DeviceCMYK byte-compare and so
   are pinned in ``_EXPECTED_DIVERGENCES``.
2. **create** — permissive factory contract. Java's ``PDIndexed`` constructor
   eagerly reads ``/hival`` (private ``getHival()`` casts to ``COSNumber`` and is
   consumed by ``readColorTable``) and the ``/lookup`` bytes, so a negative
   ``/hival`` (``NegativeArraySizeException``), a non-number ``/hival``
   (``ClassCastException`` / null), and a missing/empty ``/lookup`` all raise at
   CONSTRUCTION (``ctor=ERR``). pypdfbox is permissive: ``get_hival`` clamps to
   ``[0, 255]`` and ``get_lookup_data`` pads/truncates, so the constructor always
   succeeds. Same family as ``test_icc_based_fuzz_wave1528.py`` / wave 1512.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared helpers (mirror the Java probe) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _comps(c: list[float]) -> str:
    return ",".join(f"{v:.3f}" for v in c)


def _icc_stream(n_val: int | None, alt: COSBase | None) -> COSStream:
    s = COSStream()
    if n_val is not None:
        s.set_int("N", n_val)
    if alt is not None:
        s.set_item("Alternate", alt)
    with s.create_output_stream():
        pass
    return s


def _lookup_stream(palette: bytes) -> COSStream:
    s = COSStream()
    with s.create_output_stream(COSName.get_pdf_name("FlateDecode")) as os:
        os.write(palette)
    return s


def _indexed_arr(base: COSBase, hival: COSBase, lookup: COSBase) -> COSArray:
    a = COSArray()
    a.add(COSName.get_pdf_name("Indexed"))
    a.add(base)
    a.add(hival)
    a.add(lookup)
    return a


def _icc_rgb_base() -> COSArray:
    return _arr(_n("ICCBased"), _icc_stream(3, _n("DeviceRGB")))


# ---------- line emitters (mirror IccIndexedColorFuzzProbe.emit*) ----------


def _emit_icc(name: str, array: COSArray, sample: list[float]) -> str:
    sb = f"ICC {name} "
    try:
        created = PDColorSpace.create(array, None)
        cs = created
        assert isinstance(cs, PDICCBased)
    except Exception:  # noqa: BLE001 — mirrors Java catch(Throwable)
        return sb + "ctor=ERR"
    sb += "ctor=ok"
    try:
        sb += f" nc={cs.get_number_of_components()}"
    except Exception:  # noqa: BLE001
        sb += " nc=ERR"
    try:
        sb += " init=" + _comps(cs.get_initial_color().get_components())
    except Exception:  # noqa: BLE001
        sb += " init=ERR"
    try:
        rgb = cs.to_rgb(sample)
        if rgb is None:
            sb += " rgb=ERR"
        else:
            sb += (
                f" rgb={_clamp255(rgb[0])},{_clamp255(rgb[1])},"
                f"{_clamp255(rgb[2])}"
            )
    except Exception:  # noqa: BLE001
        sb += " rgb=ERR"
    return sb


def _emit_idx(name: str, array: COSArray, indices: list[int]) -> str:
    sb = f"IDX {name} "
    try:
        created = PDColorSpace.create(array)
        cs = created
        assert isinstance(cs, PDIndexed)
    except Exception:  # noqa: BLE001
        return sb + "ctor=ERR"
    sb += "ctor=ok"
    sb += f" nc={cs.get_number_of_components()}"
    sb += " init=" + _comps(cs.get_initial_color().get_components())
    for i in indices:
        try:
            rgb = cs.to_rgb([float(i)])
            sb += (
                f" rgb[{i}]={_clamp255(rgb[0])} {_clamp255(rgb[1])} "
                f"{_clamp255(rgb[2])}"
            )
        except Exception:  # noqa: BLE001
            sb += f" rgb[{i}]=ERR"
    return sb


def _emit_dev(
    name: str, cs: PDColorSpace, sample: list[float], cmm: bool
) -> str:
    sb = f"DEV {name} "
    sb += f"nc={cs.get_number_of_components()}"
    sb += " init=" + _comps(cs.get_initial_color().get_components())
    if cmm:
        sb += " rgb=CMM_MARKER"
    else:
        try:
            rgb = cs.to_rgb(sample)
            sb += (
                f" rgb={_clamp255(rgb[0])},{_clamp255(rgb[1])},"
                f"{_clamp255(rgb[2])}"
            )
        except Exception:  # noqa: BLE001
            sb += " rgb=ERR"
    return sb


# ---------- the corpus (identical to the Java main, in order) ----------


def _build_cases() -> list[tuple[str, str]]:
    """Return ``[(case_name, emitted_line), ...]`` in probe order."""
    gray_palette = bytes([0, 64, 128, 255])
    rgb_palette = bytes(
        [0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255]
    )
    cmyk_palette = bytes([0, 0, 0, 0, 255, 255, 255, 255])
    sweep = [-2, 0, 1, 2, 3, 4, 10]

    out: list[tuple[str, str]] = []

    def icc(name: str, array: COSArray, sample: list[float]) -> None:
        out.append((name, _emit_icc(name, array, sample)))

    def idx(name: str, array: COSArray, indices: list[int]) -> None:
        out.append((name, _emit_idx(name, array, indices)))

    def dev(name: str, cs: PDColorSpace, sample: list[float], m: bool) -> None:
        out.append((name, _emit_dev(name, cs, sample, m)))

    # ===================== ICCBased =====================
    icc("icc_n1", _arr(_n("ICCBased"), _icc_stream(1, None)), [0.5])
    icc("icc_n3", _arr(_n("ICCBased"), _icc_stream(3, None)), [0.2, 0.4, 0.6])
    icc(
        "icc_n4",
        _arr(_n("ICCBased"), _icc_stream(4, None)),
        [0.1, 0.2, 0.3, 0.4],
    )
    icc(
        "icc_n4_alt_gray",
        _arr(_n("ICCBased"), _icc_stream(4, _n("DeviceGray"))),
        [0.5, 0.5, 0.5, 0.5],
    )
    icc(
        "icc_n1_alt_gray",
        _arr(_n("ICCBased"), _icc_stream(1, _n("DeviceGray"))),
        [0.75],
    )
    icc(
        "icc_n3_alt_rgb",
        _arr(_n("ICCBased"), _icc_stream(3, _n("DeviceRGB"))),
        [1.0, 0.0, 0.5],
    )
    icc(
        "icc_n4_alt_cmyk",
        _arr(_n("ICCBased"), _icc_stream(4, _n("DeviceCMYK"))),
        [0.0, 0.0, 0.0, 0.5],
    )

    # ===================== Indexed =====================
    idx(
        "gray_ok",
        _indexed_arr(_n("DeviceGray"), COSInteger.get(3), COSString(gray_palette)),
        sweep,
    )
    idx(
        "rgb_ok",
        _indexed_arr(_n("DeviceRGB"), COSInteger.get(3), COSString(rgb_palette)),
        sweep,
    )
    idx(
        "rgb_stream",
        _indexed_arr(
            _n("DeviceRGB"), COSInteger.get(3), _lookup_stream(rgb_palette)
        ),
        sweep,
    )
    idx(
        "cmyk_ok",
        _indexed_arr(
            _n("DeviceCMYK"), COSInteger.get(1), COSString(cmyk_palette)
        ),
        [-1, 0, 1, 2],
    )
    idx(
        "base_icc_rgb",
        _indexed_arr(
            _icc_rgb_base(), COSInteger.get(3), COSString(rgb_palette)
        ),
        sweep,
    )

    # ---- malformed /hival ----
    idx(
        "hival_0",
        _indexed_arr(_n("DeviceRGB"), COSInteger.get(0), COSString(rgb_palette)),
        sweep,
    )
    idx(
        "hival_neg",
        _indexed_arr(_n("DeviceRGB"), COSInteger.get(-1), COSString(rgb_palette)),
        sweep,
    )
    idx(
        "hival_huge",
        _indexed_arr(
            _n("DeviceRGB"), COSInteger.get(100000), COSString(rgb_palette)
        ),
        sweep,
    )
    idx(
        "hival_255_short",
        _indexed_arr(
            _n("DeviceRGB"), COSInteger.get(255), COSString(rgb_palette)
        ),
        sweep,
    )
    idx(
        "hival_name",
        _indexed_arr(_n("DeviceRGB"), _n("Bogus"), COSString(rgb_palette)),
        sweep,
    )
    idx(
        "hival_null",
        _indexed_arr(_n("DeviceRGB"), COSNull.NULL, COSString(rgb_palette)),
        sweep,
    )

    # ---- malformed /lookup ----
    idx(
        "lookup_short",
        _indexed_arr(
            _n("DeviceRGB"),
            COSInteger.get(3),
            COSString(bytes([10, 20, 30, 40, 50, 60])),
        ),
        sweep,
    )
    idx(
        "lookup_long",
        _indexed_arr(_n("DeviceRGB"), COSInteger.get(1), COSString(rgb_palette)),
        sweep,
    )
    idx(
        "lookup_null",
        _indexed_arr(_n("DeviceRGB"), COSInteger.get(3), COSNull.NULL),
        sweep,
    )
    idx(
        "lookup_empty",
        _indexed_arr(_n("DeviceRGB"), COSInteger.get(3), COSString(b"")),
        sweep,
    )

    # ===================== device =====================
    dev("gray", PDDeviceGray.INSTANCE, [0.5], False)
    dev("gray_black", PDDeviceGray.INSTANCE, [0.0], False)
    dev("gray_white", PDDeviceGray.INSTANCE, [1.0], False)
    dev("rgb", PDDeviceRGB.INSTANCE, [0.25, 0.5, 0.75], False)
    dev("cmyk", PDDeviceCMYK.INSTANCE, [0.1, 0.2, 0.3, 0.4], True)
    dev("cmyk_black", PDDeviceCMYK.INSTANCE, [0.0, 0.0, 0.0, 1.0], True)

    return out


# ---------- documented both-sides-pinned divergences ----------
#
# case name -> (pypdfbox line, reason). Each entry is asserted to (a) match
# pypdfbox's emitted line exactly AND (b) differ from the Java oracle, so a
# future convergence fails and forces the pin's removal.
_CMM = (
    "Java toRGB bottoms out in PDDeviceCMYK, which routes through the bundled "
    "CGATS001Compat-v2-micro ICC profile + the JVM CMM (XYZ->sRGB); pypdfbox "
    "uses the textbook subtractive approximation r=(1-c)(1-k) etc. — known "
    "pinned device-CMYK divergence"
)
_CREATE = (
    "Java PDIndexed constructor eagerly consumes /hival (cast to COSNumber, "
    "fed to readColorTable) and /lookup, so a negative/non-number/missing/empty "
    "value raises at construction (NegativeArraySizeException / "
    "ClassCastException / NPE); pypdfbox is permissive (get_hival clamps to "
    "[0,255], get_lookup_data pads/truncates) — same family as "
    "test_icc_based_fuzz_wave1528.py / wave 1512"
)

_EXPECTED_DIVERGENCES: dict[str, tuple[str, str]] = {
    # --- CMM: ICCBased(N=4)/no-profile -> default DeviceCMYK alternate, whose
    #     toRGB is CMM-routed in Java, subtractive in pypdfbox.
    "icc_n4": (
        "ICC icc_n4 ctor=ok nc=4 init=0.000,0.000,0.000,1.000 rgb=138,122,107",
        _CMM,
    ),
    # --- CMM: explicit DeviceCMYK alternate.
    "icc_n4_alt_cmyk": (
        "ICC icc_n4_alt_cmyk ctor=ok nc=4 init=0.000,0.000,0.000,1.000 "
        "rgb=128,128,128",
        _CMM,
    ),
    # --- permissive create: malformed hival / lookup (Java ctor=ERR).
    "hival_neg": (
        "IDX hival_neg ctor=ok nc=1 init=0.000 rgb[-2]=0 0 0 rgb[0]=0 0 0 "
        "rgb[1]=0 0 0 rgb[2]=0 0 0 rgb[3]=0 0 0 rgb[4]=0 0 0 rgb[10]=0 0 0",
        _CREATE,
    ),
    "hival_name": (
        "IDX hival_name ctor=ok nc=1 init=0.000 rgb[-2]=0 0 0 rgb[0]=0 0 0 "
        "rgb[1]=0 0 0 rgb[2]=0 0 0 rgb[3]=0 0 0 rgb[4]=0 0 0 rgb[10]=0 0 0",
        _CREATE,
    ),
    "hival_null": (
        "IDX hival_null ctor=ok nc=1 init=0.000 rgb[-2]=0 0 0 rgb[0]=0 0 0 "
        "rgb[1]=0 0 0 rgb[2]=0 0 0 rgb[3]=0 0 0 rgb[4]=0 0 0 rgb[10]=0 0 0",
        _CREATE,
    ),
    "lookup_null": (
        "IDX lookup_null ctor=ok nc=1 init=0.000 rgb[-2]=0 0 0 rgb[0]=0 0 0 "
        "rgb[1]=0 0 0 rgb[2]=0 0 0 rgb[3]=0 0 0 rgb[4]=0 0 0 rgb[10]=0 0 0",
        _CREATE,
    ),
    "lookup_empty": (
        "IDX lookup_empty ctor=ok nc=1 init=0.000 rgb[-2]=0 0 0 rgb[0]=0 0 0 "
        "rgb[1]=0 0 0 rgb[2]=0 0 0 rgb[3]=0 0 0 rgb[4]=0 0 0 rgb[10]=0 0 0",
        _CREATE,
    ),
}


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not (
            line.startswith("ICC ")
            or line.startswith("IDX ")
            or line.startswith("DEV ")
        ):
            continue
        name = line.split(" ", 2)[1]
        out[name] = line
    return out


@pytest.fixture(scope="module")
def _java_lines() -> dict[str, str]:
    return _parse_probe(run_probe_text("IccIndexedColorFuzzProbe"))


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
    "name,py_line", _build_cases(), ids=[c[0] for c in _build_cases()]
)
def test_icc_indexed_color_fuzz_case(
    name: str, py_line: str, _java_lines: dict[str, str]
) -> None:
    """Each case's pypdfbox line matches Java byte-for-byte, except the
    documented both-sides-pinned divergences."""
    java_line = _java_lines[name]

    if name in _EXPECTED_DIVERGENCES:
        pinned, reason = _EXPECTED_DIVERGENCES[name]
        assert py_line == pinned, (
            f"{name}: pypdfbox line drifted from its pin.\n"
            f"  emitted: {py_line!r}\n  pinned : {pinned!r}\n  reason : {reason}"
        )
        assert py_line != java_line, (
            f"{name}: pypdfbox now matches the Java oracle — the documented "
            f"divergence ({reason}) no longer holds. Remove this pin.\n"
            f"  java/py: {java_line!r}"
        )
        return

    assert py_line == java_line, (
        f"{name}: pypdfbox diverged from the Java oracle but is not in the "
        f"documented divergence map — a real parity regression.\n"
        f"  pypdfbox: {py_line!r}\n  PDFBox  : {java_line!r}"
    )


# ---------- direct accessor parity (no oracle needed) ----------


def test_device_number_of_components() -> None:
    assert PDDeviceGray.INSTANCE.get_number_of_components() == 1
    assert PDDeviceRGB.INSTANCE.get_number_of_components() == 3
    assert PDDeviceCMYK.INSTANCE.get_number_of_components() == 4


def test_device_initial_color() -> None:
    assert PDDeviceGray.INSTANCE.get_initial_color().get_components() == [0.0]
    assert PDDeviceRGB.INSTANCE.get_initial_color().get_components() == [
        0.0,
        0.0,
        0.0,
    ]
    assert PDDeviceCMYK.INSTANCE.get_initial_color().get_components() == [
        0.0,
        0.0,
        0.0,
        1.0,
    ]


def test_indexed_color_table_size_clamps_to_lookup() -> None:
    """get_color_table / get_actual_max_index honour the lookup-shrink rule:
    a huge hival with a 4-entry palette yields exactly 4 entries."""
    arr = _indexed_arr(
        _n("DeviceRGB"),
        COSInteger.get(100000),
        COSString(bytes([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255])),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)
    assert cs.get_actual_max_index() == 3
    assert len(cs.get_color_table()) == 4


def test_indexed_hival_zero_single_entry() -> None:
    arr = _indexed_arr(
        _n("DeviceRGB"), COSInteger.get(0), COSString(bytes([12, 34, 56]))
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)
    assert cs.get_actual_max_index() == 0
    assert cs.to_rgb([0.0]) == pytest.approx(
        [12 / 255.0, 34 / 255.0, 56 / 255.0]
    )
    # Out-of-range index clamps to the single entry.
    assert cs.to_rgb([5.0]) == pytest.approx(cs.to_rgb([0.0]))


def test_icc_no_profile_get_number_of_components() -> None:
    for nval, exp in ((1, 1), (3, 3), (4, 4)):
        arr = _arr(_n("ICCBased"), _icc_stream(nval, None))
        cs = PDColorSpace.create(arr, None)
        assert isinstance(cs, PDICCBased)
        assert cs.get_number_of_components() == exp


def test_icc_default_alternate_initial_color_cmyk() -> None:
    """N=4 with no /Alternate -> default DeviceCMYK alternate; initial colour
    comes from the alternate verbatim, i.e. (0, 0, 0, 1)."""
    arr = _arr(_n("ICCBased"), _icc_stream(4, None))
    cs = PDColorSpace.create(arr, None)
    assert isinstance(cs, PDICCBased)
    assert cs.get_initial_color().get_components() == [0.0, 0.0, 0.0, 1.0]


def test_indexed_base_icc_rgb_palette_decode() -> None:
    """An Indexed space over an ICCBased(N=3, /Alternate DeviceRGB) base with
    no readable profile decodes its palette through the alternate (identity)."""
    rgb_palette = bytes([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255])
    arr = _indexed_arr(
        _icc_rgb_base(), COSInteger.get(3), COSString(rgb_palette)
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)
    assert cs.to_rgb([1.0]) == pytest.approx([1.0, 0.0, 0.0])
    assert cs.to_rgb([2.0]) == pytest.approx([0.0, 1.0, 0.0])


def test_indexed_to_rgb_requires_one_component() -> None:
    arr = _indexed_arr(
        _n("DeviceRGB"),
        COSInteger.get(0),
        COSString(bytes([0, 0, 0])),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)
    with pytest.raises(ValueError):
        cs.to_rgb([0.0, 0.0])


def test_device_cmyk_subtractive_to_rgb() -> None:
    """pypdfbox DeviceCMYK uses the subtractive approximation (documented
    divergence from upstream's CMM path)."""
    rgb = PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 0.5])
    assert rgb == pytest.approx([0.5, 0.5, 0.5])
    rgb = PDColor([0.0, 0.0, 0.0, 1.0], PDDeviceCMYK.INSTANCE).to_rgb()
    assert rgb == pytest.approx([0.0, 0.0, 0.0])
