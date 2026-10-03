"""Brightness regex and light service map v0."""

from custom_components.jev_assist.light_map import (
    light_service_call,
    parse_brightness_pct,
)


def test_parse_percent_en() -> None:
    assert parse_brightness_pct("set brightness to 50%") == 50
    assert parse_brightness_pct("80 percent please") == 80


def test_parse_percent_de() -> None:
    assert parse_brightness_pct("Helligkeit 25%") == 25
    assert parse_brightness_pct("auf 10 Prozent") == 10
    assert parse_brightness_pct("Helligkeit 40") == 40


def test_parse_rejects_over_100() -> None:
    assert parse_brightness_pct("150%") is None


def test_turn_on_off_toggle() -> None:
    assert light_service_call("turn_on", ["light.a"], "on") == (
        "light",
        "turn_on",
        {"entity_id": "light.a"},
    )
    assert light_service_call("turn_off", ["light.a", "light.b"], "off")[2]["entity_id"] == [
        "light.a",
        "light.b",
    ]
    assert light_service_call("toggle", ["light.a"], "toggle")[1] == "toggle"


def test_set_brightness_requires_number() -> None:
    assert light_service_call("set_brightness", ["light.a"], "dim it") is None
    mapped = light_service_call("set_brightness", ["light.a"], "brightness 12")
    assert mapped is not None
    assert mapped[2]["brightness_pct"] == 12


def test_unmapped_action() -> None:
    assert light_service_call("other", ["light.a"], "hello") is None
