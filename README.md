# process-sde

This project is part of the larger [EVE Killmap](https://eve-killmap.com) project
and is used to process the EVE Online Static Data Export (SDE) into more digestable
JSON files for use by the [frontend client](https://github.com/eve-killmap/frontend)
and the [FastAPI backend](https://github.com/eve-killmap/backend).

It downloads CCP's latest SDE build, transforms it into compact JSON files for
the eve-killmap frontend (per-system data, map projections, slug/system indexes,
type data), and upserts type metadata into PostgreSQL.

## Note Regarding Some Static Data

Some of the static data used by this project to build JSON files for the frontend
isn't published in the SDE, but it is included in the static game client files.
This data includes:

- Bracket icons (these are the icons that denote solar system objects, such as
stargates, stations, planets, etc. in the UI when undocked)
- Bracket icon → type, group, and category mappings
- Disrupted stargate locations and destinations
- Moon mining beacon locations

Because this data isn't published in the SDE, it's extracted from the game client
files via another script, processed, and fed into this project via the `./static`
folder.

I have chosen not to publish the code that extracts this data, for a couple reasons:

- Although this data is technically accessible by anyone, CCP/FC haven't made it
public.
- Extracting this data required reverse engineering some game client code, and that
code is simply not mine to publish.

## Requirements

- Python 3.12+
- PostgreSQL (for the type-data sync)

## Setup

```sh
python -m venv venv
venv/Scripts/activate            # Windows; use source venv/bin/activate on POSIX
pip install -r requirements.txt  # add -dev for the test suite: requirements-dev.txt

cp .env.example .env             # then edit secrets (DATABASE_URL, USER_AGENT, ...)
cp config.example.yml config.yml # optional; omit to use built-in defaults
```

## Running

```sh
python main.py                  # process the latest build if it is newer than the last run
python main.py --force          # reprocess even if already up to date
python main.py --build 1234567  # process a specific build number
```

Generated files are written under `DATA_OUTPUT` (default `./data`).

## Configuration

Settings are resolved with the precedence **code defaults < `config.yml` <
environment / `.env`**. Because every value has a built-in default that
reproduces the original behavior, both `config.yml` and `.env` are optional
(though `DATABASE_URL` is required to actually run the pipeline).

### `.env`: secrets and machine/deployment-specific values

| Variable       | Purpose                                                    |
| -------------- | ---------------------------------------------------------- |
| `DATABASE_URL` | PostgreSQL connection string (required to run).            |
| `USER_AGENT`   | Contact-bearing User-Agent for SDE downloads (CCP rule).   |
| `DATA_OUTPUT`  | Output directory for generated JSON (default `./data`).    |
| `LOG_FILE`     | Log file path (default `./process-sde.log`).               |
| `LOG_LEVEL`    | Optional override of `logging.level` from `config.yml`.    |

Secrets are never written to the log.

### `config.yml`: non-secret, operator-tweakable settings

Sections: `logging` (level, rotation), `sde` (CCP endpoint URLs), `map`
(rounding, neighbour-map size, world-unit scale factors), `type_data` (category
/ whitelist / NPC-group ID lists, default icon), `processing` (`skip_system_ids`),
and `output` (Brotli precompression). See [`config.example.yml`](config.example.yml)
for the full documented set. Invalid or out-of-range values fail fast with a
clear `ConfigError`.

## Brotli precompression (optional)

With `output.precompress: true`, every generated JSON file gets a sibling
`<file>.br` written next to it, kept in lockstep: the `.br` is (re)written only
when the JSON content actually changes, and removed if it would otherwise go
stale. This lets nginx serve the precompressed bytes via `brotli_static on;`
with zero per-request CPU. It is off by default and requires the `Brotli`
package (already in `requirements.txt`).

Serve them with, in the relevant `location`:

```nginx
brotli_static on;   # requires the ngx_brotli module
```

Keep `gzip on;` and `gzip_vary on;` as the fallback for non-Brotli clients, and
make sure responses carry `Vary: Accept-Encoding` so shared caches key on the
encoding. Because nginx derives the ETag from the served file, the `.br` must
track the JSON exactly, which the lockstep behaviour above guarantees.

## Testing

```sh
pip install -r requirements-dev.txt
python -m pytest
```

The suite covers configuration loading/precedence/validation, pure helper
functions, the system builder, locale generation, and type-data selection. It
needs no network access, credentials, or database.
