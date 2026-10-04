"""Climate service map, temperature parsing, HVAC mode parsing."""

import pytest

from custom_components.jev_assist.climate_map import (
    climate_service_call,
    parse_hvac_mode,
    parse_temperature_c,
)


def test_parse_temperature_with_unit_en() -> None:
    assert parse_temperature_c("set heating to 21°C") == 21
    assert parse_temperature_c("21 degrees celsius") == 21
    assert parse_temperature_c("set to 19.5°") == 19.5


def test_parse_temperature_with_unit_de() -> None:
    assert parse_temperature_c("Heizung auf 21 Grad") == 21
    assert parse_temperature_c("Temperatur 19,5 Grad") == 19.5


def test_parse_temperature_bare_setpoint() -> None:
    assert parse_temperature_c("set heating to 21") == 21
    assert parse_temperature_c("Heizung auf 20") == 20


def test_parse_temperature_rejects_percent_and_range() -> None:
    assert parse_temperature_c("set to 21%") is None
    assert parse_temperature_c("make it 40 Grad") is None
    assert parse_temperature_c("set to 3 degrees") is None
    assert parse_temperature_c("a bit warmer") is None


@pytest.mark.parametrize(
    "utterance",
    [
        "set to121degrees",
        "set to-20degrees",
        "set to - 20 degrees",
        "set to −20 degrees",
        "set heating to -20",
        "set heating to 121",
        "set to 35.1 degrees",
        "set to 21.5.5 degrees",
        "set to +20 degrees",
        "set to 20 degrees or 21 degrees",
    ],
)
def test_temperature_requires_one_complete_unsigned_literal(utterance: str) -> None:
    assert parse_temperature_c(utterance) is None
    assert climate_service_call("set_temperature", ["climate.study"], utterance) is None


@pytest.mark.parametrize(
    "utterance,value",
    [
        ("set to5degrees", 5),
        ("set to35degrees", 35),
        ("set to20.5degrees", 20.5),
        ("set to20,5degrees", 20.5),
        ("set heating to 5", 5),
        ("set heating to 35", 35),
    ],
)
def test_temperature_complete_literals_keep_boundaries_and_decimals(utterance: str, value: float) -> None:
    assert parse_temperature_c(utterance) == value


def test_parse_hvac_mode() -> None:
    assert parse_hvac_mode("set to heat") == "heat"
    assert parse_hvac_mode("Heizung auf Heizbetrieb") == "heat"
    assert parse_hvac_mode("switch to cool") == "cool"
    assert parse_hvac_mode("auf kühlen") == "cool"
    assert parse_hvac_mode("set heat_cool") == "heat_cool"
    assert parse_hvac_mode("fan only") == "fan_only"
    assert parse_hvac_mode("automatic") == "auto"
    assert parse_hvac_mode("entfeuchten") == "dry"
    assert parse_hvac_mode("make it cozy") is None


def test_set_temperature_service() -> None:
    mapped = climate_service_call("set_temperature", ["climate.living"], "set to 21°C")
    assert mapped == (
        "climate",
        "set_temperature",
        {"entity_id": "climate.living", "temperature": 21.0},
    )


def test_set_temperature_requires_number() -> None:
    assert climate_service_call("set_temperature", ["climate.a"], "warmer") is None


def test_turn_on_off() -> None:
    assert climate_service_call("turn_on", ["climate.a"], "on") == (
        "climate",
        "turn_on",
        {"entity_id": "climate.a"},
    )
    assert climate_service_call("turn_off", ["climate.a", "climate.b"], "off")[2]["entity_id"] == [
        "climate.a",
        "climate.b",
    ]


def test_set_hvac_mode_requires_mode() -> None:
    assert climate_service_call("set_hvac_mode", ["climate.a"], "mode please") is None
    mapped = climate_service_call("set_hvac_mode", ["climate.a"], "set to cool")
    assert mapped == (
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.a", "hvac_mode": "cool"},
    )


def test_unmapped_action() -> None:
    assert climate_service_call("toggle", ["climate.a"], "toggle") is None
    assert climate_service_call("other", ["climate.a"], "hello") is None
