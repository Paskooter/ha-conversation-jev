"""Light service map and bounded, deterministic value parsing."""

from __future__ import annotations

import re
from typing import Any, Final

from .local_targets import normalize_numeric_signs

# Only these Jev actions map to a Home Assistant light service.
LIGHT_ACTION_MAP: Final[dict[str, tuple[str, str]]] = {
    "turn_on": ("light", "turn_on"),
    "turn_off": ("light", "turn_off"),
    "toggle": ("light", "toggle"),
    "set_brightness": ("light", "turn_on"),
    "set_color": ("light", "turn_on"),
}

BRIGHTNESS_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?<![\w.,\-])(?P<value>\d{1,3})
    \s*
    (?:
        %
        | (?:percent | procent | prozent)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
_DE_ONES = "null eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn".split()
_DE_TENS = "zwanzig dreißig vierzig fünfzig sechzig siebzig achtzig neunzig".split()
_NUMBER_WORDS = {word: index for index, word in enumerate(_ONES)}
_NUMBER_WORDS.update({word: index for index, word in enumerate(_DE_ONES)})
for _index, _word in enumerate(_TENS, 2):
    _NUMBER_WORDS[_word] = _index * 10
    for _unit in range(1, 10):
        _NUMBER_WORDS[f"{_word} {_ONES[_unit]}"] = _index * 10 + _unit
for _index, _word in enumerate(_DE_TENS, 2):
    _NUMBER_WORDS[_word] = _index * 10
    for _unit in range(1, 10):
        _NUMBER_WORDS[f"{'ein' if _unit == 1 else _DE_ONES[_unit]}und{_word}"] = _index * 10 + _unit
_NUMBER_WORDS.update({"one hundred": 100, "a hundred": 100, "hundred": 100, "hundert": 100, "einhundert": 100})
_NUMBER_WORDS.update(
    {key.replace("ß", "ss").replace("ü", "ue").replace("ö", "oe"): value for key, value in list(_NUMBER_WORDS.items())}
)
_WORD_VALUES = "|".join(re.escape(word).replace(r"\ ", "[ -]") for word in sorted(_NUMBER_WORDS, key=len, reverse=True))
_SPELLED_PERCENT = re.compile(rf"\b(?P<value>{_WORD_VALUES})\s*(?:%|percent\b|procent\b|prozent\b)", re.IGNORECASE)
_SPELLED_BRIGHTNESS = re.compile(
    rf"\b(?:brightness|helligkeit|dim(?:\s+to)?|dimm(?:en|stufe)?)\s*(?:auf|to|=|:)?\s*(?P<value>{_WORD_VALUES})\b",
    re.IGNORECASE,
)
_NUMBER_TOKENS = {token for word in _NUMBER_WORDS for token in word.split()} | {
    "minus",
    "negative",
    "hundreds",
    "thousand",
    "tausend",
}

# Deliberately small vocabulary: modifiers and arbitrary CSS colors need the fallback.
NAMED_COLORS: Final[dict[str, tuple[int, int, int]]] = {
    "red": (255, 0, 0),
    "rot": (255, 0, 0),
    "green": (0, 128, 0),
    "grün": (0, 128, 0),
    "gruen": (0, 128, 0),
    "blue": (0, 0, 255),
    "blau": (0, 0, 255),
    "yellow": (255, 255, 0),
    "gelb": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "lila": (128, 0, 128),
    "violett": (128, 0, 128),
    "pink": (255, 192, 203),
    "rosa": (255, 192, 203),
    "white": (255, 255, 255),
    "weiß": (255, 255, 255),
    "weiss": (255, 255, 255),
    "cyan": (0, 255, 255),
    "türkis": (0, 255, 255),
    "tuerkis": (0, 255, 255),
    "magenta": (255, 0, 255),
}
_COLOR_END = re.compile(r"\b(" + "|".join(NAMED_COLORS) + r")\s*[.!?]*\s*(?:(?:please|bitte)[.!?]*)?$", re.IGNORECASE)


def parse_color_rgb(utterance: str) -> tuple[int, int, int] | None:
    """Read one supported final color, never invent modifiers or mixed colors."""
    match = _COLOR_END.search(utterance.strip())
    if not match:
        return None
    previous = re.findall(r"[a-zäöüß]+", utterance[: match.start()].casefold())
    if previous and previous[-1] in set(NAMED_COLORS) | {
        "and",
        "or",
        "und",
        "oder",
        "dark",
        "light",
        "warm",
        "cool",
        "pale",
        "dunkel",
        "hell",
        "kaltes",
        "warmes",
    }:
        return None
    return NAMED_COLORS[match.group(1).casefold()]


# DE/EN "brightness 40" / "Helligkeit 40" without a percent sign.
BRIGHTNESS_WORD_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?:
        brightness
        | helligkeit
        | dimm(?:er|en|stufe)?
        | dim(?:\s*to)?
    )
    \s*(?:auf|to|=|:)?\s*
    (?P<value>\d{1,3})
    (?![.,\d])\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_brightness_pct(utterance: str) -> int | None:
    """Return a 0–100 brightness percent if the utterance contains one."""
    utterance = normalize_numeric_signs(utterance)
    # More than one value is underspecified. Do not pick the first by accident.
    matches = list(BRIGHTNESS_RE.finditer(utterance)) + list(_SPELLED_PERCENT.finditer(utterance))
    if not matches:
        matches = list(BRIGHTNESS_WORD_RE.finditer(utterance)) + list(_SPELLED_BRIGHTNESS.finditer(utterance))
    if len(matches) != 1:
        return None
    match = matches[0]
    if re.search(r"[+\-]\s*$", utterance[: match.start("value")]):
        return None
    raw = match.group("value").casefold().replace("-", " ")
    value = int(raw) if raw.isdecimal() else _NUMBER_WORDS.get(raw)
    before = re.findall(r"[a-zäöüß]+", utterance[: match.start("value")].casefold())
    after = re.findall(r"[a-zäöüß]+", utterance[match.end("value") :].casefold())
    suffix = re.findall(r"[a-zäöüß]+", utterance[match.end() :].casefold())
    if (
        before
        and before[-1] in {"by", "um"}
        or suffix
        and suffix[0] in {"brighter", "darker", "higher", "lower", "heller", "dunkler"}
    ):
        return None
    if len(before) >= 2 and before[-1] in {"and", "und"} and before[-2] in _NUMBER_TOKENS:
        return None
    if before and before[-1] in _NUMBER_TOKENS or after and after[0] in _NUMBER_TOKENS:
        return None
    if value is None or not 0 <= value <= 100:
        return None
    return value


def light_service_call(
    action: str,
    entity_ids: list[str],
    utterance: str,
) -> tuple[str, str, dict[str, Any]] | None:
    """Map a Jev light action to (domain, service, data), or None if unmapped."""
    mapped = LIGHT_ACTION_MAP.get(action)
    if mapped is None or not entity_ids:
        return None
    domain, service = mapped
    data: dict[str, Any] = {
        "entity_id": entity_ids[0] if len(entity_ids) == 1 else entity_ids,
    }
    if action == "set_brightness":
        brightness = parse_brightness_pct(utterance)
        if brightness is None:
            return None
        data["brightness_pct"] = brightness
    elif action == "set_color":
        rgb = parse_color_rgb(utterance)
        if rgb is None:
            return None
        data["rgb_color"] = list(rgb)
    return domain, service, data
