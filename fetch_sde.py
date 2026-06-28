import json
import logging
import zipfile
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

from config import config

logger = logging.getLogger(__name__)


def _latest_path() -> Path:
    return config.paths.data_output / "latest.json"


def fetch_latest() -> tuple[int, str]:
    logger.info("Fetching latest SDE metadata from %s", config.sde.latest_url)
    req = Request(config.sde.latest_url, headers={"User-Agent": config.sde.user_agent})
    with urlopen(req) as response:
        content = response.read().decode("utf-8")

    data = json.loads(content.strip())
    build_number = data["buildNumber"]
    release_date = data["releaseDate"]
    logger.debug("Latest available build: %d (released %s)", build_number, release_date)
    return build_number, release_date


def fetch_sde(build_number: int) -> None:
    url = config.sde.archive_url.format(build_number=build_number)
    logger.info("Downloading SDE archive for build %d", build_number)

    req = Request(url, headers={"User-Agent": config.sde.user_agent})

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        with urlopen(req) as response:
            shutil.copyfileobj(response, tmp)
        tmp_path = tmp.name

    logger.debug("SDE archive downloaded to temporary file %s", tmp_path)

    sde_input = config.paths.sde_input
    try:
        if sde_input.exists():
            logger.debug("Removing existing SDE folder at %s", sde_input)
            shutil.rmtree(sde_input)
        sde_input.mkdir(parents=True, exist_ok=True)

        logger.debug("Extracting SDE archive to %s", sde_input)
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(sde_input)
        logger.info("SDE archive extracted successfully")
    finally:
        Path(tmp_path).unlink()


def get_last_build() -> int | None:
    latest_path = _latest_path()
    if not latest_path.exists():
        return None
    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return int(data["buildNumber"])
    except (ValueError, KeyError, OSError) as e:
        logger.warning("Could not read last build from latest.json: %s", e)
        return None


def save_latest(build_number: int, release_date: str | None) -> None:
    config.paths.data_output.mkdir(parents=True, exist_ok=True)
    data = {
        "buildNumber": build_number,
        "releaseDate": release_date,
        "buildTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with _latest_path().open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.debug("Saved latest.json for build %d", build_number)


def cleanup_sde() -> None:
    sde_input = config.paths.sde_input
    if sde_input.exists():
        logger.debug("Removing SDE folder at %s", sde_input)
        shutil.rmtree(sde_input)
    else:
        logger.debug("SDE folder does not exist, nothing to clean up")
