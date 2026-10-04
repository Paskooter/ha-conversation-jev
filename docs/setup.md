# Owner setup: OpenRouter, Grok and Jibo

## 1. Install Jev Assist

Add `https://github.com/Paskooter/ha-conversation-jev` as an **Integration** in HACS custom repositories. Download prerelease **0.3.0b1** and restart Home Assistant. Add **Jev Assist** in Settings → Devices & services. Choose **OpenRouter** and enter your key from [OpenRouter's API key page](https://openrouter.ai/settings/keys).

Jev is billed to that OpenRouter key. No separate TypeSafe account or OpenRouter chat model setting is required. Setup validates the key with one small synthetic classification request. Provider errors distinguish rejected credentials, rate limits, connectivity and account/model availability. Keys are entered only in Home Assistant.

## 2. Sign in to Grok in SpaceXAI

The upstream Jev architecture hands conversation requests to a separate Grok agent. Install [luxus/ha-spacexai](https://github.com/luxus/ha-spacexai) as a HACS custom repository, category **Integration**, then restart HA. The inspected upstream version is **2.1.2**; its subscription login is owned by that integration and remains an account-dependent check.

Add **SpaceXAI** under Settings → Devices & services. Choose **Sign in with Grok**, open the verification URL it displays, and enter its device code. Use your xAI/Grok subscription account. Wait until Home Assistant finishes linking and creates the **Grok** conversation entity, normally `conversation.spacexai_grok`.

Subscription sign-in uses the upstream public Grok CLI OAuth client. Availability depends on xAI granting that account the required access. This fork does not convert a subscription into a developer API key, silently switch billing, or guarantee that every subscription tier is accepted. If sign-in or the first Grok response is rejected, keep the local Home Assistant fallback selected and inspect the redacted SpaceXAI error. A console.x.ai API key is a separate, explicitly billed alternative in SpaceXAI; it is not required for Jev's OpenRouter path.

You do not need SpaceXAI's speech-to-text or text-to-speech entities for Jibo. Jibo already supplies both. If SpaceXAI fails to install its own auth dependency, inspect its installation logs; Jev's pinned PyPI dependency remains independent.

Open **Jev Assist → Configure → Fallback conversation agent** and select **Grok**. Save. This must be an installed agent; Jev cannot hand off to itself. Test a short text question in HA Assist using Grok directly before testing Jev's fallback.

## 3. Prepare one test light

Open the light's Home Assistant entity settings. Give it a clear name such as **Kitchen Light**, add a suitable alias if desired, and assign its **Kitchen** area. Open **Settings → Voice assistants → Expose** and expose that light to Assist.

For the first check, expose only the device you intend to test. Verify the same sentence in the Home Assistant built-in agent. Then select **Jev Assist** in your HA voice assistant's Conversation agent setting and use text Assist to try `Turn off the kitchen lights.` and `Turn on the kitchen lights.` Names and exposure remain HA settings; installing Jev does not create or rename rooms.

## 4. Select Jev for Jibo

Update [Phoenix](https://github.com/Paskooter/phoenix-home-assistant) through HACS to **0.2.0b1 or newer** and restart HA. Under **Settings → Devices & services → Phoenix → Configure**, choose **Jev Assist** as Conversation agent and save. Your existing jibo.io link is retained; no new code is needed.

If Phoenix is not linked yet, sign in to [the Phoenix console](https://jibo.io/app#/home-assistant), generate a single-use code for the robots you want to enable, and add Phoenix in HA using that code. Home Assistant connects outward over TLS; no public HA URL or port forwarding is required.

Now try:

- “Hey Jibo, turn off the kitchen lights.”
- “Hey Jibo, turn on the kitchen lights.”
- “Hey Jibo, ask Home Assistant to turn off the kitchen lights.”

Jibo's home commands explicitly use Phoenix's chosen agent. Merely choosing Jev in your HA voice assistant will not redirect Jibo. Ordinary time, jokes, weather, volume, sleep and active skill responses keep their existing Phoenix routing.

Phoenix's existing command deadline is **7.5 seconds**, including classifier and fallback work. Slow Grok responses can expire. Expired or interrupted work is never replayed, and an unconfirmed action is reported as uncertain. Check the physical state before trying again.

## 5. Room context, state answers and routines

Open **Settings → Devices & services → Phoenix**, select each robot's device, and assign its area. Jev uses the area of the HA device supplied for that turn. “Turn off the lights” or “turn off the lights here” then resolves only exposed lights in that room. Use a full entity name/alias or another room to override it. Unknown qualifiers do not select a similarly named light. Without a registered room, keep naming the intended area or device.

After a successful local command, a follow-up such as “set it to fifty percent” can use that target for 30 seconds when the same device and conversation context are supplied. A separate robot or conversation cannot reuse it. Reloading Jev clears its target context, and Phoenix disconnects, restart or agent changes begin a new conversation. A scene/script cannot become an implicit target for another activation.

Try “is the kitchen light on?”, “what is the kitchen temperature?” or “what is the kitchen blind position?” Supported questions read only exposed current states locally. No Jev provider or fallback tools run for these answers. Unknown values, unavailable devices and missing or ambiguous targets are reported directly. Names, sensor device classes and areas must match HA; this does not inspect unexposed devices or state history.

For color, use a supported named color, such as “set Kitchen Light to blue”, on a color-capable light. Brightness accepts absolute English and German numbers from zero to one hundred; relative “brighter”, dark/pale shades and color temperature remain fallback requests.

Expose only the scene or script you intend Assist to start, give it a distinctive full name or alias, then try “activate Reading Time scene” or “run Evening Prep script”. The exact single routine is started once; its own configuration defines the devices and effects. Jev says “started” and does not promise that every downstream action finished. Phoenix's owner-configured shortcuts can map an exact phrase to one explicitly exposed scene/script; configure those under Phoenix rather than asking an agent to invent a routine.

## Troubleshooting

- **Sorry, I couldn't understand that:** first verify the name/alias, Kitchen area and Assist exposure, and test the same text in the selected HA agent. Also verify Phoenix is set to Jev, not its default built-in agent.
- **Grok is not available:** ensure SpaceXAI finished sign-in, test its Grok agent directly, and choose the current entity in Jev's Configure form. Renaming or removing an agent never silently substitutes another one.
- **Jev needs a new API key:** use Jev's reauthentication prompt or Reconfigure to enter a replacement key for the selected provider.
- **Provider could not serve Jev:** check OpenRouter credit, permissions and System One availability. The integration uses `/api/v1/systemone`, not chat completions; there is no chat model dropdown to repair.
- **Couldn't confirm the result:** the action may have executed. Inspect the target before issuing another command. Jev and Phoenix do not retry an uncertain action.
- **Device does not support color:** check the light's supported color modes. Jev will not report an unsupported color as changed.
- **No exposed device for a question:** verify the complete name/alias, room, exposure and sensor device class. The question stays local and cannot be handed off to tools that guess a target.
- **Climate, scene or script behaves unexpectedly:** test the exact device or routine in HA first. A routine's effects are defined by its own configuration. Expose only the devices and scripts you want Assist to control. Phoenix still requires an explicit invocation or owner-configured shortcut for commands outside its direct home phrase set.

## Upgrade and removal

Keep a HA backup before upgrading. HACS downloads the new version; restart HA afterward. Direct TypeSafe entries from upstream remain direct TypeSafe entries. Reconfigure allows a deliberate switch to OpenRouter with the corresponding key; existing fallback options are preserved.

This fork removes upstream Jev's unused duplicate Grok authentication flow. Existing stored metadata is retained during upgrades, but its old Grok tokens are not refreshed or used here. Sign in in SpaceXAI, which actually executes Grok conversations. Remove and recreate an old Jev entry if you want to discard its unused authentication metadata.

To stop Jibo using Jev, set Phoenix's Conversation agent back to **Home Assistant (built-in)**. To stop HA Assist using it, change that voice assistant's agent. Remove Jev under Devices & services, remove the HACS download, and restart HA. Remove SpaceXAI separately if it is no longer wanted; revoke the Grok account authorization in xAI account settings when removing its access. Revoke an OpenRouter key there if it is no longer used. Removing Jev does not unlink Phoenix or change Assist exposure.
