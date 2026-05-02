from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action import (
    PDAction,
    PDActionGoTo,
    PDActionHide,
    PDActionImportData,
    PDActionJavaScript,
    PDActionLaunch,
    PDActionNamed,
    PDActionRemoteGoTo,
    PDActionResetForm,
    PDActionSubmitForm,
    PDActionThread,
    PDActionUnknown,
    PDActionURI,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)


def test_action_factory_dispatches_common_subtypes() -> None:
    expected = {
        "GoTo": PDActionGoTo,
        "URI": PDActionURI,
        "Named": PDActionNamed,
        "Launch": PDActionLaunch,
        "GoToR": PDActionRemoteGoTo,
        "JavaScript": PDActionJavaScript,
        "SubmitForm": PDActionSubmitForm,
        "ResetForm": PDActionResetForm,
        "ImportData": PDActionImportData,
        "Hide": PDActionHide,
        "Thread": PDActionThread,
    }
    for sub_type, cls in expected.items():
        raw = COSDictionary()
        raw.set_name(COSName.get_pdf_name("S"), sub_type)
        assert isinstance(PDAction.create(raw), cls)


def test_action_factory_preserves_unknown_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "TotallyMadeUpSubtype")
    action = PDAction.create(raw)
    assert isinstance(action, PDActionUnknown)
    assert action.get_cos_object() is raw


def test_goto_destination_round_trip() -> None:
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    # GoTo (local) destinations require a page dictionary at index 0;
    # ``set_page_number`` is for remote-destination targets only.
    page = COSDictionary()
    page.set_name(COSName.TYPE, "Page")
    dest.set_page(page)
    action.set_destination(dest)

    resolved = action.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page() is page


def test_uri_named_launch_remote_and_javascript_accessors() -> None:
    uri = PDActionURI()
    uri.set_uri("https://example.test")
    assert uri.get_uri() == "https://example.test"

    named = PDActionNamed()
    named.set_n("NextPage")
    assert named.get_n() == "NextPage"

    launch = PDActionLaunch()
    launch_fs = PDSimpleFileSpecification()
    launch_fs.set_file("open-me.pdf")
    launch.set_file(launch_fs)
    resolved_launch_fs = launch.get_file()
    assert resolved_launch_fs is not None
    assert resolved_launch_fs.get_file() == "open-me.pdf"

    remote = PDActionRemoteGoTo()
    remote.set_file("other.pdf")
    assert remote.get_file() == "other.pdf"

    js = PDActionJavaScript()
    js.set_action("app.alert('x')")
    assert js.get_action() == "app.alert('x')"


def test_submit_reset_import_hide_and_thread_accessors_round_trip_cos() -> None:
    fields = COSArray([COSString("name"), COSString("email")])

    submit = PDActionSubmitForm()
    submit.set_file("submit.fdf")
    submit.set_fields(fields)
    submit.set_flags(4)
    # PDActionSubmitForm.get_file() now returns a typed PDFileSpecification
    # (mirrors upstream PDFBox); the raw COS form is reachable on the dict.
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
        PDSimpleFileSpecification,
    )
    from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
        PDComplexFileSpecification,
    )
    assert isinstance(submit.get_file(), PDSimpleFileSpecification)
    assert submit.get_url() == "submit.fdf"
    assert submit.get_cos_fields() is fields
    assert submit.get_flags() == 4

    file_spec = COSDictionary()
    submit.set_file(file_spec)
    fs = submit.get_file()
    assert isinstance(fs, PDComplexFileSpecification)
    assert fs.get_cos_object() is file_spec

    reset = PDActionResetForm()
    reset.set_fields(fields)
    reset.set_flags(1)
    assert reset.get_fields() is fields
    assert reset.get_flags() == 1

    import_data = PDActionImportData()
    import_file = COSDictionary()
    import_data.set_file(import_file)
    # PDActionImportData.get_file() returns a typed PDFileSpecification
    # (mirrors upstream PDFBox); the raw COSDictionary is reachable via
    # get_cos_object().
    import_fs = import_data.get_file()
    assert import_fs is not None
    assert import_fs.get_cos_object() is import_file

    hide = PDActionHide()
    target = COSString("Widget1")
    hide.set_t(target)
    assert hide.get_t() is target
    assert hide.get_h() is True
    hide.set_h(False)
    assert hide.get_h() is False

    thread = PDActionThread()
    destination = COSInteger.get(2)
    bead = COSDictionary()
    thread.set_file("threads.pdf")
    thread.set_d(destination)
    thread.set_b(bead)
    # PDActionThread.get_file() returns a typed PDFileSpecification
    # (mirrors upstream PDFBox).
    thread_fs = thread.get_file()
    assert isinstance(thread_fs, PDSimpleFileSpecification)
    assert thread_fs.get_file() == "threads.pdf"
    assert thread.get_d() is destination
    assert thread.get_b() is bead

    submit.set_fields(None)
    import_data.set_file(None)
    hide.set_t(None)
    thread.set_b(None)
    assert submit.get_cos_fields() is None
    assert import_data.get_file() is None
    assert hide.get_t() is None
    assert thread.get_b() is None


def test_pd_action_type_constant_and_default_type_entry() -> None:
    # Class-level TYPE constant mirrors upstream public static final
    # PDAction.TYPE = "Action".
    assert PDAction.TYPE == "Action"

    action = PDActionGoTo()
    # The default constructor stamps /Type Action on the dictionary.
    assert action.get_type() == "Action"
    assert action.get_cos_object().get_name(COSName.TYPE) == "Action"


def test_pd_action_set_type_round_trip_and_preserves_existing() -> None:
    # set_type stores into /Type as a name. Behavior mirrors the protected
    # upstream setType (exposed as public here since Python lacks Java
    # visibility modifiers).
    action = PDActionGoTo()
    action.set_type("CustomType")
    assert action.get_type() == "CustomType"

    # An action wrapped around an existing dictionary that already
    # carries /Type retains that value (constructor only stamps when
    # missing).
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Preset")
    raw.set_name(COSName.get_pdf_name("S"), "URI")
    wrapped = PDActionURI(raw)
    assert wrapped.get_type() == "Preset"


def test_pd_action_get_next_returns_none_when_absent() -> None:
    action = PDActionGoTo()
    assert action.get_next() is None


def test_pd_action_set_next_with_list_round_trip() -> None:
    action = PDActionGoTo()
    follow_up_a = PDActionURI()
    follow_up_a.set_uri("https://a.example")
    follow_up_b = PDActionNamed()
    follow_up_b.set_n("NextPage")

    action.set_next([follow_up_a, follow_up_b])

    # Stored as a COSArray of action dictionaries.
    raw_next = action.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Next")
    )
    assert isinstance(raw_next, COSArray)
    assert raw_next.size() == 2

    next_actions = action.get_next()
    assert next_actions is not None
    assert len(next_actions) == 2
    assert isinstance(next_actions[0], PDActionURI)
    assert next_actions[0].get_uri() == "https://a.example"
    assert isinstance(next_actions[1], PDActionNamed)
    assert next_actions[1].get_n() == "NextPage"


def test_pd_action_get_next_handles_single_dictionary_form() -> None:
    # PDF 32000-1 §12.6.2: /Next may be either a single action dictionary
    # or an array. The single-dictionary form must be handled.
    parent = PDActionGoTo()
    nested = COSDictionary()
    nested.set_name(COSName.get_pdf_name("S"), "URI")
    nested.set_string(COSName.get_pdf_name("URI"), "https://single.example")
    parent.get_cos_object().set_item(COSName.get_pdf_name("Next"), nested)

    next_actions = parent.get_next()
    assert next_actions is not None
    assert len(next_actions) == 1
    assert isinstance(next_actions[0], PDActionURI)
    assert next_actions[0].get_uri() == "https://single.example"


def test_pd_action_set_next_with_none_clears_entry() -> None:
    action = PDActionGoTo()
    action.set_next([PDActionURI()])
    assert action.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Next")
    ) is not None
    action.set_next(None)
    assert action.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Next")
    ) is None
    assert action.get_next() is None
