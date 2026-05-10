"""Upstream-aligned parity tests for ``PDAnnotationText``.

Apache PDFBox 3.0.x has no dedicated ``PDAnnotationTextTest.java``; these
tests cover the public API surface of
``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText`` as
exercised by upstream consumers and the appearance-handler regression
tests, translated to pytest. They lock in the same defaults, round-trips,
and constant catalogue that upstream Java callers rely on.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText


def test_default_constructor_writes_text_subtype() -> None:
    annotation = PDAnnotationText()
    assert annotation.get_subtype() == PDAnnotationText.SUB_TYPE


def test_dict_constructor_keeps_existing_subtype() -> None:
    backing = COSDictionary()
    backing.set_name(COSName.SUBTYPE, "Text")
    annotation = PDAnnotationText(backing)
    assert annotation.get_subtype() == "Text"
    assert annotation.get_cos_object() is backing


def test_get_open_default_false() -> None:
    # PDAnnotationText.java line 158: getCOSObject().getBoolean("Open", false)
    assert PDAnnotationText().get_open() is False


def test_set_open_round_trip() -> None:
    # PDAnnotationText.java line 146-149.
    annotation = PDAnnotationText()
    annotation.set_open(True)
    assert annotation.get_open() is True
    annotation.set_open(False)
    assert annotation.get_open() is False


def test_get_name_default_note() -> None:
    # PDAnnotationText.java line 178-181: default value is NAME_NOTE.
    assert PDAnnotationText().get_name() == PDAnnotationText.NAME_NOTE


def test_set_name_round_trip() -> None:
    annotation = PDAnnotationText()
    annotation.set_name(PDAnnotationText.NAME_COMMENT)
    assert annotation.get_name() == "Comment"
    annotation.set_name(PDAnnotationText.NAME_HELP)
    assert annotation.get_name() == "Help"


def test_state_round_trip() -> None:
    # PDAnnotationText.java line 188-201.
    annotation = PDAnnotationText()
    assert annotation.get_state() is None
    annotation.set_state("Accepted")
    assert annotation.get_state() == "Accepted"


def test_state_model_round_trip() -> None:
    # PDAnnotationText.java line 208-221.
    annotation = PDAnnotationText()
    assert annotation.get_state_model() is None
    annotation.set_state_model(PDAnnotationText.STATE_MODEL_REVIEW)
    assert annotation.get_state_model() == "Review"
    annotation.set_state_model(PDAnnotationText.STATE_MODEL_MARKED)
    assert annotation.get_state_model() == "Marked"


def test_constants_match_upstream() -> None:
    # PDAnnotationText.java lines 41-121.
    assert PDAnnotationText.SUB_TYPE == "Text"
    assert PDAnnotationText.NAME_COMMENT == "Comment"
    assert PDAnnotationText.NAME_KEY == "Key"
    assert PDAnnotationText.NAME_NOTE == "Note"
    assert PDAnnotationText.NAME_HELP == "Help"
    assert PDAnnotationText.NAME_NEW_PARAGRAPH == "NewParagraph"
    assert PDAnnotationText.NAME_PARAGRAPH == "Paragraph"
    assert PDAnnotationText.NAME_INSERT == "Insert"
    assert PDAnnotationText.NAME_CIRCLE == "Circle"
    assert PDAnnotationText.NAME_CROSS == "Cross"
    assert PDAnnotationText.NAME_STAR == "Star"
    assert PDAnnotationText.NAME_CHECK == "Check"
    assert PDAnnotationText.NAME_RIGHT_ARROW == "RightArrow"
    assert PDAnnotationText.NAME_RIGHT_POINTER == "RightPointer"
    assert PDAnnotationText.NAME_UP_ARROW == "UpArrow"
    assert PDAnnotationText.NAME_UP_LEFT_ARROW == "UpLeftArrow"
    assert PDAnnotationText.NAME_CROSS_HAIRS == "CrossHairs"


def test_construct_appearances_default_is_noop() -> None:
    # PDAnnotationText.java line 234-237: with no custom handler the call
    # delegates to PDTextAppearanceHandler. That handler is not ported, so
    # the default path is a no-op via the base class — verified here so a
    # future port doesn't silently change call-site behaviour.
    annotation = PDAnnotationText()
    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None


def test_construct_appearances_invokes_custom_handler() -> None:
    # PDAnnotationText.java line 248-250: custom handler delegation.
    annotation = PDAnnotationText()

    class _RecordingHandler:
        def __init__(self) -> None:
            self.called = 0

        def generate_appearance_streams(self) -> None:
            self.called += 1

    handler = _RecordingHandler()
    annotation.set_custom_appearance_handler(handler)
    assert annotation.get_custom_appearance_handler() is handler

    annotation.construct_appearances()
    assert handler.called == 1
    annotation.construct_appearances(None)
    assert handler.called == 2


def test_clearing_custom_handler_restores_default_path() -> None:
    annotation = PDAnnotationText()

    class _Handler:
        def generate_appearance_streams(self) -> None:
            raise AssertionError("default path expected after clear")

    annotation.set_custom_appearance_handler(_Handler())
    annotation.set_custom_appearance_handler(None)
    assert annotation.get_custom_appearance_handler() is None
    assert annotation.construct_appearances() is None
