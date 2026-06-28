import argparse
import logging
import sys

from config import config, ensure_output_dirs, require_database_url, setup_logging
from fetch_sde import fetch_latest, fetch_sde, get_last_build, save_latest, cleanup_sde
from process import process
from utils import get_write_stats
import db

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EVE killmap SDE processor")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if the build is already up to date",
    )
    parser.add_argument(
        "--build",
        type=int,
        metavar="BUILD_NUMBER",
        help="Process a specific SDE build number instead of the latest",
    )
    return parser.parse_args()


def run() -> None:
    setup_logging(config)
    args = parse_args()
    require_database_url(config)
    logger.info("Starting SDE processing run")

    release_date = None
    if args.build is not None:
        build_number = args.build
        logger.info("Using specified build number: %d", build_number)
    else:
        try:
            build_number, release_date = fetch_latest()
        except Exception:
            logger.exception("Failed to fetch latest SDE metadata")
            raise

    last_build = get_last_build()
    if last_build is not None:
        logger.info("Last processed build: %d", last_build)
    else:
        logger.info("No previous build record found")

    if last_build == build_number:
        if not args.force:
            logger.info("Build %d is already up to date, nothing to do", build_number)
            return
        logger.info("Build %d already processed, forcing rebuild", build_number)
    else:
        logger.info("New build available: %d (previous: %s)", build_number, last_build)

    try:
        fetch_sde(build_number)
    except Exception:
        logger.exception("Failed to download SDE for build %d", build_number)
        raise

    logger.info("Preparing output directories")
    ensure_output_dirs(config)

    logger.info("Initializing database schema")
    try:
        with db.get_connection() as conn:
            db.init_schema(conn)
    except Exception:
        logger.exception("Failed to initialize database schema")
        raise

    logger.info("Starting processing pipeline")
    try:
        process()
    except Exception:
        logger.exception("Processing pipeline failed")
        raise

    logger.info("Processing pipeline complete")

    written, skipped, added_paths, modified_paths = get_write_stats()
    for path in added_paths:
        logger.debug("ADDED: %s", path)
    for path in modified_paths:
        logger.debug("MODIFIED: %s", path)
    logger.info(
        "%d files written (%d added, %d modified), %d skipped (unchanged)",
        written,
        len(added_paths),
        len(modified_paths),
        skipped,
    )

    save_latest(build_number, release_date)
    logger.info("Saved latest.json for build %d", build_number)

    logger.info("Cleaning up SDE folder")
    cleanup_sde()
    logger.info("SDE cleanup complete")

    logger.info("Run complete for build %d", build_number)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(1)
