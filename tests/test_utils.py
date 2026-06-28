import json

import pytest

from utils import (
    get_distance,
    get_planet_warp_in,
    get_write_stats,
    process_position,
    reset_write_stats,
    round_num,
    round_position,
    slugify,
    write_if_changed,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Jita", "jita"),
        ("New Caldari", "new-caldari"),
        ("A-B C_D", "a-b-c-d"),
        ("  spaced  ", "spaced"),
        ("Pétur", "petur"),
        ("Foo!!!Bar", "foobar"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_slugify_raises_on_empty_result():
    with pytest.raises(ValueError):
        slugify("!!!")


@pytest.mark.parametrize(
    "value, digits, expected",
    [
        (5, None, 5),
        (5.0, None, 5),
        (5.4, None, 5),
        (5.0, 2, 5),
        (5.456, 2, 5.46),
    ],
)
def test_round_num(value, digits, expected):
    result = round_num(value, digits)
    assert result == expected
    assert isinstance(result, type(expected))


def test_round_position_returns_ints_for_whole_numbers():
    assert round_position({"x": 1.0, "y": 2.4, "z": 3.0}) == {"x": 1, "y": 2, "z": 3}


def test_process_position_uses_z_for_3d_and_y_for_2d():
    pos = {"x": 10, "y": 20, "z": 30}
    assert process_position(pos, None) == (10, 30)
    assert process_position(pos, None, p2d=True) == (10, 20)


def test_process_position_applies_scale_factor():
    assert process_position({"x": 10, "y": 4, "z": 20}, 2) == (5, 10)


def test_get_distance():
    assert get_distance({"x": 3, "y": 0, "z": 4}) == 5.0


def test_get_planet_warp_in_is_deterministic_per_planet():
    pos = {"x": 1.0e9, "y": 2.0e9, "z": 3.0e9}
    first = get_planet_warp_in(42, pos, 5.0e6)
    second = get_planet_warp_in(42, pos, 5.0e6)
    assert first == second


def test_write_if_changed_tracks_new_unchanged_and_modified(tmp_path):
    reset_write_stats()
    path = tmp_path / "out.json"

    assert write_if_changed(path, {"a": 1}) is True
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}

    assert write_if_changed(path, {"a": 1}) is False  # unchanged -> skipped
    assert write_if_changed(path, {"a": 2}) is True  # changed -> rewritten

    written, skipped, added, modified = get_write_stats()
    assert written == 2
    assert skipped == 1
    assert added == [path]
    assert modified == [path]
