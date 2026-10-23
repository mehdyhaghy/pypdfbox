"""Live differential for the lenient xref offset check: the xref table of
every case PDF in ``test_check_xref_offsets`` must equal the one PDFBox 3.0.8
builds after ``retrieveTrailer`` (``XrefOffsetCheckProbe``)."""
import pytest

from tests.oracle.harness import requires_oracle, run_probe_text
from tests.pdfparser.test_check_xref_offsets import CASES, _table


@requires_oracle
@pytest.mark.parametrize("case", sorted(CASES))
def test_xref_table_matches_pdfbox(case: str, tmp_path) -> None:
    data = CASES[case]()
    path = tmp_path / f"{case}.pdf"
    path.write_bytes(data)
    line = run_probe_text("XrefOffsetCheckProbe", str(path)).strip()
    assert line.startswith("XREF")
    java = {}
    for item in line.split()[1:]:
        num, gen, value = (int(x) for x in item.split(","))
        java[(num, gen)] = value
    assert _table(data) == java
