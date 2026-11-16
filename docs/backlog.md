# Backlog

Open items, next first. Remove an item when it's done (log it in `changelogs/`).

- **Pi run:** on the Pi, `pip install -r requirements.txt`, migrate `config.json` (`locationID` becomes
  `latitude`/`longitude`, plus the new key), run `pytest -m hardware -v` and `python main.py --once`, then restart
  under pm2.
- **Home Assistant:** after the Pi run, expect a step change in Met Office wind history. DataPoint reported mph and
  DataHub reports m/s, which HA's `unit_of_measurement` already says.
- Publish MQTT in Home Assistant auto-discovery format, so `configuration.yaml` entries aren't needed.
- Consider `retain` on MQTT messages, so HA shows a value immediately after a restart.
- Optionally publish more observation fields (`wind_direction`, `wind_gust`, `weather_code`).
