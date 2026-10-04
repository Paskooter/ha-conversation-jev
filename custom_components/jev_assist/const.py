"""Constants for the Jev Assist integration."""

from typing import Final

DOMAIN: Final = "jev_assist"
DEFAULT_NAME: Final = "Jev Assist"

# TypeSafe / Jev
TYPESAFE_MODEL: Final = "jev-latest"
TYPESAFE_BASE_URL: Final = "https://api.typesafe.ai"
OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api"
PROVIDER_OPENROUTER: Final = "openrouter"
PROVIDER_TYPESAFE: Final = "typesafe"
PROVIDER_URLS: Final = {
    PROVIDER_OPENROUTER: OPENROUTER_BASE_URL,
    PROVIDER_TYPESAFE: TYPESAFE_BASE_URL,
}
EXPOSED_ENTITY_CAP: Final = 80

CONF_TYPESAFE_API_KEY: Final = "typesafe_api_key"
CONF_PROVIDER: Final = "provider"
CONF_API_KEY: Final = "api_key"

# Router gates (CONTRACT.md, blessed). Thresholds are code policy.
FAST_MIN_CONFIDENCE: Final = 0.80
NOUL_YES_THRESHOLD: Final = 0.55
# Noul has no separate confidence; values near 0.5 mean yes ≈ no (unsure).
NOUL_UNSURE_LOW: Final = 0.40
REJECT_MIN_CONFIDENCE: Final = 0.80

# TypeSafe Python SDK defaults (docs: RetryPolicy.max_retries=2, DEFAULT_TIMEOUT=10.0).
# Classifier requests never execute actions. Bound the whole classify call so
# Phoenix's 7.5s voice deadline still has room for local execution and speech.
TYPESAFE_RETRY_MAX: Final = 0
TYPESAFE_TIMEOUT: Final = 4.0

CATEGORY_COMMAND: Final = "command"
CATEGORY_CONVERSATION: Final = "conversation"
CATEGORY_REJECT: Final = "reject"
DOMAIN_LIGHT: Final = "light"
DOMAIN_CLIMATE: Final = "climate"
DOMAIN_COVER: Final = "cover"
TARGET_NONE: Final = "none"
TARGET_UNKNOWN: Final = "unknown"
SCOPE_NAMED_ENTITY: Final = "named_entity"
SCOPE_NAMED_AREA: Final = "named_area"
SCOPE_WHOLE_HOME: Final = "whole_home"
SCOPE_UNSPECIFIED: Final = "unspecified"

SUPPORTED_LANGUAGES: Final = ("en", "de")
DEFAULT_LANGUAGE: Final = "en"

# SpaceXAI umbrella conversation entity (luxus/HA-xAI-Custom-TTS domain spacexai).
# Override with config-entry options/data key grok_handoff_agent_id.
GROK_HANDOFF_AGENT_ID: Final = "conversation.spacexai_grok"
CONF_GROK_HANDOFF_AGENT_ID: Final = "grok_handoff_agent_id"
GROK_HANDOFF_UNAVAILABLE_SPEECH: Final = "Grok is not available."
# Spoken when classify/route/fast_service fails; never raise into Assist.
ROUTE_FAILURE_SPEECH: Final = "I can't help with that."
