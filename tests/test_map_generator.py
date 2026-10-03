import pytest

import generate_map
import sde
from generate_map import AnoikisMapGenerator, MapGenerator, NewEdenMapGenerator


def test_process_system_builds_edges_from_map_data(monkeypatch):
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
            "securityStatus": 0.0,
            "stargateDestinations": [2],
        }
    )

    record = gen.systems[1]
    assert record["name"] == "A"
    assert (record["x"], record["y"]) == (10, 20)
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
            "security_status": 0.0,
        },
        2: {
            "name": "B",
            "x": 1,
            "y": 1,
            "constellation_id": 5,
            "region_id": 7,
            "destinations": [],
            "security_status": 0.0,
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

    assert saved["constellations.json"][7]["position"] == {"x": 3, "y": 4}
    assert saved["regions.json"][9]["position"] == {"x": 5, "y": 6}
    assert saved["constellations.json"][7]["regionID"] == 9


def test_new_eden_map_carries_both_projections(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        generate_map,
        "write_if_changed",
        lambda path, data: saved.update({path.name: data}) or True,
    )

    gen = NewEdenMapGenerator(output_folder="new-eden", scale_factor=2.0)
    gen.process_system(
        {
            "solarSystemID": 1,
            "name": "A",
            "position": {"x": 20.0, "y": 999.0, "z": 40.0},
            "constellationID": 5,
            "regionID": 7,
            "securityStatus": 0.5,
            "stargateDestinations": [],
        },
        position_2d={"x": 2.0, "y": 4.0},
    )
    gen.process_system(
        {
            "solarSystemID": 2,
            "name": "B",
            "position": {"x": 60.0, "y": 111.0, "z": 80.0},
            "constellationID": 5,
            "regionID": 7,
            "securityStatus": 0.4,
            "stargateDestinations": [],
        },
        position_2d={"x": 6.0, "y": 8.0},
    )

    gen.finalize()
    out = saved["map.json"]

    assert out["systemIDs"] == [1, 2]
    assert out["positions"] == [1, 2, 3, 4]
    assert out["positions3D"] == [10, 20, 30, 40]

    assert out["meta"]["counts"] == {"systems": 2, "edges": 0}
    assert out["meta"]["bbox"] == {"minX": 1, "maxX": 3, "minY": 2, "maxY": 4}
    assert set(out["meta3D"]) == {"bbox", "span"}
    assert out["meta3D"]["bbox"] == {"minX": 10, "maxX": 30, "minY": 20, "maxY": 40}
    assert out["meta3D"]["span"] == {"x": 20, "y": 20}

    assert out["names"] == ["A", "B"]
    assert out["constellationIDs"] == [5, 5]


def test_new_eden_requires_position_2d():
    gen = NewEdenMapGenerator(output_folder="new-eden", scale_factor=1.0)
    with pytest.raises(ValueError, match="position2D"):
        gen.process_system(
            {
                "solarSystemID": 1,
                "name": "A",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "constellationID": 5,
                "regionID": 7,
                "securityStatus": 0.0,
                "stargateDestinations": [],
            }
        )


def test_new_eden_locales_carry_2d_and_3d_positions(monkeypatch):
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

    gen = NewEdenMapGenerator(output_folder="new-eden", scale_factor=2.0)
    gen.systems = {100: {"x": 10.0, "y": 20.0, "constellation_id": 7, "region_id": 9}}

    gen.process_locales()

    const = saved["constellations.json"][7]
    assert const["position"] == {"x": 10, "y": 20}
    assert const["position3D"] == {"x": 3, "y": 4}
    assert const["regionID"] == 9

    region = saved["regions.json"][9]
    assert region["position"] == {"x": 10, "y": 20}
    assert region["position3D"] == {"x": 5, "y": 6}


def test_anoikis_map_emits_wormhole_arrays(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        generate_map,
        "write_if_changed",
        lambda path, data: saved.update({path.name: data}) or True,
    )

    gen = AnoikisMapGenerator(
        output_folder="anoikis", scale_factor=1.0, process_stargates=False
    )
    gen.process_system(
        {
            "solarSystemID": 1,
            "name": "J1",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "constellationID": 5,
            "regionID": 7,
            "securityStatus": -0.9,
            "stargateDestinations": [],
            "wormholeClassID": 6,
            "wormholeEffect": 3,
        }
    )
    gen.process_system(
        {
            "solarSystemID": 2,
            "name": "J2",
            "position": {"x": 1.0, "y": 0.0, "z": 1.0},
            "constellationID": 5,
            "regionID": 7,
            "securityStatus": -0.9,
            "stargateDestinations": [],
            "wormholeClassID": 1,
        }
    )

    gen.finalize()
    out = saved["map.json"]

    assert out["systemIDs"] == [1, 2]
    assert out["wormholeClassIDs"] == [6, 1]
    assert out["wormholeEffects"] == [3, 0]


def test_anoikis_map_uses_zero_sentinel_for_missing_class(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        generate_map,
        "write_if_changed",
        lambda path, data: saved.update({path.name: data}) or True,
    )

    gen = AnoikisMapGenerator(
        output_folder="anoikis", scale_factor=1.0, process_stargates=False
    )
    gen.process_system(
        {
            "solarSystemID": 1,
            "name": "J1",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "constellationID": 5,
            "regionID": 7,
            "securityStatus": -0.9,
            "stargateDestinations": [],
        }
    )

    gen.finalize()
    out = saved["map.json"]

    assert out["wormholeClassIDs"] == [0]
    assert out["wormholeEffects"] == [0]
