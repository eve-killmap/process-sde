from typing import NotRequired, TypedDict


class Vec3(TypedDict):
    x: float
    y: float
    z: float


class Vec2(TypedDict):
    x: float
    y: float


class LocalizedText(TypedDict):
    en: str


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
    wormholeClassID: NotRequired[int]


class SecondarySun(TypedDict):
    _key: int
    effectBeaconTypeID: int
    position: Vec3
    solarSystemID: int
    typeID: int


class Constellation(TypedDict):
    _key: int
    name: LocalizedText
    position: Vec3
    regionID: int
    solarSystemIDs: list[int]
    factionID: NotRequired[int]
    wormholeClassID: NotRequired[int]


class Region(TypedDict):
    _key: int
    name: LocalizedText
    position: Vec3
    constellationIDs: list[int]
    factionID: NotRequired[int]
    wormholeClassID: NotRequired[int]


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
    metaGroupID: NotRequired[int]
    description: NotRequired[LocalizedText]
    radius: NotRequired[float]


class SdeMeta(TypedDict):
    buildNumber: int


class Bracket(TypedDict):
    name: str
    texturePath: str


class DisruptedStargate(TypedDict):
    destination: int
    position: Vec3
    typeID: int


class MiningBeacon(TypedDict):
    position: Vec3
