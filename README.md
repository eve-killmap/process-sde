# process-sde

The batch static data export (SDE) processor behind [EVE Killmap](https://eve-killmap.com). On each new SDE build it downloads CCP's JSONL export and writes compact JSON the [frontend](https://github.com/eve-killmap/frontend) loads directly: per-system files, 2D/3D map projections, slug and system-name indexes, and type data. It also upserts type metadata into the PostgreSQL database shared with the [process-kills](https://github.com/eve-killmap/process-kills) and [backend](https://github.com/eve-killmap/backend) projects, and reads the `kills` table process-kills maintains to decide which ship types need type data.

A small set of client-extracted files not published in the SDE (bracket icons, disrupted stargates, mining beacons) are consumed from `./static`. These are not part of this repository.

Requires Python 3.12+ and PostgreSQL. Install `requirements.txt`, copy `.env.example` to `.env` and fill in `DATABASE_URL` and the other values, optionally copy `config.example.yml` to `config.yml`, then run the script with `python main.py`. The script processes the latest build if it is newer than the last run, `--force` to reprocess regardless, or `--build N` for a specific build. The test suite (`requirements-dev.txt`, `python -m pytest`) needs no network, credentials, or database.

## Bugs and feature requests

Please report bugs and request features in the [frontend repository](https://github.com/eve-killmap/frontend/issues), which is the main entry point for the project. Open an issue here only if you are sure the problem originates within this project.
