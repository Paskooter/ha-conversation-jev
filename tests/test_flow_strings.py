"""Every owner-visible setup field and provider error has a translation."""

import json
from pathlib import Path

ROOT = Path("custom_components/jev_assist")


def test_localized_provider_and_fallback_fields():
    source = json.loads((ROOT / "strings.json").read_text())
    assert json.loads((ROOT / "translations/en.json").read_text()) == source
    for data in [source, json.loads((ROOT / "translations/de.json").read_text())]:
        assert set(data["selector"]["provider"]["options"]) == {
            "openrouter",
            "typesafe",
        }
        for name in ["user", "reconfigure", "reauth_confirm"]:
            assert set(data["config"]["step"][name]["data"]) == {"provider", "api_key"}
        assert "grok_handoff_agent_id" in data["options"]["step"]["init"]["data"]
        assert set(data["config"]["error"]) >= {
            "invalid_auth",
            "cannot_connect",
            "rate_limited",
            "provider_error",
        }
