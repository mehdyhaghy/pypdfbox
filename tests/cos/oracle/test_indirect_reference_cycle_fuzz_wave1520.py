"""Malformed indirect-reference and object-pool cycle differential."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSNull,
    COSObject,
    COSObjectKey,
)
from pypdfbox.loader import Loader
from tests.oracle.harness import requires_oracle, run_probe_text

_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"

_CASES: dict[str, tuple[tuple[int, int, int, str], ...]] = {
    "scalar": ((1, 0, 0, "42"),),
    "self": ((1, 0, 0, "1 0 R"),),
    "two": ((1, 0, 0, "2 0 R"), (2, 0, 0, "1 0 R")),
    "missing": ((1, 0, 0, "[99 0 R]"),),
    "gen_gap": ((1, 0, 0, "[2 1 R]"), (2, 0, 0, "22")),
    "gen_exact": ((1, 0, 0, "[2 1 R]"), (2, 1, 1, "21")),
    "gen_header": ((1, 1, 0, "7"),),
    "array_self": ((1, 0, 0, "[1 0 R]"),),
    "dict_self": ((1, 0, 0, "<< /Loop 1 0 R >>"),),
    "array_two": (
        (1, 0, 0, "[2 0 R]"),
        (2, 0, 0, "[1 0 R]"),
    ),
    "dict_two": (
        (1, 0, 0, "<< /Next 2 0 R >>"),
        (2, 0, 0, "<< /Next 1 0 R >>"),
    ),
    "nested": (
        (1, 0, 0, "<< /Loop [2 0 R] >>"),
        (2, 0, 0, "<< /Back 1 0 R >>"),
    ),
}
_IDS = tuple(_CASES)


def _object(number: int, generation: int, body: str) -> bytes:
    return (
        f"{number} {generation} obj\n{body}\nendobj\n".encode("latin-1")
    )


def _build_pdf(definitions: Iterable[tuple[int, int, int, str]]) -> bytes:
    data = bytearray(_HEADER)
    offsets: dict[int, int] = {}
    xref_generations: dict[int, int] = {}

    for number, header_generation, xref_generation, body in definitions:
        offsets[number] = len(data)
        xref_generations[number] = xref_generation
        data.extend(_object(number, header_generation, body))

    offsets[10] = len(data)
    xref_generations[10] = 0
    data.extend(_object(10, 0, "<< /Type /Catalog /Pages 11 0 R >>"))
    offsets[11] = len(data)
    xref_generations[11] = 0
    data.extend(_object(11, 0, "<< /Type /Pages /Kids [] /Count 0 >>"))

    xref_offset = len(data)
    data.extend(b"xref\n0 12\n")
    data.extend(b"0000000000 65535 f \n")
    for number in range(1, 12):
        if number in offsets:
            data.extend(
                f"{offsets[number]:010d} "
                f"{xref_generations[number]:05d} n \n".encode("ascii")
            )
        else:
            data.extend(b"0000000000 00000 f \n")
    data.extend(b"trailer\n<< /Size 12 /Root 10 0 R >>\nstartxref\n")
    data.extend(f"{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(data)


def _walk(base: COSBase | None, seen: dict[int, int]) -> str:
    if base is None or base is COSNull.NULL:
        return "null"
    identity = id(base)
    if identity in seen:
        return f"@{seen[identity]}"
    seen[identity] = len(seen)

    if isinstance(base, COSObject):
        return (
            f"ref({base.get_object_number()}:{base.get_generation_number()})->"
            f"{_walk(base.get_object(), seen)}"
        )
    if isinstance(base, COSInteger):
        return f"int({base.long_value()})"
    if isinstance(base, COSArray):
        values = (_walk(base.get(index), seen) for index in range(base.size()))
        return "array[" + ",".join(values) + "]"
    if isinstance(base, COSDictionary):
        keys = sorted(base.key_set(), key=lambda key: key.get_name())
        values = (
            f"/{key.get_name()}->{_walk(base.get_item(key), seen)}"
            for key in keys
        )
        return "dict{" + ",".join(values) + "}"
    return f"other({type(base).__name__})"


def _project(data: bytes) -> str:
    document = Loader.load_pdf(data)
    try:
        target = document.get_object_from_pool(COSObjectKey(1, 0))
        return _walk(target, {})
    except Exception as exc:  # noqa: BLE001 - matches the probe error arm
        return f"ERR:{type(exc).__name__}"
    finally:
        document.close()


def _write_corpus(directory: Path) -> None:
    for case_id, definitions in _CASES.items():
        (directory / f"{case_id}.pdf").write_bytes(_build_pdf(definitions))
    (directory / "manifest.txt").write_text(
        "\n".join(_IDS) + "\n",
        encoding="utf-8",
    )


@requires_oracle
def test_indirect_reference_cycles_match_pdfbox(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    java = run_probe_text("IndirectReferenceCycleFuzzProbe", str(tmp_path))
    python = "\n".join(
        f"CASE {case_id} {_project(_build_pdf(definitions))}"
        for case_id, definitions in _CASES.items()
    )
    assert python + "\n" == java


@pytest.mark.parametrize("case_id", _IDS, ids=_IDS)
def test_indirect_reference_cycles_terminate(case_id: str) -> None:
    projection = _project(_build_pdf(_CASES[case_id]))
    assert not projection.startswith("ERR:")


def test_cos_object_swallows_loader_oserror_once() -> None:
    calls = 0

    def loader(_object: COSObject) -> COSBase | None:
        nonlocal calls
        calls += 1
        raise OSError("broken xref target")

    target = COSObject(1, 0, loader=loader)
    assert target.get_object() is None
    assert target.get_object() is None
    assert target.is_dereferenced()
    assert calls == 1


def test_cos_object_propagates_programming_error_without_retry() -> None:
    calls = 0

    def loader(_object: COSObject) -> COSBase | None:
        nonlocal calls
        calls += 1
        raise RuntimeError("loader bug")

    target = COSObject(1, 0, loader=loader)
    with pytest.raises(RuntimeError, match="loader bug"):
        target.get_object()
    assert target.get_object() is None
    assert calls == 1
