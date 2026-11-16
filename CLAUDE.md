# bme280-sensor-logger: rules for Claude

Python app for a Raspberry Pi: reads a BME280 (temperature, pressure, humidity) and Met Office outdoor observations,
publishes to MQTT (Home Assistant) and/or MongoDB. Design and decisions: [docs/design.md](docs/design.md).
**Don't re-propose its decisions** unless something changes the reason; if you think it has, say why in one line and ask.
Machine-specific notes live in `CLAUDE.local.md` (git-ignored). Read it if it exists.

## Commands
- Setup: `python -m venv .venv`, then `pip install -r requirements-dev.txt`
- Tests: `python -m pytest` (the hardware test skips itself off-Pi; on the Pi: `pytest -m hardware -v`)
- Lint: `ruff check .` and `ruff format .`. CI runs both plus pytest with `-W error::DeprecationWarning`
  (Ubuntu + Windows, Python 3.11 + 3.13).
- Run without hardware: `python main.py --config config/config-fake.json --once`

## Rules
- **Public repo:** nothing tracked may mention the author's homelab, hosts, IPs, real locations or credentials. Put
  those in `CLAUDE.local.md` or `docs/local/` (both git-ignored). `config/config.json` is git-ignored and holds the
  real keys; only `config-example.json` (placeholders) and `config-fake.json` are tracked.
- **Never log secrets.** The start-up summary masks them via `Config.summary()`; keep new fields masked there too.
- **Payload shapes are a contract.** MQTT/Mongo keys (`source`, `temperature`, `pressure`, `humidity`, `wind`, plus
  `deviceName`/`observedAt` for Met Office) are used by Home Assistant templates and Mongo charts. Additive changes only.
- **Met Office free plan = 360 calls/day.** Keep the poll interval floor (`MIN_METOFFICE_POLL_SECONDS`) and the local
  daily budget in `src/metoffice.py`. Tests never hit the network: use the fakes in `tests/conftest.py`.
- Runtime deps stay at five (`requirements.txt`); tooling goes in `requirements-dev.txt`. Pin exact versions.
- Hardware libraries are imported lazily so everything runs on Windows with `sensor.type: "fake"`.
- Commit/push only when asked; branch first if on `main`. Log changes in `docs/changelogs/YYYY-MM.md`; open items in
  [docs/backlog.md](docs/backlog.md). Dependency/security refreshes are tracked by `/project-health`.
