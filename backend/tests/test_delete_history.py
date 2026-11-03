"""History deletion: scope formatting and the destructive guard."""

from __future__ import annotations

import sys

import scripts.delete_history as deletion


def test_scope_key_matches_the_harmonization_scope_format() -> None:
    assert deletion._scope_key("-70.0,-12.0,-50.0,2.0") == "bbox:-70,-12,-50,2"


def test_world_tile_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["delete_history", "--tile-key", "world"])

    assert deletion.main() == 2
