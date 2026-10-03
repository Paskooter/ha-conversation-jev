"""TypeSafe SDK wrapper: AsyncTypeSafeClient + jev-latest system_one."""

from __future__ import annotations

import asyncio
from typing import Any, Sequence

import httpcore2  # noqa: F401 — preload httpx2's otherwise lazy transport imports
import httpx2
from homeassistant.util.ssl import get_default_context
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    Noul,
    RetryPolicy,
    SystemOneResponse,
)

from . import criteria
from .const import (
    EXPOSED_ENTITY_CAP,
    PROVIDER_TYPESAFE,
    PROVIDER_URLS,
    TARGET_NONE,
    TARGET_UNKNOWN,
    TYPESAFE_MODEL,
    TYPESAFE_RETRY_MAX,
    TYPESAFE_TIMEOUT,
)
from .jev_router import (
    ChoiceView,
    ExposedEntity,
    JevClassification,
    NoulView,
    normalize_language,
)


def _new_http_client() -> httpx2.AsyncClient:
    """Use HA's warmed TLS context without certificate I/O in the event loop."""
    return httpx2.AsyncClient(
        verify=get_default_context(), trust_env=False, follow_redirects=False, timeout=TYPESAFE_TIMEOUT
    )


def localized_options(options: dict[str, dict[str, str]], language: str) -> dict[str, str]:
    """Pick the language string for each option key."""
    return {key: value[language] for key, value in options.items()}


def unique_areas(exposed: Sequence[ExposedEntity]) -> list[str]:
    """Stable unique area names from exposed entities."""
    seen: list[str] = []
    for item in exposed:
        if not item.area:
            continue
        area = str(item.area)
        if area not in seen:
            seen.append(area)
    return seen


def _plain_text(value: object) -> str:
    return str(value)


def _plain_optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def build_state(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    language: str,
) -> dict[str, Any]:
    """Named JSON object for system_one (utterance, language, entities, areas).

    Pass the dict through to the SDK — do not stringify first. Alias/name/area
    values are coerced to ``str`` so HA ``ComputedNameType`` never reaches JSON.
    """
    capped = list(exposed)[:EXPOSED_ENTITY_CAP]
    return {
        "utterance": _plain_text(utterance),
        "language": _plain_text(language),
        "exposed_entities": [
            {
                "entity_id": _plain_text(item.entity_id),
                "domain": _plain_text(item.domain),
                "name": _plain_text(item.name),
                "area": _plain_optional_text(item.area),
                "aliases": [_plain_text(alias) for alias in item.aliases],
            }
            for item in capped
        ],
        "areas": unique_areas(capped),
    }


def build_questions(language: str, areas: Sequence[str]) -> dict[str, Choice | Noul]:
    """Speculative fan-out: all Choice/Noul questions in one system_one call."""
    # Area names may be HA ComputedNameType Enums; Choice criteria must stay JSON-safe.
    area_criteria: dict[str, str] = {_plain_text(area): _plain_text(area) for area in areas}
    area_criteria[TARGET_NONE] = criteria.TARGET_AREA_NONE[language]
    area_criteria[TARGET_UNKNOWN] = criteria.TARGET_AREA_UNKNOWN[language]
    return {
        "category": Choice(
            instructions=criteria.CATEGORY_INSTRUCTIONS[language],
            criteria=localized_options(criteria.CATEGORY_OPTIONS, language),
        ),
        "domain": Choice(
            instructions=criteria.DOMAIN_INSTRUCTIONS[language],
            criteria=localized_options(criteria.DOMAIN_OPTIONS, language),
        ),
        "action": Choice(
            instructions=criteria.ACTION_INSTRUCTIONS[language],
            criteria=localized_options(criteria.ACTION_OPTIONS, language),
        ),
        "scope": Choice(
            instructions=criteria.SCOPE_INSTRUCTIONS[language],
            criteria=localized_options(criteria.SCOPE_OPTIONS, language),
        ),
        "target_area": Choice(
            instructions=criteria.TARGET_AREA_INSTRUCTIONS[language],
            criteria=area_criteria,
        ),
        "needs_llm": Noul(
            instructions=criteria.NOUL_NEEDS_LLM[language],
            criteria=localized_options(criteria.NOUL_NEEDS_LLM_CRITERIA, language),
        ),
        "is_compound": Noul(
            instructions=criteria.NOUL_IS_COMPOUND[language],
            criteria=localized_options(criteria.NOUL_IS_COMPOUND_CRITERIA, language),
        ),
    }


def _choice_view(result: SystemOneResponse, name: str) -> ChoiceView:
    answer = None
    answers = getattr(result, "answers", None)
    if isinstance(answers, dict):
        answer = answers.get(name)
    if answer is None:
        choices = getattr(result, "choices", None)
        if isinstance(choices, dict):
            answer = choices.get(name)
    if answer is None:
        raise KeyError(name)
    return ChoiceView(
        choice=str(answer.choice),
        confidence=float(answer.confidence),
        probabilities=dict(getattr(answer, "probabilities", {}) or {}),
    )


def _noul_view(result: SystemOneResponse, name: str) -> NoulView:
    answer = None
    answers = getattr(result, "answers", None)
    if isinstance(answers, dict):
        answer = answers.get(name)
    if answer is None:
        nouls = getattr(result, "nouls", None)
        if isinstance(nouls, dict):
            answer = nouls.get(name)
    if answer is None:
        raise KeyError(name)
    return NoulView(noul=float(answer.noul))


def classification_from_sdk(result: SystemOneResponse) -> JevClassification:
    """Normalize SDK SystemOneResponse (answers or choices/nouls)."""
    return JevClassification(
        category=_choice_view(result, "category"),
        domain=_choice_view(result, "domain"),
        action=_choice_view(result, "action"),
        scope=_choice_view(result, "scope"),
        target_area=_choice_view(result, "target_area"),
        needs_llm=_noul_view(result, "needs_llm"),
        is_compound=_noul_view(result, "is_compound"),
    )


class TypeSafeJevClient:
    """Thin async wrapper around ``AsyncTypeSafeClient``."""

    def __init__(
        self,
        api_key: str,
        *,
        provider: str = PROVIDER_TYPESAFE,
        model: str = TYPESAFE_MODEL,
    ) -> None:
        self._api_key = api_key
        self._model = model
        # Explicit, fixed URLs prevent environment variables from sending one
        # provider's key or household metadata to a different destination.
        self._base_url = PROVIDER_URLS[provider]

    async def async_validate(self) -> None:
        """Validate credentials through System One without sending household data."""
        async with asyncio.timeout(TYPESAFE_TIMEOUT), self._client() as client:
            await client.system_one(
                state={"connection_test": "synthetic"},
                questions={"connection": Noul(instructions="Is this a connection test?")},
            )

    def _client(self) -> AsyncTypeSafeClient:
        return AsyncTypeSafeClient(
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
            retry=RetryPolicy(max_retries=TYPESAFE_RETRY_MAX),
            timeout=TYPESAFE_TIMEOUT,
            http_client=_new_http_client(),
        )

    async def classify(
        self,
        utterance: str,
        exposed: Sequence[ExposedEntity],
        *,
        language: str,
    ) -> JevClassification:
        lang = normalize_language(language)
        capped = list(exposed)[:EXPOSED_ENTITY_CAP]
        state = build_state(utterance, capped, lang)
        questions = build_questions(lang, unique_areas(capped))
        async with asyncio.timeout(TYPESAFE_TIMEOUT), self._client() as client:
            result = await client.system_one(state=state, questions=questions)
        return classification_from_sdk(result)
