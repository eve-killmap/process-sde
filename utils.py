import json
import math
import re
import unicodedata
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import brotli
except ImportError:  # optional; only needed when output.precompress is enabled
    brotli = None

from config import config, JSON_SETTINGS

# round_num collapses whole floats back to int, so numeric results are int | float.
Number = int | float


@dataclass
class WriteStats:
    written: int = 0
    skipped: int = 0
    added_paths: list[Path] = field(default_factory=list)
    modified_paths: list[Path] = field(default_factory=list)


write_stats = WriteStats()


def reset_write_stats() -> None:
    global write_stats
    write_stats = WriteStats()


def write_if_changed(path: Path | str, data: Any) -> bool:
    new_bytes = json.dumps(data, **JSON_SETTINGS).encode("utf-8")
    path = Path(path)
    is_new = False
    try:
        if path.read_bytes() == new_bytes:
            write_stats.skipped += 1
            _sync_precompressed(path, new_bytes, changed=False)
            return False
    except FileNotFoundError:
        is_new = True
    path.write_bytes(new_bytes)
    write_stats.written += 1
    (write_stats.added_paths if is_new else write_stats.modified_paths).append(path)
    _sync_precompressed(path, new_bytes, changed=True)
    return True


def _sync_precompressed(path: Path, new_bytes: bytes, *, changed: bool) -> None:
    """Keep ``path``'s sibling ``.br`` file consistent with the current content.

    nginx's ``brotli_static`` serves ``path.br`` blindly, so the invariant is:
    after this call the sibling either matches ``new_bytes`` or does not exist.
    A ``.br`` is only (re)written when the file is enabled for precompression;
    otherwise a stale sibling is removed whenever the content actually changed.
    """
    sibling = path.with_name(path.name + ".br")
    out = config.output
    should_precompress = out.precompress and len(new_bytes) >= out.precompress_min_bytes

    if should_precompress:
        if changed or not sibling.exists():
            if brotli is None:
                raise RuntimeError(
                    "output.precompress is enabled but the 'Brotli' package is not installed"
                )
            sibling.write_bytes(brotli.compress(new_bytes, quality=out.brotli_quality))
    elif changed and sibling.exists():
        sibling.unlink()


def get_write_stats() -> tuple[int, int, list[Path], list[Path]]:
    return (
        write_stats.written,
        write_stats.skipped,
        write_stats.added_paths,
        write_stats.modified_paths,
    )


def set_nested_if_present(
    dst: dict[str, Any],
    src: Mapping[str, Any],
    outer: str,
    inner: str,
    dst_key: str | None = None,
) -> None:
    value = src.get(outer, {}).get(inner)
    if value is not None:
        dst[dst_key or outer] = value


_slug_cleanup_re = re.compile(r"[^a-z0-9-]+")
_dash_collapse_re = re.compile(r"-{2,}")


def round_num(num: float, digits: int | None = None) -> Number:
    rounded = round(num, digits)

    if isinstance(rounded, int):
        return rounded

    return int(rounded) if rounded.is_integer() else rounded


def round_position(position: Mapping[str, Any]) -> dict[str, Number]:
    x = round_num(position["x"])
    y = round_num(position["y"])
    z = round_num(position["z"])

    return {"x": x, "y": y, "z": z}


def process_position(
    position: Mapping[str, Any], scale_factor: float | None, p2d: bool = False
) -> tuple[Number, Number]:
    x = float(position["x"]) / (scale_factor or 1)
    y = float(position["y" if p2d else "z"]) / (scale_factor or 1)

    x = round_num(x, config.map.position_round)
    y = round_num(y, config.map.position_round)

    return x, y


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = s.casefold()
    s = re.sub(r"[\s_]+", "-", s)
    s = _slug_cleanup_re.sub("", s)
    s = _dash_collapse_re.sub("-", s)
    s = s.strip("-")
    if not s:
        raise ValueError(f"Unable to slugify system name: {name}")

    return s


def get_distance(position: Mapping[str, Any]) -> float:
    x_2 = position["x"] ** 2
    y_2 = position["y"] ** 2
    z_2 = position["z"] ** 2
    return math.sqrt(x_2 + y_2 + z_2)


def get_sun_warp_in(radius: float) -> dict[str, Number]:
    x = (radius + 100000) * math.cos(radius)
    y = 0.2 * radius
    z = -(radius + 100000) * math.sin(radius)

    return {"x": round_num(x), "y": round_num(y), "z": round_num(z)}


def get_moon_warp_in(position: Mapping[str, Any], radius: float) -> dict[str, Number]:
    x = (radius + 5000000) * math.cos(radius)
    y = 1.3 * radius - 7500
    z = -(radius + 5000000) * math.sin(radius)

    return {
        "x": round_num(position["x"] + x),
        "y": round_num(position["y"] + y),
        "z": round_num(position["z"] + z),
    }


def get_planet_warp_in(
    planet_id: int, position: Mapping[str, Any], radius: float
) -> dict[str, Number]:
    x, y, z = position["x"], position["y"], position["z"]

    j = (random.Random(planet_id).random() - 1.0) / 3.0
    t = math.asin(x / abs(x) * (z / math.sqrt(x**2 + z**2))) + j
    s = 20.0 * (1.0 / 40.0 * (10 * math.log10(radius / 10**6) - 39)) ** 20.0 + 1.0 / 2.0
    s = max(0.5, min(s, 10.5))
    d = radius * (s + 1) + 1000000

    return {
        "x": round_num(x + d * math.sin(t)),
        "y": round_num(y + 1.0 / 2.0 * radius * math.sin(j)),
        "z": round_num(z - d * math.cos(t)),
    }


def scale_neighbors(
    center: tuple[float, float],
    neighbors: dict[int, tuple[float, float]],
    beta: float = 10,
    min_radius_px: float = 6,
) -> dict[int, tuple[Number, Number]]:
    c1_x, c1_y = center

    centered = {}
    for key, (x, y) in neighbors.items():
        dx = x - c1_x
        dy = y - c1_y
        centered[key] = (math.hypot(dx, dy), math.atan2(dy, dx))

    max_r = max(r for r, _ in centered.values())
    output_radius = config.map.neighbor_map_size / 2

    result = {}
    for key, (r, theta) in centered.items():
        if r == 0:
            scaled_radius = 0
        else:
            linear_r = r / max_r
            scaled = math.log(1 + beta * linear_r) / math.log(1 + beta)
            scaled_radius = min_radius_px + scaled * (output_radius - min_radius_px)

        result[key] = (
            round_num(scaled_radius * math.cos(theta), config.map.position_round),
            round_num(scaled_radius * math.sin(theta), config.map.position_round),
        )

    return result
