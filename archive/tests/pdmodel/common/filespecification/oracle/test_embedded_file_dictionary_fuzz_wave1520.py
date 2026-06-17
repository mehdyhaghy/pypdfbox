"""Malformed embedded-file/file-spec dictionary differential, wave 1520 D."""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from tests.oracle.harness import requires_oracle, run_probe_text

CASE_IDS = (
    "ef-0", "ef-n", "ef-z", "ef-iz", "ef-e", "ef-fd", "ef-fs", "ef-fi",
    "ef-all", "ef-bad", "p-0", "p-n", "p-z", "p-iz", "p-e", "p-i",
    "sz-i", "sz-f", "sz-w", "sz-s", "sz-n", "sz-ii", "sz-iz",
    "dt-v", "dt-p", "dt-np", "dt-z", "dt-bad", "dt-roll", "dt-n", "dt-i",
    "cs-s", "cs-n", "cs-i", "cs-z", "st-n", "st-s", "st-i", "st-z",
    "mac-v", "mac-i", "mac-n", "mac-bad", "mac-z",
)

EF = COSName.get_pdf_name("EF")
F = COSName.get_pdf_name("F")
UF = COSName.get_pdf_name("UF")
DOS = COSName.get_pdf_name("DOS")
MAC = COSName.get_pdf_name("Mac")
UNIX = COSName.get_pdf_name("Unix")
PARAMS = COSName.get_pdf_name("Params")
SIZE = COSName.get_pdf_name("Size")
CREATION_DATE = COSName.get_pdf_name("CreationDate")
MOD_DATE = COSName.get_pdf_name("ModDate")
CHECK_SUM = COSName.get_pdf_name("CheckSum")
SUBTYPE = COSName.get_pdf_name("Subtype")
CREATOR = COSName.get_pdf_name("Creator")
RES_FORK = COSName.get_pdf_name("ResFork")


def _indirect(value: object, number: int = 100) -> COSObject:
    return COSObject(number, resolved=value)


def _stream() -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("EmbeddedFile"))
    return stream


def _params(stream: COSStream) -> COSDictionary:
    values = COSDictionary()
    stream.set_item(PARAMS, values)
    return values


def _build(case_id: str) -> PDComplexFileSpecification:
    file_spec = COSDictionary()
    ef = COSDictionary()
    embedded = _stream()

    if case_id == "ef-0":
        return PDComplexFileSpecification(file_spec)
    if case_id == "ef-n":
        file_spec.set_item(EF, COSName.get_pdf_name("Wrong"))
        return PDComplexFileSpecification(file_spec)
    if case_id == "ef-z":
        file_spec.set_item(EF, COSNull.NULL)
        return PDComplexFileSpecification(file_spec)
    if case_id == "ef-iz":
        file_spec.set_item(EF, _indirect(None))
        return PDComplexFileSpecification(file_spec)
    if case_id == "ef-e":
        file_spec.set_item(EF, ef)
        return PDComplexFileSpecification(file_spec)
    if case_id == "ef-fd":
        ef.set_item(F, COSDictionary())
    elif case_id == "ef-fs":
        ef.set_item(F, embedded)
    elif case_id == "ef-fi":
        ef.set_item(F, _indirect(embedded))
    elif case_id == "ef-all":
        ef.set_item(F, _stream())
        ef.set_item(UF, _indirect(_stream(), 101))
        ef.set_item(DOS, _stream())
        ef.set_item(MAC, _indirect(_stream(), 102))
        ef.set_item(UNIX, _stream())
    elif case_id == "ef-bad":
        ef.set_item(F, COSName.get_pdf_name("Wrong"))
        ef.set_item(UF, COSNull.NULL)
        ef.set_item(DOS, _indirect(None))
        ef.set_item(MAC, COSDictionary())
        ef.set_item(UNIX, COSInteger.ONE)
    else:
        ef.set_item(F, embedded)
        if case_id == "p-0":
            pass
        elif case_id == "p-n":
            embedded.set_item(PARAMS, COSName.get_pdf_name("Wrong"))
        elif case_id == "p-z":
            embedded.set_item(PARAMS, COSNull.NULL)
        elif case_id == "p-iz":
            embedded.set_item(PARAMS, _indirect(None))
        elif case_id == "p-e":
            _params(embedded)
        elif case_id == "p-i":
            embedded.set_item(PARAMS, _indirect(COSDictionary()))
        elif case_id == "sz-i":
            _params(embedded).set_item(SIZE, COSInteger.get(42))
        elif case_id == "sz-f":
            _params(embedded).set_item(SIZE, COSFloat(3.75))
        elif case_id == "sz-w":
            _params(embedded).set_item(SIZE, COSInteger.get(4_294_967_297))
        elif case_id == "sz-s":
            _params(embedded).set_item(SIZE, COSString("42"))
        elif case_id == "sz-n":
            _params(embedded).set_item(SIZE, COSName.get_pdf_name("FortyTwo"))
        elif case_id == "sz-ii":
            _params(embedded).set_item(SIZE, _indirect(COSInteger.get(42)))
        elif case_id == "sz-iz":
            _params(embedded).set_item(SIZE, _indirect(None))
        elif case_id == "dt-v":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSString("D:20240102030405+06'30'"))
            values.set_item(MOD_DATE, COSString("D:20231231235958-04'15'"))
        elif case_id == "dt-p":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSString("D:2024"))
            values.set_item(MOD_DATE, COSString("D:202402"))
        elif case_id == "dt-np":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSString("20240102"))
            values.set_item(MOD_DATE, COSString("20240102030405Z"))
        elif case_id == "dt-z":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSString("D:20240102030405Z"))
            values.set_item(MOD_DATE, COSNull.NULL)
        elif case_id == "dt-bad":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSString("garbage"))
            values.set_item(MOD_DATE, COSString("D:99999999"))
        elif case_id == "dt-roll":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSString("D:20241301000000"))
            values.set_item(MOD_DATE, COSString("D:20240230000000"))
        elif case_id == "dt-n":
            values = _params(embedded)
            values.set_item(CREATION_DATE, COSName.get_pdf_name("D:20240101"))
            values.set_item(MOD_DATE, COSInteger.ONE)
        elif case_id == "dt-i":
            values = _params(embedded)
            values.set_item(CREATION_DATE, _indirect(COSString("D:20240102")))
            values.set_item(MOD_DATE, _indirect(COSString("D:20240103"), 101))
        elif case_id == "cs-s":
            _params(embedded).set_item(CHECK_SUM, COSString("abc123"))
        elif case_id == "cs-n":
            _params(embedded).set_item(CHECK_SUM, COSName.get_pdf_name("abc123"))
        elif case_id == "cs-i":
            _params(embedded).set_item(CHECK_SUM, _indirect(COSString("abc123")))
        elif case_id == "cs-z":
            _params(embedded).set_item(CHECK_SUM, COSNull.NULL)
        elif case_id == "st-n":
            embedded.set_item(SUBTYPE, COSName.get_pdf_name("application/pdf"))
        elif case_id == "st-s":
            embedded.set_item(SUBTYPE, COSString("text/plain"))
        elif case_id == "st-i":
            embedded.set_item(SUBTYPE, _indirect(COSString("image/png")))
        elif case_id == "st-z":
            embedded.set_item(SUBTYPE, COSNull.NULL)
        elif case_id in {"mac-v", "mac-i", "mac-n"}:
            values = COSDictionary()
            if case_id == "mac-v":
                values.set_item(SUBTYPE, COSString("TEXT"))
                values.set_item(CREATOR, COSString("ttxt"))
                values.set_item(RES_FORK, COSString("fork"))
                _params(embedded).set_item(MAC, values)
            elif case_id == "mac-i":
                values.set_item(SUBTYPE, _indirect(COSString("TEXT")))
                values.set_item(CREATOR, _indirect(COSString("ttxt"), 101))
                values.set_item(RES_FORK, _indirect(COSString("fork"), 102))
                _params(embedded).set_item(MAC, _indirect(values, 103))
            else:
                values.set_item(SUBTYPE, COSName.get_pdf_name("TEXT"))
                values.set_item(CREATOR, COSName.get_pdf_name("ttxt"))
                values.set_item(RES_FORK, COSName.get_pdf_name("fork"))
                _params(embedded).set_item(MAC, values)
        elif case_id == "mac-bad":
            _params(embedded).set_item(MAC, COSInteger.ONE)
        elif case_id == "mac-z":
            _params(embedded).set_item(MAC, _indirect(None))
        else:
            raise AssertionError(case_id)

    file_spec.set_item(EF, ef)
    return PDComplexFileSpecification(file_spec)


def _value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bytes):
        return value.decode("latin-1")
    return str(value)


def _call(function: object) -> str:
    try:
        return _value(function())
    except Exception as exception:
        return f"ERR:{type(exception).__name__}"


def _date(function: object) -> str:
    try:
        value = function()
    except Exception as exception:
        return f"ERR:{type(exception).__name__}"
    if value is None:
        return "null"
    offset = value.utcoffset()
    minutes = 0 if offset is None else int(offset.total_seconds() / 60)
    return value.strftime("%Y%m%d%H%M%S") + f"@{minutes}"


def _slot(function: object) -> str:
    try:
        return "0" if function() is None else "1"
    except Exception as exception:
        return f"ERR:{type(exception).__name__}"


def _python_line(case_id: str) -> str:
    file_spec = _build(case_id)
    slots = "".join(
        (
            _slot(file_spec.get_embedded_file),
            _slot(file_spec.get_embedded_file_unicode),
            _slot(file_spec.get_embedded_file_dos),
            _slot(file_spec.get_embedded_file_mac),
            _slot(file_spec.get_embedded_file_unix),
        )
    )
    embedded = file_spec.get_embedded_file()
    if embedded is None:
        return f"CASE {case_id} slots={slots} ef=null"
    return (
        f"CASE {case_id} slots={slots} ef=stream"
        f" sub={_call(embedded.get_subtype)}"
        f" size={_call(embedded.get_size)}"
        f" cd={_date(embedded.get_creation_date)}"
        f" md={_date(embedded.get_mod_date)}"
        f" sum={_call(embedded.get_check_sum_string)}"
        f" macsub={_call(embedded.get_mac_subtype)}"
        f" maccreator={_call(embedded.get_mac_creator)}"
        f" macres={_call(embedded.get_mac_res_fork)}"
    )


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    raw = run_probe_text("EmbeddedFileDictionaryFuzzProbe")
    lines = [line for line in raw.splitlines() if line.startswith("CASE ")]
    assert len(lines) == len(CASE_IDS), raw
    return {line.split(" ", 2)[1]: line for line in lines}


@requires_oracle
@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_embedded_file_dictionary_accessors_match_pdfbox(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _python_line(case_id) == java_lines[case_id]
