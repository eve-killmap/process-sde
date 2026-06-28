import logging
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import sde
from config import config

logger = logging.getLogger(__name__)
from utils import Number, process_position, round_num, write_if_changed


class MapGenerator:

    def __init__(
        self,
        output_folder: str | Path,
        scale_factor: float,
        process_stargates: bool = True,
        translate_positions: bool = False,
        calc_locale_positions: bool = True,
    ) -> None:
        self.output_folder = output_folder
        self.scale_factor = scale_factor
        self.process_stargates = process_stargates
        self.translate_positions = translate_positions
        self.calc_locale_positions = calc_locale_positions

        self.systems: dict[int, dict[str, Any]] = {}
        # Bounding box, seeded to +/-inf so the first system sets real bounds.
        self.min_x: Number = math.inf
        self.max_x: Number = -math.inf
        self.min_y: Number = math.inf
        self.max_y: Number = -math.inf

    def process_system(
        self, system: dict[str, Any], position_2d: Mapping[str, Any] | None = None
    ) -> None:
        system_id = system["solarSystemID"]
        system_name = system["name"]

        if position_2d is not None:
            x, y = process_position(position_2d, self.scale_factor, p2d=True)
        else:
            x, y = process_position(system["position"], self.scale_factor)

        region_id = system["regionID"]
        constellation_id = system["constellationID"]

        destinations = []
        for destination_id in system["stargateDestinations"]:
            destination_data = sde.solar_systems[destination_id]

            edge_type = 1
            if constellation_id != destination_data["constellationID"]:
                edge_type = 2
            if region_id != destination_data["regionID"]:
                edge_type = 3

            destinations.append({"id": destination_id, "type": edge_type})

        record = {
            "name": system_name,
            "x": x,
            "y": y,
            "constellation_id": constellation_id,
            "region_id": region_id,
            "destinations": destinations,
        }

        self.systems[system_id] = record

        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)

    def finalize(self) -> None:
        logger.info(
            "Finalizing map for %s (%d systems)", self.output_folder, len(self.systems)
        )
        self.min_x = round_num(self.min_x, config.map.position_round)
        self.max_x = round_num(self.max_x, config.map.position_round)
        self.min_y = round_num(self.min_y, config.map.position_round)
        self.max_y = round_num(self.max_y, config.map.position_round)

        if self.translate_positions:
            self._translate()

        system_ids = sorted(self.systems.keys())

        span_x = round_num(self.max_x - self.min_x, config.map.position_round)
        span_y = round_num(self.max_y - self.min_y, config.map.position_round)

        positions = []
        for system_id in system_ids:
            record = self.systems[system_id]

            positions.append(record["x"])
            positions.append(record["y"])

        out = {
            "meta": {
                "bbox": {
                    "minX": self.min_x,
                    "maxX": self.max_x,
                    "minY": self.min_y,
                    "maxY": self.max_y,
                },
                "span": {"x": span_x, "y": span_y},
                "counts": {"systems": len(system_ids)},
            },
            "systemIDs": system_ids,
            "positions": positions,
            "names": [self.systems[system_id]["name"] for system_id in system_ids],
            "constellationIDs": [
                self.systems[system_id]["constellation_id"] for system_id in system_ids
            ],
        }

        if self.process_stargates:
            self._process_stargates(system_ids, out)

        output_folder = config.paths.universe_output / self.output_folder

        output_folder.mkdir(parents=True, exist_ok=True)

        output_file = output_folder / "map.json"
        write_if_changed(output_file, out)

    def process_locales(self) -> None:
        logger.info("Processing locales for %s", self.output_folder)
        locale_generator = LocaleGenerator(
            self.systems,
            self.output_folder,
            self.scale_factor,
            calc_position=self.calc_locale_positions,
        )
        locale_generator.process()
        locale_generator.save_files()

    def _process_stargates(self, system_ids: list[int], out: dict[str, Any]) -> None:
        id_to_index = {system_id: i for i, system_id in enumerate(system_ids)}

        edge_types_by_pair = {}

        for system_id in system_ids:
            a = id_to_index[system_id]

            for destination in self.systems[system_id]["destinations"]:
                destination_id = destination["id"]
                b = id_to_index.get(destination_id)

                if b is None or b == a:
                    continue
                i, j = (a, b) if a < b else (b, a)
                if (i, j) not in edge_types_by_pair:
                    edge_types_by_pair[(i, j)] = destination["type"]

        edges_pairs = sorted(edge_types_by_pair.keys())
        edges_flat = [v for pair in edges_pairs for v in pair]
        edge_types = [edge_types_by_pair[pair] for pair in edges_pairs]

        out["meta"]["counts"]["edges"] = len(edges_pairs)
        out["edges"] = edges_flat
        out["edgeTypes"] = edge_types

    def _translate(self) -> None:
        cx = (self.min_x + self.max_x) / 2
        cy = (self.min_y + self.max_y) / 2

        for _, system in self.systems.items():
            x = system["x"]
            y = system["y"]

            x = round_num(x - cx, config.map.position_round)
            y = round_num(y - cy, config.map.position_round)

            system["x"] = x
            system["y"] = y

        self.min_x = round_num(self.min_x - cx, config.map.position_round)
        self.max_x = round_num(self.max_x - cx, config.map.position_round)
        self.min_y = round_num(self.min_y - cy, config.map.position_round)
        self.max_y = round_num(self.max_y - cy, config.map.position_round)


class LocaleGenerator:

    def __init__(
        self,
        systems: dict[int, dict[str, Any]],
        output_folder: str | Path,
        scale_factor: float,
        calc_position: bool = True,
    ) -> None:
        self.systems = systems
        self.output_folder = output_folder
        self.scale_factor = scale_factor
        self.calc_position = calc_position

        self.constellations: dict[int, dict[str, Any]] = {}

        self.regions: dict[int, dict[str, Any]] = {}

    def process(self) -> None:
        for system_id in self.systems:
            record = self.systems[system_id]

            self._process_const(record["constellation_id"])
            self._process_region(record["region_id"])

    def save_files(self) -> None:
        def _save(data: dict[int, dict[str, Any]], name: str) -> None:
            output_folder = config.paths.universe_output / self.output_folder

            output_folder.mkdir(parents=True, exist_ok=True)

            output_file = output_folder / f"{name}.json"
            write_if_changed(output_file, data)

        _save(self.constellations, "constellations")
        _save(self.regions, "regions")

    def _process_const(self, constellation_id: int) -> None:
        if constellation_id in self.constellations:
            return

        const = self._process_locale(constellation_id, sde.constellations_by_id)
        const["regionID"] = sde.constellations_by_id[constellation_id]["regionID"]

        self.constellations[constellation_id] = const

    def _process_region(self, region_id: int) -> None:
        if region_id in self.regions:
            return

        region = self._process_locale(region_id, sde.regions_by_id)

        self.regions[region_id] = region

    def _process_locale(
        self, id: int, data: Mapping[int, Mapping[str, Any]]
    ) -> dict[str, Any]:
        locale = data[id]

        if self.calc_position:
            # Average the already-scaled 2D system positions (the SDE has no 2D
            # locale position), so no further scaling is applied here.
            pos = self._calc_position(locale)
            x, y = process_position(pos, None, p2d=True)
        else:
            # Use the SDE's own (3D-only) locale position, scaled to match the
            # map's system positions.
            x, y = process_position(locale["position"], self.scale_factor)

        return {"name": locale["name"]["en"], "position": {"x": x, "y": y}}

    def _calc_position(self, data: Mapping[str, Any]) -> dict[str, float]:
        x_sum = float(0)
        y_sum = float(0)
        points = 0

        def loop_systems(constellation: Mapping[str, Any]) -> None:
            for system_id in constellation["solarSystemIDs"]:
                nonlocal x_sum, y_sum, points
                x_sum += self.systems[system_id]["x"]
                y_sum += self.systems[system_id]["y"]
                points += 1

        if "constellationIDs" in data:
            for constellation_id in data["constellationIDs"]:
                constellation = sde.constellations_by_id[constellation_id]
                loop_systems(constellation)
        else:
            loop_systems(data)

        x = x_sum / points
        y = y_sum / points

        return {"x": x, "y": y}
