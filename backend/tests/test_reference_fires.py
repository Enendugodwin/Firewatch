"""Reference fire catalogue validity (the events themselves are validated live)."""

from __future__ import annotations

import pytest

from app.services.reference_fires import REFERENCE_FIRES, get_reference_fire


def test_catalogue_entries_are_valid_and_unique() -> None:
    keys = [fire.key for fire in REFERENCE_FIRES]
    slugs = [fire.slug for fire in REFERENCE_FIRES]

    assert len(set(keys)) == len(keys)
    assert len(set(slugs)) == len(slugs)
    assert len(REFERENCE_FIRES) >= 2

    for fire in REFERENCE_FIRES:
        assert -90 <= fire.latitude <= 90
        assert -180 <= fire.longitude <= 180
        assert 0 < fire.radius_km <= 2000
        assert fire.start < fire.end
        assert fire.expected
        assert fire.sources and all(source.startswith("https://") for source in fire.sources)


def test_unknown_reference_fire_is_a_key_error() -> None:
    with pytest.raises(KeyError):
        get_reference_fire("does-not-exist")
