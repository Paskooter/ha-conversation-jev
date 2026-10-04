"""criteria.py is bilingual DE/EN for every option."""

from custom_components.jev_assist import criteria

_LANGS = ("en", "de")


def _assert_lang_map(name: str, value: dict[str, str]) -> None:
    assert set(value) >= set(_LANGS), name


def test_instruction_maps_are_bilingual() -> None:
    for name in (
        "CATEGORY_INSTRUCTIONS",
        "DOMAIN_INSTRUCTIONS",
        "ACTION_INSTRUCTIONS",
        "SCOPE_INSTRUCTIONS",
        "TARGET_AREA_INSTRUCTIONS",
        "TARGET_AREA_NONE",
        "TARGET_AREA_UNKNOWN",
        "NOUL_NEEDS_LLM",
        "NOUL_IS_COMPOUND",
    ):
        _assert_lang_map(name, getattr(criteria, name))


def test_option_maps_are_bilingual() -> None:
    for name in (
        "CATEGORY_OPTIONS",
        "DOMAIN_OPTIONS",
        "ACTION_OPTIONS",
        "SCOPE_OPTIONS",
    ):
        options = getattr(criteria, name)
        assert options
        for key, langs in options.items():
            _assert_lang_map(f"{name}.{key}", langs)


def test_action_keys_align_with_fast_maps() -> None:
    """Action keys include light/climate/cover maps; ``other`` stays unmapped."""
    from custom_components.jev_assist.climate_map import CLIMATE_ACTION_MAP
    from custom_components.jev_assist.cover_map import COVER_ACTION_MAP
    from custom_components.jev_assist.light_map import LIGHT_ACTION_MAP

    frozen = {
        "turn_on",
        "turn_off",
        "toggle",
        "set_brightness",
        "set_color",
        "activate",
        "set_temperature",
        "set_hvac_mode",
        "open",
        "close",
        "stop",
        "set_position",
        "set_tilt",
        "other",
    }
    assert set(criteria.ACTION_OPTIONS) == frozen
    assert set(LIGHT_ACTION_MAP) == {
        "turn_on",
        "turn_off",
        "toggle",
        "set_brightness",
        "set_color",
    }
    assert set(CLIMATE_ACTION_MAP) == {
        "set_temperature",
        "turn_on",
        "turn_off",
        "set_hvac_mode",
    }
    assert "open" in COVER_ACTION_MAP
    assert "close" in COVER_ACTION_MAP
    assert "stop" in COVER_ACTION_MAP
    assert "set_position" in COVER_ACTION_MAP
    assert "set_tilt" in COVER_ACTION_MAP
    assert COVER_ACTION_MAP["set_tilt"] == ("cover", "set_cover_tilt_position")
    assert set(LIGHT_ACTION_MAP) <= frozen
    assert set(CLIMATE_ACTION_MAP) <= frozen
    assert set(COVER_ACTION_MAP) <= frozen
    assert "other" not in LIGHT_ACTION_MAP
    assert "other" not in CLIMATE_ACTION_MAP
    assert "other" not in COVER_ACTION_MAP


def test_noul_criteria_are_bilingual() -> None:
    for name in ("NOUL_NEEDS_LLM_CRITERIA", "NOUL_IS_COMPOUND_CRITERIA"):
        options = getattr(criteria, name)
        assert set(options) == {"true", "false"}
        for key, langs in options.items():
            _assert_lang_map(f"{name}.{key}", langs)


def test_scope_keys_are_frozen() -> None:
    assert set(criteria.SCOPE_OPTIONS) == {
        "named_entity",
        "named_area",
        "whole_home",
        "unspecified",
    }


def test_set_tilt_criteria_are_percent_based() -> None:
    en = criteria.ACTION_OPTIONS["set_tilt"]["en"].lower()
    de = criteria.ACTION_OPTIONS["set_tilt"]["de"].lower()
    assert "percent" in en
    assert "tilt" in en
    assert "prozent" in de
    assert "lamellen" in de or "neigung" in de


def test_blessed_gate_constants() -> None:
    from custom_components.jev_assist.const import (
        FAST_MIN_CONFIDENCE,
        NOUL_UNSURE_LOW,
        NOUL_YES_THRESHOLD,
        REJECT_MIN_CONFIDENCE,
        TYPESAFE_MODEL,
    )

    assert FAST_MIN_CONFIDENCE == 0.80
    assert NOUL_YES_THRESHOLD == 0.55
    assert NOUL_UNSURE_LOW == 0.40
    assert REJECT_MIN_CONFIDENCE == 0.80
    assert TYPESAFE_MODEL == "jev-latest"
