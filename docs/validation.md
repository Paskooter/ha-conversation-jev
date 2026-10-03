# Beta 0.2.0b1 validation

Observed on 2026-10-03. All devices, classifier responses and identities below are invented. No household changes were made for this fork.

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
