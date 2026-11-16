# Backlog

Open items, next first. Remove an item when it's done (log it in `changelogs/`).

- **Live DataHub check:** once a Land Observations key is in `config/config.json`, make one real call. Confirm the
  `nearest` and observation shapes, and the units of `mslp` (hPa?) and `wind_speed` (m/s?), then update
  [metoffice-datahub.md](metoffice-datahub.md) and `tests/fixtures/` if anything differs.
- **Pi run:** on the Pi, `pip install -r requirements.txt`, migrate `config.json` (`locationID` becomes
  `latitude`/`longitude`, plus the new key), run `pytest -m hardware -v` and `python main.py --once`, then restart
  under pm2.
- **Home Assistant:** after the Pi run, check that the Met Office wind value looks right. DataPoint reported mph,
  DataHub is believed to report m/s, so HA's history will show a step change.
- Publish MQTT in Home Assistant auto-discovery format, so `configuration.yaml` entries aren't needed.
- Consider `retain` on MQTT messages, so HA shows a value immediately after a restart.
- Optionally publish more observation fields (`wind_direction`, `wind_gust`, `weather_code`).
