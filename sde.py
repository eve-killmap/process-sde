"""In-memory SDE dataset.

Call :func:`load` once (after the SDE archive has been downloaded and
extracted) to populate the module-level lookup tables. Importing this module
has no side effects, so it is safe to import before the data files exist.
"""

import json
import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from config import config
from schema import (
    AsteroidBelt,
    Bracket,
    Constellation,
    DisruptedStargate,
    Faction,
    Group,
    MiningBeacon,
    Moon,
    NpcCorporation,
    NpcStation,
    Planet,
    Region,
    SdeMeta,
    SolarSystem,
    Star,
    Stargate,
    StationOperation,
    Type,
)

logger = logging.getLogger(__name__)

# Populated by load(). Empty until then.
sde: list[SdeMeta] = []
build_number: int | None = None

solar_systems: dict[int, SolarSystem] = {}
constellations_by_id: dict[int, Constellation] = {}
regions_by_id: dict[int, Region] = {}
stars_by_id: dict[int, Star] = {}
stargates_by_id: dict[int, Stargate] = {}
planets_by_id: dict[int, Planet] = {}
moons_by_id: dict[int, Moon] = {}
belts_by_id: dict[int, AsteroidBelt] = {}
factions_by_id: dict[int, Faction] = {}
stations_by_id: dict[int, NpcStation] = {}
npc_corporations_by_id: dict[int, NpcCorporation] = {}
station_operations_by_id: dict[int, StationOperation] = {}
groups_by_id: dict[int, Group] = {}
types_by_id: dict[int, Type] = {}

# Static (non-SDE) data, keyed by stringified IDs.
disrupted_stargates: dict[str, dict[str, DisruptedStargate]] = {}
mining_beacons: dict[str, MiningBeacon] = {}
brackets: dict[str, Bracket] = {}
brackets_by_category: dict[str, int] = {}
brackets_by_group: dict[str, int] = {}
brackets_by_type: dict[str, int] = {}

_loaded = False


def load_jsonl(path: Path) -> Iterator[Any]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _by_key(rows: Iterable[Any]) -> dict[int, Any]:
    return {row["_key"]: row for row in rows}


def load(force: bool = False) -> None:
    """Read the SDE and static data files into the module-level tables."""
    global _loaded, sde, build_number
    global solar_systems, constellations_by_id, regions_by_id, stars_by_id
    global stargates_by_id, planets_by_id, moons_by_id, belts_by_id, factions_by_id
    global stations_by_id, npc_corporations_by_id
    global station_operations_by_id, groups_by_id, types_by_id
    global disrupted_stargates, mining_beacons
    global brackets, brackets_by_category, brackets_by_group, brackets_by_type

    if _loaded and not force:
        return

    sde_input = config.paths.sde_input
    static_input = config.paths.static_input
    logger.info("Loading SDE data files from %s", sde_input)

    sde = list(load_jsonl(sde_input / "_sde.jsonl"))
    build_number = sde[0]["buildNumber"]

    solar_systems = _by_key(load_jsonl(sde_input / "mapSolarSystems.jsonl"))
    constellations_by_id = _by_key(load_jsonl(sde_input / "mapConstellations.jsonl"))
    regions_by_id = _by_key(load_jsonl(sde_input / "mapRegions.jsonl"))
    stars_by_id = _by_key(load_jsonl(sde_input / "mapStars.jsonl"))
    stargates_by_id = _by_key(load_jsonl(sde_input / "mapStargates.jsonl"))
    planets_by_id = _by_key(load_jsonl(sde_input / "mapPlanets.jsonl"))
    moons_by_id = _by_key(load_jsonl(sde_input / "mapMoons.jsonl"))
    belts_by_id = _by_key(load_jsonl(sde_input / "mapAsteroidBelts.jsonl"))
    factions_by_id = _by_key(load_jsonl(sde_input / "factions.jsonl"))
    stations_by_id = _by_key(load_jsonl(sde_input / "npcStations.jsonl"))
    npc_corporations_by_id = _by_key(load_jsonl(sde_input / "npcCorporations.jsonl"))
    station_operations_by_id = _by_key(
        load_jsonl(sde_input / "stationOperations.jsonl")
    )
    groups_by_id = _by_key(load_jsonl(sde_input / "groups.jsonl"))
    types_by_id = _by_key(load_jsonl(sde_input / "types.jsonl"))

    disrupted_stargates = load_json(static_input / "disruptedStargates.json")
    mining_beacons = load_json(static_input / "miningBeacons.json")
    brackets = load_json(static_input / "brackets.json")
    brackets_by_category = load_json(static_input / "bracketsByCategory.json")
    brackets_by_group = load_json(static_input / "bracketsByGroup.json")
    brackets_by_type = load_json(static_input / "bracketsByType.json")

    _loaded = True
    logger.info("SDE data loaded (build %d)", build_number)
