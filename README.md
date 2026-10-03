# Jev Assist with OpenRouter

Owner beta **0.2.0b1**. A fork of [luxus/ha-conversation-jev](https://github.com/luxus/ha-conversation-jev), preserving its Jev classifier, confidence gates and light/climate/cover routing. Tested with real isolated Home Assistant **2026.8.1 and 2026.9.4** on Python 3.14.

Choose **OpenRouter** during setup to charge Jev classification to your OpenRouter account. A separate TypeSafe account is unnecessary. Direct TypeSafe keys remain supported. Jev uses `jev-latest` through the official [System One API](https://openrouter.ai/docs/guides/community/typesafe-sdk); it is a classifier, not a chat model.

Simple, confident commands execute locally against Assist-exposed devices. Other requests go once to your explicitly selected conversation agent. For Grok, install SpaceXAI and sign in there with your xAI account. Jev does not create a Grok agent or store a second Grok login. Without Grok, Home Assistant's built-in agent is available as the fallback.

## Install from HACS

1. Open HACS → menu → **Custom repositories**.
2. Add `https://github.com/Paskooter/ha-conversation-jev`, category **Integration**.
3. Download **Jev Assist**. Enable beta/prerelease versions and select **0.2.0b1**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Jev Assist**.
6. Select **OpenRouter** and enter your OpenRouter API key. Setup makes one small synthetic classification request to check credentials, using no household metadata.

If the original Jev integration is already installed, use this fork instead of that HACS repository. Both use `custom_components/jev_assist`; install only one copy. Existing direct TypeSafe entries retain their provider and key. See [upgrade and removal](docs/setup.md#upgrade-and-removal).

For manual installation, download `jev_assist.zip` from the [beta release](https://github.com/Paskooter/ha-conversation-jev/releases/tag/v0.2.0b1), create `custom_components/jev_assist` in your HA configuration directory, and extract the archive's files directly there. The path must end in `custom_components/jev_assist/manifest.json`. Restart HA.

## Connect Grok and Jibo

Follow [the complete owner setup guide](docs/setup.md). The three relevant settings are:

| Setting | Choose |
| --- | --- |
| Jev Assist → Configure → Fallback conversation agent | SpaceXAI's **Grok** agent, after signing in in SpaceXAI |
| Home Assistant voice assistant → Conversation agent | **Jev Assist**, to use it in Home Assistant Assist |
| Phoenix **0.1.0b4+** → Configure → Conversation agent | **Jev Assist**, to use it for Jibo's home commands |

Changing the default Assist pipeline alone does **not** change Jibo's agent. Phoenix defaults to Home Assistant's built-in agent until you opt in. Jibo keeps its existing recognition and voice; SpaceXAI TTS and STT are unnecessary for this connection.

## Commands and boundaries

The deterministic fast path supports lights on/off/toggle and numeric brightness, climate setpoint/on/off/mode, and covers open/close/stop/numeric position/tilt. Only explicitly resolved Assist-exposed targets are eligible. Whole-home targeting cannot silently expand to every exposed device. Other domains, colors, spelled-out brightness and mixed operations go to the selected fallback agent, whose capabilities and exposure settings govern them.

Try these in Home Assistant's text Assist **after selecting Jev Assist and entering your key**:

- `Turn off the kitchen lights.`
- `Turn on the kitchen lights.`
- `Set bedroom light brightness to 50 percent.`

These routing cases are tested with synthetic classifier answers and actual HA services. Live Jev inference with an owner's key and Grok subscription entitlement remain installation checks; this beta does not claim their accuracy or latency from mocked responses. Device names, aliases and areas still need to match your household. An AI agent cannot supply a missing Kitchen area or grant itself access to an unexposed light.

For Jibo, say “Hey Jibo” first. Use **“ask Home Assistant to…”** for a custom phrase. Phoenix still selects a home-command route before invoking any HA agent, preserving ordinary Jibo commands and active skill responses.

## Reliability and privacy

The classifier has a four-second overall deadline and sends one request without retries. A service action executes once. Light on/off/toggle and brightness wait up to two seconds for the resolved states to confirm. An exception or missing confirmation returns uncertainty; the integration never hands off after an action has started. Unavailable targets are reported honestly, including partial results.

Only Assist-exposed entity identifiers, names, aliases and areas, the utterance and language are sent to the selected Jev provider (at most 80 entities in classifier state). The fallback agent manages its own provider data. Keys stay in HA's config entry; diagnostics omit keys, tokens, names, utterances and agent identifiers. Never share `.storage/core.config_entries`. Errors log exception types rather than provider response bodies or household utterances.

See [setup, troubleshooting, upgrade and removal](docs/setup.md), [validation](docs/validation.md), [development](CONTRIBUTING.md), and [the routing contract](CONTRACT.md).
