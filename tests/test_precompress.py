"""Tests for the optional Brotli precompression in write_if_changed."""

import brotli
import pytest

import utils
from config import load_config
from utils import reset_write_stats, write_if_changed


def _config(tmp_path, **output):
    lines = "\n".join(
        f"  {k}: {str(v).lower() if isinstance(v, bool) else v}"
        for k, v in output.items()
    )
    yaml = tmp_path / "c.yml"
    yaml.write_text(f"output:\n{lines}\n", encoding="utf-8")
    return load_config(yaml_path=yaml, env={}, base_dir=tmp_path)


@pytest.fixture(autouse=True)
def _clean_stats():
    reset_write_stats()


def test_no_brotli_sibling_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "config", _config(tmp_path, precompress=False))
    path = tmp_path / "map.json"

    write_if_changed(path, {"a": 1})

    assert not (tmp_path / "map.json.br").exists()


def test_precompress_writes_valid_brotli_sibling(tmp_path, monkeypatch):
    monkeypatch.setattr(
        utils, "config", _config(tmp_path, precompress=True, precompress_min_bytes=0)
    )
    path = tmp_path / "map.json"

    write_if_changed(path, {"hello": "world"})

    sibling = tmp_path / "map.json.br"
    assert sibling.exists()
    assert brotli.decompress(sibling.read_bytes()) == path.read_bytes()


def test_files_below_threshold_are_not_precompressed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        utils,
        "config",
        _config(tmp_path, precompress=True, precompress_min_bytes=10_000),
    )
    path = tmp_path / "small.json"

    write_if_changed(path, {"a": 1})

    assert not (tmp_path / "small.json.br").exists()


def test_skip_regenerates_missing_sibling(tmp_path, monkeypatch):
    monkeypatch.setattr(
        utils, "config", _config(tmp_path, precompress=True, precompress_min_bytes=0)
    )
    path = tmp_path / "map.json"
    write_if_changed(path, {"a": 1})
    (tmp_path / "map.json.br").unlink()

    # Content unchanged -> skipped, but the missing sibling is recreated.
    assert write_if_changed(path, {"a": 1}) is False
    assert (tmp_path / "map.json.br").exists()


def test_disabling_precompress_removes_stale_sibling_on_change(tmp_path, monkeypatch):
    monkeypatch.setattr(
        utils, "config", _config(tmp_path, precompress=True, precompress_min_bytes=0)
    )
    path = tmp_path / "map.json"
    write_if_changed(path, {"a": 1})
    assert (tmp_path / "map.json.br").exists()

    monkeypatch.setattr(utils, "config", _config(tmp_path, precompress=False))
    write_if_changed(path, {"a": 2})  # content changed

    assert not (tmp_path / "map.json.br").exists()


def test_sibling_updates_when_content_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        utils, "config", _config(tmp_path, precompress=True, precompress_min_bytes=0)
    )
    path = tmp_path / "map.json"
    write_if_changed(path, {"a": 1})
    write_if_changed(path, {"a": 2})

    sibling = tmp_path / "map.json.br"
    assert brotli.decompress(sibling.read_bytes()) == path.read_bytes()
