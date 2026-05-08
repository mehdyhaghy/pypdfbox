from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead


def test_wave321_append_repairs_missing_next_link() -> None:
    first = PDThreadBead(COSDictionary())
    second = PDThreadBead()

    first.append_bead(second)

    assert first.get_next_bead() == second
    assert first.get_previous_bead() == second
    assert second.get_next_bead() == first
    assert second.get_previous_bead() == first
    assert [bead.get_cos_object() for bead in first.iter_beads()] == [
        first.get_cos_object(),
        second.get_cos_object(),
    ]
    assert first.count_beads() == 2
