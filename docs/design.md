# Design

## What it does

Every `app.readingIntervalSeconds` (default 600 s) one cycle runs:

1. Read the sensor (`src/sensor.py`): a real BME280 over I2C, or `FakeSensor` when `sensor.type` is `"fake"`.
2. Publish the reading to MQTT (`mqtt.sensorTopic`) and insert it into MongoDB, for each output that is enabled.
3. If the Met Office is enabled and a poll is due, fetch the latest station observation. New observations are
   inserted into MongoDB once. The latest observation is published to MQTT every cycle.
4. Sleep until the next cycle, or stop cleanly on SIGTERM (pm2/systemd) or Ctrl+C.

A failure in any one output (sensor, MQTT, MongoDB, Met Office) is logged and the cycle carries on.

## Modules

| File | Role |
| --- | --- |
| `main.py` | CLI (`--config`, `--once`), logging, `App` (one cycle, loop, shutdown) |
| `src/config.py` | Loads and validates `config.json` into frozen dataclasses; masked summary for the start-up log |
| `src/sensor.py` | `Bme280Sensor` (lazy hardware imports) and `FakeSensor` |
| `src/metoffice.py` | DataHub Land Observations client, response parser, quota guard, `MetOfficePoller` |
| `src/mqtt_handler.py` | paho-mqtt 2.x: connect, wait for CONNACK, QoS 1 publish confirmed, disconnect |
| `src/mongo.py` | One long-lived `MongoClient`, inserts, de-duplication of observations |

## Decisions

- **Met Office: Land Observations, not Site Specific.** The original code used DataPoint `wxobs`, which returns
  hourly observations from the nearest station. DataPoint was retired in 2025. On Weather DataHub the like-for-like
  replacement is Land Observations (about 150 UK stations, hourly, last 48 h). Site Specific (Global Spot) returns
  forecasts, which would silently change what "outside temperature" means. (16 Nov 2026)
- **Location is lat/lon.** It is resolved to the nearest station's geohash once at start-up, then cached, as the DataHub
  FAQ recommends. An optional `geohash` setting skips the lookup.
- **The Met Office poll is decoupled from the sensor interval.** Observations update hourly, so `pollIntervalSeconds`
  defaults to 3600. The validator rejects anything under 300 s (at most 288 calls/day against the free plan's 360).
  A local daily budget of 340 calls and an HTTP 429 handler both suspend calls until 00:00 UTC, when the quota
  resets. After a transient failure the poller retries after 10 minutes rather than waiting a full hour.
- **De-duplication by `observedAt`.** The old code skipped a Met Office insert if any document existed in the
  current clock hour. Now each observation carries its timestamp from the API, and Mongo skips the insert if that
  `source` + `observedAt` pair already exists. This also covers several devices sharing one collection.
- **MQTT connects per cycle.** With a 10-minute interval this is simpler than a persistent connection and recovers
  from broker restarts without any reconnect logic. The handler waits for CONNACK, so bad credentials are reported
  as such, and it confirms each QoS 1 publish before disconnecting.
- **Payload shapes are unchanged** from v1, so existing Home Assistant templates and Mongo charts keep working.
  Met Office messages gain `observedAt`, which is additive.
- **Config keys stay compatible with v1** (`i2c_port`, `mqttUsername` and so on). The only breaking change is
  replacing `metoffice.locationID` (a DataPoint ID) with `latitude`/`longitude`. A v1 config gets a clear migration
  error.
- **Five runtime dependencies, all pinned.** Validation and logging use the standard library only.

## Met Office API notes

See [metoffice-datahub.md](metoffice-datahub.md).
