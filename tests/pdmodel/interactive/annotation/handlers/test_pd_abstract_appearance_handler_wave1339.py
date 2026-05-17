"""Coverage-boost wave 1339 tests for :class:`PDAbstractAppearanceHandler`.

Targets the remaining miss lines:
- existing-stream-entry happy returns for /AP /N, /D, /R
- ``get_appearance_entry_as_content_stream`` when the entry holds no stream
- ``draw_style`` for LE_R_OPEN_ARROW, LE_R_CLOSED_ARROW, LE_SLASH
- ``_components_to_rgb`` zero-length default
- ``generate_rollover_appearance`` / ``generate_down_appearance`` default no-ops
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_abstract_appearance_handler import (
    PDAbstractAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class _ConcreteHandler(PDAbstractAppearanceHandler):
    def generate_normal_appearance(self) -> None:
        return None


# ---------- existing stream entry returns ----------


def _annot_with_rect() -> PDAnnotation:
    annot = PDAnnotation()
    annot.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    return annot


def test_get_normal_appearance_returns_existing_stream_entry() -> None:
    """When /AP /N already exists as a stream entry, ``get_normal_appearance``
    returns it directly (covers line 226 — the ``return normal_entry``
    branch where the entry is not None and not a sub-dictionary)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    ap = handler.get_appearance()
    # Seed /N with a real stream so the next get_normal_appearance call
    # follows the existing-entry path.
    cos_stream = handler.create_cos_stream()
    ap.set_normal_appearance(PDAppearanceEntry(cos_stream))
    result = handler.get_normal_appearance()
    assert result is not None
    assert result.is_stream()


def test_get_down_appearance_returns_existing_stream_entry() -> None:
    """/AP /D as a stream entry -> direct return (line 310)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    ap = handler.get_appearance()
    cos_stream = handler.create_cos_stream()
    ap.set_down_appearance(PDAppearanceEntry(cos_stream))
    result = handler.get_down_appearance()
    assert result is not None
    assert result.is_stream()


def test_get_rollover_appearance_returns_existing_stream_entry() -> None:
    """/AP /R as a stream entry -> direct return (line 323)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    ap = handler.get_appearance()
    cos_stream = handler.create_cos_stream()
    ap.set_rollover_appearance(PDAppearanceEntry(cos_stream))
    result = handler.get_rollover_appearance()
    assert result is not None
    assert result.is_stream()


# ---------- get_appearance_entry_as_content_stream fallback ----------


def test_get_appearance_entry_as_content_stream_falls_back_when_no_stream() -> None:
    """An entry whose ``get_appearance_stream()`` returns None forces the
    fallback to ``get_normal_appearance_stream`` (line 291)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)

    class _NoStreamEntry:
        def get_appearance_stream(self):
            return None

    cs = handler.get_appearance_entry_as_content_stream(_NoStreamEntry())
    try:
        # The content stream was created on the always-allocated normal entry.
        assert cs is not None
    finally:
        cs.close()


# ---------- draw_style: LE_R_OPEN_ARROW, LE_R_CLOSED_ARROW, LE_SLASH ----------


def _open_writer(handler: _ConcreteHandler):
    return handler.get_normal_appearance_as_content_stream()


def test_draw_style_r_open_arrow_emits_arrow_arms() -> None:
    """LE_R_OPEN_ARROW -> draw_arrow with negated sign + no close-path
    (covers lines 508-512)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    cs = _open_writer(handler)
    handler.draw_style(
        PDAnnotationLine.LE_R_OPEN_ARROW, cs, 50.0, 50.0, 1.0,
        has_stroke=True, has_background=False, ending=False,
    )
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    # draw_arrow emits 1 moveto + 2 linetos.
    assert body.count(b" m\n") >= 1
    assert body.count(b" l\n") >= 2


def test_draw_style_r_closed_arrow_emits_close_path() -> None:
    """LE_R_CLOSED_ARROW is also a closed style — emits ``h``."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    cs = _open_writer(handler)
    handler.draw_style(
        PDAnnotationLine.LE_R_CLOSED_ARROW, cs, 50.0, 50.0, 1.0,
        has_stroke=True, has_background=True, ending=True,
    )
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    assert body.count(b"h\n") >= 1


def test_draw_style_slash_emits_single_segment() -> None:
    """LE_SLASH emits one moveto + one lineto at 60/240 degrees
    (covers lines 513-523)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    cs = _open_writer(handler)
    handler.draw_style(
        PDAnnotationLine.LE_SLASH, cs, 50.0, 50.0, 1.0,
        has_stroke=True, has_background=False, ending=False,
    )
    cs.close()
    body = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    assert body.count(b" m\n") >= 1
    assert body.count(b" l\n") >= 1


def test_draw_style_unknown_style_is_silent_noop() -> None:
    """An unknown style takes the ``else: return`` early-exit branch
    (line 525)."""
    annot = _annot_with_rect()
    handler = _ConcreteHandler(annot)
    cs = _open_writer(handler)
    before = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    handler.draw_style(
        "Wonkavator", cs, 50.0, 50.0, 1.0,
        has_stroke=True, has_background=False, ending=False,
    )
    cs.close()
    after = handler.get_normal_appearance_stream().get_cos_object().to_byte_array()
    # No new geometry was emitted (only the writer's own boilerplate, if any).
    # The early ``return`` skips the closing draw_shape call.
    assert b" m\n" not in (after[len(before):])


# ---------- _components_to_rgb zero-length default ----------


def test_components_to_rgb_empty_list_returns_black() -> None:
    """An empty /C component list falls through to the default ``(0, 0, 0)``
    (covers line 653)."""
    result = PDAbstractAppearanceHandler._components_to_rgb([])
    assert result == (0.0, 0.0, 0.0)


def test_components_to_rgb_grayscale_one_component() -> None:
    """One-component path returns ``(g, g, g)`` clipped to [0, 1]."""
    assert PDAbstractAppearanceHandler._components_to_rgb([0.5]) == (0.5, 0.5, 0.5)


def test_components_to_rgb_two_components_falls_through_to_zero() -> None:
    """Two-component (rare) /C falls through the if/elif chain since
    ``len(components) >= 3 and len(components) != 4`` doesn't match and
    ``len(components) == 4`` doesn't match — returns ``(0, 0, 0)``."""
    assert PDAbstractAppearanceHandler._components_to_rgb([0.5, 0.6]) == (0.0, 0.0, 0.0)


def test_components_to_rgb_cmyk_inverts_through_black() -> None:
    """CMYK->RGB conversion."""
    r, g, b = PDAbstractAppearanceHandler._components_to_rgb([0.0, 0.0, 0.0, 0.5])
    # K=0.5 with no chroma -> all channels = 0.5.
    assert (r, g, b) == (0.5, 0.5, 0.5)


# ---------- default no-op generate_rollover / generate_down ----------


def test_generate_rollover_appearance_default_is_noop() -> None:
    """The base ``generate_rollover_appearance`` returns None (line 662)."""

    class _BareHandler(PDAbstractAppearanceHandler):
        def generate_normal_appearance(self) -> None:
            return None

    handler = _BareHandler(PDAnnotation())
    # Call via the MRO to hit the base method (not an override).
    assert PDAbstractAppearanceHandler.generate_rollover_appearance(handler) is None


def test_generate_down_appearance_default_is_noop() -> None:
    """The base ``generate_down_appearance`` returns None (line 666)."""

    class _BareHandler(PDAbstractAppearanceHandler):
        def generate_normal_appearance(self) -> None:
            return None

    handler = _BareHandler(PDAnnotation())
    assert PDAbstractAppearanceHandler.generate_down_appearance(handler) is None
