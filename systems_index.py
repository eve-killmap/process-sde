import logging
from typing import Any

from config import config, SYSTEMS_FILENAME
from utils import write_if_changed

logger = logging.getLogger(__name__)


class SystemsIndexGenerator:
    """Accumulates the parallel system-name / system-ID arrays and writes them out."""

    def __init__(self) -> None:
        self.systems: dict[str, list[Any]] = {"systems": [], "systemIDs": []}

    def process_system(self, data: dict[str, Any]) -> None:
        self.systems["systems"].append(data["name"])
        self.systems["systemIDs"].append(data["solarSystemID"])

    def finalize(self) -> None:
        logger.info(
            "Finalizing systems index (%d systems)", len(self.systems["systemIDs"])
        )
        out_path = config.paths.universe_output / SYSTEMS_FILENAME
        if write_if_changed(out_path, self.systems):
            logger.debug("Systems index written to %s", out_path)
        else:
            logger.debug("Systems index unchanged, skipping %s", out_path)
