"""Cover service map and position / tilt percent parsing."""

from __future__ import annotations

import re
from typing import Any, Final

from .local_targets import normalize_numeric_signs

# Jev actions that map to a Home Assistant cover service.
# turn_on / turn_off are aliases when Jev reuses those action keys.
COVER_ACTION_MAP: Final[dict[str, tuple[str, str]]] = {
    "open": ("cover", "open_cover"),
    "close": ("cover", "close_cover"),
    "stop": ("cover", "stop_cover"),
    "set_position": ("cover", "set_cover_position"),
    "set_tilt": ("cover", "set_cover_tilt_position"),
    "turn_on": ("cover", "open_cover"),
    "turn_off": ("cover", "close_cover"),
}

# Shared DE/EN percent for lift position and slat tilt. Not on/off.
PERCENT_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?<![\d.,+\-])
    (?P<value>(?:[+\-]\s*)?\d+(?:[.,]\d+)?)
    (?![\d.,])
    \s*
    (?:
        %
        | (?:percent | procent | prozent)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
POSITION_RE: Final[re.Pattern[str]] = PERCENT_RE


def parse_percent_pct(utterance: str) -> int | None:
    """Return a 0–100 percent if the utterance contains one."""
    utterance = normalize_numeric_signs(utterance)
    matches = list(PERCENT_RE.finditer(utterance))
    if len(matches) != 1:
        return None
    raw = matches[0].group("value")
    if not re.fullmatch(r"\d+", raw):
        return None
    value = int(raw)
    if value > 100:
        return None
    return value


def parse_position_pct(utterance: str) -> int | None:
    """Return a 0–100 cover position if the utterance contains a percent."""
    return parse_percent_pct(utterance)


def parse_tilt_pct(utterance: str) -> int | None:
    """Return a 0–100 cover tilt if the utterance contains a percent."""
    return parse_percent_pct(utterance)


def cover_service_call(
    action: str,
    entity_ids: list[str],
    utterance: str,
) -> tuple[str, str, dict[str, Any]] | None:
    """Map a Jev cover action to (domain, service, data), or None if unmapped."""
    mapped = COVER_ACTION_MAP.get(action)
    if mapped is None or not entity_ids:
        return None
    domain, service = mapped
    data: dict[str, Any] = {
        "entity_id": entity_ids[0] if len(entity_ids) == 1 else entity_ids,
    }
    if action == "set_position":
        position = parse_position_pct(utterance)
        if position is None:
            return None
        data["position"] = position
    elif action == "set_tilt":
        tilt = parse_tilt_pct(utterance)
        if tilt is None:
            return None
        data["tilt_position"] = tilt
    return domain, service, data
