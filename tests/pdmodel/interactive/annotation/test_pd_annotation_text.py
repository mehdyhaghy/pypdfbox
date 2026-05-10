from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText


def test_default_constructor_sets_text_subtype() -> None:
    ann = PDAnnotationText()
    assert ann.get_subtype() == "Text"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_subtype_constant() -> None:
    assert PDAnnotationText.SUB_TYPE == "Text"


def test_open_default_false() -> None:
    ann = PDAnnotationText()
    assert ann.get_open() is False


def test_open_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_open(True)
    assert ann.get_open() is True
    ann.set_open(False)
    assert ann.get_open() is False


def test_snake_case_accessors_round_trip() -> None:
    ann = PDAnnotationText()

    ann.set_open(True)
    assert ann.get_open() is True

    ann.set_name(PDAnnotationText.NAME_COMMENT)
    assert ann.get_name() == PDAnnotationText.NAME_COMMENT
    ann.set_name(None)
    assert ann.get_name() == PDAnnotationText.NAME_NOTE

    ann.set_state(PDAnnotationText.STATE_ACCEPTED)
    assert ann.get_state() == PDAnnotationText.STATE_ACCEPTED
    ann.set_state(None)
    assert ann.get_state() is None

    ann.set_state_model(PDAnnotationText.STATE_MODEL_REVIEW)
    assert ann.get_state_model() == PDAnnotationText.STATE_MODEL_REVIEW
    ann.set_state_model(None)
    assert ann.get_state_model() is None


def test_name_default_note() -> None:
    ann = PDAnnotationText()
    assert ann.get_name() == PDAnnotationText.NAME_NOTE


def test_name_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_name(PDAnnotationText.NAME_COMMENT)
    assert ann.get_name() == "Comment"
    ann.set_name(PDAnnotationText.NAME_HELP)
    assert ann.get_name() == "Help"


def test_name_clear_returns_default() -> None:
    ann = PDAnnotationText()
    ann.set_name(PDAnnotationText.NAME_KEY)
    ann.set_name(None)
    assert ann.get_name() == PDAnnotationText.NAME_NOTE


def test_state_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_state("Accepted")
    assert ann.get_state() == "Accepted"


def test_state_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_state() is None


def test_state_clear() -> None:
    ann = PDAnnotationText()
    ann.set_state("Rejected")
    ann.set_state(None)
    assert ann.get_state() is None


def test_state_model_round_trip() -> None:
    ann = PDAnnotationText()
    ann.set_state_model("Review")
    assert ann.get_state_model() == "Review"
    ann.set_state_model("Marked")
    assert ann.get_state_model() == "Marked"


def test_state_model_default_none() -> None:
    ann = PDAnnotationText()
    assert ann.get_state_model() is None


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    ann = PDAnnotationText(d)
    assert ann.get_subtype() == "Text"


def test_icon_constants_exist() -> None:
    # Spot-check the catalog matches upstream.
    expected = {
        "NAME_COMMENT": "Comment",
        "NAME_KEY": "Key",
        "NAME_NOTE": "Note",
        "NAME_HELP": "Help",
        "NAME_NEW_PARAGRAPH": "NewParagraph",
        "NAME_PARAGRAPH": "Paragraph",
        "NAME_INSERT": "Insert",
        "NAME_CIRCLE": "Circle",
        "NAME_CROSS": "Cross",
        "NAME_STAR": "Star",
        "NAME_CHECK": "Check",
        "NAME_RIGHT_ARROW": "RightArrow",
        "NAME_RIGHT_POINTER": "RightPointer",
        "NAME_UP_ARROW": "UpArrow",
        "NAME_UP_LEFT_ARROW": "UpLeftArrow",
        "NAME_CROSS_HAIRS": "CrossHairs",
    }
    for attr, value in expected.items():
        assert getattr(PDAnnotationText, attr) == value
