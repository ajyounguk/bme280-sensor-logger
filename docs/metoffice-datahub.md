# Met Office Weather DataHub: Land Observations

**Base URL:** `https://data.hub.api.metoffice.gov.uk/observation-land/1`
**Auth:** an `apikey` HTTP header. The key never goes in the URL.

| Call | Returns |
| --- | --- |
| `GET /nearest?lat=51.5&lon=-0.12` | A JSON array of the nearest station(s): `geohash`, `area`, `region`, `country`, `olson_time_zone` |
| `GET /{geohash}` | A JSON array of 48 hourly observations (last 48 h), oldest first |

The fields the app uses from each observation:

| API field | App field | Unit |
| --- | --- | --- |
| `datetime` | `observedAt` | ISO-8601 UTC |
| `temperature` | `temperature` | °C |
| `humidity` | `humidity` | % |
| `mslp` | `pressure` | hPa (a safeguard treats values above 2000 as Pa) |
| `wind_speed` | `wind` | m/s, 10 m height, averaged over the previous 10 minutes |

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

Verified against the live API on 16 Nov 2026:
- The response shapes, field names and order match this page.
- `mslp` read 995 to 1012 over 48 h, which confirms hPa.
- The DataHub glossary gives `wind_speed` in m/s. It renders in a browser only:
  <https://datahub.metoffice.gov.uk/docs/glossary?models=mo-land-observations>

Other things seen in live data:
- `visibility` can arrive as a float.
- `pressure_tendency` is a letter, for example `F` or `R`.
