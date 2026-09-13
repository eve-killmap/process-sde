"""Tests for type/group selection and the empty-view guard."""

import contextlib

import pytest

import generate_type_data as gtd
import sde

GENERATORS = (
    "generate_type_names",
    "generate_type_tree",
    "generate_group_names",
    "generate_brackets",
    "generate_type_metas",
    "generate_type_radii",
    "generate_npc_types",
)


def test_fetch_types_filters_by_group(monkeypatch):
    monkeypatch.setattr(
        sde,
        "types_by_id",
        {100: {"groupID": 10}, 101: {"groupID": 11}, 200: {"groupID": 10}},
    )

    assert gtd.fetch_types({10}) == {100, 200}


def test_fetch_types_includes_unpublished_types(monkeypatch):
    # fetch_types now serves only the NPC-group path, and npcTypes.json must
    # still cover types seen in historical loss mails, so `published` is
    # deliberately not filtered.
    monkeypatch.setattr(
        sde,
        "types_by_id",
        {
            100: {"groupID": 10, "published": False},
            200: {"groupID": 10, "published": True},
        },
    )

    assert gtd.fetch_types({10}) == {100, 200}


@contextlib.contextmanager
def _fake_connection():
    yield object()


def _stub_db(monkeypatch, mv_types):
    monkeypatch.setattr(gtd.db, "get_connection", _fake_connection)
    monkeypatch.setattr(gtd, "generate_type_db", lambda conn: None)
    monkeypatch.setattr(gtd.db, "fetch_types", lambda conn: set(mv_types))


def test_generate_type_data_raises_when_view_is_empty(monkeypatch):
    writes = []
    _stub_db(monkeypatch, set())
    monkeypatch.setattr(
        gtd, "write_if_changed", lambda path, data: writes.append(path) or True
    )

    with pytest.raises(RuntimeError, match="mv_ship_search"):
        gtd.generate_type_data(collidable_types=set())

    # The guard must fire before any generator runs: an empty view must never
    # clobber good output.
    assert writes == []


def test_generate_type_data_proceeds_when_view_has_types(monkeypatch):
    called = []
    _stub_db(monkeypatch, {100})
    monkeypatch.setattr(sde, "types_by_id", {100: {"groupID": 10}})
    for name in GENERATORS:
        monkeypatch.setattr(gtd, name, lambda *a, n=name, **k: called.append(n))

    gtd.generate_type_data(collidable_types=set())

    assert called == list(GENERATORS)
