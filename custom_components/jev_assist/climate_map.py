"""Climate service map and temperature / HVAC-mode parsing."""

from __future__ import annotations

import re
from typing import Any, Final

from .local_targets import normalize_numeric_signs

# Jev actions that map to a Home Assistant climate service.
CLIMATE_ACTION_MAP: Final[dict[str, tuple[str, str]]] = {
    "set_temperature": ("climate", "set_temperature"),
    "turn_on": ("climate", "turn_on"),
    "turn_off": ("climate", "turn_off"),
    "set_hvac_mode": ("climate", "set_hvac_mode"),
}

# Indoor setpoints only; outside this range the utterance is underspecified.
_TEMP_MIN_C: Final = 5.0
_TEMP_MAX_C: Final = 35.0

TEMP_UNIT_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?<![\d.,+\-])
    (?P<value>(?:[+\-]\s*)?\d+(?:[.,]\d+)?)
    (?![\d.,])
    \s*
    (?:
        °\s*c(?:elsius)?
        | celsius\b
        | grad(?:e)?s?\b
        | degrees?(?:\s*c(?:elsius)?)?\b
        | °
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "set heating to 21" / "Heizung auf 21" without a unit — not a percent.
TEMP_BARE_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?:
        (?:temperatur(?:e)?|sollwert|heizung|heating|thermostat|klima)
        \s*(?:auf|to|=|:)?\s*
        | (?:auf|to)\s+
    )
    (?P<value>(?:[+\-]\s*)?\d+(?:[.,]\d+)?)
    (?![\d.,])
    (?!\s*(?:%|percent|procent|prozent))
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Longer HVAC phrases first so heat_cool wins over heat/cool.
_HVAC_MODE_RES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(r"heat\s*[_\-]?\s*cool|heizen\s+und\s+kühlen", re.IGNORECASE),
        "heat_cool",
    ),
    (
        re.compile(
            r"fan\s*[_\-]?\s*only|nur\s+l[üu]fter|\bl[üu]fter\b",
            re.IGNORECASE,
        ),
        "fan_only",
    ),
    (re.compile(r"\b(heat(?:ing)?|heizen|heizbetrieb)\b", re.IGNORECASE), "heat"),
    (
        re.compile(r"\b(cool(?:ing)?|kühlen|kühlbetrieb|\bac\b)\b", re.IGNORECASE),
        "cool",
    ),
    (re.compile(r"\b(auto(?:matic)?|automatisch)\b", re.IGNORECASE), "auto"),
    (re.compile(r"\b(dry|entfeucht\w*)\b", re.IGNORECASE), "dry"),
    (re.compile(r"\b(off)\b", re.IGNORECASE), "off"),
)


def _parse_temp_value(raw: str) -> float | None:
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", raw):
        return None
    value = float(raw.replace(",", "."))
    if value < _TEMP_MIN_C or value > _TEMP_MAX_C:
        return None
    if value == int(value):
        return float(int(value))
    return value


def parse_temperature_c(utterance: str) -> float | None:
    """Return a °C setpoint in 5–35 if the utterance contains one."""
    utterance = normalize_numeric_signs(utterance)
    matches = list(TEMP_UNIT_RE.finditer(utterance)) or list(TEMP_BARE_RE.finditer(utterance))
    if len(matches) != 1:
        return None
    return _parse_temp_value(matches[0].group("value"))


def parse_hvac_mode(utterance: str) -> str | None:
    """Return an HA HVAC mode string if clearly present in the utterance."""
    for pattern, mode in _HVAC_MODE_RES:
        if pattern.search(utterance):
            return mode
    return None


def climate_service_call(
    action: str,
    entity_ids: list[str],
    utterance: str,
) -> tuple[str, str, dict[str, Any]] | None:
    """Map a Jev climate action to (domain, service, data), or None if unmapped."""
    mapped = CLIMATE_ACTION_MAP.get(action)
    if mapped is None or not entity_ids:
        return None
    domain, service = mapped
    data: dict[str, Any] = {
        "entity_id": entity_ids[0] if len(entity_ids) == 1 else entity_ids,
    }
    if action == "set_temperature":
        temperature = parse_temperature_c(utterance)
        if temperature is None:
            return None
        data["temperature"] = temperature
    elif action == "set_hvac_mode":
        mode = parse_hvac_mode(utterance)
        if mode is None:
            return None
        data["hvac_mode"] = mode
    return domain, service, data
