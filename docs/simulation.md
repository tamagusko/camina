# Mock mode: a simulated Dublin network

`scripts/generate_mock_dublin.py` writes deterministic JSON fixtures to `data/mock/dublin/`
(gitignored). The dashboard reads them when `CAMINA_DATA_SOURCE=mock`, so it runs with no
database and no sensors. `scripts/run_dashboard.sh` generates them for you.

```bash
python scripts/generate_mock_dublin.py
```

## The network

Eight sensors on real Dublin streets, 14 days of 15-minute windows, seeded (`SEED = 20260421`)
so every run gives identical files.

| ID | Location | Zone | Transport |
|---|---|---|---|
| `cam-dub-01` | UCD Stillorgan Road Entrance | ucd | cellular |
| `cam-dub-02` | UCD Wynnsward Drive / Clonskeagh Entrance | ucd | cellular |
| `cam-dub-03` | N11 Belfield Flyover | ucd | wifi |
| `cam-dub-04` | UCD Foster's Avenue Entrance | ucd | cellular |
| `cam-dub-05` | Leeson Street Lower | corridor | cellular |
| `cam-dub-06` | Morehampton Road, Donnybrook | corridor | cellular |
| `cam-dub-07` | N11 Stillorgan Road at RTE / Montrose | corridor | wifi |
| `cam-dub-08` | Ranelagh Road | corridor | cellular |

- **UCD** sensors skew to pedestrians, cyclists and e-scooters, with weekday peaks at
  ~08:30 and ~17:30. **Corridor** sensors skew to cars, buses and freight.
- **Missing windows:** WiFi drops ~0.5% of windows, cellular ~1.5% (isolated gaps, seeded
  per sensor). Daily rollups show them as `window_count` < 96.
- Street geometry is a 2-point line per sensor; `transport` appears only in `sensors.json`
  (admin data), never in an ingest payload.

## Files

| File | Contents |
|---|---|
| `streets.json`, `streets.geojson` | Street lines (public) |
| `sensors.json` | Sensors, with admin-only coordinates and transport |
| `sensor_street_coverage.json` | Sensor → street |
| `sensor_readings.json` | 15-minute counts and speeds per class |
| `sensor_heartbeats.json` | 5-minute heartbeats, last 24 h |
| `sensor_daily_totals.json` | Daily rollups |
| `meta.json` | Seed, row counts, gap statistics |
