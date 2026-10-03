"""Shared fakes for Jev router tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from custom_components.jev_assist.jev_router import (
    ChoiceView,
    ExposedEntity,
    JevClassification,
    NoulView,
)

LIVING_LAMP = ExposedEntity(
    entity_id="light.living_lamp",
    domain="light",
    name="Living lamp",
    area="Living room",
)

SCHLAFZIMMER_LIGHT = ExposedEntity(
    entity_id="light.schlafzimmer",
    domain="light",
    name="Schlafzimmerlampe",
    area="Schlafzimmer",
)

FLUR_LIGHT = ExposedEntity(
    entity_id="light.flur",
    domain="light",
    name="Flurlicht",
    area="Flur",
)

WOHNZIMMER_LIGHT = ExposedEntity(
    entity_id="light.wohnzimmer",
    domain="light",
    name="Wohnzimmerlampe",
    area="Wohnzimmer",
)

BEDROOM_LIGHT = ExposedEntity(
    entity_id="light.bedroom",
    domain="light",
    name="Bedroom lamp",
    area="bedroom",
)

HALLWAY_LIGHT = ExposedEntity(
    entity_id="light.hallway",
    domain="light",
    name="Hallway lamp",
    area="hallway",
)

LIVING_CLIMATE = ExposedEntity(
    entity_id="climate.living",
    domain="climate",
    name="Living thermostat",
    area="Living room",
)

BEDROOM_COVER = ExposedEntity(
    entity_id="cover.bedroom_blind",
    domain="cover",
    name="Bedroom blind",
    area="bedroom",
)


def choice(label: str, confidence: float = 0.95) -> ChoiceView:
    return ChoiceView(choice=label, confidence=confidence, probabilities={label: confidence})


def noul(p_yes: float) -> NoulView:
    return NoulView(noul=p_yes)


def classification(
    *,
    category: str = "command",
    category_c: float = 0.95,
    domain: str = "light",
    domain_c: float = 0.95,
    action: str = "turn_off",
    action_c: float = 0.95,
    target_area: str = "Living room",
    target_c: float = 0.95,
    scope: str = "unspecified",
    scope_c: float = 0.95,
    needs_llm: float = 0.05,
    is_compound: float = 0.05,
) -> JevClassification:
    return JevClassification(
        category=choice(category, category_c),
        domain=choice(domain, domain_c),
        action=choice(action, action_c),
        scope=choice(scope, scope_c),
        target_area=choice(target_area, target_c),
        needs_llm=noul(needs_llm),
        is_compound=noul(is_compound),
    )


@dataclass
class FakeJevClient:
    result: JevClassification
    last_utterance: str | None = None
    last_language: str | None = None

    async def classify(
        self,
        utterance: str,
        exposed: Sequence[ExposedEntity],
        *,
        language: str,
    ) -> JevClassification:
        self.last_utterance = utterance
        self.last_language = language
        return self.result
