import logging
from pathlib import Path

import pytest

from config import ConfigError, load_config, require_database_url, setup_logging


def write_yaml(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_used_when_no_yaml_and_empty_env(tmp_path):
    cfg = load_config(yaml_path=tmp_path / "missing.yml", env={}, base_dir=tmp_path)

    assert cfg.logging.level == "INFO"
    assert cfg.logging.backup_count == 5
    assert cfg.map.position_round == 2
    assert cfg.map.neighbor_map_size == 128
    assert cfg.map.scale_factors["au"] == pytest.approx(1.496e11)
    assert 6 in cfg.type_data.fetch_categories
    assert cfg.type_data.default_icon == 4533
    assert 19000001 in cfg.skip_system_ids
    assert cfg.database_url is None


def test_derived_output_paths_live_under_data_output(tmp_path):
    cfg = load_config(yaml_path=tmp_path / "none.yml", env={}, base_dir=tmp_path)

    assert cfg.paths.data_output == tmp_path / "data"
    assert cfg.paths.system_output == cfg.paths.data_output / "system"
    assert cfg.paths.universe_output == cfg.paths.data_output / "universe"
    assert cfg.paths.type_output == cfg.paths.data_output / "type"


def test_yaml_overrides_defaults(tmp_path):
    yaml_path = write_yaml(
        tmp_path,
        """
        logging:
          level: WARNING
          backup_count: 9
        map:
          position_round: 4
        type_data:
          default_icon: 1234
        processing:
          skip_system_ids: [1, 2, 3]
        """,
    )

    cfg = load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)

    assert cfg.logging.level == "WARNING"
    assert cfg.logging.backup_count == 9
    assert cfg.map.position_round == 4
    assert cfg.type_data.default_icon == 1234
    assert cfg.skip_system_ids == frozenset({1, 2, 3})
    # Untouched defaults remain
    assert cfg.map.neighbor_map_size == 128


def test_env_overrides_yaml_and_defaults(tmp_path):
    yaml_path = write_yaml(tmp_path, "logging:\n  level: WARNING\n")
    env = {
        "LOG_LEVEL": "DEBUG",
        "DATA_OUTPUT": str(tmp_path / "custom_out"),
        "DATABASE_URL": "postgresql://u:p@host/db",
        "USER_AGENT": "test-agent/1.0",
        "LOG_FILE": "custom.log",
    }

    cfg = load_config(yaml_path=yaml_path, env=env, base_dir=tmp_path)

    assert cfg.logging.level == "DEBUG"
    assert cfg.paths.data_output == tmp_path / "custom_out"
    assert cfg.database_url == "postgresql://u:p@host/db"
    assert cfg.sde.user_agent == "test-agent/1.0"
    assert cfg.logging.file == tmp_path / "custom.log"


def test_env_defaults_to_os_environ_when_not_passed(tmp_path, monkeypatch):
    # env=None means "use the real process environment" (so .env is honored);
    # only an explicit dict (even empty) opts out.
    monkeypatch.setenv("DATABASE_URL", "postgresql://from/environ")
    cfg = load_config(yaml_path=tmp_path / "x.yml", base_dir=tmp_path)
    assert cfg.database_url == "postgresql://from/environ"


def test_log_level_is_case_insensitive(tmp_path):
    cfg = load_config(
        yaml_path=tmp_path / "x.yml", env={"LOG_LEVEL": "debug"}, base_dir=tmp_path
    )
    assert cfg.logging.level == "DEBUG"


def test_invalid_log_level_raises(tmp_path):
    yaml_path = write_yaml(tmp_path, "logging:\n  level: CHATTY\n")
    with pytest.raises(ConfigError, match="log level"):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_malformed_yaml_raises_config_error(tmp_path):
    yaml_path = write_yaml(tmp_path, "logging: : :\n  - broken\n")
    with pytest.raises(ConfigError):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_yaml_top_level_must_be_mapping(tmp_path):
    yaml_path = write_yaml(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_scale_factors_accept_unsigned_exponent_strings(tmp_path):
    # PyYAML parses `1.496e11` (no sign in the exponent) as a string, so the
    # loader must coerce numeric strings to floats.
    yaml_path = write_yaml(tmp_path, "map:\n  scale_factors:\n    au: 1.496e11\n")
    cfg = load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)
    assert cfg.map.scale_factors["au"] == pytest.approx(1.496e11)


def test_non_numeric_scale_factor_raises(tmp_path):
    yaml_path = write_yaml(tmp_path, "map:\n  scale_factors:\n    au: not-a-number\n")
    with pytest.raises(ConfigError, match="number"):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_output_precompress_defaults_off(tmp_path):
    cfg = load_config(yaml_path=tmp_path / "x.yml", env={}, base_dir=tmp_path)
    assert cfg.output.precompress is False
    assert cfg.output.brotli_quality == 11
    assert cfg.output.precompress_min_bytes == 1024


def test_output_precompress_from_yaml(tmp_path):
    yaml_path = write_yaml(
        tmp_path,
        "output:\n  precompress: true\n  brotli_quality: 5\n  precompress_min_bytes: 0\n",
    )
    cfg = load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)
    assert cfg.output.precompress is True
    assert cfg.output.brotli_quality == 5
    assert cfg.output.precompress_min_bytes == 0


def test_invalid_brotli_quality_raises(tmp_path):
    yaml_path = write_yaml(tmp_path, "output:\n  brotli_quality: 99\n")
    with pytest.raises(ConfigError, match="brotli_quality"):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_invalid_numeric_type_raises(tmp_path):
    yaml_path = write_yaml(tmp_path, "map:\n  position_round: not-a-number\n")
    with pytest.raises(ConfigError):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_negative_numeric_value_raises(tmp_path):
    yaml_path = write_yaml(tmp_path, "logging:\n  max_bytes: -10\n")
    with pytest.raises(ConfigError):
        load_config(yaml_path=yaml_path, env={}, base_dir=tmp_path)


def test_require_database_url_raises_when_missing(tmp_path):
    cfg = load_config(yaml_path=tmp_path / "x.yml", env={}, base_dir=tmp_path)
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        require_database_url(cfg)


def test_require_database_url_returns_value(tmp_path):
    cfg = load_config(
        yaml_path=tmp_path / "x.yml",
        env={"DATABASE_URL": "postgresql://u:p@h/db"},
        base_dir=tmp_path,
    )
    assert require_database_url(cfg) == "postgresql://u:p@h/db"


def test_setup_logging_applies_level(tmp_path):
    cfg = load_config(
        yaml_path=tmp_path / "x.yml",
        env={"LOG_LEVEL": "DEBUG", "LOG_FILE": str(tmp_path / "app.log")},
        base_dir=tmp_path,
    )
    root = logging.getLogger()
    original_level = root.level
    original_handlers = root.handlers[:]
    try:
        setup_logging(cfg)
        assert root.level == logging.DEBUG
    finally:
        for handler in root.handlers[:]:
            handler.close()
        root.handlers[:] = original_handlers
        root.setLevel(original_level)
