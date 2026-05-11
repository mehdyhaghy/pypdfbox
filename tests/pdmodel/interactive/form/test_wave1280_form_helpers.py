"""Hand-written tests for Wave 1280 AcroForm helper classes ported from
``org.apache.pdfbox.pdmodel.interactive.form`` upstream sources."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.form.appearance_generator_helper import (
    AppearanceGeneratorHelper,
)
from pypdfbox.pdmodel.interactive.form.appearance_style import AppearanceStyle
from pypdfbox.pdmodel.interactive.form.builder import Builder
from pypdfbox.pdmodel.interactive.form.field_iterator import FieldIterator
from pypdfbox.pdmodel.interactive.form.field_utils import FieldUtils
from pypdfbox.pdmodel.interactive.form.key_value import KeyValue
from pypdfbox.pdmodel.interactive.form.paragraph import Line, Paragraph
from pypdfbox.pdmodel.interactive.form.plain_text import PlainText
from pypdfbox.pdmodel.interactive.form.plain_text_formatter import (
    PlainTextFormatter,
)
from pypdfbox.pdmodel.interactive.form.scripting_handler import (
    ScriptingHandler,
)
from pypdfbox.pdmodel.interactive.form.text_align import TextAlign
from pypdfbox.pdmodel.interactive.form.word import Word

# ---------- AppearanceStyle ----------


def test_appearance_style_defaults_to_size_12_leading_14_4() -> None:
    style = AppearanceStyle()
    assert style.get_font() is None
    assert style.get_font_size() == 12.0
    assert style.get_leading() == 14.4


def test_appearance_style_set_font_size_recomputes_leading() -> None:
    style = AppearanceStyle()
    style.set_font_size(10.0)
    assert style.get_font_size() == 10.0
    assert style.get_leading() == pytest.approx(12.0)


def test_appearance_style_set_leading_does_not_change_font_size() -> None:
    style = AppearanceStyle()
    style.set_leading(20.0)
    assert style.get_leading() == 20.0
    assert style.get_font_size() == 12.0


def test_appearance_style_set_font_stores_reference() -> None:
    style = AppearanceStyle()
    font = object()
    style.set_font(font)  # type: ignore[arg-type]
    assert style.get_font() is font


# ---------- KeyValue ----------


def test_key_value_holds_key_and_value() -> None:
    kv = KeyValue("k", "v")
    assert kv.get_key() == "k"
    assert kv.get_value() == "v"


def test_key_value_str_representation_matches_upstream() -> None:
    assert str(KeyValue("foo", "bar")) == "(foo, bar)"
    assert repr(KeyValue("foo", "bar")) == "(foo, bar)"


def test_key_value_equality_and_hash() -> None:
    assert KeyValue("a", "b") == KeyValue("a", "b")
    assert KeyValue("a", "b") != KeyValue("a", "c")
    assert hash(KeyValue("a", "b")) == hash(KeyValue("a", "b"))


# ---------- FieldUtils ----------


def test_field_utils_is_not_instantiable() -> None:
    with pytest.raises(TypeError):
        FieldUtils()


def test_field_utils_to_key_value_list_pairs_elements() -> None:
    pairs = FieldUtils.to_key_value_list(["k1", "k2"], ["v1", "v2"])
    assert pairs == [KeyValue("k1", "v1"), KeyValue("k2", "v2")]


def test_field_utils_sort_by_value_sorts_in_place() -> None:
    pairs = [KeyValue("k1", "z"), KeyValue("k2", "a")]
    FieldUtils.sort_by_value(pairs)
    assert [kv.get_value() for kv in pairs] == ["a", "z"]


def test_field_utils_sort_by_key_sorts_in_place() -> None:
    pairs = [KeyValue("z", "v1"), KeyValue("a", "v2")]
    FieldUtils.sort_by_key(pairs)
    assert [kv.get_key() for kv in pairs] == ["a", "z"]


def test_field_utils_get_pairable_items_rejects_invalid_index() -> None:
    with pytest.raises(ValueError, match="0 and 1"):
        FieldUtils.get_pairable_items(COSArray(), 2)
    with pytest.raises(ValueError, match="0 and 1"):
        FieldUtils.get_pairable_items(COSArray(), -1)


def test_field_utils_get_pairable_items_handles_single_string() -> None:
    assert FieldUtils.get_pairable_items(COSString("foo"), 0) == ["foo"]


def test_field_utils_get_pairable_items_handles_flat_string_array() -> None:
    arr = COSArray()
    arr.add(COSString("a"))
    arr.add(COSString("b"))
    assert FieldUtils.get_pairable_items(arr, 0) == ["a", "b"]


def test_field_utils_get_pairable_items_handles_two_element_arrays() -> None:
    outer = COSArray()
    pair1 = COSArray()
    pair1.add(COSString("export1"))
    pair1.add(COSString("display1"))
    outer.add(pair1)
    pair2 = COSArray()
    pair2.add(COSString("export2"))
    pair2.add(COSString("display2"))
    outer.add(pair2)
    assert FieldUtils.get_pairable_items(outer, 0) == ["export1", "export2"]
    assert FieldUtils.get_pairable_items(outer, 1) == ["display1", "display2"]


def test_field_utils_get_pairable_items_returns_empty_for_non_string_non_array() -> (
    None
):
    assert FieldUtils.get_pairable_items(COSName("name"), 0) == []
    assert FieldUtils.get_pairable_items(None, 0) == []


# ---------- ScriptingHandler ----------


def test_scripting_handler_is_abstract() -> None:
    with pytest.raises(TypeError):
        ScriptingHandler()  # type: ignore[abstract]


def test_scripting_handler_concrete_subclass_can_be_instantiated() -> None:
    class _Stub(ScriptingHandler):
        def keyboard(self, action, value):  # noqa: ANN001
            return value

        def format(self, action, value):  # noqa: ANN001
            return value

        def validate(self, action, value):  # noqa: ANN001
            return True

        def calculate(self, action, value):  # noqa: ANN001
            return value

    h = _Stub()
    assert h.keyboard(None, "x") == "x"
    assert h.format(None, "x") == "x"
    assert h.validate(None, "x") is True
    assert h.calculate(None, "x") == "x"


# ---------- TextAlign ----------


def test_text_align_values_match_pdf_quadding_codes() -> None:
    assert TextAlign.LEFT.get_text_align() == 0
    assert TextAlign.CENTER.get_text_align() == 1
    assert TextAlign.RIGHT.get_text_align() == 2
    assert TextAlign.JUSTIFY.get_text_align() == 4


def test_text_align_value_of_resolves_int_code() -> None:
    assert TextAlign.value_of(0) is TextAlign.LEFT
    assert TextAlign.value_of(1) is TextAlign.CENTER
    assert TextAlign.value_of(2) is TextAlign.RIGHT
    assert TextAlign.value_of(4) is TextAlign.JUSTIFY


def test_text_align_value_of_returns_left_for_unknown_code() -> None:
    assert TextAlign.value_of(99) is TextAlign.LEFT
    assert TextAlign.value_of(-1) is TextAlign.LEFT


# ---------- Word ----------


def test_word_holds_text_and_attributes() -> None:
    word = Word("hello")
    assert word.get_text() == "hello"
    assert word.get_attributes() is None
    word.set_attributes({"WIDTH": 1.5})
    assert word.get_attributes() == {"WIDTH": 1.5}


# ---------- Paragraph / Line ----------


class _StubFont:
    """Minimal font stub returning per-character glyph widths."""

    def __init__(self, char_width: float = 500.0) -> None:
        self._char_width = char_width

    def get_string_width(self, text: str) -> float:
        return self._char_width * len(text)


def test_paragraph_get_text_round_trips() -> None:
    para = Paragraph("hello world")
    assert para.get_text() == "hello world"


def test_paragraph_get_lines_returns_empty_for_non_positive_width() -> None:
    para = Paragraph("hello")
    assert para.get_lines(_StubFont(), 12.0, 0.0) == []
    assert para.get_lines(_StubFont(), 12.0, -5.0) == []


def test_paragraph_get_lines_returns_at_least_one_line() -> None:
    para = Paragraph("hello world")
    lines = para.get_lines(_StubFont(), 12.0, 1000.0)
    assert len(lines) >= 1
    assert any("hello" in w.get_text() for line in lines for w in line.get_words())


def test_line_calculate_width_handles_empty_words() -> None:
    line = Line()
    assert line.calculate_width(_StubFont(), 12.0) == 0.0


def test_line_add_word_appends_to_words_list() -> None:
    line = Line()
    word = Word("hi")
    word.set_attributes({"WIDTH": 5.0})
    line.add_word(word)
    assert line.get_words() == [word]


def test_line_set_width_round_trips() -> None:
    line = Line()
    line.set_width(42.0)
    assert line.get_width() == 42.0


# ---------- PlainText ----------


def test_plain_text_from_empty_string_yields_single_empty_paragraph() -> None:
    pt = PlainText("")
    assert len(pt.get_paragraphs()) == 1
    assert pt.get_paragraphs()[0].get_text() == ""


def test_plain_text_splits_on_unicode_linebreaks() -> None:
    pt = PlainText("a\nb\r\nc d")
    texts = [p.get_text() for p in pt.get_paragraphs()]
    assert texts == ["a", "b", "c", "d"]


def test_plain_text_empty_paragraph_becomes_single_space() -> None:
    pt = PlainText("a\n\nb")
    texts = [p.get_text() for p in pt.get_paragraphs()]
    assert texts == ["a", " ", "b"]


def test_plain_text_tabs_replaced_with_space() -> None:
    pt = PlainText("a\tb")
    assert pt.get_paragraphs()[0].get_text() == "a b"


def test_plain_text_from_list_creates_one_paragraph_per_entry() -> None:
    pt = PlainText(["one", "two", "three"])
    assert [p.get_text() for p in pt.get_paragraphs()] == [
        "one",
        "two",
        "three",
    ]


def test_plain_text_inner_classes_exposed_for_upstream_parity() -> None:
    assert PlainText.Paragraph is Paragraph
    assert PlainText.Line is Line
    assert PlainText.Word is Word


# ---------- Builder + PlainTextFormatter ----------


class _FakeContents:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def new_line_at_offset(self, dx: float, dy: float) -> None:
        self.calls.append(("new_line_at_offset", (dx, dy)))

    def show_text(self, text: str) -> None:
        self.calls.append(("show_text", (text,)))


def test_builder_round_trips_all_setters() -> None:
    contents = _FakeContents()
    style = AppearanceStyle()
    text = PlainText("hello")
    b = (
        Builder(contents)
        .style(style)
        .wrap_lines(True)
        .width(100.0)
        .text(text)
        .text_align(TextAlign.RIGHT)
        .initial_offset(5.0, 6.0)
    )
    assert b._contents is contents
    assert b._appearance_style is style
    assert b._text_content is text
    assert b._wrap_lines is True
    assert b._width == 100.0
    assert b._text_alignment is TextAlign.RIGHT
    assert b._horizontal_offset == 5.0
    assert b._vertical_offset == 6.0


def test_builder_text_align_accepts_int_code() -> None:
    b = Builder(_FakeContents()).text_align(2)
    assert b._text_alignment is TextAlign.RIGHT


def test_builder_build_returns_plain_text_formatter() -> None:
    formatter = Builder(_FakeContents()).build()
    assert isinstance(formatter, PlainTextFormatter)


def test_plain_text_formatter_emits_nothing_without_text() -> None:
    contents = _FakeContents()
    formatter = (
        Builder(contents).style(AppearanceStyle()).build()
    )
    formatter.format()
    assert contents.calls == []


def test_plain_text_formatter_emits_show_text_for_single_line() -> None:
    contents = _FakeContents()
    style = AppearanceStyle()
    style.set_font(_StubFont(500.0))
    style.set_font_size(12.0)
    formatter = (
        Builder(contents)
        .style(style)
        .text(PlainText("hi"))
        .width(1000.0)
        .text_align(TextAlign.LEFT)
        .build()
    )
    formatter.format()
    assert any(c[0] == "show_text" for c in contents.calls)


def test_plain_text_formatter_exposes_nested_classes_for_parity() -> None:
    assert PlainTextFormatter.Builder is Builder
    assert PlainTextFormatter.TextAlign is TextAlign


# ---------- FieldIterator ----------


def test_field_iterator_subclasses_underlying_iterator() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_field_tree import _FieldIterator

    assert issubclass(FieldIterator, _FieldIterator)


def test_field_iterator_walks_empty_acroform() -> None:
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    doc = PDDocument()
    form = PDAcroForm(doc)
    it = FieldIterator(form)
    assert it.has_next() is False
    with pytest.raises(StopIteration):
        next(it)


# ---------- AppearanceGeneratorHelper ----------


def test_appearance_generator_helper_exposes_upstream_constants() -> None:
    assert AppearanceGeneratorHelper.FONTSCALE == 1000
    assert AppearanceGeneratorHelper.DEFAULT_FONT_SIZE == 12.0
    assert AppearanceGeneratorHelper.MINIMUM_FONT_SIZE == 4.0
    assert AppearanceGeneratorHelper.DEFAULT_PADDING == 0.5
    assert AppearanceGeneratorHelper.HIGHLIGHT_COLOR == (
        153.0 / 255.0,
        193.0 / 255.0,
        215.0 / 255.0,
    )


def test_appearance_generator_helper_get_formatted_value_collapses_newlines() -> (
    None
):
    assert (
        AppearanceGeneratorHelper.get_formatted_value("a\nb\r\nc")
        == "a b c"
    )
    assert AppearanceGeneratorHelper.get_formatted_value("plain") == "plain"


def test_appearance_generator_helper_binds_to_field() -> None:
    class _StubField:
        def get_default_appearance_string(self):
            return None

    field = _StubField()
    helper = AppearanceGeneratorHelper(field)  # type: ignore[arg-type]
    assert helper.get_field() is field
    assert helper.get_value() == ""
