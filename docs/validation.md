# Beta 0.3.0b1 local validation

Observed on 2026-10-04 with Python **3.14.8** and the pinned TypeSafe SDK
**0.7.2**. Both runs imported this checkout through `PYTHONPATH` into the
existing isolated Home Assistant environments; no shared environment was
modified and no live credentials or devices were used.

| Check | HA 2026.8.1 | HA 2026.9.4 |
| --- | --- | --- |
| Complete Jev suite | **266 passed** | **266 passed** |
| Ruff lint and format | Passed | Passed |
| Git whitespace checks | Passed | Passed |

The 127 new cases exercise absolute English/German spelled brightness, bounded
named colors, actual RGB and HS light service conversion/confirmation, missing
color support, lost confirmation without retry/handoff, exact named virgin
scene and script activation through actual HA services, and exposure changes
during classification. Existing climate setpoint/mode/on/off and cover
open/close/stop/position/tilt paths now also run through actual HA entities,
including dot/comma decimal climate setpoints. Relative brightness and
out-of-range phrases such as “one hundred and fifty” cannot become absolute
percentages by matching only a suffix.
Target names such as “Heating Thermostat” and “Thermostat 20” cannot supply the
HVAC mode or numeric setting; parameter parsing excludes resolved target names
and areas while preserving decimal values.
Complete numeric literal checks reject decimal cover values, negative signs
(including Unicode forms), oversized numbers and mixed values without issuing
a fast service call, using both compact and ordinary spaced actual HA phrases.
Actual ONOFF-only lights reject brightness before any
service, and malformed NaN, boolean or out-of-range brightness/HS observations
remain unconfirmed after one call with no retry or handoff.

Read-only query tests assert that provider classification and fallback are
never invoked, no device service occurs, hidden targets cannot be read, and
unknown/unavailable values remain distinct in partial HA query results. Tests
cover current light brightness, ambient temperature/humidity, binary-sensor
door/window state, climate current/target temperature and cover position/tilt.
Generic doors, windows, motion, blinds and garage doors filter the appropriate
device classes rather than including unrelated entities in the same domain.

Registered device room tests cover plain room commands, full names overriding
the robot room, 30-second pronoun context, cross-device isolation, expired and
unexposed targets, reload cleanup and aggregate diagnostics without identifiers.
Partial actions and queries discard target memory instead of letting a pronoun
silently select only their successful subset.
Target regressions reject unknown qualifiers and duplicate aliases, preserve
complete names sharing a word, and ensure explicitly named lights across two
rooms never expand to other lights in either room. The official HA alias
resolver handles computed-name aliases; area lookup has an explicit HA 2026.8.1
fallback. The real SDK serializer includes only visible retained target IDs in
context, without robot/device/user/conversation identifiers.

These tests replace only provider transport/classifier answers and use invented
local fixtures. They establish local behavior and API compatibility, not live
provider accuracy, latency or physical-robot operation. Release-archive and
hardware evidence for 0.3.0b1 belongs to the final coordinated release check.
The earlier evidence below is specifically for 0.2.0b1.

Official references checked for this work: [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python),
[TypeSafe confidence](https://docs.typesafe.ai/confidence),
[bounded value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook),
[OpenRouter TypeSafe adapter](https://openrouter.ai/docs/guides/community/typesafe-sdk),
[HA conversation API](https://developers.home-assistant.io/docs/intent_conversation_api/),
and [HA light actions and state](https://www.home-assistant.io/integrations/light/).

# Beta 0.2.0b1 validation

Observed on 2026-10-03. All devices, classifier responses and identities below are invented. No household changes were made for this fork.

Both exact flat release archives (`jev_assist.zip` and `phoenix.zip`) were extracted into a fresh isolated HA configuration. HA loaded only the extracted source, validated Jev with synthetic provider transport, linked Phoenix through the real isolated TLS broker, changed its selected agent without relinking, and unloaded/reloaded/removed both integrations. No device action was issued during this archive-install check.

| Check | HA 2026.8.1 | HA 2026.9.4 |
| --- | --- | --- |
| Jev repository suite | 139 passed | 139 passed |
| Phoenix connector suite with Jev installed | 20 passed | 20 passed |
| Ruff lint and format | Passed | Passed |

The 139-test suite retains upstream routing, confidence, multi-area and whole-home protection checks, and replaces the original process-wide HA stubs with real HA imports. Added tests exercise the real TypeSafe SDK HTTP transport and response parser at the OpenRouter System One endpoint, explicit provider URLs overriding environment variables, synthetic-only key validation, authentication/rate limit rejection without retries, deadline cancellation/transport closure, real config flow, setup/unload/reload/removal, legacy entry compatibility, reauthentication/reconfiguration, and actual conversation processing/local light services.

Device tests verify hidden/unknown/unavailable targets, partial results, an exposure change during inference, and a missing state confirmation. An issued action is neither repeated nor handed to a second agent when confirmation is lost. Error bodies and synthetic secrets are absent from integration logs.

The cross-repository check installs Jev and Phoenix in one isolated HA instance, connects the real outbound TLS WebSocket to Phoenix's isolated Account/Gateway backend, supplies a native text turn, runs the real Jev SDK with mocked OpenRouter HTTP transport, executes a real HA light service, and checks the returned Jibo skill envelope. A second turn reaches a real HA conversation entity providing synthetic Grok speech. Angle brackets and ampersands are escaped in the robot envelope. Agent changes retain the owner credential, unload the old connector, and do not replay actions. A removed agent and expired work fail before execution.

Observed cross-repository transcript-to-result latency was **33.4 ms** on HA 2026.8.1 and **32.8 ms** on HA 2026.9.4 with the **classifier network mocked**. These values measure local plumbing, not OpenRouter or Grok latency. No real provider classification, subscription entitlement, or Grok tool execution was claimed from these tests.

Phoenix's earlier native hardware evidence used the built-in HA agent and beta 0.1.0b3. It does not validate Jev/Grok on a physical robot. Remaining owner checks: enter a real OpenRouter key, complete SpaceXAI's account-dependent Grok sign-in, test that agent directly, select Jev in both Assist and Phoenix, then test the single intended light with fresh spoken Jibo input.

Official references inspected: [OpenRouter TypeSafe SDK adapter](https://openrouter.ai/docs/guides/community/typesafe-sdk), [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python), [HA conversation API](https://developers.home-assistant.io/docs/intent_conversation_api/), [HA conversation entities](https://developers.home-assistant.io/docs/core/entity/conversation/), and [SpaceXAI's authentication and handoff documentation](https://github.com/luxus/ha-spacexai). The installed SDK was 0.7.2. SpaceXAI upstream 2.1.2 was inspected; its live subscription operation was not tested.

GitHub Actions validate both supported HA versions, hassfest and HACS custom-repository metadata. HACS CI excludes the catalogue brands and action-only license checks; upstream has no declared source license, which this fork preserves (see UPSTREAM.md). GitHub issue reporting is enabled on the fork.
