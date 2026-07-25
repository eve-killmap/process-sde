import logging

import sde
from config import config

from generate_system import SystemBuilder
from generate_map import MapGenerator, NewEdenMapGenerator
from generate_type_data import generate_type_data
from slug_index import SlugIndexGenerator
from systems_index import SystemsIndexGenerator

logger = logging.getLogger(__name__)


def process() -> None:
    sde.load()

    system_builder = SystemBuilder()
    slug_generator = SlugIndexGenerator()
    systems_generator = SystemsIndexGenerator()

    scale_factors = config.map.scale_factors
    logger.info("Initializing map generators")
    new_eden_generator = NewEdenMapGenerator(
        output_folder="new-eden", scale_factor=scale_factors["au"]
    )
    anoikis_generator = MapGenerator(
        output_folder="anoikis",
        scale_factor=scale_factors["au"],
        process_stargates=False,
        translate_positions=True,
    )
    ad_generator = MapGenerator(
        output_folder="abyssal-deadspace",
        scale_factor=scale_factors["abyssal_deadspace"],
        process_stargates=False,
        translate_positions=True,
    )
    tut_generator = MapGenerator(
        output_folder="tutorials",
        scale_factor=scale_factors["tutorials"],
        process_stargates=False,
        translate_positions=True,
    )

    total = len(sde.solar_systems)
    logger.info("Processing %d solar systems", total)

    for system_id, row in sde.solar_systems.items():
        if system_id in config.skip_system_ids:
            logger.debug("Skipping system %d (in skip list)", system_id)
            continue

        logger.debug(
            "Processing system %d (%s)", system_id, row.get("name", {}).get("en", "?")
        )
        built = system_builder.build(row)
        map_data = built.map_data
        system_type = built.system_type

        systems_generator.process_system(built.file_data)
        slug_generator.process_system(built.file_data)

        if system_type == 0:
            new_eden_generator.process_system(map_data, built.position_2d)
        elif system_type == 1:
            anoikis_generator.process_system(map_data)
        elif system_type == 2:
            ad_generator.process_system(map_data)
        elif system_type == 4:
            tut_generator.process_system(map_data)
        else:
            raise ValueError(
                f"Unable to determine system type for solarSystemID {system_id}"
            )

    logger.info("Finished processing solar systems, finalizing output files")

    systems_generator.finalize()
    slug_generator.finalize()

    new_eden_generator.finalize()
    anoikis_generator.finalize()
    ad_generator.finalize()
    tut_generator.finalize()

    logger.info("Generating locale data")
    new_eden_generator.process_locales()
    anoikis_generator.process_locales()
    ad_generator.process_locales()
    tut_generator.process_locales()

    logger.info("Generating type data")
    generate_type_data(system_builder.collidable_types)
