"""Wave 1377 — port the /R (rollover) and /D (down) push-button appearance
variants in :class:`PDAppearanceGenerator`. Closes the wave-1374 deferred
note documented in :file:`CHANGES.md`.

For each push-button widget the generator emits:

- ``/AP /N`` — neutral (already shipped wave 33+).
- ``/AP /R`` — rollover (Wave 1377): tints ``/MK /BG`` lighter, uses
  ``/MK /RC`` caption if set (falls back to ``/CA``).
- ``/AP /D`` — down/clicked (Wave 1377): tints ``/MK /BG`` darker, uses
  ``/MK /AC`` caption if set (falls back to ``/CA``).

When neither ``/RC`` nor ``/BG`` is set the rollover variant has no
visual signal and the entry is omitted; same for ``/AC`` + ``/BG`` for
the down variant.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_R: COSName = COSName.get_pdf_name("R")
_D: COSName = COSName.get_pdf_name("D")
_MK: COSName = COSName.get_pdf_name("MK")
_CA_KEY: COSName = COSName.get_pdf_name("CA")
_RC_KEY: COSName = COSName.get_pdf_name("RC")
_AC_KEY: COSName = COSName.get_pdf_name("AC")
_BG_KEY: COSName = COSName.get_pdf_name("BG")
_BC_KEY: COSName = COSName.get_pdf_name("BC")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _gray(value: float) -> COSArray:
    """Single-component gray /MK colour array."""
    return COSArray([COSFloat(value)])


def _rgb(r: float, g: float, b: float) -> COSArray:
    """Three-component RGB /MK colour array."""
    return COSArray([COSFloat(r), COSFloat(g), COSFloat(b)])


def _build_push_button(
    *,
    ca: str | None = None,
    rc: str | None = None,
    ac: str | None = None,
    bg: COSArray | None = None,
    bc: COSArray | None = None,
) -> PDPushButton:
    """Build a fresh push-button field with the requested /MK entries
    populated. Each test gets its own AcroForm + field so widget state
    doesn't leak between cases."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    cos = pb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 30))
    mk = COSDictionary()
    if ca is not None:
        mk.set_string(_CA_KEY, ca)
    if rc is not None:
        mk.set_string(_RC_KEY, rc)
    if ac is not None:
        mk.set_string(_AC_KEY, ac)
    if bg is not None:
        mk.set_item(_BG_KEY, bg)
    if bc is not None:
        mk.set_item(_BC_KEY, bc)
    if (
        ca is not None
        or rc is not None
        or ac is not None
        or bg is not None
        or bc is not None
    ):
        cos.set_item(_MK, mk)
    return pb


def _ap_dict(pb: PDPushButton) -> COSDictionary:
    widget_cos = pb.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    return ap


# ---------- baseline: all three states emitted ----------


def test_push_button_emits_normal_rollover_and_down_when_all_captions_present() -> None:
    """Captions /CA + /RC + /AC -> /N + /R + /D streams all written."""
    pb = _build_push_button(ca="Click", rc="Hover", ac="Pressed")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    n = ap.get_dictionary_object(_N)
    r = ap.get_dictionary_object(_R)
    d = ap.get_dictionary_object(_D)
    assert isinstance(n, COSStream)
    assert isinstance(r, COSStream)
    assert isinstance(d, COSStream)

    # Each stream's content reflects its caption.
    assert b"(Click)" in n.create_input_stream().read()
    assert b"(Hover)" in r.create_input_stream().read()
    assert b"(Pressed)" in d.create_input_stream().read()


# ---------- caption-only without /BG -> only /N ----------


def test_push_button_only_normal_when_neither_rc_ac_nor_bg() -> None:
    """A push button with only /CA carries no visual rollover or down
    signal, so /R + /D are skipped (viewers fall back to /N)."""
    pb = _build_push_button(ca="Submit")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    # No /R or /D when there's nothing to distinguish them visually.
    assert ap.get_dictionary_object(_R) is None
    assert ap.get_dictionary_object(_D) is None


def test_push_button_with_only_rc_emits_rollover_but_not_down() -> None:
    """/RC present + /BG absent + /AC absent -> /R emitted, /D skipped."""
    pb = _build_push_button(ca="Submit", rc="Hover-me")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    assert isinstance(ap.get_dictionary_object(_N), COSStream)
    r = ap.get_dictionary_object(_R)
    assert isinstance(r, COSStream)
    assert b"(Hover-me)" in r.create_input_stream().read()
    assert ap.get_dictionary_object(_D) is None


def test_push_button_with_only_ac_emits_down_but_not_rollover() -> None:
    """/AC present + /BG absent + /RC absent -> /D emitted, /R skipped."""
    pb = _build_push_button(ca="Submit", ac="Clicked!")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    assert isinstance(ap.get_dictionary_object(_N), COSStream)
    assert ap.get_dictionary_object(_R) is None
    d = ap.get_dictionary_object(_D)
    assert isinstance(d, COSStream)
    assert b"(Clicked!)" in d.create_input_stream().read()


# ---------- background-only -> all three with tinted /BG ----------


def test_push_button_with_bg_only_emits_all_three_with_tinted_backgrounds() -> None:
    """A push button with /MK /BG (no /RC, /AC) still emits /R and /D
    because the lighter / darker background fill carries the rollover
    + down signal even when the caption is unchanged."""
    pb = _build_push_button(
        ca="Action", bg=_gray(0.5), bc=_gray(0.0)
    )

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    n_body = ap.get_dictionary_object(_N).create_input_stream().read()
    r_body = ap.get_dictionary_object(_R).create_input_stream().read()
    d_body = ap.get_dictionary_object(_D).create_input_stream().read()

    # All three reference the /N caption (no /RC, /AC override).
    assert b"(Action)" in n_body
    assert b"(Action)" in r_body
    assert b"(Action)" in d_body

    # /N uses the raw /BG = 0.5 grey. /R lightens to 0.6, /D darkens to 0.4.
    # Lite content stream emits gray-fill as "<g> g" (lowercase g operator).
    assert b"0.5 g" in n_body
    assert b"0.6 g" in r_body
    assert b"0.4 g" in d_body


def test_push_button_rgb_bg_is_lightened_for_rollover_darkened_for_down() -> None:
    """RGB /MK /BG = (0.4, 0.4, 0.4) -> rollover = (0.5, 0.5, 0.5),
    down = (0.3, 0.3, 0.3). Delta is per-component clamp at [0, 1].
    """
    pb = _build_push_button(
        ca="Press", bg=_rgb(0.4, 0.4, 0.4)
    )

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    n_body = ap.get_dictionary_object(_N).create_input_stream().read()
    r_body = ap.get_dictionary_object(_R).create_input_stream().read()
    d_body = ap.get_dictionary_object(_D).create_input_stream().read()

    # RGB fill emitted as "<r> <g> <b> rg".
    assert b"0.4 0.4 0.4 rg" in n_body
    assert b"0.5 0.5 0.5 rg" in r_body
    assert b"0.3 0.3 0.3 rg" in d_body


def test_push_button_bg_clamps_at_unit_interval() -> None:
    """A near-white /BG = (0.95, 0.95, 0.95) clamps to 1.0 on rollover
    (no overshoot above 1.0). A near-black /BG = (0.05, 0.05, 0.05)
    clamps to 0.0 on down. Sanity-checks the [0, 1] clamp inside
    :meth:`_adjust_color_brightness`."""
    pb = _build_push_button(ca="X", bg=_rgb(0.95, 0.95, 0.95))
    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)
    r_body = ap.get_dictionary_object(_R).create_input_stream().read()
    # 0.95 + 0.10 = 1.05 -> clamps to 1.0; emitted as "1 1 1" (int form).
    assert b"1 1 1 rg" in r_body or b"1.0 1.0 1.0 rg" in r_body

    pb2 = _build_push_button(ca="X", bg=_rgb(0.05, 0.05, 0.05))
    PDAppearanceGenerator().generate(pb2)
    ap2 = _ap_dict(pb2)
    d_body = ap2.get_dictionary_object(_D).create_input_stream().read()
    # 0.05 - 0.10 = -0.05 -> clamps to 0.0; emitted as "0 0 0" or "0.0 0.0 0.0".
    assert b"0 0 0 rg" in d_body or b"0.0 0.0 0.0 rg" in d_body


# ---------- /RC + /AC override the caption inside the variant streams ----------


def test_push_button_rc_overrides_caption_in_rollover_stream() -> None:
    """/RC text is written into /R, /CA stays inside /N."""
    pb = _build_push_button(ca="Normal", rc="Rolled-over")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    n_body = ap.get_dictionary_object(_N).create_input_stream().read()
    r_body = ap.get_dictionary_object(_R).create_input_stream().read()
    assert b"(Normal)" in n_body
    assert b"(Rolled-over)" in r_body
    # The /N caption shouldn't leak into the rollover stream.
    assert b"(Normal)" not in r_body


def test_push_button_ac_overrides_caption_in_down_stream() -> None:
    """/AC text is written into /D, /CA stays inside /N."""
    pb = _build_push_button(ca="Normal", ac="Pressed-state")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    n_body = ap.get_dictionary_object(_N).create_input_stream().read()
    d_body = ap.get_dictionary_object(_D).create_input_stream().read()
    assert b"(Normal)" in n_body
    assert b"(Pressed-state)" in d_body
    assert b"(Normal)" not in d_body


# ---------- /BC border colour reused across all three variants ----------


def test_push_button_border_color_consistent_across_states() -> None:
    """/MK /BC stroke colour is reused on /N, /R, /D (no tint applied)
    so the rollover / down only affects the *fill*. Border stroke is
    emitted as "<r> <g> <b> RG" (capital RG = stroking colour)."""
    pb = _build_push_button(
        ca="A", rc="B", ac="C",
        bg=_gray(0.5),
        bc=_rgb(0.2, 0.4, 0.8),
    )

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    expected = b"0.2 0.4 0.8 RG"
    for key in (_N, _R, _D):
        body = ap.get_dictionary_object(key).create_input_stream().read()
        assert expected in body, f"/BC stroke missing from /{key.name}"


# ---------- empty /RC / /AC strings behave like absent (caption sentinel) ----------


def test_push_button_empty_rc_string_falls_back_to_ca_when_bg_set() -> None:
    """/MK /RC = "" + /MK /BG set -> /R is still emitted because /BG
    provides the rollover signal. The caption falls back to /CA."""
    pb = _build_push_button(ca="Hello", rc="", bg=_gray(0.6))

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    r = ap.get_dictionary_object(_R)
    assert isinstance(r, COSStream)
    assert b"(Hello)" in r.create_input_stream().read()


def test_push_button_empty_rc_and_no_bg_skips_rollover() -> None:
    """/MK /RC = "" + no /BG -> no rollover signal at all -> /R skipped."""
    pb = _build_push_button(ca="Hi", rc="")

    PDAppearanceGenerator().generate(pb)
    ap = _ap_dict(pb)

    assert isinstance(ap.get_dictionary_object(_N), COSStream)
    assert ap.get_dictionary_object(_R) is None
