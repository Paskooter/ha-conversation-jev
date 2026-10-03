"""Assert installed typesafe-sdk exports the documented call shape."""

from __future__ import annotations

import json

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, RetryPolicy

from custom_components.jev_assist.jev_client import build_questions, build_state
from custom_components.jev_assist.jev_router import ExposedEntity


def test_sdk_exports() -> None:
    assert AsyncTypeSafeClient is not None
    assert Choice is not None
    assert Noul is not None
    assert RetryPolicy is not None
    noul = Noul(instructions="yes?", criteria={"true": "yes", "false": "no"})
    assert hasattr(noul, "instructions")
    assert noul.criteria is not None


def test_questions_use_choice_and_noul() -> None:
    questions = build_questions("en", ["Living room"])
    assert isinstance(questions["category"], Choice)
    assert isinstance(questions["domain"], Choice)
    assert isinstance(questions["action"], Choice)
    assert isinstance(questions["scope"], Choice)
    assert isinstance(questions["target_area"], Choice)
    assert isinstance(questions["needs_llm"], Noul)
    assert isinstance(questions["is_compound"], Noul)
    assert "none" in questions["target_area"].criteria
    assert "unknown" in questions["target_area"].criteria
    assert "Living room" in questions["target_area"].criteria
    assert set(questions["scope"].criteria) == {
        "named_entity",
        "named_area",
        "whole_home",
        "unspecified",
    }
    assert questions["needs_llm"].criteria is not None
    assert questions["is_compound"].criteria is not None
    assert "`utterance`" in questions["category"].instructions
    assert "`exposed_entities`" in questions["domain"].instructions
    assert "`areas`" in questions["target_area"].instructions


def test_state_is_named_json_object() -> None:
    state = build_state(
        "Licht aus",
        [
            ExposedEntity(
                entity_id="light.a",
                domain="light",
                name="A",
                area="Küche",
            )
        ],
        "de",
    )
    assert isinstance(state, dict)
    json.dumps(state, ensure_ascii=False)
    assert state["utterance"] == "Licht aus"
    assert "text" not in state
    assert state["language"] == "de"
    assert state["areas"] == ["Küche"]
    assert state["exposed_entities"][0]["entity_id"] == "light.a"
    assert state["exposed_entities"][0]["aliases"] == []
