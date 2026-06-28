import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import sde
from config import config
from schema import Planet, SolarSystem, Vec2
from utils import (
    Number,
    get_distance,
    get_moon_warp_in,
    get_planet_warp_in,
    get_sun_warp_in,
    round_num,
    round_position,
    scale_neighbors,
    set_nested_if_present,
    write_if_changed,
)

logger = logging.getLogger(__name__)

# System ID of Zarzakh, which has an orphaned station that must be attached
# explicitly because it is not referenced by any celestial.
_ZARZAKH_SYSTEM_ID = 30100000
_ZARZAKH_STATION_ID = 60015187

# Abyssal Deadspace and tutorial systems have no meaningful celestial extent;
# use a fixed large "farthest object" so the client frames them sensibly.
_UNBOUNDED_SYSTEM_TYPES = (2, 4)
_UNBOUNDED_FARTHEST = 15000000000000


@dataclass
class BuiltSystem:
    """Result of building one solar system.

    ``file_data`` is the clean record saved for the frontend. ``map_data`` holds
    only the fields the map generators need (system position, region/
    constellation IDs, and stargate destination IDs) and is never written to
    disk, so the two concerns stay separate.
    """

    file_data: dict[str, Any]
    map_data: dict[str, Any]
    position_2d: Vec2 | None
    system_type: int


def get_system_type(system_id: int) -> int:
    return int(str(system_id)[1])


def get_faction_sov(system_row: SolarSystem) -> str | None:
    """Sovereign faction name for a system, resolved from the system's own
    factionID, then its constellation, then its region. Each level is optional;
    returns None when none is set (e.g. player-ownable space)."""
    if "factionID" in system_row:
        return sde.factions_by_id[system_row["factionID"]]["name"]["en"]

    constellation = sde.constellations_by_id[system_row["constellationID"]]
    if "factionID" in constellation:
        return sde.factions_by_id[constellation["factionID"]]["name"]["en"]

    region = sde.regions_by_id[system_row["regionID"]]
    if "factionID" in region:
        return sde.factions_by_id[region["factionID"]]["name"]["en"]

    return None


class SystemBuilder:
    """Builds the per-system frontend file and tracks collidable type IDs.

    A single builder is reused across all systems in a run; ``collidable_types``
    accumulates every station/stargate type encountered so type radii can be
    generated afterwards.

    The ``set_*`` methods populate the given destination dict and return the
    distance of the farthest object they added, so callers can track the
    system's overall extent.
    """

    def __init__(self) -> None:
        self.collidable_types: set[int] = set()

    def set_star_data(self, dst: dict[str, Any], src: SolarSystem) -> None:
        if "starID" not in src:
            return

        star = sde.stars_by_id[src["starID"]]
        dst["star"] = {
            "radius": round_num(star["radius"]),
            "starID": src["starID"],
            "warpPosition": get_sun_warp_in(star["radius"]),
        }

    def set_asteroid_belt_data(self, dst: dict[str, Any], src: Planet) -> Number:
        if "asteroidBeltIDs" not in src:
            return 0

        belts = []
        farthest = 0

        for belt_id in src["asteroidBeltIDs"]:
            belt = sde.belts_by_id[belt_id]

            belt_obj = {
                "asteroidBeltID": belt_id,
                "position": round_position(belt["position"]),
                "orbitIndex": belt["orbitIndex"],
            }

            set_nested_if_present(belt_obj, belt, "uniqueName", "en")

            if "radius" in belt:
                belt_obj["radius"] = round_num(belt["radius"])

            belts.append(belt_obj)
            farthest = max(farthest, get_distance(belt["position"]))

        dst["asteroidBelts"] = belts

        return farthest

    def set_station_data(self, dst: dict[str, Any], src: Mapping[str, Any]) -> Number:
        if "npcStationIDs" not in src:
            return 0

        stations = []
        farthest = 0

        for station_id in src["npcStationIDs"]:
            station = sde.stations_by_id[station_id]

            name = sde.npc_corporations_by_id[station["ownerID"]]["name"]["en"]
            if station["useOperationName"]:
                name += (
                    " "
                    + sde.station_operations_by_id[station["operationID"]][
                        "operationName"
                    ]["en"]
                )

            stations.append(
                {
                    "stationID": station_id,
                    "position": round_position(station["position"]),
                    "name": name,
                    "typeID": station["typeID"],
                }
            )

            farthest = max(farthest, get_distance(station["position"]))
            self.collidable_types.add(station["typeID"])

        dst["stations"] = stations

        return farthest

    def set_moon_data(self, dst: dict[str, Any], src: Planet) -> Number:
        if "moonIDs" not in src:
            return 0

        moons = []
        farthest = 0

        for moon_id in src["moonIDs"]:
            moon = sde.moons_by_id[moon_id]

            moon_obj = {
                "moonID": moon_id,
                "position": round_position(moon["position"]),
                "radius": round_num(moon["radius"]),
                "warpPosition": get_moon_warp_in(moon["position"], moon["radius"]),
                "orbitIndex": moon["orbitIndex"],
            }

            if str(moon_id) in sde.mining_beacons:
                mining_beacon = sde.mining_beacons[str(moon_id)]
                moon_obj["miningBeacon"] = {
                    "x": round_num(mining_beacon["position"]["x"]),
                    "y": round_num(mining_beacon["position"]["y"]),
                    "z": round_num(mining_beacon["position"]["z"]),
                }

            set_nested_if_present(moon_obj, moon, "uniqueName", "en")

            # A moon's stations do not extend the system's farthest object.
            self.set_station_data(moon_obj, moon)

            moons.append(moon_obj)
            farthest = max(farthest, get_distance(moon["position"]))

        dst["moons"] = moons

        return farthest

    def set_planet_data(self, dst: dict[str, Any], src: SolarSystem) -> Number:
        if "planetIDs" not in src:
            return 0

        planets = []
        farthest = 0

        for planet_id in src["planetIDs"]:
            planet = sde.planets_by_id[planet_id]

            planet_obj = {
                "planetID": planet_id,
                "position": round_position(planet["position"]),
                "radius": round_num(planet["radius"]),
                "warpPosition": get_planet_warp_in(
                    planet_id, planet["position"], planet["radius"]
                ),
                "celestialIndex": planet["celestialIndex"],
            }

            set_nested_if_present(planet_obj, planet, "uniqueName", "en")

            belt_farthest = self.set_asteroid_belt_data(planet_obj, planet)
            moon_farthest = self.set_moon_data(planet_obj, planet)
            station_farthest = self.set_station_data(planet_obj, planet)

            farthest = max(
                farthest,
                get_distance(planet["position"]),
                belt_farthest,
                moon_farthest,
                station_farthest,
            )

            planets.append(planet_obj)

        dst["planets"] = planets

        return farthest

    def set_stargate_data(self, dst: dict[str, Any], src: SolarSystem) -> Number:
        if "stargateIDs" not in src:
            return 0

        stargates = []
        farthest = 0
        neighbors = {}

        for stargate_id in src["stargateIDs"]:
            stargate = sde.stargates_by_id[stargate_id]
            dest = sde.solar_systems[stargate["destination"]["solarSystemID"]]

            gate_type = 1
            if src["constellationID"] != dest["constellationID"]:
                gate_type = 2
            if src["regionID"] != dest["regionID"]:
                gate_type = 3

            stargates.append(
                {
                    "stargateID": stargate_id,
                    "position": round_position(stargate["position"]),
                    "destName": dest["name"]["en"],
                    "jumpType": gate_type,
                    "typeID": stargate["typeID"],
                }
            )

            # Stargate destinations are k-space systems, always on the 2D map.
            neighbor_pos = dest.get("position2D")
            assert neighbor_pos is not None
            neighbors[stargate_id] = (
                float(neighbor_pos["x"]),
                float(neighbor_pos["y"]),
            )

            farthest = max(farthest, get_distance(stargate["position"]))
            self.collidable_types.add(stargate["typeID"])

        # A system with stargates is k-space, so it always has a 2D position.
        system_pos_2d = src.get("position2D")
        assert system_pos_2d is not None
        system_position = (float(system_pos_2d["x"]), float(system_pos_2d["y"]))
        transformed = scale_neighbors(system_position, neighbors)

        for item in stargates:
            x, y = transformed[item["stargateID"]]
            item["position2D"] = {"x": x, "y": y}

        dst["stargates"] = stargates

        system_id = str(src["_key"])
        if system_id in sde.disrupted_stargates:
            disrupted = []

            for stargate_id, stargate in sde.disrupted_stargates[system_id].items():
                dest_name = sde.solar_systems[stargate["destination"]]["name"]["en"]

                disrupted.append(
                    {
                        "stargateID": stargate_id,
                        "destination": stargate["destination"],
                        "position": round_position(stargate["position"]),
                        "destName": dest_name,
                        "typeID": stargate["typeID"],
                    }
                )

                farthest = max(farthest, get_distance(stargate["position"]))
                self.collidable_types.add(stargate["typeID"])

            dst["disruptedStargates"] = disrupted

        return farthest

    def save_system(self, system_id: int, data: dict[str, Any]) -> None:
        out_path = config.paths.system_output / f"{system_id}.json"
        write_if_changed(out_path, data)

    def _build_map_data(self, row: SolarSystem) -> dict[str, Any]:
        return {
            "solarSystemID": row["_key"],
            "name": row["name"]["en"],
            "position": round_position(row["position"]),
            "constellationID": row["constellationID"],
            "regionID": row["regionID"],
            "stargateDestinations": [
                sde.stargates_by_id[stargate_id]["destination"]["solarSystemID"]
                for stargate_id in row.get("stargateIDs", [])
            ],
        }

    def build(self, row: SolarSystem) -> BuiltSystem:
        system_id = row["_key"]
        system_name = row["name"]["en"]
        logger.debug("Generating system file for %s (%d)", system_name, system_id)

        system_type = get_system_type(system_id)

        data = {
            "solarSystemID": system_id,
            "constellationName": sde.constellations_by_id[row["constellationID"]][
                "name"
            ]["en"],
            "name": system_name,
            "radius": round_num(row["radius"]),
            "regionName": sde.regions_by_id[row["regionID"]]["name"]["en"],
            "securityStatus": row["securityStatus"],
        }

        if system_id == _ZARZAKH_SYSTEM_ID:
            self.set_station_data(data, {"npcStationIDs": [_ZARZAKH_STATION_ID]})

        faction_name = get_faction_sov(row)
        if faction_name is not None:
            data["sovFactionName"] = faction_name

        self.set_star_data(data, row)
        planet_farthest = self.set_planet_data(data, row)
        stargate_farthest = self.set_stargate_data(data, row)
        farthest = max(planet_farthest, stargate_farthest)

        if system_type in _UNBOUNDED_SYSTEM_TYPES:
            farthest = _UNBOUNDED_FARTHEST

        data["farthestObject"] = round_num(farthest)

        self.save_system(system_id, data)

        return BuiltSystem(
            file_data=data,
            map_data=self._build_map_data(row),
            position_2d=row.get("position2D"),
            system_type=system_type,
        )
