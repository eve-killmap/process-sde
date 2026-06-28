import logging
from typing import Any

from config import config, SLUG_INDEX_FILENAME
from utils import slugify, write_if_changed

logger = logging.getLogger(__name__)


class SlugIndexGenerator:
    """Accumulates a slug -> solar system ID index and writes it out."""

    def __init__(self) -> None:
        self.slug_index: dict[str, int] = {}

    def process_system(self, data: dict[str, Any]) -> None:
        slug = slugify(data["name"])
        self.slug_index[slug] = data["solarSystemID"]

    def finalize(self) -> None:
        logger.info("Finalizing slug index (%d entries)", len(self.slug_index))
        out_path = config.paths.universe_output / SLUG_INDEX_FILENAME
        if write_if_changed(out_path, self.slug_index):
            logger.debug("Slug index written to %s", out_path)
        else:
            logger.debug("Slug index unchanged, skipping %s", out_path)
