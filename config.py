"""Application configuration.

Configuration is resolved with the following precedence (lowest to highest):

  1. Defaults defined in this module.
  2. Values from the YAML config file (``config.yml`` by default), for
     non-secret, operator-tweakable settings.
  3. Environment variables / ``.env``, for secrets and machine-specific
     overrides (``DATABASE_URL``, ``DATA_OUTPUT``, ``LOG_FILE``, ``USER_AGENT``,
     ``LOG_LEVEL``).

Secrets (e.g. ``DATABASE_URL``) live only in the environment and are never
written to the log.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yml"

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Output format and contract constants. These are not operator-tweakable: they
# define the on-disk format the frontend consumes.
JSON_SETTINGS = {"ensure_ascii": False, "separators": (",", ":"), "sort_keys": True}
SLUG_INDEX_FILENAME = "slug_index.json"
SYSTEMS_FILENAME = "systems.json"

_DEFAULT_LATEST_URL = (
    "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
)
_DEFAULT_ARCHIVE_URL = (
    "https://developers.eveonline.com/static-data/tranquility/"
    "eve-online-static-data-{build_number}-jsonl.zip"
)
# Generic, PII-free default. Operators should override USER_AGENT in .env with a
# real contact per CCP's API rules.
_DEFAULT_USER_AGENT = (
    "eve-killmap:process-sde/1.0.0 (+https://github.com/eve-killmap/process-sde)"
)


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    file: Path
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class SdeConfig:
    latest_url: str
    archive_url: str
    user_agent: str


@dataclass(frozen=True)
class MapConfig:
    position_round: int
    neighbor_map_size: int
    scale_factors: dict[str, float]


@dataclass(frozen=True)
class TypeDataConfig:
    fetch_categories: list[int]
    whitelist_types: list[int]
    npc_groups: list[int]
    default_icon: int


@dataclass(frozen=True)
class OutputConfig:
    precompress: bool
    brotli_quality: int
    precompress_min_bytes: int


@dataclass(frozen=True)
class Paths:
    base_dir: Path
    sde_input: Path
    static_input: Path
    data_output: Path
    system_output: Path
    universe_output: Path
    type_output: Path


@dataclass(frozen=True)
class Config:
    paths: Paths
    logging: LoggingConfig
    sde: SdeConfig
    map: MapConfig
    type_data: TypeDataConfig
    output: OutputConfig
    skip_system_ids: frozenset[int]
    database_url: str | None


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name) or {}
    if not isinstance(section, dict):
        raise ConfigError(f"Config section '{name}' must be a mapping")
    return section


def _as_int(
    value: Any, label: str, *, minimum: int | None = None, maximum: int | None = None
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"Config value '{label}' must be an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"Config value '{label}' must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"Config value '{label}' must be <= {maximum}, got {value}")
    return value


def _as_int_list(value: Any, label: str) -> list[int]:
    if not isinstance(value, list):
        raise ConfigError(f"Config value '{label}' must be a list of integers")
    return [_as_int(item, f"{label}[{i}]") for i, item in enumerate(value)]


def _as_positive_float(value: Any, label: str) -> float:
    # Accept ints, floats, and numeric strings. PyYAML parses exponent
    # literals without a sign (e.g. "1.496e11") as strings, so coerce here.
    if isinstance(value, bool):
        raise ConfigError(f"Config value '{label}' must be a number, got {value!r}")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"Config value '{label}' must be a number, got {value!r}"
        ) from None
    if result <= 0:
        raise ConfigError(f"Config value '{label}' must be > 0, got {result}")
    return result


def _load_yaml(yaml_path: Path) -> dict[str, Any]:
    if not yaml_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse config file {yaml_path}: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Config file {yaml_path} must contain a top-level mapping")
    return loaded


def load_config(
    yaml_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> Config:
    """Build a :class:`Config` from defaults, the YAML file, and the environment.

    Raises :class:`ConfigError` for missing/invalid values. ``DATABASE_URL`` is
    not required here; validate it lazily via :func:`require_database_url`.
    """
    base_dir = base_dir or BASE_DIR
    env = os.environ if env is None else env
    data = _load_yaml(yaml_path or DEFAULT_CONFIG_PATH)

    log_cfg = _section(data, "logging")
    sde_cfg = _section(data, "sde")
    map_cfg = _section(data, "map")
    type_cfg = _section(data, "type_data")
    out_cfg = _section(data, "output")
    proc_cfg = _section(data, "processing")

    level = (env.get("LOG_LEVEL") or log_cfg.get("level") or "INFO").upper()
    if level not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"Invalid log level {level!r}; expected one of {sorted(VALID_LOG_LEVELS)}"
        )

    log_file = Path(env.get("LOG_FILE") or log_cfg.get("file") or "process-sde.log")
    if not log_file.is_absolute():
        log_file = base_dir / log_file

    logging_config = LoggingConfig(
        level=level,
        file=log_file,
        max_bytes=_as_int(
            log_cfg.get("max_bytes", 10 * 1024 * 1024), "logging.max_bytes", minimum=1
        ),
        backup_count=_as_int(
            log_cfg.get("backup_count", 5), "logging.backup_count", minimum=0
        ),
    )

    sde_config = SdeConfig(
        latest_url=sde_cfg.get("latest_url") or _DEFAULT_LATEST_URL,
        archive_url=sde_cfg.get("archive_url") or _DEFAULT_ARCHIVE_URL,
        user_agent=env.get("USER_AGENT")
        or sde_cfg.get("user_agent")
        or _DEFAULT_USER_AGENT,
    )

    raw_scale_factors = map_cfg.get("scale_factors") or {
        "au": 1.496e11,
        "abyssal_deadspace": 5.236e11,
        "tutorials": 3.74e11,
    }
    scale_factors = {
        str(key): _as_positive_float(value, f"map.scale_factors.{key}")
        for key, value in raw_scale_factors.items()
    }

    map_config = MapConfig(
        position_round=_as_int(
            map_cfg.get("position_round", 2), "map.position_round", minimum=0
        ),
        neighbor_map_size=_as_int(
            map_cfg.get("neighbor_map_size", 128), "map.neighbor_map_size", minimum=1
        ),
        scale_factors=scale_factors,
    )

    type_data_config = TypeDataConfig(
        fetch_categories=_as_int_list(
            type_cfg.get("fetch_categories", [6, 18, 22, 23, 39, 40, 65, 87]),
            "type_data.fetch_categories",
        ),
        whitelist_types=_as_int_list(
            type_cfg.get(
                "whitelist_types", [2233, 3962, 4318, 45470, 45474, 46653, 46654, 81080]
            ),
            "type_data.whitelist_types",
        ),
        npc_groups=_as_int_list(
            type_cfg.get(
                "npc_groups",
                [
                    1764,
                    1765,
                    1766,
                    1767,
                    1803,
                    1813,
                    1814,
                    1876,
                    1924,
                    1878,
                    1879,
                    1880,
                    1896,
                    1909,
                    4917,
                ],
            ),
            "type_data.npc_groups",
        ),
        default_icon=_as_int(
            type_cfg.get("default_icon", 4533), "type_data.default_icon"
        ),
    )

    output_config = OutputConfig(
        precompress=bool(out_cfg.get("precompress", False)),
        brotli_quality=_as_int(
            out_cfg.get("brotli_quality", 11),
            "output.brotli_quality",
            minimum=0,
            maximum=11,
        ),
        precompress_min_bytes=_as_int(
            out_cfg.get("precompress_min_bytes", 1024),
            "output.precompress_min_bytes",
            minimum=0,
        ),
    )

    skip_ids = _as_int_list(
        proc_cfg.get("skip_system_ids", [19000001, 26000001, 36000001]),
        "processing.skip_system_ids",
    )

    data_output = Path(env.get("DATA_OUTPUT") or base_dir / "data")
    paths = Paths(
        base_dir=base_dir,
        sde_input=base_dir / "sde",
        static_input=base_dir / "static",
        data_output=data_output,
        system_output=data_output / "system",
        universe_output=data_output / "universe",
        type_output=data_output / "type",
    )

    return Config(
        paths=paths,
        logging=logging_config,
        sde=sde_config,
        map=map_config,
        type_data=type_data_config,
        output=output_config,
        skip_system_ids=frozenset(skip_ids),
        database_url=env.get("DATABASE_URL") or None,
    )


def require_database_url(config: Config) -> str:
    """Return the database URL or raise :class:`ConfigError` if unset."""
    if not config.database_url:
        raise ConfigError("DATABASE_URL is required but not set (define it in .env)")
    return config.database_url


def ensure_output_dirs(config: Config) -> None:
    """Create the data output directories if they do not yet exist."""
    for directory in (
        config.paths.data_output,
        config.paths.system_output,
        config.paths.universe_output,
        config.paths.type_output,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def setup_logging(config: Config) -> None:
    """Configure root logging from ``config`` (idempotent)."""
    root_logger = logging.getLogger()
    root_logger.setLevel(config.logging.level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    config.logging.file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        config.logging.file,
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count,
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# Module-level singleton: loaded once from .env + config.yml for normal app use.
# Tests should call load_config() directly with explicit arguments instead.
load_dotenv(BASE_DIR / ".env")
config = load_config()
