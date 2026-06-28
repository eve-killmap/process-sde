"""Regression tests for map/locale generation."""

import generate_map
import sde
from generate_map import MapGenerator


def test_process_system_builds_edges_from_map_data(monkeypatch):
    # Destination in the same region but a different constellation -> edge type 2.
    monkeypatch.setattr(
        sde, "solar_systems", {2: {"constellationID": 6, "regionID": 7}}
    )

    gen = MapGenerator(output_folder="folder", scale_factor=1.0)
    gen.process_system(
        {
            "solarSystemID": 1,
            "name": "A",
            "position": {"x": 10.0, "y": 0.0, "z": 20.0},
            "constellationID": 5,
            "regionID": 7,
            "stargateDestinations": [2],
        }
    )

    record = gen.systems[1]
    assert record["name"] == "A"
    assert (record["x"], record["y"]) == (10, 20)  # 3D map projects (x, z)
    assert record["destinations"] == [{"id": 2, "type": 2}]


def test_map_json_omits_per_system_region_ids(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        generate_map,
        "write_if_changed",
        lambda path, data: saved.update({path.name: data}) or True,
    )

    gen = MapGenerator(
        output_folder="folder", scale_factor=1.0, process_stargates=False
    )
    gen.systems = {
        1: {
            "name": "A",
            "x": 0,
            "y": 0,
            "constellation_id": 5,
            "region_id": 7,
            "destinations": [],
        },
        2: {
            "name": "B",
            "x": 1,
            "y": 1,
            "constellation_id": 5,
            "region_id": 7,
            "destinations": [],
        },
    }
    gen.min_x = gen.min_y = 0
    gen.max_x = gen.max_y = 1

    gen.finalize()

    out = saved["map.json"]
    assert "regionIDs" not in out
    assert out["constellationIDs"] == [5, 5]
    assert out["systemIDs"] == [1, 2]


def test_calc_locale_positions_false_uses_locale_own_position(monkeypatch):
    # Regression: process_locales must honor calc_locale_positions=False and use
    # the locale's own stored position rather than the centroid of its systems.
    monkeypatch.setattr(
        sde,
        "constellations_by_id",
        {
            7: {
                "name": {"en": "Const"},
                "regionID": 9,
                "solarSystemIDs": [100],
                "position": {"x": 6.0, "y": 0.0, "z": 8.0},
            }
        },
    )
    monkeypatch.setattr(
        sde,
        "regions_by_id",
        {
            9: {
                "name": {"en": "Reg"},
                "constellationIDs": [7],
                "position": {"x": 10.0, "y": 0.0, "z": 12.0},
            }
        },
    )

    saved = {}
    monkeypatch.setattr(
        generate_map,
        "write_if_changed",
        lambda path, data: saved.update({path.name: data}) or True,
    )

    gen = MapGenerator(
        output_folder="folder", scale_factor=2.0, calc_locale_positions=False
    )
    gen.systems = {100: {"x": 10.0, "y": 20.0, "constellation_id": 7, "region_id": 9}}

    gen.process_locales()

    # Own SDE position projected (x, z) and scaled by 2: (6, 8) -> (3, 4),
    # not the system centroid (10, 20).
    assert saved["constellations.json"][7]["position"] == {"x": 3, "y": 4}
    assert saved["regions.json"][9]["position"] == {"x": 5, "y": 6}
    assert saved["constellations.json"][7]["regionID"] == 9
