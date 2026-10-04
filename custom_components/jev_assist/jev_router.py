"""Jev routing: local state questions, confidence-gated HA actions and fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol, Sequence

from .climate_map import CLIMATE_ACTION_MAP, climate_service_call
from .const import (
    CATEGORY_COMMAND,
    CATEGORY_CONVERSATION,
    CATEGORY_REJECT,
    DEFAULT_LANGUAGE,
    DOMAIN_CLIMATE,
    DOMAIN_COVER,
    DOMAIN_LIGHT,
    FAST_MIN_CONFIDENCE,
    NOUL_UNSURE_LOW,
    NOUL_YES_THRESHOLD,
    REJECT_MIN_CONFIDENCE,
    SCOPE_WHOLE_HOME,
    TARGET_NONE,
    TARGET_UNKNOWN,
)
from .cover_map import COVER_ACTION_MAP, cover_service_call
from .light_map import LIGHT_ACTION_MAP, light_service_call
from .local_targets import (
    PRONOUN_REFERENCE,
    ROOM_REFERENCE,
    entity_names,
    exact_named_targets,
    exact_routine_targets,
    has_unscoped_all,
    normalized,
)

_TOKEN_RE = re.compile(r"[a-z0-9äöüß]+", re.IGNORECASE)
_STOP_TOKENS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "on",
        "off",
        "turn",
        "set",
        "please",
        "all",
        "make",
        "it",
        "and",
        "in",
        "of",
        "my",
        "me",
        "das",
        "die",
        "der",
        "den",
        "dem",
        "ein",
        "eine",
        "einen",
        "auf",
        "aus",
        "bitte",
        "schalte",
        "mach",
        "machen",
        "alle",
        "und",
        "im",
    }
)
_GENERIC_LIGHT_TOKENS = frozenset(
    {
        "light",
        "lights",
        "lamp",
        "lamps",
        "licht",
        "lichter",
        "lampe",
        "lampen",
        "bulb",
        "bulbs",
        "led",
        "dimmer",
    }
)
_GENERIC_CLIMATE_TOKENS = frozenset(
    {
        "climate",
        "thermostat",
        "heating",
        "heater",
        "hvac",
        "temperature",
        "heizung",
        "heizkörper",
        "heizkoerper",
        "klima",
        "klimaanlage",
        "temperatur",
    }
)
_GENERIC_COVER_TOKENS = frozenset(
    {
        "cover",
        "covers",
        "blind",
        "blinds",
        "shade",
        "shades",
        "shutter",
        "shutters",
        "curtain",
        "curtains",
        "jalousie",
        "jalousien",
        "rollladen",
        "rollläden",
        "rolllaeden",
        "rollo",
        "rollos",
        "vorhang",
        "vorhänge",
        "vorhaenge",
        "garagentor",
    }
)
_GENERIC_TOKENS_BY_DOMAIN: dict[str, frozenset[str]] = {
    DOMAIN_LIGHT: _GENERIC_LIGHT_TOKENS,
    DOMAIN_CLIMATE: _GENERIC_CLIMATE_TOKENS,
    DOMAIN_COVER: _GENERIC_COVER_TOKENS,
}

_FAST_ACTION_MAPS: dict[str, dict[str, tuple[str, str]]] = {
    DOMAIN_LIGHT: LIGHT_ACTION_MAP,
    DOMAIN_CLIMATE: CLIMATE_ACTION_MAP,
    DOMAIN_COVER: COVER_ACTION_MAP,
}
_FAST_SERVICE_CALLS: dict[str, Callable[[str, list[str], str], tuple[str, str, dict[str, Any]] | None]] = {
    DOMAIN_LIGHT: light_service_call,
    DOMAIN_CLIMATE: climate_service_call,
    DOMAIN_COVER: cover_service_call,
}
_FAST_REASONS: dict[str, str] = {
    DOMAIN_LIGHT: "light_v0",
    DOMAIN_CLIMATE: "climate_v0",
    DOMAIN_COVER: "cover_v0",
}
_SOLE_FAST_ACTIONS: dict[str, frozenset[str]] = {
    DOMAIN_LIGHT: frozenset({"turn_on", "turn_off", "toggle"}),
    DOMAIN_CLIMATE: frozenset({"turn_on", "turn_off"}),
    DOMAIN_COVER: frozenset({"open", "close", "stop", "turn_on", "turn_off"}),
}
_UNPARSED_REASONS: dict[str, str] = {
    "set_brightness": "brightness_unparsed",
    "set_color": "color_unparsed",
    "set_temperature": "temperature_unparsed",
    "set_hvac_mode": "hvac_mode_unparsed",
    "set_position": "position_unparsed",
    "set_tilt": "tilt_unparsed",
}
_COVER_PHRASES = ("garage door", "garage doors")

RouteKind = Literal["fast_service", "fast_query", "grok", "reject"]


@dataclass(frozen=True)
class ExposedEntity:
    """An Assist-exposed entity passed into Jev state."""

    entity_id: str
    domain: str
    name: str
    area: str | None = None
    aliases: tuple[str, ...] = ()
    device_class: str | None = None

    def __post_init__(self) -> None:
        # HA entity_registry aliases are AliasEntry = str | ComputedNameType.
        object.__setattr__(self, "entity_id", str(self.entity_id))
        object.__setattr__(self, "domain", str(self.domain))
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "area", None if self.area is None else str(self.area))
        object.__setattr__(self, "aliases", tuple(str(alias) for alias in self.aliases))
        object.__setattr__(self, "device_class", None if self.device_class is None else str(self.device_class))


@dataclass(frozen=True)
class ChoiceView:
    """SDK-agnostic Choice answer."""

    choice: str
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class NoulView:
    """SDK-agnostic Noul answer. ``noul`` is P(yes) in [0, 1]."""

    noul: float


@dataclass(frozen=True)
class JevClassification:
    """Normalized Jev answers used by the gate."""

    category: ChoiceView
    domain: ChoiceView
    action: ChoiceView
    scope: ChoiceView
    target_area: ChoiceView
    needs_llm: NoulView
    is_compound: NoulView


@dataclass(frozen=True)
class RouteResult:
    """Result of ``route``."""

    kind: RouteKind
    reason: str
    domain: str | None = None
    service: str | None = None
    service_data: dict[str, Any] | None = None
    classification: JevClassification | None = None
    target_entity_ids: tuple[str, ...] = ()
    query_property: str = "state"


class JevClientProtocol(Protocol):
    """Mockable Jev classifier (real SDK or test double)."""

    async def classify(
        self,
        utterance: str,
        exposed: Sequence[ExposedEntity],
        *,
        language: str,
    ) -> JevClassification: ...


def normalize_language(language: str | None) -> str:
    """Map HA language tags to ``en`` / ``de``."""
    if not language:
        return DEFAULT_LANGUAGE
    tag = language.lower().replace("_", "-")
    if tag == "de" or tag.startswith("de-"):
        return "de"
    return DEFAULT_LANGUAGE


def _choice_ok(view: ChoiceView, expected: str | None = None) -> bool:
    if view.confidence < FAST_MIN_CONFIDENCE:
        return False
    if expected is not None and view.choice != expected:
        return False
    return True


def _noul_yes(view: NoulView) -> bool:
    return view.noul >= NOUL_YES_THRESHOLD


def _noul_unsure(view: NoulView) -> bool:
    """Noul has no confidence field; near 0.5 means yes ≈ no."""
    return NOUL_UNSURE_LOW <= view.noul < NOUL_YES_THRESHOLD


def _noul_handoff(view: NoulView) -> bool:
    return _noul_yes(view) or _noul_unsure(view)


def _noul_handoff_reason(prefix: str, view: NoulView) -> str:
    return prefix if _noul_yes(view) else f"{prefix}_unsure"


def _confident_whole_home(classification: JevClassification) -> bool:
    return classification.scope.choice == SCOPE_WHOLE_HOME and classification.scope.confidence >= FAST_MIN_CONFIDENCE


def _words(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text)}


def _unique_area_names(exposed: Sequence[ExposedEntity]) -> list[str]:
    seen: list[str] = []
    for item in exposed:
        if not item.area:
            continue
        if item.area not in seen:
            seen.append(item.area)
    return seen


def _area_mentioned(utterance: str, area: str) -> bool:
    """True if ``area`` appears as a phrase in the utterance (DE/EN letters)."""
    folded_area = area.casefold().strip()
    if len(folded_area) < 2:
        return False
    pattern = re.compile(r"(?<![a-z0-9äöüß])" + re.escape(folded_area) + r"(?![a-z0-9äöüß])")
    return pattern.search(utterance.casefold()) is not None


def named_areas_in_utterance(utterance: str, exposed: Sequence[ExposedEntity]) -> list[str]:
    """Area names from exposed entities that appear as phrases in the utterance."""
    return [area for area in _unique_area_names(exposed) if _area_mentioned(utterance, area)]


def _mentions_other_fast_domain(utterance: str, domain: str) -> bool:
    uttered = _words(utterance)
    for other, tokens in _GENERIC_TOKENS_BY_DOMAIN.items():
        if other != domain and uttered & tokens:
            return True
    if domain != DOMAIN_COVER:
        folded = utterance.casefold()
        if any(phrase in folded for phrase in _COVER_PHRASES):
            return True
    return False


def _has_conflicting_actions(utterance: str) -> bool:
    tokens = _words(utterance)
    on_like = tokens & {"on", "an", "ein"}
    off_like = tokens & {"off", "aus"}
    if on_like and off_like:
        return True
    open_like = tokens & {"open", "öffnen", "oeffnen", "oeffne"}
    close_like = tokens & {"close", "schließen", "schliessen", "schliesse"}
    return bool(open_like and close_like)


def _is_multi_area_same_action(
    utterance: str,
    named_areas: Sequence[str],
    domain: str,
) -> bool:
    """Same domain + same action + two or more named rooms (not mixed ops)."""
    if len(named_areas) < 2:
        return False
    if _mentions_other_fast_domain(utterance, domain):
        return False
    if _has_conflicting_actions(utterance):
        return False
    return True


def _resolve_targets(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    domain: str,
    target_area: str,
    named_areas: Sequence[str],
    *,
    action: str | None = None,
) -> tuple[list[ExposedEntity], str | None]:
    """Resolve domain targets. Never fire all exposed entities on ``none`` alone.

    Fast path requires an explicit area (not none/unknown), two or more named
    areas in the utterance (union of those rooms only), a name-token match, or
    exactly one Assist-exposed entity of this domain for simple on/off-style
    actions. Otherwise the caller should Grok, not whole-home.
    """
    of_domain = [item for item in exposed if item.domain == domain]
    missing = f"no_exposed_{domain}"

    if len(named_areas) >= 2:
        wanted = {area.casefold() for area in named_areas}
        scoped = [item for item in of_domain if (item.area or "").casefold() in wanted]
        if not scoped:
            return [], missing
        return scoped, None

    if target_area == TARGET_UNKNOWN:
        return [], "target_area_unknown"
    if target_area and target_area != TARGET_NONE:
        wanted = target_area.casefold()
        scoped = [item for item in of_domain if (item.area or "").casefold() == wanted]
        if not scoped:
            return [], missing
        return scoped, None
    named = exact_named_targets(utterance, of_domain)
    if named:
        return named, None
    if (
        action in _SOLE_FAST_ACTIONS.get(domain, frozenset())
        and len(of_domain) == 1
        and _bare_room_target(utterance, domain, allow_all=True)
    ):
        return of_domain, None
    return [], "no_named_or_area_target"


def apply_gates(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    classification: JevClassification,
    *,
    room: str | None = None,
    followup_entity_ids: Sequence[str] = (),
) -> RouteResult:
    """Apply CONTRACT.md gates to a Jev classification."""
    cat = classification.category
    if cat.choice == CATEGORY_REJECT and cat.confidence >= REJECT_MIN_CONFIDENCE:
        return RouteResult(
            kind="reject",
            reason="category_reject",
            classification=classification,
        )
    if cat.choice == CATEGORY_CONVERSATION and cat.confidence >= FAST_MIN_CONFIDENCE:
        return RouteResult(
            kind="grok",
            reason="conversation",
            classification=classification,
        )

    named_areas = named_areas_in_utterance(utterance, exposed)
    domain_choice = classification.domain.choice
    routine = domain_choice in {"scene", "script"}
    action_map = (
        {"activate": (domain_choice, "turn_on"), "turn_on": (domain_choice, "turn_on")}
        if routine
        else _FAST_ACTION_MAPS.get(domain_choice, {})
    )
    multi_area = (
        domain_choice in _FAST_ACTION_MAPS
        and classification.action.choice in action_map
        and _choice_ok(classification.domain)
        and classification.action.confidence >= FAST_MIN_CONFIDENCE
        and _is_multi_area_same_action(utterance, named_areas, domain_choice)
    )
    mixed_or_conflict = len(named_areas) >= 2 and (
        _mentions_other_fast_domain(utterance, domain_choice) or _has_conflicting_actions(utterance)
    )
    whole_home = _confident_whole_home(classification) and not multi_area

    if _noul_handoff(classification.is_compound) and not multi_area:
        return RouteResult(
            kind="grok",
            reason=_noul_handoff_reason("is_compound", classification.is_compound),
            classification=classification,
        )
    if mixed_or_conflict:
        return RouteResult(
            kind="grok",
            reason="mixed_ops",
            classification=classification,
        )
    if _noul_handoff(classification.needs_llm):
        return RouteResult(
            kind="grok",
            reason=_noul_handoff_reason("needs_llm", classification.needs_llm),
            classification=classification,
        )

    if not _choice_ok(cat, CATEGORY_COMMAND):
        return RouteResult(
            kind="grok",
            reason="not_fast_command",
            classification=classification,
        )
    if not _choice_ok(classification.domain) or domain_choice not in _FAST_ACTION_MAPS and not routine:
        return RouteResult(
            kind="grok",
            reason="domain_unmapped",
            classification=classification,
        )
    if classification.action.choice not in action_map or classification.action.confidence < FAST_MIN_CONFIDENCE:
        return RouteResult(
            kind="grok",
            reason="action_unmapped",
            classification=classification,
        )
    if classification.target_area.confidence < FAST_MIN_CONFIDENCE and not multi_area and not whole_home:
        return RouteResult(
            kind="grok",
            reason="target_area_low_confidence",
            classification=classification,
        )

    target_area = TARGET_NONE if whole_home else classification.target_area.choice
    if routine:
        targets = exact_routine_targets(utterance, exposed, domain_choice)
        if len(targets) != 1:
            return RouteResult(kind="reject", reason="routine_explicit_target_required", classification=classification)
        return RouteResult(
            kind="fast_service",
            reason="named_routine",
            domain=domain_choice,
            service="turn_on",
            service_data={"entity_id": targets[0].entity_id},
            classification=classification,
            target_entity_ids=(targets[0].entity_id,),
        )
    explicit_names = exact_named_targets(utterance, [item for item in exposed if item.domain == domain_choice])
    if not explicit_names and len(named_areas) == 1 and not whole_home:
        target_area = named_areas[0]
    if not explicit_names and not multi_area and target_area == TARGET_UNKNOWN:
        return RouteResult(kind="grok", reason="target_area_unknown", classification=classification)
    if (
        not explicit_names
        and not multi_area
        and target_area not in {TARGET_NONE, TARGET_UNKNOWN, ""}
        and not any(
            item.domain == domain_choice and (item.area or "").casefold() == target_area.casefold() for item in exposed
        )
    ):
        return RouteResult(kind="reject", reason=f"no_exposed_{domain_choice}", classification=classification)
    if explicit_names and not multi_area and len(explicit_names) != 1:
        return RouteResult(kind="reject", reason="target_name_ambiguous", classification=classification)
    if any(
        len([item for item in explicit_names if name in entity_names(item)]) > 1
        and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", normalized(utterance))
        for name in {name for item in explicit_names for name in entity_names(item)}
    ):
        return RouteResult(kind="reject", reason="target_name_ambiguous", classification=classification)
    target_text = normalized(utterance)
    parameter_text = utterance.casefold()
    for name in sorted(
        {name for item in explicit_names for name in entity_names(item)} | {normalized(area) for area in named_areas},
        key=len,
        reverse=True,
    ):
        target_text = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", " ", target_text)
        parameter_text = re.sub(
            r"(?<!\w)" + r"[\W_]+".join(re.escape(word) for word in name.split()) + r"(?!\w)",
            " ",
            parameter_text,
        )
    value_mapped = _FAST_SERVICE_CALLS[domain_choice](classification.action.choice, ["_value_check"], parameter_text)
    if value_mapped is not None and not _bare_room_target(
        target_text, domain_choice, allow_all=True, require_domain=False
    ):
        return RouteResult(kind="reject", reason="unknown_named_target", classification=classification)
    if (
        classification.action.choice in {"set_temperature", "set_position", "set_tilt"}
        and len(re.findall(r"(?<!\w)-?\d+(?:[.,]\d+)?", parameter_text)) > 1
    ):
        return RouteResult(kind="grok", reason="mixed_values", classification=classification)
    if classification.action.choice == "set_color":
        from .light_map import NAMED_COLORS

        if len([word for word in target_text.split() if word in NAMED_COLORS]) != 1:
            return RouteResult(kind="grok", reason="color_unparsed", classification=classification)
    if ROOM_REFERENCE.search(utterance) and not room and not named_areas and not explicit_names:
        return RouteResult(kind="reject", reason="device_room_missing", classification=classification)
    if explicit_names:
        targets, target_reason = explicit_names, None
    elif not named_areas and PRONOUN_REFERENCE.search(utterance):
        if (
            not followup_entity_ids
            and _FAST_SERVICE_CALLS[domain_choice](classification.action.choice, ["_value_check"], parameter_text)
            is None
        ):
            return RouteResult(
                kind="grok",
                reason=_UNPARSED_REASONS.get(classification.action.choice, "action_unmapped"),
                classification=classification,
            )
        wanted = set(followup_entity_ids)
        targets = [item for item in exposed if item.entity_id in wanted and item.domain == domain_choice]
        if not wanted or len(targets) != len(wanted):
            return RouteResult(kind="reject", reason="followup_target_missing", classification=classification)
        target_reason = None
    else:
        if (
            not whole_home
            and not named_areas
            and not explicit_names
            and room
            and _bare_room_target(utterance, domain_choice)
        ):
            target_area = room
        targets, target_reason = _resolve_targets(
            utterance,
            exposed,
            domain_choice,
            target_area,
            named_areas,
            action=classification.action.choice,
        )
    if not targets:
        kind: RouteKind = "reject" if (target_reason or "").startswith("no_exposed_") else "grok"
        return RouteResult(
            kind=kind,
            reason=target_reason or "no_named_or_area_target",
            classification=classification,
        )

    mapped = _FAST_SERVICE_CALLS[domain_choice](
        classification.action.choice,
        [item.entity_id for item in targets],
        parameter_text,
    )
    if mapped is None:
        return RouteResult(
            kind="grok",
            reason=_UNPARSED_REASONS.get(classification.action.choice, "action_unmapped"),
            classification=classification,
        )
    domain, service, data = mapped
    return RouteResult(
        kind="fast_service",
        reason=_FAST_REASONS[domain_choice],
        domain=domain,
        service=service,
        service_data=data,
        classification=classification,
        target_entity_ids=tuple(item.entity_id for item in targets),
    )


def _bare_room_target(utterance: str, domain: str, *, allow_all: bool = False, require_domain: bool = True) -> bool:
    """Only a generic device phrase may take the robot's room implicitly."""
    from .light_map import _NUMBER_WORDS, NAMED_COLORS

    words = _words(utterance)
    if (
        require_domain
        and not words & _GENERIC_TOKENS_BY_DOMAIN.get(domain, frozenset())
        or not allow_all
        and has_unscoped_all(utterance)
    ):
        return False
    allowed = (
        _STOP_TOKENS
        | _GENERIC_TOKENS_BY_DOMAIN.get(domain, frozenset())
        | {
            "switch",
            "brightness",
            "dim",
            "dimm",
            "dimme",
            "helligkeit",
            "percent",
            "prozent",
            "degrees",
            "degree",
            "grad",
            "celsius",
            "color",
            "colour",
            "farbe",
            "here",
            "this",
            "room",
            "hier",
            "diesem",
            "raum",
            "at",
            "open",
            "close",
            "stop",
            "öffne",
            "schließe",
            "position",
            "tilt",
            "heat",
            "cool",
            "auto",
            "heizen",
            "kühlen",
            "mode",
            "modus",
            "lamellen",
            "neigung",
            "slats",
            "slat",
            "c",
            "f",
            "fahrenheit",
            "procent",
            "hvac",
            "fan_only",
            "heat_cool",
            "dry",
            "fan",
            "only",
            "heatcool",
            "um",
            "umschalten",
            "an",
            "ein",
            "öffnen",
            "oeffne",
            "schließen",
            "schliessen",
            "schließe",
            "schliesse",
            "öffne",
            "them",
            "that",
            "one",
            "those",
            "es",
            "sie",
            "theirs",
            "start",
            "enable",
            "disable",
            "or",
            "oder",
        }
        | ({"garage", "door"} if domain == DOMAIN_COVER else set())
        | set(NAMED_COLORS)
        | {token for number in _NUMBER_WORDS for token in number.split()}
    )
    return all(word in allowed or word.isdecimal() for word in words)


async def route(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    *,
    language: str,
    client: JevClientProtocol,
    room: str | None = None,
    followup_entity_ids: Sequence[str] = (),
) -> RouteResult:
    """Read supported questions locally; classify and gate other requests."""
    from .home_query import parse_home_query

    query = parse_home_query(utterance, exposed, room=room, followup_entity_ids=followup_entity_ids)
    if query is not None:
        return RouteResult(
            kind="fast_query", reason=query.reason, target_entity_ids=query.entity_ids, query_property=query.property
        )
    contextual_classify = getattr(client, "classify_with_context", None)
    if contextual_classify is not None and (room or followup_entity_ids):
        classification = await contextual_classify(
            utterance,
            exposed,
            language=normalize_language(language),
            room=room,
            followup_entity_ids=followup_entity_ids,
        )
    else:
        classification = await client.classify(utterance, exposed, language=normalize_language(language))
    return apply_gates(utterance, exposed, classification, room=room, followup_entity_ids=followup_entity_ids)
