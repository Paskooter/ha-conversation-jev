"""Bounded read-only home questions; no services, history or provider calls."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from .local_targets import (
    PRONOUN_REFERENCE,
    ROOM_REFERENCE,
    entity_names,
    exact_named_targets,
    has_unscoped_all,
    normalized,
)

if TYPE_CHECKING:
    from homeassistant.core import State

    from .jev_router import ExposedEntity

_QUESTION = re.compile(
    r"^(?:is|are|what(?: is| are| s)?|how (?:bright|warm|hot|cold)|tell me|check|status|ist|sind|was|wie (?:hell|warm|heiß|kalt)|sag mir|prüfe)\b",
    re.IGNORECASE,
)
_DOMAINS = {
    "light": {"light", "lights", "lamp", "lamps", "licht", "lichter", "lampe", "lampen"},
    "climate": {"thermostat", "thermostats", "climate", "hvac", "heating", "heizung", "klimaanlage"},
    "cover": {
        "blind",
        "blinds",
        "shade",
        "shades",
        "cover",
        "covers",
        "shutter",
        "shutters",
        "garage",
        "jalousie",
        "jalousien",
        "rollladen",
        "rollläden",
        "garagentor",
    },
    "lock": {"lock", "locks", "schloss", "schlösser"},
    "switch": {"switch", "switches", "plug", "plugs", "schalter", "steckdose"},
    "fan": {"fan", "fans", "lüfter"},
    "binary_sensor": {
        "door",
        "doors",
        "window",
        "windows",
        "motion",
        "smoke",
        "tür",
        "türen",
        "fenster",
        "bewegung",
        "rauch",
    },
}
_SUPPORTED = frozenset(_DOMAINS) | {"sensor", "input_boolean", "media_player"}
_STATE_WORDS = {
    "on",
    "off",
    "open",
    "closed",
    "locked",
    "unlocked",
    "state",
    "status",
    "brightness",
    "color",
    "colour",
    "temperature",
    "humidity",
    "position",
    "tilt",
    "an",
    "aus",
    "offen",
    "geschlossen",
    "verriegelt",
    "entriegelt",
    "zustand",
    "helligkeit",
    "farbe",
    "temperatur",
    "luftfeuchtigkeit",
    "neigung",
}
_QUERY_WORDS = (
    _STATE_WORDS
    | {token for tokens in _DOMAINS.values() for token in tokens}
    | {
        "is",
        "are",
        "what",
        "s",
        "how",
        "bright",
        "warm",
        "hot",
        "cold",
        "heiß",
        "kalt",
        "ist",
        "sind",
        "was",
        "wie",
        "the",
        "a",
        "an",
        "my",
        "tell",
        "me",
        "check",
        "of",
        "in",
        "here",
        "this",
        "room",
        "set",
        "to",
        "target",
        "setpoint",
        "mode",
        "modus",
        "die",
        "das",
        "der",
        "den",
        "des",
        "dem",
        "im",
        "hier",
        "diesem",
        "raum",
        "sag",
        "mir",
        "bitte",
        "please",
        "on",
        "off",
        "and",
        "und",
        "current",
        "now",
        "right",
        "aktuell",
        "ein",
        "eine",
        "einem",
        "einer",
        "sollwert",
        "solltemperatur",
        "eingestellt",
        "auf",
        "it",
        "them",
        "es",
        "sie",
        "that",
        "those",
        "one",
    }
)


@dataclass(frozen=True)
class HomeQuery:
    entity_ids: tuple[str, ...]
    property: str = "state"
    reason: str = "home_state"


def parse_home_query(
    text: str,
    exposed: Sequence[ExposedEntity],
    *,
    room: str | None = None,
    followup_entity_ids: Sequence[str] = (),
) -> HomeQuery | None:
    """Recognize home-state questions, including unresolved targets, locally."""
    folded = normalized(text)
    if not _QUESTION.search(folded):
        return None
    words = set(folded.split())
    domains = {domain for domain, tokens in _DOMAINS.items() if words & tokens}
    binary_classes: set[str] = set()
    cover_classes: set[str] = set()
    for nouns, binary, cover in (
        ({"door", "doors", "tür", "türen"}, {"door"}, {"door"}),
        ({"window", "windows", "fenster"}, {"window"}, {"window"}),
        ({"motion", "bewegung"}, {"motion"}, set()),
        ({"smoke", "rauch"}, {"smoke"}, set()),
        ({"blind", "blinds", "jalousie", "jalousien"}, set(), {"blind"}),
        ({"shade", "shades"}, set(), {"shade"}),
        ({"shutter", "shutters", "rollladen", "rollläden"}, set(), {"shutter"}),
    ):
        if words & nouns:
            binary_classes.update(binary)
            cover_classes.update(cover)
    if words & {"garage", "garagentor"}:
        binary_classes, cover_classes = {"garage_door"}, {"garage"}
    if cover_classes:
        domains.add("cover")
    if binary_classes:
        domains.add("binary_sensor")
    named = exact_named_targets(text, exposed)
    property_name = "state"
    if words & {"brightness", "bright", "helligkeit", "hell"}:
        property_name = "brightness"
        domains = {"light"}
    elif words & {"color", "colour", "farbe"}:
        property_name = "color"
        domains = {"light"}
    elif words & {"temperature", "temperatur", "warm", "hot", "cold", "heiß", "kalt"}:
        property_name = (
            "target_temperature"
            if words & {"target", "setpoint", "sollwert", "solltemperatur"} or "set to" in folded
            else "temperature"
        )
    elif words & {"humidity", "luftfeuchtigkeit"}:
        property_name = "humidity"
    elif words & {"position", "tilt", "neigung"}:
        property_name = "tilt" if words & {"tilt", "neigung"} else "position"
        domains = {"cover"}
    elif "mode" in words or "modus" in words:
        property_name = "state"
        domains = {"climate"}
    is_pronoun = bool(PRONOUN_REFERENCE.search(folded))
    if not domains and not named and property_name == "state" and not words & _STATE_WORDS:
        return None
    areas = sorted({item.area for item in exposed if item.area and f" {normalized(item.area)} " in f" {folded} "})
    target_text = folded
    for name in sorted(
        {name for item in named for name in entity_names(item)} | {normalized(area) for area in areas},
        key=len,
        reverse=True,
    ):
        target_text = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", " ", target_text)
    if set(target_text.split()) - _QUERY_WORDS - {"all", "every", "alle"}:
        return HomeQuery((), property_name, "query_unknown_named_target")
    # Any recognized home question stays local even if no target can be resolved.
    candidates = [item for item in exposed if item.domain in _SUPPORTED]
    if named:
        # A full name collision is ambiguous; do not answer for a guessed device.
        if len(named) != 1:
            return HomeQuery((), property_name, "query_ambiguous")
        candidates = [item for item in candidates if item.entity_id == named[0].entity_id]
    elif is_pronoun and followup_entity_ids:
        wanted = set(followup_entity_ids)
        candidates = [item for item in candidates if item.entity_id in wanted]
        if len(candidates) != len(wanted):
            return HomeQuery((), property_name, "query_context_unexposed")
    elif is_pronoun:
        return HomeQuery((), property_name, "query_context_missing")
    else:
        if ROOM_REFERENCE.search(folded):
            if not room:
                return HomeQuery((), property_name, "query_room_missing")
            if not areas:
                areas = [room]
        if not areas and room:
            if has_unscoped_all(folded):
                return HomeQuery((), property_name, "query_target_missing")
            areas = [room]
        if not areas:
            return HomeQuery((), property_name, "query_target_missing")
        wanted_areas = {area.casefold() for area in areas}
        candidates = [item for item in candidates if (item.area or "").casefold() in wanted_areas]
    if domains and not named:
        candidates = [item for item in candidates if item.domain in domains]
    if not named:
        candidates = [
            item
            for item in candidates
            if (item.domain != "binary_sensor" or not binary_classes or item.device_class in binary_classes)
            and (item.domain != "cover" or not cover_classes or item.device_class in cover_classes)
        ]
    if property_name in {"temperature", "humidity"}:
        candidates = [
            item
            for item in candidates
            if item.domain == "climate" or item.domain == "sensor" and item.device_class == property_name
        ]
    elif property_name == "target_temperature":
        candidates = [item for item in candidates if item.domain == "climate"]
    if not candidates:
        return HomeQuery((), property_name, "query_no_exposed_target")
    if len(candidates) > 12:
        return HomeQuery((), property_name, "query_too_many_targets")
    return HomeQuery(tuple(item.entity_id for item in candidates), property_name)


def _number(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except TypeError, ValueError:
        return None
    if not math.isfinite(numeric):
        return None
    return f"{numeric:g}"


def describe_state(state: State, property_name: str, *, temperature_unit: str = "degrees") -> str | None:
    """Use only supported current values, never arbitrary attributes."""
    domain = state.domain
    attrs = state.attributes
    if property_name == "brightness":
        if domain != "light":
            return None
        if state.state == "off":
            return "brightness is 0 percent (off)"
        value = _number(attrs.get("brightness"))
        return (
            f"brightness is {round(float(value) * 100 / 255)} percent" if value and 0 <= float(value) <= 255 else None
        )
    if property_name == "color":
        rgb = attrs.get("rgb_color")
        if (
            state.state == "off"
            or not isinstance(rgb, (tuple, list))
            or len(rgb) != 3
            or any(_number(value) is None or not 0 <= float(value) <= 255 for value in rgb)
        ):
            return None
        from .light_map import NAMED_COLORS

        named = next((name for name, color in NAMED_COLORS.items() if tuple(rgb) == color), None)
        return f"color is {named}" if named else "color is RGB " + ", ".join(str(round(float(value))) for value in rgb)
    if property_name in {"temperature", "target_temperature", "humidity"}:
        attr = {
            "temperature": "current_temperature",
            "target_temperature": "temperature",
            "humidity": "current_humidity",
        }[property_name]
        value = _number(attrs.get(attr) if domain == "climate" else state.state)
        if value is None:
            return None
        unit = (
            "%"
            if property_name == "humidity"
            else str(attrs.get("temperature_unit", attrs.get("unit_of_measurement", temperature_unit)))
        )
        label = "target temperature" if property_name == "target_temperature" else property_name
        return f"{label} is {value} {unit}"
    if property_name in {"position", "tilt"}:
        value = _number(attrs.get("current_tilt_position" if property_name == "tilt" else "current_position"))
        return f"{property_name} is {value} percent" if value and 0 <= float(value) <= 100 else None
    if domain == "sensor":
        value = _number(state.state)
        return f"is {value} {attrs.get('unit_of_measurement', '')}".strip() if value is not None else None
    if domain == "binary_sensor":
        if state.state not in {"on", "off"}:
            return None
        device_class = attrs.get("device_class")
        if device_class in {"door", "window", "opening", "garage_door"}:
            return "is open" if state.state == "on" else "is closed"
        if device_class == "lock":
            return "is unlocked" if state.state == "on" else "is locked"
        if device_class in {"motion", "occupancy", "presence", "smoke", "gas", "moisture"}:
            return "is detected" if state.state == "on" else "is clear"
    allowed = {
        "on",
        "off",
        "open",
        "closed",
        "opening",
        "closing",
        "locked",
        "unlocked",
        "locking",
        "unlocking",
        "jammed",
        "heat",
        "cool",
        "auto",
        "dry",
        "fan_only",
        "heat_cool",
        "playing",
        "paused",
        "idle",
        "standby",
    }
    return f"is {state.state.replace('_', ' ')}" if state.state in allowed else None
