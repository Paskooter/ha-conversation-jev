"""Fail-closed expose helper and lights-first ordering."""

from __future__ import annotations

import json

import pytest

from custom_components.jev_assist.const import EXPOSED_ENTITY_CAP
from custom_components.jev_assist.exposure import (
    should_expose_compat,
    sort_lights_first,
)
from custom_components.jev_assist.jev_client import build_state
from custom_components.jev_assist.jev_router import ExposedEntity


def test_should_expose_true() -> None:
    assert should_expose_compat(lambda: True) is True


def test_should_expose_false() -> None:
    assert should_expose_compat(lambda: False) is False


def test_should_expose_typeerror_fails_closed() -> None:
    def boom() -> bool:
        raise TypeError("unexpected keyword argument")

    assert should_expose_compat(boom) is False


def test_should_expose_unexpected_error_reraise() -> None:
    def boom() -> bool:
        raise RuntimeError("hass exploded")

    with pytest.raises(RuntimeError, match="hass exploded"):
        should_expose_compat(boom)


def test_sort_lights_first_before_cap() -> None:
    sensors = [
        ExposedEntity(
            entity_id=f"sensor.s{i:03d}",
            domain="sensor",
            name=f"Sensor {i}",
        )
        for i in range(EXPOSED_ENTITY_CAP)
    ]
    light = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area="Kitchen",
    )
    ordered = sort_lights_first([*sensors, light])
    assert ordered[0].entity_id == "light.kitchen"
    capped = ordered[:EXPOSED_ENTITY_CAP]
    assert any(item.domain == "light" for item in capped)
    payload = build_state("turn off kitchen", capped, "en")
    json.dumps(payload)
    ids = [item["entity_id"] for item in payload["exposed_entities"]]
    assert "light.kitchen" in ids


class ComputedNameType:
    """Stand-in for HA's non-str `state.name` (not JSON serializable)."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def test_build_state_serializes_non_str_name() -> None:
    name = ComputedNameType("Kitchen lamp")
    area = ComputedNameType("Kitchen")
    alias = ComputedNameType("Küche")
    with pytest.raises(TypeError, match="ComputedNameType"):
        json.dumps({"name": name})

    entity = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name=name,  # type: ignore[arg-type]
        area=area,  # type: ignore[arg-type]
        aliases=(alias,),  # type: ignore[arg-type]
    )
    raw = build_state("lichter aus", [entity], "de")
    payload = raw if isinstance(raw, dict) else json.loads(raw)
    dumped = payload["exposed_entities"][0]
    assert dumped["name"] == "Kitchen lamp"
    assert isinstance(dumped["name"], str)
    assert dumped["area"] == "Kitchen"
    assert isinstance(dumped["area"], str)
    assert dumped["aliases"] == ["Küche"]
    assert all(isinstance(item, str) for item in dumped["aliases"])
    assert payload["areas"] == ["Kitchen"]
    assert all(isinstance(item, str) for item in payload["areas"])
    json.dumps(payload)
