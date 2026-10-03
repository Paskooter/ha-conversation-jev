"""Regression: HA ComputedNameType Enum must not break Jev state JSON."""

from __future__ import annotations

import json
from enum import Enum

import pytest

from custom_components.jev_assist.jev_client import (
    build_questions,
    build_state,
    unique_areas,
)
from custom_components.jev_assist.jev_router import ExposedEntity


class ComputedNameType(Enum):
    """Mirror HA ``entity_registry.ComputedNameType`` (JSON-unsafe sentinel)."""

    _singleton = 0


COMPUTED_NAME = ComputedNameType._singleton


def test_raw_computed_name_enum_is_not_json_serializable() -> None:
    """Documents why build_state / ExposedEntity coerce via str()."""
    with pytest.raises(TypeError, match="ComputedNameType"):
        json.dumps(COMPUTED_NAME)
    with pytest.raises(TypeError, match="ComputedNameType"):
        json.dumps({"aliases": [COMPUTED_NAME, "kitchen"]})


def test_build_state_coerces_computed_name_enum_aliases() -> None:
    entity = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name=COMPUTED_NAME,  # type: ignore[arg-type]
        area=COMPUTED_NAME,  # type: ignore[arg-type]
        aliases=(COMPUTED_NAME, "kitchen"),  # type: ignore[arg-type]
    )
    raw = build_state("lichter aus", [entity], "de")
    payload = raw if isinstance(raw, dict) else json.loads(raw)
    dumped = payload["exposed_entities"][0]
    expected = str(COMPUTED_NAME)

    assert payload["utterance"] == "lichter aus"
    assert dumped["name"] == expected
    assert isinstance(dumped["name"], str)
    assert not isinstance(dumped["name"], Enum)
    assert dumped["area"] == expected
    assert isinstance(dumped["area"], str)
    assert dumped["aliases"] == [expected, "kitchen"]
    assert all(isinstance(alias, str) for alias in dumped["aliases"])
    assert all(not isinstance(alias, Enum) for alias in dumped["aliases"])
    assert payload["areas"] == [expected]
    assert all(isinstance(area, str) for area in payload["areas"])
    json.dumps(payload)


def test_unique_areas_and_questions_criteria_are_plain_str() -> None:
    entity = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area=COMPUTED_NAME,  # type: ignore[arg-type]
        aliases=(COMPUTED_NAME, "kitchen"),  # type: ignore[arg-type]
    )
    areas = unique_areas([entity])
    assert areas == [str(COMPUTED_NAME)]
    assert all(isinstance(area, str) for area in areas)

    questions = build_questions("en", [COMPUTED_NAME, "Kitchen"])  # type: ignore[list-item]
    criteria = questions["target_area"].criteria
    assert str(COMPUTED_NAME) in criteria
    assert "Kitchen" in criteria
    assert all(isinstance(key, str) for key in criteria)
    assert all(not isinstance(key, Enum) for key in criteria)
    assert all(isinstance(value, str) for value in criteria.values())
    json.dumps(list(criteria.items()))
