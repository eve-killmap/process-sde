import logging
from collections.abc import Collection

from config import config
from utils import write_if_changed
import sde
import db

logger = logging.getLogger(__name__)


def fetch_wl_groups() -> set[int]:
    groups = set()

    for type_id in config.type_data.whitelist_types:
        type = sde.types_by_id[type_id]
        groups.add(type["groupID"])

    return groups


def fetch_groups() -> set[int]:
    groups = set()

    for id, row in sde.groups_by_id.items():
        if row["categoryID"] in config.type_data.fetch_categories:
            groups.add(id)

    return groups


def fetch_types(groups: Collection[int]) -> set[int]:
    types = set()

    for id, row in sde.types_by_id.items():
        if row["groupID"] in groups:
            types.add(id)

    return types


def generate_group_names(groups: Collection[int]) -> None:
    logger.debug("Generating group names for %d groups", len(groups))
    out = {}

    for group_id in groups:
        group_name = sde.groups_by_id[group_id]["name"]["en"]
        out[group_id] = group_name

    output_path = config.paths.type_output / "groupNames.json"
    write_if_changed(output_path, out)


def generate_type_names(types: Collection[int]) -> None:
    logger.debug("Generating type names for %d types", len(types))
    out = {}

    for type_id in types:
        type_name = sde.types_by_id[type_id]["name"]["en"]
        out[type_id] = type_name

    output_path = config.paths.type_output / "typeNames.json"
    write_if_changed(output_path, out)


def generate_type_tree(types: Collection[int]) -> None:
    logger.debug("Generating type tree for %d types", len(types))
    out = {}

    for type_id in types:
        type = sde.types_by_id[type_id]

        group_id = type["groupID"]

        if group_id in out:
            out[group_id].append(type_id)
        else:
            out[group_id] = [type_id]

    out = {group_id: sorted(arr) for group_id, arr in out.items()}

    output_path = config.paths.type_output / "typeTree.json"
    write_if_changed(output_path, out)


def process_icons(icon_ids: Collection[int]) -> None:
    out = {}

    for icon_id in icon_ids:
        icon_id_str = str(icon_id)
        icon_path = sde.brackets[icon_id_str]["texturePath"]
        icon_name = icon_path.rsplit("/", 1)[-1]

        out[icon_id] = icon_name

    output_path = config.paths.type_output / "brackets.json"
    write_if_changed(output_path, out)


def generate_brackets(types: Collection[int]) -> None:
    logger.debug("Generating bracket icons for %d types", len(types))
    icon_ids = []

    out = {}

    def cache_icon_id(type_id: int, icon_id: int) -> None:
        nonlocal icon_ids, out

        if icon_id not in icon_ids:
            icon_ids.append(icon_id)
        out[int(type_id)] = icon_id

    for type_id in types:
        type = sde.types_by_id[type_id]
        type_id_str = str(type_id)

        group_id = type["groupID"]
        group_id_str = str(group_id)

        category = sde.groups_by_id[group_id]
        category_id = category["categoryID"]
        category_id_str = str(category_id)

        icon_id = None

        if category_id_str in sde.brackets_by_category:
            icon_id = sde.brackets_by_category[category_id_str]
            cache_icon_id(type_id, icon_id)

        if group_id_str in sde.brackets_by_group:
            icon_id = sde.brackets_by_group[group_id_str]
            cache_icon_id(type_id, icon_id)

        if type_id_str in sde.brackets_by_type:
            icon_id = sde.brackets_by_type[type_id_str]
            cache_icon_id(type_id, icon_id)

        if icon_id is None:
            cache_icon_id(type_id, config.type_data.default_icon)

    output_path = config.paths.type_output / "typeBrackets.json"
    write_if_changed(output_path, out)

    process_icons(icon_ids)


def generate_type_radii(collidable_types: Collection[int]) -> None:
    logger.debug("Generating radii data for %s collidable types", len(collidable_types))
    out = {}

    for collidable_type in collidable_types:
        radius = sde.types_by_id[collidable_type].get("radius")

        if radius is None:
            logger.warning(
                "Type %s does not have a defined radius in the SDE types file",
                collidable_type,
            )
            continue

        out[collidable_type] = int(radius)

    output_path = config.paths.type_output / "typeRadii.json"
    write_if_changed(output_path, out)


def generate_npc_types(groups: Collection[int]) -> None:
    logger.debug("Generating NPC types for %s groups", len(groups))
    types = fetch_types(groups)

    out = sorted(list(types))

    output_path = config.paths.type_output / "npcTypes.json"
    write_if_changed(output_path, out)


def generate_type_db() -> None:
    logger.debug("Syncing type data to database")
    types = []
    for id, row in sde.types_by_id.items():
        type = {
            "id": id,
            "group_id": row["groupID"],
            "faction_id": row.get("factionID"),
            "name": row["name"]["en"],
            "description": row.get("description", {}).get("en"),
            "published": row["published"],
        }

        types.append(type)

    logger.debug("Inserting %d types into database", len(types))
    with db.get_connection() as conn:
        changed = db.insert_types_batch(conn, types)

        logger.info("Updated %s types in database", changed)


def generate_type_data(collidable_types: Collection[int]) -> None:
    groups = fetch_groups()
    types = fetch_types(groups)

    wl_groups = fetch_wl_groups()
    for wl_group in wl_groups:
        groups.add(wl_group)

    for type_id in config.type_data.whitelist_types:
        types.add(type_id)

    generate_type_names(types)
    generate_type_tree(types)
    generate_group_names(groups)
    generate_brackets(types)
    generate_type_radii(collidable_types)
    generate_npc_types(config.type_data.npc_groups)

    generate_type_db()
