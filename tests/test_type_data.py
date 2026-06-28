"""Tests for the config-driven type/group selection logic."""

import generate_type_data as gtd
import sde
from config import load_config


def _config_with(tmp_path, fetch_categories, whitelist_types):
    yaml = tmp_path / "config.yml"
    yaml.write_text(
        f"type_data:\n  fetch_categories: {fetch_categories}\n  whitelist_types: {whitelist_types}\n",
        encoding="utf-8",
    )
    return load_config(yaml_path=yaml, env={}, base_dir=tmp_path)


def test_fetch_groups_filters_by_configured_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(gtd, "config", _config_with(tmp_path, [6], [100]))
    monkeypatch.setattr(
        sde, "groups_by_id", {10: {"categoryID": 6}, 11: {"categoryID": 99}}
    )

    assert gtd.fetch_groups() == {10}


def test_fetch_types_filters_by_group(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sde,
        "types_by_id",
        {100: {"groupID": 10}, 101: {"groupID": 11}, 200: {"groupID": 10}},
    )

    assert gtd.fetch_types({10}) == {100, 200}


def test_fetch_wl_groups_resolves_whitelist_type_groups(tmp_path, monkeypatch):
    monkeypatch.setattr(gtd, "config", _config_with(tmp_path, [6], [100, 200]))
    monkeypatch.setattr(
        sde,
        "types_by_id",
        {100: {"groupID": 10}, 200: {"groupID": 10}, 300: {"groupID": 99}},
    )

    assert gtd.fetch_wl_groups() == {10}
