"""Wave 244 — pdmodel/interactive/annotation small parity gaps for
``PDAnnotationLink``.

Covers:
- ``STANDARD_HIGHLIGHT_MODES`` set + ``is_standard_highlight_mode``
  predicate (parity with the ``STANDARD_NAMES`` / ``is_standard_name``
  pattern on ``PDAnnotationStamp``).
- own-dictionary ``has_*`` predicates: ``has_action`` / ``has_destination`` /
  ``has_highlight_mode`` / ``has_border_style`` / ``has_quad_points`` /
  ``has_p_a`` / ``has_previous_uri``. Cheaper than the corresponding
  ``get_*() is not None`` and let callers distinguish "explicit default"
  from "no entry" for ``/H``.
- ``quad_point_count()`` helper mirroring the
  ``PDAnnotationTextMarkup.quad_point_count`` shape.
- ``is_uri_action()`` predicate so callers can tell "no action" from
  "non-URI action" from "URI action with empty ``/URI``".
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.action import PDActionGoTo, PDActionURI
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink


# ---------- STANDARD_HIGHLIGHT_MODES ----------


def test_standard_highlight_modes_size_and_contents() -> None:
    """Spec defines exactly four ``/H`` values (Table 173)."""
    assert len(PDAnnotationLink.STANDARD_HIGHLIGHT_MODES) == 4
    expected = {
        PDAnnotationLink.HIGHLIGHT_MODE_NONE,
        PDAnnotationLink.HIGHLIGHT_MODE_INVERT,
        PDAnnotationLink.HIGHLIGHT_MODE_OUTLINE,
        PDAnnotationLink.HIGHLIGHT_MODE_PUSH,
    }
    assert PDAnnotationLink.STANDARD_HIGHLIGHT_MODES == expected


def test_standard_highlight_modes_is_frozenset() -> None:
    """Constant must be immutable to prevent accidental mutation."""
    assert isinstance(PDAnnotationLink.STANDARD_HIGHLIGHT_MODES, frozenset)


def test_standard_highlight_modes_contains_each_constant() -> None:
    cls = PDAnnotationLink
    assert cls.HIGHLIGHT_MODE_NONE in cls.STANDARD_HIGHLIGHT_MODES
    assert cls.HIGHLIGHT_MODE_INVERT in cls.STANDARD_HIGHLIGHT_MODES
    assert cls.HIGHLIGHT_MODE_OUTLINE in cls.STANDARD_HIGHLIGHT_MODES
    assert cls.HIGHLIGHT_MODE_PUSH in cls.STANDARD_HIGHLIGHT_MODES


# ---------- is_standard_highlight_mode ----------


def test_is_standard_highlight_mode_default_invert() -> None:
    """Spec default ``I`` (returned when ``/H`` absent) is standard."""
    ann = PDAnnotationLink()
    assert ann.is_standard_highlight_mode() is True


def test_is_standard_highlight_mode_each_constant() -> None:
    """Every value in ``STANDARD_HIGHLIGHT_MODES`` is recognised."""
    for mode in PDAnnotationLink.STANDARD_HIGHLIGHT_MODES:
        ann = PDAnnotationLink()
        ann.set_highlight_mode(mode)
        assert ann.is_standard_highlight_mode() is True


def test_is_standard_highlight_mode_rejects_custom_value() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode("X")
    assert ann.is_standard_highlight_mode() is False


def test_is_standard_highlight_mode_rejects_widget_toggle() -> None:
    """Widget annotations also accept ``T`` (Toggle); link annotations
    do not — ``T`` should not register as a standard link highlight."""
    ann = PDAnnotationLink()
    ann.set_highlight_mode("T")
    assert ann.is_standard_highlight_mode() is False


def test_is_standard_highlight_mode_is_case_sensitive() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode("i")
    assert ann.is_standard_highlight_mode() is False


def test_is_standard_highlight_mode_after_clear_returns_true() -> None:
    """Clearing ``/H`` falls back to the spec default, which is standard."""
    ann = PDAnnotationLink()
    ann.set_highlight_mode("X")
    assert ann.is_standard_highlight_mode() is False
    ann.set_highlight_mode(None)
    assert ann.is_standard_highlight_mode() is True


# ---------- has_action / has_destination ----------


def test_has_action_default_false() -> None:
    ann = PDAnnotationLink()
    assert ann.has_action() is False


def test_has_action_after_set_returns_true() -> None:
    ann = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("https://example.test")
    ann.set_action(action)
    assert ann.has_action() is True


def test_has_action_after_clear_returns_false() -> None:
    ann = PDAnnotationLink()
    ann.set_action(PDActionURI())
    ann.set_action(None)
    assert ann.has_action() is False


def test_has_action_ignores_non_dict_value() -> None:
    """Defensive against malformed PDFs storing ``/A`` as a non-dict."""
    ann = PDAnnotationLink()
    ann.get_cos_object().set_int(COSName.get_pdf_name("A"), 5)  # type: ignore[attr-defined]
    assert ann.has_action() is False


def test_has_destination_default_false() -> None:
    ann = PDAnnotationLink()
    assert ann.has_destination() is False


def test_has_destination_named_true() -> None:
    ann = PDAnnotationLink()
    ann.set_destination(COSName.get_pdf_name("Chapter1"))
    assert ann.has_destination() is True


def test_has_destination_string_true() -> None:
    ann = PDAnnotationLink()
    ann.set_destination("MyDest")
    assert ann.has_destination() is True


def test_has_destination_after_clear_returns_false() -> None:
    ann = PDAnnotationLink()
    ann.set_destination("X")
    ann.set_destination(None)
    assert ann.has_destination() is False


# ---------- has_highlight_mode (distinguish explicit-default from absent) ----------


def test_has_highlight_mode_default_false() -> None:
    """Fresh annotation: ``/H`` absent → ``has_highlight_mode`` False even
    though ``get_highlight_mode`` returns the spec default ``I``."""
    ann = PDAnnotationLink()
    assert ann.has_highlight_mode() is False
    assert ann.get_highlight_mode() == PDAnnotationLink.HIGHLIGHT_MODE_INVERT


def test_has_highlight_mode_after_explicit_invert_returns_true() -> None:
    """Explicit ``/H /I`` (the spec default written out) is detectable."""
    ann = PDAnnotationLink()
    ann.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_INVERT)
    assert ann.has_highlight_mode() is True


def test_has_highlight_mode_after_clear_returns_false() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode("P")
    assert ann.has_highlight_mode() is True
    ann.set_highlight_mode(None)
    assert ann.has_highlight_mode() is False


# ---------- has_border_style ----------


def test_has_border_style_default_false() -> None:
    ann = PDAnnotationLink()
    assert ann.has_border_style() is False


def test_has_border_style_after_set_returns_true() -> None:
    ann = PDAnnotationLink()
    bs = COSDictionary()
    bs.set_int(COSName.get_pdf_name("W"), 2)
    ann.set_border_style(bs)
    assert ann.has_border_style() is True


def test_has_border_style_after_clear_returns_false() -> None:
    ann = PDAnnotationLink()
    ann.set_border_style(COSDictionary())
    ann.set_border_style(None)
    assert ann.has_border_style() is False


# ---------- has_quad_points / quad_point_count ----------


def test_has_quad_points_default_false() -> None:
    ann = PDAnnotationLink()
    assert ann.has_quad_points() is False


def test_has_quad_points_after_set_returns_true() -> None:
    ann = PDAnnotationLink()
    ann.set_quad_points([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    assert ann.has_quad_points() is True


def test_has_quad_points_empty_array_returns_true() -> None:
    """Empty ``/QuadPoints`` is still present — predicate reports True."""
    ann = PDAnnotationLink()
    ann.set_quad_points([])
    assert ann.has_quad_points() is True
    assert ann.quad_point_count() == 0


def test_has_quad_points_ignores_non_array_value() -> None:
    ann = PDAnnotationLink()
    ann.get_cos_object().set_int(COSName.get_pdf_name("QuadPoints"), 7)  # type: ignore[attr-defined]
    assert ann.has_quad_points() is False
    assert ann.quad_point_count() == 0


def test_quad_point_count_default_zero() -> None:
    ann = PDAnnotationLink()
    assert ann.quad_point_count() == 0


def test_quad_point_count_one_quadrilateral() -> None:
    ann = PDAnnotationLink()
    ann.set_quad_points([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    assert ann.quad_point_count() == 1


def test_quad_point_count_multiple_quadrilaterals() -> None:
    """Two quadrilaterals = 16 floats."""
    ann = PDAnnotationLink()
    coords = [float(i) for i in range(16)]
    ann.set_quad_points(coords)
    assert ann.quad_point_count() == 2


def test_quad_point_count_rounds_down_partial() -> None:
    """A trailing partial quadrilateral (not a multiple of 8) is rounded
    down — same convention used by upstream readers and the markup
    cluster."""
    ann = PDAnnotationLink()
    # 13 floats = 1 complete quadrilateral + 5 trailing values
    coords = [float(i) for i in range(13)]
    ann.set_quad_points(coords)
    assert ann.quad_point_count() == 1


# ---------- has_p_a / has_previous_uri ----------


def test_has_p_a_default_false() -> None:
    ann = PDAnnotationLink()
    assert ann.has_p_a() is False
    assert ann.has_previous_uri() is False


def test_has_p_a_after_set_returns_true() -> None:
    ann = PDAnnotationLink()
    pa = PDActionURI()
    pa.set_uri("https://prev.example.test")
    ann.set_p_a(pa)
    assert ann.has_p_a() is True
    assert ann.has_previous_uri() is True


def test_has_p_a_after_clear_returns_false() -> None:
    ann = PDAnnotationLink()
    ann.set_previous_uri(PDActionURI())
    ann.set_p_a(None)
    assert ann.has_p_a() is False
    assert ann.has_previous_uri() is False


def test_has_p_a_ignores_non_dict_value() -> None:
    ann = PDAnnotationLink()
    ann.get_cos_object().set_int(COSName.get_pdf_name("PA"), 7)  # type: ignore[attr-defined]
    assert ann.has_p_a() is False


# ---------- is_uri_action ----------


def test_is_uri_action_default_false() -> None:
    ann = PDAnnotationLink()
    assert ann.is_uri_action() is False


def test_is_uri_action_with_uri_action_returns_true() -> None:
    ann = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("https://example.test")
    ann.set_action(action)
    assert ann.is_uri_action() is True


def test_is_uri_action_with_goto_action_returns_false() -> None:
    """Non-URI action present → predicate returns False (and
    ``get_url_uri`` returns ``None``)."""
    ann = PDAnnotationLink()
    action = PDActionGoTo()
    ann.set_action(action)
    assert ann.is_uri_action() is False
    assert ann.get_url_uri() is None


def test_is_uri_action_with_empty_uri_string_returns_true() -> None:
    """``/A << /S /URI /URI () >>`` is still a URI action; predicate
    must not silently treat an empty ``/URI`` as 'not a URI action'."""
    ann = PDAnnotationLink()
    action_dict = COSDictionary()
    action_dict.set_name(COSName.get_pdf_name("S"), "URI")
    action_dict.set_string(COSName.get_pdf_name("URI"), "")
    ann.get_cos_object().set_item(COSName.get_pdf_name("A"), action_dict)
    assert ann.is_uri_action() is True
    # get_url_uri returns the empty string, not None — this is the value
    # the spec allows authors to write.
    assert ann.get_url_uri() == ""


def test_is_uri_action_ignores_non_dict_a_entry() -> None:
    ann = PDAnnotationLink()
    ann.get_cos_object().set_int(COSName.get_pdf_name("A"), 1)  # type: ignore[attr-defined]
    assert ann.is_uri_action() is False
