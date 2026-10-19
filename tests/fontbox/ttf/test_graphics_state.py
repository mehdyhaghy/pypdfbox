"""Hand-written tests for ``GraphicsState``: super-round derivation and int-wrapping rounding."""

from pypdfbox.fontbox.ttf.graphics_state import GraphicsState

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1


def test_s45round_records_round_super():
    gs = GraphicsState()
    gs.set_super_round(0x2D41, 0x48)
    # upstream sets ROUND_SUPER for S45ROUND too, never ROUND_SUPER_45
    assert gs.get_round_state() == GraphicsState.ROUND_SUPER


def test_super_round_negative_threshold_truncates_toward_zero():
    gs = GraphicsState()
    # selector 0x41: period 1px, phase 0, threshold (1 - 4) * period / 8 = -6144 in F2Dot14
    # (Java truncation), >> 8 = -24 (arithmetic shift)
    gs.set_super_round(0x4000, 0x41)
    assert gs._round_threshold == -24
    assert gs.round(100) == 64  # floor((100 - 24) / 64) * 64
    assert gs.round(-100) == -64


def test_super_round_period_never_zero():
    gs = GraphicsState()
    gs.set_super_round(0x10, 0x00)  # tiny grid period: (0x10 / 2) >> 8 == 0, clamped to 1
    assert gs._round_period == 1
    assert gs.round(5) == 5


def test_round_off_then_back():
    gs = GraphicsState()
    gs.set_round_state(GraphicsState.ROUND_OFF)
    assert gs.round(37) == 37
    gs.set_round_state(GraphicsState.ROUND_TO_GRID)
    assert gs.round(37) == 64


def _java_round(gs, distance):
    """Upstream round() with every int intermediate wrapped (reference for the slow path)."""

    def w(v):
        return ((v + 2**31) & 0xFFFFFFFF) - 2**31

    if gs._round_off:
        return distance
    period, phase, thr = gs._round_period, gs._round_phase, gs._round_threshold
    if distance >= 0:
        val = w((w(w(distance - phase) + thr) // period) * period)
        val = max(val, 0)
        return w(val + phase)
    val = w(-w((w(w(thr - phase) - distance) // period) * period))
    val = min(val, 0)
    return w(val - phase)


def test_round_huge_distances_wrap_like_java():
    for state in (
        GraphicsState.ROUND_TO_GRID,
        GraphicsState.ROUND_TO_HALF_GRID,
        GraphicsState.ROUND_UP_TO_GRID,
        GraphicsState.ROUND_DOWN_TO_GRID,
        GraphicsState.ROUND_TO_DOUBLE_GRID,
    ):
        gs = GraphicsState()
        gs.set_round_state(state)
        for d in (INT_MAX, INT_MAX - 20, INT_MIN, INT_MIN + 1, 2**30, -(2**30), 12345):
            assert gs.round(d) == _java_round(gs, d), (state, d)


def test_copy_preserves_every_field():
    gs = GraphicsState()
    gs.set_super_round(0x2D41, 0x58)
    gs.set_scan_control(0x1FF)
    gs.set_scan_type(4)
    gs.set_instruct_control(6)
    gs.set_single_width_cut_in(10)
    gs.set_single_width_value(70)
    gs.set_auto_flip(False)
    gs.set_delta_shift(5)
    gs.set_zp2(0)
    clone = gs.copy()
    for name in GraphicsState.__slots__:
        if name.endswith("_vector"):
            assert getattr(clone, name) == getattr(gs, name)
            assert getattr(clone, name) is not getattr(gs, name)
        else:
            assert getattr(clone, name) == getattr(gs, name), name
