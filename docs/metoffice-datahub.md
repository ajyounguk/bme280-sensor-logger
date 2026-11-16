# Met Office Weather DataHub: Land Observations

**Base URL:** `https://data.hub.api.metoffice.gov.uk/observation-land/1`
**Auth:** an `apikey` HTTP header. The key never goes in the URL.

| Call | Returns |
| --- | --- |
| `GET /nearest?lat=51.5&lon=-0.12` | A JSON array of the nearest station(s): `geohash`, `area`, `region`, `country`, `olson_time_zone` |
| `GET /{geohash}` | A JSON array of hourly observations for the last 48 h |

The fields the app uses from each observation:

| API field | App field | Unit |
| --- | --- | --- |
| `datetime` | `observedAt` | ISO-8601 UTC |
| `temperature` | `temperature` | °C |
| `humidity` | `humidity` | % |
| `mslp` | `pressure` | hPa (values above 2000 are treated as Pa and divided by 100) |
| `wind_speed` | `wind` | m/s |

Other fields (`wind_direction` as a 16-point compass string, `wind_gust`, `visibility`, `weather_code`,
`pressure_tendency`) are ignored for now. Fields can be missing for a given site and hour. The parser picks the
newest observation that has a temperature.

## Plan and limits

- Free plan: **360 calls per day**, reset at 00:00 UTC. Over quota, the API returns **HTTP 429**.
- Land Observations is its own subscription on DataHub. A Site Specific key won't work, so a 401/403 is reported
  as "check it is a Land Observations subscription key".
- Shown on the Met Office site at the time of writing: around 150 stations, roughly 50 km apart, updated hourly.

## Sign-up

1. Register at <https://datahub.metoffice.gov.uk/>.
2. Subscribe to **Land Observations**, free plan.
3. Copy the API key from the subscription into `metoffice.APIKey` in `config/config.json`.

## Provenance

The official API reference page needs a login. The endpoint paths and field names above come from the DataHub
overview and FAQ pages plus two open-source clients. Units for `mslp` and `wind_speed` still need checking against
a live response (see [backlog.md](backlog.md)).
