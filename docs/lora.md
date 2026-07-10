# CAMINA LoRaWAN Transport (Phase 4)

The LoRaWAN path is CAMINA's P1 transport: a bandwidth- and duty-cycle-limited
radio bearer for sensors that cannot use WiFi/cellular HTTPS. A sensor packs one
15-minute window of nine-class counts into a fixed **20-byte binary frame**,
transmits it over LoRaWAN to a gateway, and The Things Network (TTN) forwards it
base64-encoded to the ingest webhook `POST /api/ingest/lora/uplink`.

This document specifies the binary codec and the airtime/duty-cycle budget.
Companion implementations:

- Python packer/unpacker: `src/camina/io/lora_codec.py` (edge reference)
- TypeScript decoder: `dashboard/src/lib/lora-codec.ts` (webhook)
- Reference fixture packer (v1, historical): `pack_lora_reference` in
  `scripts/generate_mock_dublin.py`

## 1. Why a new schema (v2, 20 bytes)

The v1 reference codec (`pack_lora_reference`, 17 bytes) packed **every** class
as a single `uint8` (max 255). The Dublin simulation (`docs/simulation.md`)
showed `person` counts at UCD pedestrian peaks reaching **259–425 per 15-min
window** — a `uint8` field saturates and silently loses count.

v2 fixes this by **widening the three busy classes** — `person`, `cyclist`,
`car` — to `uint16` (max 65535), which comfortably covers any realistic Dublin
street density. The other six classes stay `uint8`; they never approach 255 at
any observed density, and the Python packer logs a warning if one ever clamps.
No saturation flag is needed for the widened classes.

## 2. Byte layout (schema version 2, big-endian)

Total **20 bytes**. Class order is the canonical nine-class taxonomy shared by
`CLASSES` (generator + `lora_codec.py`) and `ROAD_USER_CLASSES` (`types.ts`).

| Offset | Size | Field            | Type              | Notes |
|-------:|-----:|------------------|-------------------|-------|
| 0      | 3    | camera id        | ASCII             | `"LNN"`/`"DNN"`, e.g. `D01` |
| 3      | 4    | window start     | `uint32` BE       | unix epoch seconds, UTC |
| 7      | 2    | person           | `uint16` BE       | widened busy class |
| 9      | 2    | cyclist          | `uint16` BE       | widened busy class |
| 11     | 2    | car              | `uint16` BE       | widened busy class |
| 13     | 1    | e-scooter        | `uint8`           | clamps at 255 (warns) |
| 14     | 1    | SUV              | `uint8`           | clamps at 255 (warns) |
| 15     | 1    | motorcyclist     | `uint8`           | clamps at 255 (warns) |
| 16     | 1    | bus              | `uint8`           | clamps at 255 (warns) |
| 17     | 1    | delivery_van     | `uint8`           | clamps at 255 (warns) |
| 18     | 1    | truck            | `uint8`           | clamps at 255 (warns) |
| 19     | 1    | schema version   | `uint8`           | `== 2` |

struct format string: `">3sIHHHBBBBBBB"` (3 + 4 + 6 + 6 + 1 = 20 bytes).

`window_end` is not transmitted — it is derived at ingest as
`window_start + 900 s`. LoRa frames carry **no per-class speeds** (the HTTPS
path's `avg_speed_kmh` is empty for LoRa readings).

### Payload size vs. the caps

- **base64 of 20 bytes = 28 characters.** Well under the 200-character LoRa
  payload cap in `CLAUDE.md`.
- **20 raw bytes** is well under the **EU868 SF12 51-byte** application-payload
  limit — the tightest data-rate limit in the EU868 band (see §4). So a single
  window fits in one uplink at **every** EU868 spreading factor, SF7–SF12.

## 3. Ingest flow

1. TTN POSTs the uplink JSON to `/api/ingest/lora/uplink`.
2. The route verifies authenticity with a shared secret header
   `X-Camina-Webhook-Key` compared timing-safe against `TTN_WEBHOOK_KEY`
   (fail-closed in production if the secret is unset; dev skips only when unset
   and not production — same idiom as `cron-auth.ts`).
3. It parses `end_device_ids.device_id`, `uplink_message.frm_payload` (base64),
   and `received_at`, then decodes the frame.
4. The camera id in the frame is the authoritative sensor id.
5. **Live mode:** the window persists through the *same* idempotent upsert as
   the HTTPS counts path (`persistCounts`), so a duplicate TTN uplink is a no-op
   (deduped on the `(sensor_id, window_start, class_name)` primary key).
   **Mock mode:** the route validates and returns `202` without persisting.

## 4. Airtime and duty-cycle budget (EU868)

LoRaWAN EU868 imposes a **1% duty cycle** per sub-band (regulatory) and TTN adds
a **Fair Use Policy** of **30 s of airtime per device per day**. Each sensor
sends **96 uplinks/day** (one per 15-min window).

Airtime depends on the spreading factor (SF). For a **20-byte** application
payload (13-byte LoRaWAN MAC overhead → 33-byte PHY payload) at 125 kHz BW,
CR 4/5, EU868, approximate time-on-air per uplink:

| SF   | ~Airtime / uplink | ×96 uplinks/day | ≤ 30 s/day (TTN FUP)? | 1% duty cycle headroom |
|------|-------------------|-----------------|-----------------------|------------------------|
| SF7  | ~0.05 s           | ~5 s            | yes (large margin)    | trivially satisfied    |
| SF8  | ~0.10 s           | ~9 s            | yes                   | satisfied              |
| SF9  | ~0.18 s           | ~17 s           | **yes** (~13 s spare) | satisfied              |
| SF10 | ~0.33 s           | ~31 s           | **no** (~31 s > 30 s) | 1% ok, FUP exceeded    |
| SF11 | ~0.66 s           | ~63 s           | no                    | FUP exceeded           |
| SF12 | ~1.15 s           | ~110 s          | no                    | FUP exceeded           |

(Airtime figures are the standard EU868 125 kHz values; they scale with payload
but the 20-byte frame keeps them at the low end.)

**Conclusion.** The 96-uplink/day cadence fits comfortably within the EU868 1%
duty cycle at every SF. Against TTN's stricter 30 s/day Fair Use Policy, the
**maximum spreading factor that respects it at 96 uplinks/day is SF9**
(~17 s/day, ~13 s of margin). SF10 already exceeds the FUP (~31 s/day), so
sensors should be provisioned to keep the LoRaWAN Adaptive Data Rate (ADR) at
**SF9 or faster**. In practice, urban Dublin gateways give short links where ADR
settles at SF7–SF9, so the budget holds with wide margin. If a sensor is forced
to SF10+ by a poor link, either the reporting interval must lengthen or the
gateway placement must improve — the 20-byte frame is already minimal.
