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
