# Jev Assist with OpenRouter

Owner beta **0.3.0b1**. A fork of [luxus/ha-conversation-jev](https://github.com/luxus/ha-conversation-jev), preserving its Jev classifier, confidence gates and light/climate/cover routing. Adds named colors, spelled brightness, exact scenes/scripts, local state questions and brief device context. Tested with real isolated Home Assistant **2026.8.1 and 2026.9.4** on Python 3.14.

Choose **OpenRouter** during setup to charge Jev classification to your OpenRouter account. A separate TypeSafe account is unnecessary. Direct TypeSafe keys remain supported. Jev uses `jev-latest` through the official [System One API](https://openrouter.ai/docs/guides/community/typesafe-sdk); it is a classifier, not a chat model.

Simple, confident commands execute locally against Assist-exposed devices. Other requests go once to your explicitly selected conversation agent. For Grok, install SpaceXAI and sign in there with your xAI account. Jev does not create a Grok agent or store a second Grok login. Without Grok, Home Assistant's built-in agent is available as the fallback.

## Install from HACS

1. Open HACS → menu → **Custom repositories**.
2. Add `https://github.com/Paskooter/ha-conversation-jev`, category **Integration**.
3. Download **Jev Assist**. Enable beta/prerelease versions and select **0.3.0b1**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Jev Assist**.
6. Select **OpenRouter** and enter your OpenRouter API key. Setup makes one small synthetic classification request to check credentials, using no household metadata.

If the original Jev integration is already installed, use this fork instead of that HACS repository. Both use `custom_components/jev_assist`; install only one copy. Existing direct TypeSafe entries retain their provider and key. See [upgrade and removal](docs/setup.md#upgrade-and-removal).

For manual installation, download `jev_assist.zip` from the [beta release](https://github.com/Paskooter/ha-conversation-jev/releases/tag/v0.3.0b1), create `custom_components/jev_assist` in your HA configuration directory, and extract the archive's files directly there. The path must end in `custom_components/jev_assist/manifest.json`. Restart HA.

## Connect Grok and Jibo

Follow [the complete owner setup guide](docs/setup.md). The three relevant settings are:

| Setting | Choose |
| --- | --- |
| Jev Assist → Configure → Fallback conversation agent | SpaceXAI's **Grok** agent, after signing in in SpaceXAI |
| Home Assistant voice assistant → Conversation agent | **Jev Assist**, to use it in Home Assistant Assist |
| Phoenix **0.2.0b1+** → Configure → Conversation agent | **Jev Assist**, to use it with robot room context and brief follow-ups |

Changing the default Assist pipeline alone does **not** change Jibo's agent. Phoenix defaults to Home Assistant's built-in agent until you opt in. Jibo keeps its existing recognition and voice; SpaceXAI TTS and STT are unnecessary for this connection.

## Commands and boundaries

The deterministic fast path supports lights on/off/toggle, absolute numeric or spelled brightness from zero to one hundred percent, and the named colors red, green, blue, yellow, orange, purple, pink, white, cyan and magenta. Color requires a light that supports color. Climate setpoint/on/off/mode and covers open/close/stop/numeric position/tilt retain their existing paths. One exactly named Assist-exposed scene or script can be started; Jev does not infer a routine or report its downstream effects as confirmed.

State questions read current Assist-exposed values locally, without a classifier, service call or fallback tools. Supported answers include on/off, open/closed, locked/unlocked, light brightness/color, cover position/tilt, climate current/target temperature and humidity, numeric sensor values and door/window or detection sensors. Unknown or unavailable values are reported honestly; a question with an unresolved target stays local.

Assign each Phoenix robot's Home Assistant device to an area to use “here” or a plain “turn off the lights” for that room. Explicit names and rooms take precedence. When HA supplies a registered device and conversation ID, successful local targets can support “turn it off” or “set it to fifty percent” for **30 seconds**. Context stays in memory, is separated by device, conversation and user, and resets when Jev reloads. Phoenix discards its conversation IDs on disconnect, restart and agent changes. Whole-home wording cannot expand the room or retained target.

Only explicitly resolved Assist-exposed targets are eligible, with exposure checked again before execution or a state answer. Full names and aliases take precedence over room targeting; shared name fragments or an unknown name cannot select another device. Other control domains, relative values, unsupported colors and mixed operations go to the selected fallback agent, whose capabilities and exposure settings govern them.

Try these in Home Assistant's text Assist **after selecting Jev Assist and entering your key**:

- `Turn off the kitchen lights.`
- `Turn on the kitchen lights.`
- `Set bedroom light brightness to 50 percent.`
- `Set bedroom light brightness to fifty percent.`
- `Set bedroom light to blue.`
- `Activate Reading Time scene.`
- `Is the bedroom light on?`

These routing cases are tested with synthetic classifier answers and actual HA services. Live Jev inference with an owner's key and Grok subscription entitlement remain installation checks; this beta does not claim their accuracy or latency from mocked responses. Device names, aliases and areas still need to match your household. An AI agent cannot supply a missing Kitchen area or grant itself access to an unexposed light.

For Jibo, say “Hey Jibo” first. Use **“ask Home Assistant to…”** for a custom phrase. Phoenix still selects a home-command route before invoking any HA agent, preserving ordinary Jibo commands and active skill responses.

## Reliability and privacy

The classifier has a four-second overall deadline and sends one request without retries. A service action executes once. Light on/off/toggle, brightness and color wait up to two seconds for the resolved states to confirm. An exception or missing confirmation returns uncertainty; the integration never hands off after an action has started. Unavailable or unsupported targets are reported honestly, including partial results.

Only Assist-exposed entity identifiers, names, aliases and areas, the utterance and language are sent to the selected Jev provider (at most 80 entities in classifier state). Device context adds only its area and still-visible retained target IDs, without robot, user or conversation identifiers. Current state values remain local for supported questions. The fallback agent manages its own provider data. Keys stay in HA's config entry; diagnostics contain aggregate route counts and omit keys, tokens, names, utterances and identifiers. Phoenix supplies separate per-robot diagnostics. Never share `.storage/core.config_entries`. Errors log exception types rather than provider response bodies or household utterances.

See [setup, troubleshooting, upgrade and removal](docs/setup.md), [validation](docs/validation.md), [development](CONTRIBUTING.md), and [the routing contract](CONTRACT.md).
