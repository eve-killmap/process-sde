"""TypedDict shapes for the SDE and static input data.

These describe the fields this pipeline actually reads (derived from the SDE
JSON schemas), not every field CCP publishes. ``NotRequired`` marks fields that
are optional per the schema. They are static-only annotations: the rows stay
plain dicts at runtime, so there is no parsing or memory cost.
"""

from typing import NotRequired, TypedDict


class Vec3(TypedDict):
    x: float
    y: float
    z: float


class Vec2(TypedDict):
    x: float
    y: float


class LocalizedText(TypedDict):
    # Other locale keys (de, es, fr, ...) exist but are unused here.
    en: str


# --- map data ---------------------------------------------------------------


class SolarSystem(TypedDict):
    _key: int
    constellationID: int
    regionID: int
    name: LocalizedText
    position: Vec3
    radius: float
    securityStatus: float
    factionID: NotRequired[int]
    starID: NotRequired[int]
    planetIDs: NotRequired[list[int]]
    stargateIDs: NotRequired[list[int]]
    position2D: NotRequired[Vec2]


class Constellation(TypedDict):
    _key: int
    name: LocalizedText
    position: Vec3
    regionID: int
    solarSystemIDs: list[int]
    factionID: NotRequired[int]


class Region(TypedDict):
    _key: int
    name: LocalizedText
    position: Vec3
    constellationIDs: list[int]
    factionID: NotRequired[int]


class Star(TypedDict):
    _key: int
    radius: int


class StargateDestination(TypedDict):
    solarSystemID: int
    stargateID: int


class Stargate(TypedDict):
    _key: int
    destination: StargateDestination
    position: Vec3
    typeID: int


class Planet(TypedDict):
    _key: int
    position: Vec3
    radius: int
    celestialIndex: int
    asteroidBeltIDs: NotRequired[list[int]]
    moonIDs: NotRequired[list[int]]
    npcStationIDs: NotRequired[list[int]]
    uniqueName: NotRequired[LocalizedText]


class Moon(TypedDict):
    _key: int
    position: Vec3
    radius: float
    orbitIndex: int
    npcStationIDs: NotRequired[list[int]]
    uniqueName: NotRequired[LocalizedText]


class AsteroidBelt(TypedDict):
    _key: int
    position: Vec3
    orbitIndex: int
    radius: NotRequired[float]
    uniqueName: NotRequired[LocalizedText]


class NpcStation(TypedDict):
    _key: int
    position: Vec3
    ownerID: int
    operationID: int
    typeID: int
    useOperationName: bool


# --- name / type data -------------------------------------------------------


class Faction(TypedDict):
    _key: int
    name: LocalizedText


class NpcCorporation(TypedDict):
    _key: int
    name: LocalizedText


class StationOperation(TypedDict):
    _key: int
    operationName: LocalizedText


class Group(TypedDict):
    _key: int
    categoryID: int
    name: LocalizedText


class Type(TypedDict):
    _key: int
    groupID: int
    name: LocalizedText
    published: bool
    factionID: NotRequired[int]
    description: NotRequired[LocalizedText]
    radius: NotRequired[float]


class SdeMeta(TypedDict):
    buildNumber: int


# --- static (non-SDE) data --------------------------------------------------


class Bracket(TypedDict):
    name: str
    texturePath: str


class DisruptedStargate(TypedDict):
    destination: int
    position: Vec3
    typeID: int


class MiningBeacon(TypedDict):
    position: Vec3
