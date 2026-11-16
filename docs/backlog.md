# Backlog

Open items, next first. Remove an item when it's done (log it in `changelogs/`).

- **Real-hardware check (when a Pi with a BME280 is to hand):** run `pytest -m hardware -v` and
  `python main.py --once`. The v2 sensor code is only tested with fakes so far.
- Publish MQTT in Home Assistant auto-discovery format, so `configuration.yaml` entries aren't needed.
- Consider `retain` on MQTT messages, so HA shows a value immediately after a restart.
- Optionally publish more observation fields (`wind_direction`, `wind_gust`, `weather_code`).
