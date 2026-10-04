"""Exact exposed target names and bounded device-context phrases."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .jev_router import ExposedEntity


def normalize_numeric_signs(text: str) -> str:
    """Preserve minus/plus semantics before numeric value extraction."""
    return text.translate(str.maketrans({**dict.fromkeys("−‐‑‒–—﹣－", "-"), **dict.fromkeys("＋﹢", "+")}))


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[\w]+", str(text).casefold().replace("_", " ")))


def entity_names(entity: ExposedEntity) -> set[str]:
    object_name = entity.entity_id.split(".", 1)[-1].replace("_", " ")
    return {
        value
        for name in (entity.name, *entity.aliases, entity.entity_id, object_name if " " in object_name else "")
        if (value := normalized(name))
    }


def exact_named_targets(text: str, exposed: Sequence[ExposedEntity]) -> list[ExposedEntity]:
    """Prefer the longest full name/alias; collisions remain ambiguous."""
    utterance = f" {normalized(text)} "
    matches = [
        (match.start(), match.end(), item)
        for item in exposed
        for name in entity_names(item)
        for match in re.finditer(r"(?<= )" + re.escape(name) + r"(?= )", utterance)
    ]
    if not matches:
        return []
    # Prefer longer names only where their spans overlap. Separate targets and
    # duplicate aliases stay visible as ambiguity instead of disappearing.
    ids = {
        item.entity_id
        for start, end, item in matches
        if not any(
            other_start <= start and other_end >= end and other_end - other_start > end - start
            for other_start, other_end, _ in matches
        )
    }
    return [item for item in exposed if item.entity_id in ids]


def exact_routine_targets(text: str, exposed: Sequence[ExposedEntity], domain: str) -> list[ExposedEntity]:
    """A routine is exactly one explicitly named scene/script, with no tail."""
    utterance = normalized(text)
    utterance = re.sub(r"^(?:please|bitte) ", "", utterance)
    utterance = re.sub(r" (?:please|bitte)$", "", utterance)
    if domain == "scene":
        verbs, nouns = ("activate", "start", "turn on", "aktiviere", "aktivieren", "starte"), ("scene", "szene")
    else:
        verbs, nouns = ("run", "start", "turn on", "activate", "starte", "aktiviere", "führe"), ("script", "skript")
    found = []
    for item in exposed:
        if item.domain != domain:
            continue
        targets = entity_names(item)
        phrases = set(targets)
        for name in targets:
            for noun in nouns:
                phrases.update((f"{noun} {name}", f"{name} {noun}"))
        allowed = {
            f"{verb} {article}{phrase}{suffix}"
            for verb in verbs
            for phrase in phrases
            for article in ("", "the ", "my ", "die ", "das ")
            for suffix in ("", " aus" if verb == "führe" else "")
        }
        if utterance in allowed:
            found.append(item)
    return found


ROOM_REFERENCE = re.compile(r"\b(?:here|in this room|this room|hier|in diesem raum|diesem raum)\b", re.IGNORECASE)
PRONOUN_REFERENCE = re.compile(r"\b(?:it|them|that one|those|es|sie)\b", re.IGNORECASE)
WHOLE_HOME_REFERENCE = re.compile(
    r"\b(?:whole (?:home|house)|entire (?:home|house)|everywhere|all rooms|ganzes haus|ganzen haus|überall|alle räume)\b",
    re.IGNORECASE,
)


def has_unscoped_all(text: str) -> bool:
    return bool(WHOLE_HOME_REFERENCE.search(text) or re.search(r"\b(?:all|every|alle|alles)\b", text, re.IGNORECASE))
