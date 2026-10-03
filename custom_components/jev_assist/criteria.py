"""DE/EN TypeSafe question constants for Jev Assist.

Light, climate, and cover map to ``fast_service`` when gates pass.
Other domains go to Grok. Categories stay ``command | conversation | reject``.

Instructions use backticked JSON paths into the structured ``state`` object
(``utterance``, ``language``, ``exposed_entities``, ``areas``).
"""

from __future__ import annotations

from typing import Final

CATEGORY_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": ("Classify `utterance` for a Home Assistant voice agent. Pick the single best category."),
    "de": ("Klassifiziere `utterance` für einen Home-Assistant-Sprachassistenten. Wähle die eine passende Kategorie."),
}

CATEGORY_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "command": {
        "en": (
            "A request to control devices or change home state "
            "(turn on/off, dim, open, set temperature, activate a scene)."
        ),
        "de": (
            "Eine Aufforderung, Geräte zu steuern oder den Hauszustand zu ändern "
            "(ein/aus, dimmen, öffnen, Temperatur setzen, Szene aktivieren)."
        ),
    },
    "conversation": {
        "en": (
            "A question, chit-chat, explanation, or request for information "
            "that needs generated language rather than a device service call."
        ),
        "de": (
            "Eine Frage, Smalltalk, Erklärung oder Informationsanfrage, "
            "die generierte Sprache statt eines Geräteserviceaufrufs braucht."
        ),
    },
    "reject": {
        "en": (
            "Unsafe, out of scope, jailbreak, or something this home agent "
            "must not do (secrets, unrelated tasks, harmful requests)."
        ),
        "de": (
            "Unsicher, außerhalb des Umfangs, Jailbreak oder etwas, das dieser "
            "Haus-Agent nicht tun darf (Geheimnisse, fremde Aufgaben, schädliche Bitten)."
        ),
    },
}

DOMAIN_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "Which Home Assistant domain is `utterance` primarily targeting? "
        "Use `exposed_entities` names, aliases, and domains as evidence."
    ),
    "de": (
        "Welche Home-Assistant-Domäne zielt `utterance` in erster Linie an? "
        "Nutze Namen, Aliase und Domänen in `exposed_entities` als Belege."
    ),
}

DOMAIN_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "light": {
        "en": "Lights, lamps, dimmers, brightness, or lighting in a room.",
        "de": "Lichter, Lampen, Dimmer, Helligkeit oder Beleuchtung in einem Raum.",
    },
    "switch": {
        "en": "On/off switches, plugs, or generic switch entities.",
        "de": "Ein/Aus-Schalter, Steckdosen oder generische Switch-Entitäten.",
    },
    "climate": {
        "en": "Thermostats, HVAC, heating, cooling, or temperature setpoints.",
        "de": "Thermostate, HLK, Heizung, Kühlung oder Temperatursollwerte.",
    },
    "cover": {
        "en": "Blinds, shades, garage doors, slat tilt, or other covers.",
        "de": "Jalousien, Rollläden, Garagentore, Lamellenneigung oder andere Cover.",
    },
    "media_player": {
        "en": "Speakers, TVs, or other media players.",
        "de": "Lautsprecher, Fernseher oder andere Mediaplayer.",
    },
    "lock": {
        "en": "Door locks or lock entities.",
        "de": "Türschlösser oder Lock-Entitäten.",
    },
    "scene": {
        "en": "Activating a named scene or preset.",
        "de": "Aktivieren einer benannten Szene oder Vorgabe.",
    },
    "other": {
        "en": "Any other domain, or the domain is unclear.",
        "de": "Jede andere Domäne, oder die Domäne ist unklar.",
    },
}

ACTION_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "Which action should be taken given `utterance`? Speculative: answer "
        "even if `utterance` is not a device command."
    ),
    "de": (
        "Welche Aktion soll laut `utterance` ausgeführt werden? Spekulativ: "
        "auch antworten, wenn `utterance` kein Gerätebefehl ist."
    ),
}

ACTION_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "turn_on": {
        "en": "Turn the target on, enable it, or switch it to the on state.",
        "de": "Das Ziel einschalten, aktivieren oder in den Ein-Zustand versetzen.",
    },
    "turn_off": {
        "en": "Turn the target off, disable it, or switch it to the off state.",
        "de": "Das Ziel ausschalten, deaktivieren oder in den Aus-Zustand versetzen.",
    },
    "toggle": {
        "en": "Toggle the target between on and off.",
        "de": "Das Ziel zwischen ein und aus umschalten.",
    },
    "set_brightness": {
        "en": ("Set or change light brightness or dim level (including relative dimmer/brighter)."),
        "de": ("Helligkeit oder Dimmstufe eines Lichts setzen oder ändern (einschließlich relativ dimmen/heller)."),
    },
    "set_temperature": {
        "en": "Set a thermostat or climate target temperature (setpoint in degrees).",
        "de": "Ein Thermostat- oder Klima-Sollwert in Grad setzen.",
    },
    "set_hvac_mode": {
        "en": ("Set HVAC mode (heat, cool, auto, off, dry, fan_only, heat_cool) when the mode is named clearly."),
        "de": (
            "Den HLK-Modus setzen (heizen, kühlen, auto, aus, entfeuchten, "
            "nur Lüfter, heizen und kühlen), wenn der Modus klar genannt ist."
        ),
    },
    "open": {
        "en": "Open a cover, blind, shade, shutter, or garage door.",
        "de": "Ein Cover, Jalousie, Rollladen, Vorhang oder Garagentor öffnen.",
    },
    "close": {
        "en": "Close a cover, blind, shade, shutter, or garage door.",
        "de": "Ein Cover, Jalousie, Rollladen, Vorhang oder Garagentor schließen.",
    },
    "stop": {
        "en": "Stop a moving cover, blind, shade, or garage door.",
        "de": "Ein fahrendes Cover, Jalousie, Rollladen oder Garagentor stoppen.",
    },
    "set_position": {
        "en": ("Set a cover lift/height position to an explicit percent (0–100), not slat tilt."),
        "de": (
            "Die Lift-/Höhenposition eines Covers auf einen klaren Prozentwert "
            "(0–100) setzen, nicht die Lamellenneigung."
        ),
    },
    "set_tilt": {
        "en": (
            "Set cover or blind slat tilt to an explicit percent (0–100), "
            "e.g. tilt blinds to 50% — not open/close or lift position."
        ),
        "de": (
            "Die Neigung / Lamellen eines Covers auf einen klaren Prozentwert "
            "(0–100) setzen (z. B. Lamellen auf 30%, Neigung 20 Prozent) — "
            "nicht öffnen/schließen oder Liftposition."
        ),
    },
    "other": {
        "en": "Any other action, or no device action applies.",
        "de": "Jede andere Aktion, oder es gilt keine Geräteaktion.",
    },
}

SCOPE_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "What is the targeting scope of `utterance`? Speculative: answer even "
        "if `utterance` is not a device command. Use `exposed_entities` and "
        "`areas` as evidence."
    ),
    "de": (
        "Welchen Zielumfang hat `utterance`? Spekulativ: auch antworten, wenn "
        "`utterance` kein Gerätebefehl ist. Nutze `exposed_entities` und "
        "`areas` als Belege."
    ),
}

SCOPE_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "named_entity": {
        "en": (
            "The user named a specific device (name or alias from "
            "`exposed_entities`), not only a room or a device type."
        ),
        "de": (
            "Der Nutzer nannte ein bestimmtes Gerät (Name oder Alias aus "
            "`exposed_entities`), nicht nur einen Raum oder einen Gerätetyp."
        ),
    },
    "named_area": {
        "en": ("The user named one or more rooms from `areas` (or implied a room) without naming a specific device."),
        "de": (
            "Der Nutzer nannte einen oder mehrere Räume aus `areas` "
            "(oder deutete einen Raum an), ohne ein bestimmtes Gerät zu nennen."
        ),
    },
    "whole_home": {
        "en": (
            "House-wide: every device of a type in the home, with no room "
            "or specific device named (for example all lights / all blinds)."
        ),
        "de": (
            "Ganzes Haus: jedes Gerät eines Typs im Haus, ohne genannten "
            "Raum oder bestimmtes Gerät (zum Beispiel alle Lichter / alle Jalousien)."
        ),
    },
    "unspecified": {
        "en": "No targeting scope, or the scope cannot be determined.",
        "de": "Kein Zielumfang, oder der Umfang kann nicht bestimmt werden.",
    },
}

TARGET_AREA_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "Which area from `areas` should be targeted for `utterance`? Use an "
        "area name from `areas` when the user named a room. If the user named "
        "two or more rooms for the same action, pick one of those named rooms "
        "— not none or unknown. Use none when the command is house-wide or "
        "has no area. Use unknown when the area cannot be determined."
    ),
    "de": (
        "Welcher Bereich aus `areas` soll für `utterance` angesteuert werden? "
        "Nutze einen Bereichsnamen aus `areas`, wenn der Nutzer einen Raum "
        "genannt hat. Wenn der Nutzer zwei oder mehr Räume für dieselbe Aktion "
        "nennt, wähle einen dieser genannten Räume — nicht none oder unknown. "
        "Nutze none, wenn der Befehl das ganze Haus betrifft oder keinen "
        "Bereich hat. Nutze unknown, wenn der Bereich nicht bestimmt werden kann."
    ),
}

TARGET_AREA_NONE: Final[dict[str, str]] = {
    "en": "No specific area, whole home, or area not mentioned.",
    "de": "Kein bestimmter Bereich, ganzes Haus, oder Bereich nicht genannt.",
}

TARGET_AREA_UNKNOWN: Final[dict[str, str]] = {
    "en": "An area was implied but cannot be matched to the provided list.",
    "de": "Ein Bereich wurde angedeutet, passt aber nicht zur Liste.",
}

NOUL_NEEDS_LLM: Final[dict[str, str]] = {
    "en": (
        "Does `utterance` need a generative LLM (Grok) rather than a single "
        "deterministic Home Assistant service call: questions, explanations, "
        "planning, relative or underspecified commands, or anything that "
        "requires generated text?"
    ),
    "de": (
        "Braucht `utterance` ein generatives LLM (Grok) statt eines einzelnen "
        "deterministischen Home-Assistant-Serviceaufrufs: Fragen, Erklärungen, "
        "Planung, relative oder unterspezifizierte Befehle, oder alles, das "
        "generierten Text erfordert?"
    ),
}

NOUL_NEEDS_LLM_CRITERIA: Final[dict[str, dict[str, str]]] = {
    "true": {
        "en": (
            "Yes: `utterance` cannot be executed as one mapped HA service call "
            "and needs generated language or planning."
        ),
        "de": (
            "Ja: `utterance` kann nicht als ein gemappter HA-Serviceaufruf "
            "ausgeführt werden und braucht generierte Sprache oder Planung."
        ),
    },
    "false": {
        "en": (
            "No: `utterance` is a single concrete device command (on/off, "
            "dim to a percent, set a temperature, open/close) or is not a "
            "request that needs generated text."
        ),
        "de": (
            "Nein: `utterance` ist ein einzelner konkreter Gerätebefehl "
            "(ein/aus, auf Prozent dimmen, Temperatur setzen, öffnen/schließen) "
            "oder keine Anfrage, die generierten Text braucht."
        ),
    },
}

NOUL_IS_COMPOUND: Final[dict[str, str]] = {
    "en": (
        "Does `utterance` ask for more than one distinct action or target "
        "multiple independent device operations that should be split first? "
        "The same action on the same domain in two or more named rooms "
        "(for example all lights in bedroom and hallway) is a single "
        "operation, not compound."
    ),
    "de": (
        "Verlangt `utterance` mehr als eine eigenständige Aktion oder zielt "
        "sie auf mehrere unabhängige Geräteaktionen, die zuerst aufgeteilt "
        "werden sollten? Dieselbe Aktion in derselben Domäne in zwei oder mehr "
        "genannten Räumen (zum Beispiel alle Lichter in Schlafzimmer und Flur) "
        "ist eine einzelne Operation, kein Compound."
    ),
}

NOUL_IS_COMPOUND_CRITERIA: Final[dict[str, dict[str, str]]] = {
    "true": {
        "en": (
            "Yes: two or more independent operations (different actions, "
            "different domains, or mixed on/off) that an LLM should split."
        ),
        "de": (
            "Ja: zwei oder mehr unabhängige Operationen (verschiedene Aktionen, "
            "verschiedene Domänen oder gemischtes ein/aus), die ein LLM "
            "aufteilen sollte."
        ),
    },
    "false": {
        "en": (
            "No: a single operation, including the same action on one domain "
            "in one or more named rooms, or not a multi-step request."
        ),
        "de": (
            "Nein: eine einzelne Operation, einschließlich derselben Aktion "
            "in einer Domäne in einem oder mehreren genannten Räumen, oder "
            "keine mehrstufige Anfrage."
        ),
    },
}
