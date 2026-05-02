from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDAction, PDActionRichMediaExecute

_S: COSName = COSName.get_pdf_name("S")
_TA: COSName = COSName.get_pdf_name("TA")
_TI: COSName = COSName.get_pdf_name("TI")
_CMD: COSName = COSName.get_pdf_name("CMD")
_N: COSName = COSName.get_pdf_name("N")
_A: COSName = COSName.get_pdf_name("A")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


def test_default_constructor_sets_subtype_and_type() -> None:
    """A default-constructed action carries ``/Type /Action`` and
    ``/S /RichMediaExecute`` per ISO 32000-2 §13.6.4."""
    action = PDActionRichMediaExecute()
    cos = action.get_cos_object()

    assert cos.get_name(_TYPE) == "Action"
    assert cos.get_name(_S) == "RichMediaExecute"
    assert action.get_sub_type() == "RichMediaExecute"
    assert PDActionRichMediaExecute.SUB_TYPE == "RichMediaExecute"


def test_wrapping_existing_dictionary_preserves_entries() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "RichMediaExecute")
    ta = COSDictionary()
    raw.set_item(_TA, ta)

    action = PDActionRichMediaExecute(raw)
    assert action.get_cos_object() is raw
    assert action.get_target_annotation() is ta


def test_target_annotation_round_trip() -> None:
    action = PDActionRichMediaExecute()
    assert action.get_target_annotation() is None

    ta = COSDictionary()
    action.set_target_annotation(ta)
    assert action.get_target_annotation() is ta

    action.set_target_annotation(None)
    assert action.get_target_annotation() is None
    assert action.get_cos_object().get_dictionary_object(_TA) is None


def test_target_instance_round_trip() -> None:
    action = PDActionRichMediaExecute()
    assert action.get_target_instance() is None

    ti = COSDictionary()
    action.set_target_instance(ti)
    assert action.get_target_instance() is ti

    action.set_target_instance(None)
    assert action.get_target_instance() is None


def test_command_round_trip() -> None:
    action = PDActionRichMediaExecute()
    assert action.get_command() is None

    cmd = COSDictionary()
    cmd.set_string(_N, "play")
    action.set_command(cmd)
    assert action.get_command() is cmd
    assert action.get_command_name() == "play"

    action.set_command(None)
    assert action.get_command() is None
    assert action.get_command_name() is None


def test_set_command_name_creates_command_dict_when_absent() -> None:
    """Setting a command name on a fresh action auto-creates ``/CMD``."""
    action = PDActionRichMediaExecute()
    assert action.get_command() is None

    action.set_command_name("rewind")
    cmd = action.get_command()
    assert cmd is not None
    assert cmd.get_string(_N) == "rewind"
    assert action.get_command_name() == "rewind"


def test_set_command_name_none_keeps_dict_but_clears_name() -> None:
    """Passing ``None`` to ``set_command_name`` clears /N but does not
    remove an existing /CMD dictionary."""
    action = PDActionRichMediaExecute()
    action.set_command_name("play")
    cmd_before = action.get_command()
    assert cmd_before is not None

    action.set_command_name(None)
    # /CMD still exists; /N entry is cleared.
    assert action.get_command() is cmd_before
    assert cmd_before.get_string(_N) is None


def test_set_command_name_none_with_no_command_is_noop() -> None:
    """Passing ``None`` when /CMD is absent is a no-op (does not create)."""
    action = PDActionRichMediaExecute()
    action.set_command_name(None)
    assert action.get_command() is None


def test_set_command_arguments_creates_command_dict_when_absent() -> None:
    action = PDActionRichMediaExecute()
    args = COSArray([COSInteger.get(1), COSString("foo")])
    action.set_command_arguments(args)

    cmd = action.get_command()
    assert cmd is not None
    assert cmd.get_dictionary_object(_A) is args
    assert action.get_command_arguments() is args


def test_set_command_arguments_none_removes_entry_but_keeps_dict() -> None:
    action = PDActionRichMediaExecute()
    action.set_command_arguments(COSString("x"))
    cmd = action.get_command()
    assert cmd is not None
    assert action.get_command_arguments() is not None

    action.set_command_arguments(None)
    # /CMD survives; /A is gone.
    assert action.get_command() is cmd
    assert action.get_command_arguments() is None
    assert cmd.get_dictionary_object(_A) is None


def test_set_command_arguments_none_with_no_command_is_noop() -> None:
    action = PDActionRichMediaExecute()
    action.set_command_arguments(None)
    assert action.get_command() is None


def test_command_arguments_get_when_no_command_returns_none() -> None:
    action = PDActionRichMediaExecute()
    assert action.get_command_arguments() is None
    assert action.get_command_name() is None


def test_factory_dispatch_returns_typed_instance() -> None:
    """``PDAction.create`` must hand back a ``PDActionRichMediaExecute``
    for an ``S=RichMediaExecute`` dictionary."""
    raw = COSDictionary()
    raw.set_name(_S, "RichMediaExecute")

    result = PDAction.create(raw)
    assert isinstance(result, PDActionRichMediaExecute)
    assert result.get_cos_object() is raw


def test_ta_alias_round_trip() -> None:
    """``get_ta``/``set_ta`` are raw key-name aliases of the
    target-annotation accessors."""
    action = PDActionRichMediaExecute()
    ta = COSDictionary()
    action.set_ta(ta)
    assert action.get_ta() is ta
    assert action.get_target_annotation() is ta

    action.set_ta(None)
    assert action.get_ta() is None
    assert action.get_target_annotation() is None


def test_ti_alias_round_trip() -> None:
    """``get_ti``/``set_ti`` are raw key-name aliases of the
    target-instance accessors."""
    action = PDActionRichMediaExecute()
    ti = COSDictionary()
    action.set_ti(ti)
    assert action.get_ti() is ti
    assert action.get_target_instance() is ti

    action.set_ti(None)
    assert action.get_ti() is None


def test_cmd_alias_round_trip() -> None:
    """``get_cmd``/``set_cmd`` are raw key-name aliases of the
    command-dictionary accessors."""
    action = PDActionRichMediaExecute()
    cmd = COSDictionary()
    cmd.set_string(_N, "stop")
    action.set_cmd(cmd)
    assert action.get_cmd() is cmd
    assert action.get_command() is cmd
    assert action.get_command_name() == "stop"

    action.set_cmd(None)
    assert action.get_cmd() is None
    assert action.get_command() is None
