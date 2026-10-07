"""Every translation carries the same keys as strings.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components" / "lokalenet"


def _keys(tree: dict, prefix: str = "") -> set[str]:
    keys = set()
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        keys |= _keys(value, path) if isinstance(value, dict) else {path}
    return keys


@pytest.mark.parametrize("language", ["en", "pl"])
def test_same_keys(language: str) -> None:
    source = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    translated = json.loads(
        (COMPONENT / "translations" / f"{language}.json").read_text(encoding="utf-8")
    )
    assert _keys(translated) == _keys(source)


def test_every_sensor_has_a_name() -> None:
    from custom_components.lokalenet.sensor import SENSORS

    source = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    assert {d.key for d in SENSORS} == set(source["entity"]["sensor"])
