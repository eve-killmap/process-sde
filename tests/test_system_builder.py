"""Behavioral tests for the per-system file builder.

These characterize the output of building a minimal solar system (no star,
planets, or stargates) so the module -> class refactor can be verified
without the full SDE dataset or a database.
"""

import sde
from generate_system import SystemBuilder, get_system_type


def _minimal_universe(monkeypatch):
    monkeypatch.setattr(
        sde, "constellations_by_id", {200: {"name": {"en": "ConstName"}}}
    )
    monkeypatch.setattr(sde, "regions_by_id", {100: {"name": {"en": "RegName"}}})
    monkeypatch.setattr(sde, "factions_by_id", {})


def _minimal_row():
    return {
        "_key": 30000142,  # second digit "0" -> New Eden system type
        "constellationID": 200,
        "regionID": 100,
        "name": {"en": "TestSys"},
        "position": {"x": 1.0, "y": 2.0, "z": 3.0},
        "radius": 1234.5,
        "securityStatus": 0.9,
        "position2D": {"x": 5.0, "y": 6.0},
    }


def test_get_system_type_reads_second_digit():
    assert get_system_type(30000142) == 0
    assert get_system_type(31000005) == 1
    assert get_system_type(32000001) == 2


def test_build_minimal_system(monkeypatch):
    _minimal_universe(monkeypatch)
    written = {}
    builder = SystemBuilder()
    monkeypatch.setattr(
        "generate_system.write_if_changed",
        lambda path, data: written.update({"path": path, "data": data}) or True,
    )

    built = builder.build(_minimal_row())
    data = built.file_data

    assert built.system_type == 0
    assert built.position_2d == {"x": 5.0, "y": 6.0}
    assert data["solarSystemID"] == 30000142
    assert data["name"] == "TestSys"
    assert data["constellationName"] == "ConstName"
    assert data["regionName"] == "RegName"
    assert data["securityStatus"] == 0.9
    assert data["farthestObject"] == 0
    assert "sovFactionName" not in data
    assert builder.collidable_types == set()
    # Map-only fields live in map_data, never in the saved file.
    assert "regionID" not in written["data"]
    assert "position" not in written["data"]
    assert built.map_data["regionID"] == 100
    assert built.map_data["constellationID"] == 200
    assert built.map_data["stargateDestinations"] == []


def _stargate_universe(monkeypatch):
    monkeypatch.setattr(
        sde,
        "constellations_by_id",
        {200: {"name": {"en": "C200"}}, 201: {"name": {"en": "C201"}}},
    )
    monkeypatch.setattr(sde, "regions_by_id", {100: {"name": {"en": "R100"}}})
    monkeypatch.setattr(sde, "factions_by_id", {})
    monkeypatch.setattr(sde, "mining_beacons", {})
    monkeypatch.setattr(sde, "disrupted_stargates", {})
    monkeypatch.setattr(
        sde,
        "solar_systems",
        {
            30000143: {
                "constellationID": 201,
                "regionID": 100,
                "name": {"en": "B"},
                "position2D": {"x": 100.0, "y": 0.0},
            }
        },
    )
    monkeypatch.setattr(
        sde,
        "stargates_by_id",
        {
            50000001: {
                "destination": {"solarSystemID": 30000143},
                "position": {"x": 30.0, "y": 0.0, "z": 40.0},
                "typeID": 29624,
            }
        },
    )


def _stargate_row():
    return {
        "_key": 30000142,
        "constellationID": 200,
        "regionID": 100,
        "name": {"en": "A"},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "radius": 1000.0,
        "securityStatus": 0.5,
        "position2D": {"x": 0.0, "y": 0.0},
        "stargateIDs": [50000001],
    }


def test_saved_file_for_stargate_system_is_clean(monkeypatch):
    _stargate_universe(monkeypatch)
    saved = {}
    monkeypatch.setattr(
        "generate_system.write_if_changed",
        lambda path, data: saved.update(data) or True,
    )

    builder = SystemBuilder()
    built = builder.build(_stargate_row())

    # The destination IDs the map needs are carried in map_data, not the file.
    assert built.map_data["stargateDestinations"] == [30000143]

    # Map-only fields never appear in the saved frontend file.
    assert "position" not in saved
    assert "constellationID" not in saved
    assert "regionID" not in saved

    # The saved stargate carries the frontend fields but not the raw destination.
    (gate,) = saved["stargates"]
    assert gate == {
        "stargateID": 50000001,
        "position": {"x": 30, "y": 0, "z": 40},
        "destName": "B",
        "jumpType": 2,
        "typeID": 29624,
        "position2D": {"x": 64, "y": 0},
    }
    assert saved["farthestObject"] == 50
    assert builder.collidable_types == {29624}


def test_build_sets_sov_faction_from_region(monkeypatch):
    monkeypatch.setattr(sde, "constellations_by_id", {200: {"name": {"en": "C"}}})
    monkeypatch.setattr(
        sde, "regions_by_id", {100: {"name": {"en": "R"}, "factionID": 500}}
    )
    monkeypatch.setattr(sde, "factions_by_id", {500: {"name": {"en": "Amarr Empire"}}})
    monkeypatch.setattr("generate_system.write_if_changed", lambda path, data: True)

    built = SystemBuilder().build(_minimal_row())

    assert built.file_data["sovFactionName"] == "Amarr Empire"


def test_build_prefers_system_faction_over_constellation_and_region(monkeypatch):
    monkeypatch.setattr(
        sde, "constellations_by_id", {200: {"name": {"en": "C"}, "factionID": 600}}
    )
    monkeypatch.setattr(
        sde, "regions_by_id", {100: {"name": {"en": "R"}, "factionID": 700}}
    )
    monkeypatch.setattr(
        sde,
        "factions_by_id",
        {
            500: {"name": {"en": "System Faction"}},
            600: {"name": {"en": "Const Faction"}},
            700: {"name": {"en": "Region Faction"}},
        },
    )
    monkeypatch.setattr("generate_system.write_if_changed", lambda path, data: True)

    row = _minimal_row()
    row["factionID"] = 500

    built = SystemBuilder().build(row)

    assert built.file_data["sovFactionName"] == "System Faction"


def _wormhole_row():
    return {
        "_key": 31000005,  # second digit "1" -> anoikis/wormhole system type
        "constellationID": 200,
        "regionID": 100,
        "name": {"en": "J000005"},
        "position": {"x": 1.0, "y": 2.0, "z": 3.0},
        "radius": 1000.0,
        "securityStatus": -0.99,
        "wormholeClassID": 6,
    }


def test_set_wormhole_data_uses_system_level_class(monkeypatch):
    monkeypatch.setattr(sde, "secondary_suns", {})
    dst = {}
    SystemBuilder().set_wormhole_data(dst, _wormhole_row())
    assert dst["wormholeClassID"] == 6
    assert "wormholeEffect" not in dst


def test_set_wormhole_data_falls_back_constellation_then_region(monkeypatch):
    monkeypatch.setattr(sde, "secondary_suns", {})

    # constellation carries the class when the system does not
    monkeypatch.setattr(sde, "constellations_by_id", {200: {"wormholeClassID": 3}})
    monkeypatch.setattr(sde, "regions_by_id", {100: {"wormholeClassID": 9}})
    row = _wormhole_row()
    del row["wormholeClassID"]
    dst = {}
    SystemBuilder().set_wormhole_data(dst, row)
    assert dst["wormholeClassID"] == 3

    # neither system nor constellation -> region
    monkeypatch.setattr(sde, "constellations_by_id", {200: {}})
    dst = {}
    SystemBuilder().set_wormhole_data(dst, row)
    assert dst["wormholeClassID"] == 9


def test_set_wormhole_data_omits_class_when_unresolved(monkeypatch):
    monkeypatch.setattr(sde, "constellations_by_id", {200: {}})
    monkeypatch.setattr(sde, "regions_by_id", {100: {}})
    monkeypatch.setattr(sde, "secondary_suns", {})
    row = _wormhole_row()
    del row["wormholeClassID"]
    dst = {}
    SystemBuilder().set_wormhole_data(dst, row)  # warns, must not raise
    assert "wormholeClassID" not in dst


def test_set_wormhole_data_sets_effect_from_secondary_sun(monkeypatch):
    monkeypatch.setattr(sde, "secondary_suns", {31000005: {"typeID": 30577}})  # -> 4
    dst = {}
    SystemBuilder().set_wormhole_data(dst, _wormhole_row())
    assert dst["wormholeEffect"] == 4


def test_set_wormhole_data_omits_effect_when_no_secondary_sun(monkeypatch):
    monkeypatch.setattr(sde, "secondary_suns", {})
    dst = {}
    SystemBuilder().set_wormhole_data(dst, _wormhole_row())
    assert "wormholeEffect" not in dst


def test_set_wormhole_data_omits_effect_when_undecodable(monkeypatch):
    monkeypatch.setattr(sde, "secondary_suns", {31000005: {"typeID": 999999}})  # -> None
    dst = {}
    SystemBuilder().set_wormhole_data(dst, _wormhole_row())  # warns, must not raise
    assert "wormholeEffect" not in dst


def _wormhole_universe(monkeypatch):
    monkeypatch.setattr(sde, "constellations_by_id", {200: {"name": {"en": "C"}}})
    monkeypatch.setattr(sde, "regions_by_id", {100: {"name": {"en": "R"}}})
    monkeypatch.setattr(sde, "factions_by_id", {})
    monkeypatch.setattr("generate_system.write_if_changed", lambda path, data: True)


def test_build_wormhole_system_populates_file_and_map_data(monkeypatch):
    _wormhole_universe(monkeypatch)
    monkeypatch.setattr(sde, "secondary_suns", {31000005: {"typeID": 30574}})  # -> 1

    built = SystemBuilder().build(_wormhole_row())

    assert built.system_type == 1
    assert built.file_data["wormholeClassID"] == 6
    assert built.file_data["wormholeEffect"] == 1
    assert built.map_data["wormholeClassID"] == 6
    assert built.map_data["wormholeEffect"] == 1


def test_build_effectless_wormhole_omits_effect_without_crashing(monkeypatch):
    _wormhole_universe(monkeypatch)
    monkeypatch.setattr(sde, "secondary_suns", {})  # this system has no effect

    built = SystemBuilder().build(_wormhole_row())

    assert built.file_data["wormholeClassID"] == 6
    assert "wormholeEffect" not in built.file_data
    # Regression: appending map data for an effectless system used to KeyError.
    assert built.map_data["wormholeClassID"] == 6
    assert "wormholeEffect" not in built.map_data


def test_build_non_wormhole_system_has_no_wormhole_data(monkeypatch):
    _minimal_universe(monkeypatch)
    monkeypatch.setattr("generate_system.write_if_changed", lambda path, data: True)

    built = SystemBuilder().build(_minimal_row())

    assert built.system_type == 0
    assert "wormholeClassID" not in built.file_data
    assert "wormholeEffect" not in built.file_data
    assert "wormholeClassID" not in built.map_data
    assert "wormholeEffect" not in built.map_data
