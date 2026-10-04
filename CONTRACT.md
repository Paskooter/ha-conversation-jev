# Jev Assist contract (0.3)

Blessed decisions for the HACS `jev_assist` conversation agent. Fast-path
domains are **light**, **climate**, **cover**, and exactly named **scene/script**
activation. Supported home-state questions are read locally before classification.
Other control domains stay with the selected fallback agent.

## Router kinds

`jev_router.route(...)` returns one of:

| kind | meaning |
|------|---------|
| `fast_service` | Deterministic Home Assistant light / climate / cover service call, or one exact scene/script activation |
| `fast_query` | Read only current exposed target states; no classifier, services or fallback tools |
| `grok` | Hand off to `conversation.spacexai_grok` via HA `conversation.async_converse` (compound, needs LLM, low confidence, unmapped domain/action, ambiguous target) |
| `reject` | Do not act (unsafe / out of scope / no matching exposed entity for an explicit area) |

## Categories

Choice keys are frozen at **`command | conversation | reject`**.

| Jev category | Route |
|--------------|--------|
| `command` | Fast path if gates + domain map + target resolution pass; otherwise Grok |
| `conversation` | Grok with reason `conversation` when confidence ≥ `FAST_MIN_CONFIDENCE`, after the bounded local home-query recognizer has declined the utterance |
| `reject` | Reject when confidence ≥ `REJECT_MIN_CONFIDENCE` (includes `out_of_scope`) |

Compound utterances are **not** a fourth category: they are the `is_compound` Noul.
When that Noul is yes, route **Grok** (split / generate) **except** the multi-area
same-action case below.

Do not add categories. Switch / lock / other control domains remain Grok. Scene
and script actions use `activate` or `turn_on` and the same confidence gates.

## Gates (blessed)

| constant | value | use |
|----------|-------|-----|
| `FAST_MIN_CONFIDENCE` | **0.80** | Minimum Choice confidence for command / domain / action / target_area on the fast path; also for `category=conversation` → Grok and `scope=whole_home` override |
| `NOUL_YES_THRESHOLD` | **0.55** | `needs_llm` or `is_compound` `.noul` (P(yes)) at or above this → Grok (unless multi-area same-action) |
| `NOUL_UNSURE_LOW` | **0.40** | Noul has no `confidence`. Values in `[0.40, 0.55)` are treated as unsure (yes ≈ no) → Grok, same exceptions as yes |
| `REJECT_MIN_CONFIDENCE` | 0.80 | `category=reject` at or above this → reject |

## Target resolution (whole-home safety)

`target_area=none` **must not** fire every Assist-exposed entity of a domain when
more than one of that domain is exposed.

Fast path requires **one of**:

1. an **explicit area** (not `none` / `unknown`), scoped to entities of the
   classified domain in that area,
2. **two or more named areas** in the utterance (see multi-area), scoped to the
   union of that domain’s Assist-exposed entities in **only those rooms**,
3. a complete normalized **name or alias** match, full entity ID, or multiword
   object ID. Partial shared tokens cannot select another entity. Exact names
   take precedence over room targeting, including a multi-area utterance.
Duplicate aliases are ambiguous and rejected; unknown qualifiers are rejected,
4. a registered HA device area for a **bounded bare room command** (such as
   “turn off the lights” or “turn off the lights here”), with no explicit name,
   named area, unknown qualifier or whole-home scope,
5. **brief follow-up targets** described below, or
6. **exactly one** Assist-exposed entity of that domain, and the action is a
   simple on/off-style action (no name or area needed):
   - light: `turn_on` / `turn_off` / `toggle`
   - climate: `turn_on` / `turn_off`
   - cover: `open` / `close` / `stop` (and `turn_on` / `turn_off` aliases)
   `set_brightness`, `set_temperature`, `set_hvac_mode`, `set_position`, and
   `set_tilt` and `set_color` still need a name, area, device room or retained
   explicit target. The sole-entity shortcut accepts only a generic device
   command; an unknown explicit name cannot select that sole entity.

If none of those → **`grok`** with reason `no_named_or_area_target`. Never fire
all lights / climates / covers.

`scope` is a speculative Choice (`named_entity | named_area | whole_home |
unspecified`) asked in the same TypeSafe call. When `scope=whole_home` at
`FAST_MIN_CONFIDENCE` and the utterance is **not** the multi-area same-action
case, the router treats targeting like `target_area=none` (ignores a single
room Choice). That blocks “all lights” from firing one room if Jev also picked
an area. Sole exposed entity of that domain for simple on/off-style actions
still fast-paths.

`unknown` area → Grok (unless two or more named areas were recovered from the
utterance). Explicit area with no matching exposed entity of that domain →
reject (`no_exposed_light` / `no_exposed_climate` / `no_exposed_cover`).

Grok handoff (`conversation.async_converse` / agent lookup) must **never** raise
into the Assist pipeline. Any failure speaks `GROK_HANDOFF_UNAVAILABLE_SPEECH`
and logs route `kind` + `reason` at INFO.

Jev classify / `route()` / exposed-entity collection / `fast_service` `async_call`
must **never** raise into the Assist pipeline. Unexpected exceptions are logged at
ERROR with traceback and Assist speaks `ROUTE_FAILURE_SPEECH`.

## Multi-area same action

`target_area` remains a **single** Choice. The router also matches area **names**
from exposed entities as phrases in the utterance.

**Same domain + same action + two or more named areas** stays **`fast_service`**:
call the mapped service for every Assist-exposed entity of that domain in the
named rooms, unless full entity names were supplied: then use only the explicitly
named entity set. This applies even
when `is_compound` is yes (Noul often treats “Schlafzimmer und Flur” as
compound). Low-confidence / `none` / `unknown` `target_area` is allowed for this
recovery path; command / domain / action still need `FAST_MIN_CONFIDENCE`.

Examples that must stay fast (lights on/off):

- DE: „alle Lichter in Schlafzimmer und Flur“
- EN: „all lights in bedroom and hallway“

**Different actions or different domains** in one utterance still go **Grok**
(`is_compound` or `mixed_ops`): e.g. lights on in one room and off in another,
or lights plus blinds. Conflicting on/off or open/close tokens, or generic
tokens from another fast domain, block the multi-area bypass.

Multiple explicit numeric parameter values or colors do not map to one value
for all targets; they hand off before execution. Routines never use area unions.

## Light map

Action keys: `turn_on | turn_off | toggle | set_brightness | set_color | other`
(plus climate/cover and `activate` keys). Brightness percent is parsed in
`light_map.py`: absolute 0–100 digits and English/German spelled numbers,
including hyphenated English tens and German compound numbers. Negative,
out-of-range, decimal, relative or multiple values do not map.
Unparsed brightness → Grok (`brightness_unparsed`).
The execution path filters targets without brightness-capable
`supported_color_modes` before calling a service, including requests for zero.
Confirmation requires a finite, non-boolean brightness observation in 0–255.

Parameter parsing uses the utterance with resolved target names and areas
removed, preserving decimal separators. Target-name numbers or words such as
“Heating” cannot supply a temperature or mode.

`set_color` maps to `light.turn_on` with `rgb_color` for one clear final named
color: red, green, blue, yellow, orange, purple, pink, white, cyan or magenta
(and their German names). RGB values use CSS named-color values.
Modifiers, mixed colors and color temperature are unmapped
(`color_unparsed`). The execution path filters targets without color-capable
`supported_color_modes`, reports them as failed and never claims color changed
without state confirmation.
HS confirmation also requires finite, non-boolean channels within 0–360 hue
and 0–100 saturation; malformed observations remain unconfirmed.

## Climate map

HA services (verified against climate integration actions):
`climate.set_temperature` (`temperature` setpoint), `climate.turn_on`,
`climate.turn_off`, `climate.set_hvac_mode` (`hvac_mode`).

| Jev action | HA service | Extra data |
|------------|------------|------------|
| `set_temperature` | `climate.set_temperature` | `temperature` °C parsed from the utterance (unit or “to/auf N”). Indoor range **5–35**. Percent values and relative “warmer” → Grok (`temperature_unparsed`) |
| `turn_on` / `turn_off` | `climate.turn_on` / `climate.turn_off` | entity ids only |
| `set_hvac_mode` | `climate.set_hvac_mode` | `hvac_mode` in `heat \| cool \| auto \| off \| dry \| fan_only \| heat_cool` when clearly named; else Grok (`hvac_mode_unparsed`) |

`toggle`, humidity, presets, fan/swing, and heat/cool **ranges** (`target_temp_high` /
`target_temp_low`) are underspecified → Grok. Prefer explicit area or name-token;
same whole-home safety as lights.

Setpoints use one complete unsigned numeric literal, including dot/comma
decimals. Values outside 5–35, negative signs, or malformed numeric suffixes
never supply a fast service parameter. Common Unicode minus/dash forms retain
their sign during parsing.

## Cover map

HA services (verified against cover integration actions):
`cover.open_cover`, `cover.close_cover`, `cover.stop_cover`,
`cover.set_cover_position` (`position` 0–100),
`cover.set_cover_tilt_position` (`tilt_position` 0–100).

| Jev action | HA service | Extra data |
|------------|------------|------------|
| `open` | `cover.open_cover` | entity ids only |
| `close` | `cover.close_cover` | entity ids only |
| `stop` | `cover.stop_cover` | entity ids only |
| `set_position` | `cover.set_cover_position` | `position` when a **percent** is clear (`%` / percent / Prozent); else Grok (`position_unparsed`) |
| `set_tilt` | `cover.set_cover_tilt_position` | `tilt_position` when a **percent** is clear (`%` / percent / Prozent); else Grok (`tilt_unparsed`) |
| `turn_on` / `turn_off` | aliases for open / close | when Jev reuses those keys |

`toggle`, relative “halfway” without a percent, and tilt open/close/stop
(on/off-style) → Grok. Prefer explicit area or name-token; same whole-home
safety as lights. `set_tilt` is percent-only — never invent a tilt value.
Position and tilt accept one complete unsigned integer in 0–100. Decimal,
signed or out-of-range values never become an integer by matching a suffix.

## Provider and authentication (OpenRouter fork)

The original classifier thresholds and existing domain actions above remain unchanged. New entries default to OpenRouter; older entries without a provider retain direct TypeSafe. Use a fixed HTTPS provider URL with the official typesafe-sdk 0.7.2. OpenRouter's SDK base is `https://openrouter.ai/api`; the SDK appends `/v1/systemone`. Direct TypeSafe uses `https://api.typesafe.ai`. Explicit URLs and keys override environment defaults. Model is `jev-latest`.

State is a named JSON object (`utterance`, `language`, `exposed_entities`, `areas`), with all Choice and Noul questions in one request. When present, `device_context` adds only the area and retained IDs still in the capped exposed-entity set. It contains no robot, device, user or conversation identifier. Current state values stay local for supported queries. The whole classifier call has a four-second timeout and no retries. Setup validates a key using only synthetic state, not household metadata.

Grok authentication belongs to the selected conversation agent, normally SpaceXAI. This fork removes the original unused duplicate Jev OAuth flow and its unpinned Git dependency. Existing entry metadata remains intact, but Jev never refreshes or uses those Grok tokens. Owners sign in in SpaceXAI and select its installed agent through Jev options. New entries use Home Assistant's local agent if Grok is not installed.

A fast service rechecks exposure after classification. Unavailable or unsupported targets are omitted from execution and reported in HA's failed result targets; partial success is preserved. Actions execute once, never followed by a fallback or retry after execution begins. Light on/off/toggle/brightness/color waits up to two seconds for state confirmation; lost confirmation is FAILED_TO_HANDLE uncertainty. Rejections before execution use NO_VALID_TARGETS. Classifier/auth failures use a spoken error, never a service call.

## Device room and brief follow-up context

ConversationInput `device_id` is resolved through the HA device registry. Its
effective area is authoritative, including a child device's inherited area when
HA provides that API. HA 2026.8.1 uses the direct device area. No identity or area
is parsed from `extra_system_prompt`. Explicit names and areas take precedence;
whole-home scope cannot acquire the robot room implicitly.

Complete successful local entity results may be remembered for **30 seconds**, keyed by
registered device ID, conversation ID and context user ID. Initial local results
return the supplied conversation ID or HA Context.id. `it/them` (`es/sie`) may
reuse only those targets, with ordinary command/domain/action/area confidence and
Noul gates still required. Exposure is checked afresh. Missing, expired,
cross-device, cross-user or hidden target context cannot execute a guessed
device. Unsupported relative values may still hand off before execution under
the existing gates.

Partial results with any failed target discard memory; a pronoun cannot select
only the successful subset. Memory contains at most 128 conversation entries, expires opportunistically and
is cleared when Jev unloads/reloads. Local failures and handoffs discard that
conversation's targets. Scene/script activation does not seed an implicit
activation target. Phoenix separately discards its conversation ID on disconnect,
restart or agent change; Jev has no persistent conversation memory.

## Scenes and scripts

`scene` and `script` accept `activate` and `turn_on`, mapping to the domain's
`turn_on` service. The entire normalized utterance must match an activation
verb plus one complete exposed name/alias/ID, with optional domain noun,
article and politeness. No partial name, area-only target, whole-home expansion,
compound tail or inferred routine can execute on this path. Duplicate exact
matches reject. Exposure is rechecked before the single call.

An exposed scene's initial `unknown` timestamp is valid before its first
activation; `unavailable` still blocks it. Scene/script success says “Started
<name>.” and returns the routine entity in HA success results, without asserting
its downstream effects completed. Execution exceptions return uncertainty and
never retry or hand off.

## Local state questions

Bounded English/German state questions are recognized before Jev classification.
Resolve only complete exposed names/aliases/IDs, an explicitly named area plus
device domain/property, a registered device room, or brief pronoun targets.
Unknown qualifiers and name collisions fail locally. Area queries are bounded
to at most 12 targets; unscoped whole-home questions cannot acquire a room.
Generic door/window/motion/smoke and blind/shade/shutter/garage nouns restrict
the target set to matching supported device classes. Exact names take precedence.

Supported readers cover light/switch/fan/input_boolean on/off, cover
open/closed/movement and position/tilt, lock status, climate mode/current or
target temperature/humidity, numeric sensors and door/window/lock/detection
binary sensors. Named media-player current playback states can also be read.
Light brightness/color are current attributes; an off light reports brightness
zero and does not invent a current color. Sensor values require finite numbers;
unrecognized states or missing properties are unknown. No history, arbitrary
attribute dump, services, provider classification or fallback tools run.

`fast_query` rechecks Assist exposure and reads current HA states immediately.
It returns HA `query_answer` with accurate entity success/failed targets and
separate wording for unknown/unavailable properties, including partial answers.
Missing, hidden or ambiguous targets use `NO_VALID_TARGETS` without handoff.

## Grok handoff

When the router returns `kind=grok`, the conversation entity calls Home Assistant
`conversation.async_converse` with `agent_id=GROK_HANDOFF_AGENT_ID` (legacy default
`conversation.spacexai_grok`, the SpaceXAI umbrella conversation entity). The
same `text`, `conversation_id`, `context`, `language`, `device_id`,
`satellite_id`, and `extra_system_prompt` are forwarded.

Jev does **not** run TTS, STT, or a Grok chat stack. Override the target with
config-entry option/data key `grok_handoff_agent_id`. If the agent is missing,
the target is this agent, or handoff raises any exception, Assist gets
`Grok is not available.` — never an uncaught error in the pipeline.

Handoff contract assumptions (SpaceXAI umbrella, not this repo): the target
agent receives the original Assist turn (`text`, `conversation_id`, `language`,
device/satellite ids, `extra_system_prompt`). Jev does not pre-split compound
utterances; Grok is expected to generate prose, split mixed ops, and call HA
tools when the umbrella agent is configured to do so.
