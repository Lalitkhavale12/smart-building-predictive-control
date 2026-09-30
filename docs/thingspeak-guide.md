<!-- generated-by: gsd-doc-writer -->
# ThingSpeak / Blynk IoT-Cloud Screenshot Guide

Syllabus IoT-cloud screenshot path: forward one building metric from a
successful run to a free-tier cloud channel and screenshot the cloud
dashboard. Optional per `REPRODUCE.md` §6 — never blocks report or dashboard.

Legend used on every step: `[done in repo]` = already implemented or
producible offline; `[manual: needs human + cloud account]` = requires a
human with a browser and a free-tier cloud account. No step below creates
accounts or sends network traffic by itself.

## 1. ThingSpeak account + channel setup [manual: needs human + cloud account]

1. Create a free ThingSpeak account and sign in (MathWorks ID).
   `[manual: needs human + cloud account]`.
2. Create one channel: **Channels → New Channel**. Name it e.g.
   `smart-building-weekday-seed00`.
   `[manual: needs human + cloud account]`.
3. Enable 8 fields and label them exactly as below
   (`timestamp` maps to ThingSpeak's built-in `created_at`, not to a field).
   `[manual: needs human + cloud account]`.

   Source schema is `sim/logger.py` `TELEMETRY_COLUMNS` `[done in repo]`:

   `timestamp, room, T_in_C, T_out_C, RH_pct, occupancy, HVAC_state, power_kW, light_on`

   | ThingSpeak slot | Telemetry column | Notes |
   |---|---|---|
   | `created_at` | `timestamp` | ISO-8601 sim-time (`sim/logger.py:sim_timestamp`, `RUN_START` 2026-01-15T00:00:00). Paste into the import CSV's `created_at` column. |
   | Field 1 | `T_in_C` | Room indoor temp [°C], 4 decimals. |
   | Field 2 | `T_out_C` | Outdoor temp [°C], 4 decimals. |
   | Field 3 | `RH_pct` | Relative humidity [%]. |
   | Field 4 | `occupancy` | Persons (int). |
   | Field 5 | `HVAC_state` | Text `{OFF, REDUCED, ON}`. ThingSpeak charts numeric fields best — encode `OFF=0, REDUCED=1, ON=2` on upload and note the mapping in the field label (e.g. `HVAC (0=OFF 1=RED 2=ON)`). |
   | Field 6 | `power_kW` | Electrical power [kW], 4 decimals (`|Q_hvac|/COP + light`). |
   | Field 7 | `light_on` | `0`/`1`. |
   | Field 8 | `room` | Room name (`classroom_A`, `classroom_B`, `office`, `lab` per `sim/config.py:ROOMS`). For a per-room chart use one channel per room and leave Field 8 constant; for the recommended aggregated channel put `all` or the seed id here. |

4. One channel per room vs one building-aggregated channel: **use one
   building-aggregated channel** `[manual: needs human + cloud account]`.
   Reason `[done in repo]`: free-tier rate limit is one update per 15 s per
   channel; 4 rooms × 1440 one-minute steps = 5760 rows/day. Four channels
   quadruple the upload and chart work; one aggregated channel (hourly or
   per-minute building totals) fits the limit with margin and still proves
   the IoT-cloud path. Keep per-room channels only if the report needs a
   per-room screenshot — same 8-field layout, Field 8 = room name.
5. Aggregated-channel recipe `[manual: needs human + cloud account]` (compute
   offline first, `[done in repo]` via pandas):
   - `T_in_C` → mean across 4 rooms per timestamp.
   - `T_out_C` → mean (identical across rooms by construction).
   - `RH_pct` → mean.
   - `occupancy` → sum (building headcount).
   - `HVAC_state` → number of rooms ON (0–4), label field accordingly.
   - `power_kW` → sum (building load — the headline energy metric).
   - `light_on` → sum (0–4 rooms lit).
   - `room` → `all`.
6. Save the channel's **Write API Key** (API Keys tab) somewhere private —
   needed for §3. Never commit it `[manual: needs human + cloud account]`.

## 2. Manual upload path (recommended — no credentials in code)

Use this path for the report screenshot. No API key in the repo, no network
from Python, fully reproducible from committed CSVs.

1. Produce the CSV `[done in repo]`:

   ```bash
   python -m sim.run --scenario weekday --days 1 --seed 0
   ```

   Output: `results/weekday/seed00/telemetry.csv` (+ `run_meta.json`).
   For controller-comparison data use the matrix output instead:
   `results/full_matrix/<controller>/<scenario>/seed<NN>/telemetry.csv`
   (e.g. `results/full_matrix/c4-with/weekday/seed00/telemetry.csv`),
   produced by `eval/matrix.py` via `python -m eval.report`.
   Both files carry the exact `TELEMETRY_COLUMNS` order from §1.
2. Aggregate (only for the recommended single-channel upload) `[done in repo]`:

   ```bash
   python - <<'PY'
   import pandas as pd
   df = pd.read_csv("results/full_matrix/c4-with/weekday/seed00/telemetry.csv",
                    parse_dates=["timestamp"])
   g = df.groupby("timestamp")
   agg = pd.DataFrame({
       "created_at": g["timestamp"].first(),
       "field1": g["T_in_C"].mean().round(4),
       "field2": g["T_out_C"].mean().round(4),
       "field3": g["RH_pct"].mean().round(4),
       "field4": g["occupancy"].sum(),
       "field5": g["HVAC_state"].map({"OFF": 0, "REDUCED": 1, "ON": 2}).groupby(df["timestamp"]).max(),
       "field6": g["power_kW"].sum().round(4),
       "field7": g["light_on"].sum(),
       "field8": "all",
   })
   agg.to_csv("results/thingspeak_upload.csv", index=False)
   print(f"wrote results/thingspeak_upload.csv ({len(agg)} rows)")
   PY
   ```

   For a per-room upload skip the aggregation and export one room's rows
   with columns renamed to `created_at,field1..field8` in the §1 order.
   `results/` is gitignored — the upload CSV is a scratch artifact, never
   committed.
3. Import: ThingSpeak channel → **Import / Export → Import CSV**, upload
   `results/thingspeak_upload.csv` `[manual: needs human + cloud account]`.
   UNVERIFIED: the exact import-button label varies by ThingSpeak UI
   revision — if no import button exists, fall back to the §3 MQTT publish
   path one row at a time (1-min steps clear the 15 s limit).
4. MATLAB visualization snippet for the energy plot
   (channel → Apps → MATLAB Visualizations → New → Custom)
   `[manual: needs human + cloud account]` — paste:

   ```matlab
   % Building total power (Field 6) vs time — mirrors report G1.
   data = thingSpeakRead(CHANNEL_ID, 'Fields', 6, 'NumPoints', 1440);
   plot(data.Timestamps, data.BuildingPowerkW, 'LineWidth', 1.5);
   xlabel('sim time'); ylabel('total power [kW]');
   title('C4-with weekday seed00 — building power (ThingSpeak)');
   grid on;
   ```

   Replace `CHANNEL_ID` with the numeric channel ID and
   `BuildingPowerkW` with the actual Field-6 variable name ThingSpeak
   assigns. UNVERIFIED: variable naming (`data.<FieldName>`) depends on
   the field labels entered in step 1 — adjust to match the live table.
   Add a second visualization reading Field 4 (occupancy) to mirror the
   G1 occupancy shade.

## 3. MQTT publish path to ThingSpeak (alternative, live)

Publishes from Python straight to the ThingSpeak broker. Use only if the
manual CSV import is unavailable.

- Broker: `mqtt3.thingspeak.com`, port `1883` (TLS `8883` UNVERIFIED —
   not tested from this repo; local `mosquitto.conf` documents only the
   lab `listener 1883` anonymous setup `[done in repo]`).
- Topic UNVERIFIED: `channels/<CHANNEL_ID>/publish` with payload
  `field1=..&field2=..&...&api_key=<WRITE_API_KEY>` per public ThingSpeak
  MQTT docs — not exercised by any code or test in this repo, so verify
  against the channel's API Keys page before use.
- Credentials `[manual: needs human + cloud account]`: username = any
  string (convention: MQTT device ID), password = the channel Write API
  Key from §1 step 6. Never commit the key; pass via environment variable.
- Client code pointer `[done in repo]`: reuse `iot/mqtt_client.py`
  `MqttClientWrapper` (paho-mqtt 2.1.0, `CallbackAPIVersion.VERSION2`,
  MQTT v3.1.1 default — see `default_client_factory`). Example shape
  (adapt topic/key at runtime, do not hardcode):

  ```python
  from iot.mqtt_client import MqttClientWrapper
  w = MqttClientWrapper("thingspeak-pub")
  w.connect("mqtt3.thingspeak.com", 1883, 60)  # UNVERIFIED host/port
  w.start_loop()
  w.publish("channels/<CHANNEL_ID>/publish",  # UNVERIFIED topic shape
            "field1=24.5&field6=1.17&api_key=$TS_KEY", qos=0, retain=False)
  ```

- QoS note `[done in repo]`: telemetry publishes at QoS 0, never retained
  (`iot/node.py:publish_telemetry`, `iot/bridge.py`); commands use QoS 1.
  ThingSpeak ingestion is at-most-once — QoS 0 matches; do not use
  retained messages (a retained stale row replays on every reconnect).
- Rate limit: free tier accepts one update per channel per 15 s. Our sim
  cadence is 1 min (`sim/config.py:DT_S = 60`, firmware `delay(60000)` in
  `iot/esp32_node.ino`) — one publish per sim minute fits with 4× margin.
  Never publish the 4 rooms to one channel faster than 15 s apart; either
  aggregate (§1 step 5) or space per-room publishes ≥15 s.

## 4. ESP32 sketch pointer [done in repo]

- `iot/esp32_node.ino` publishes JSON telemetry (keys in
  `TELEMETRY_COLUMNS` order) to `building/<ROOM_ID>/telemetry` at QoS 0 on
  the **local** Mosquitto (`MQTT_HOST "host.wokwi.internal"` via the Wokwi
  Private Gateway, port 1883; see `docs/protocols.md` for why MQTT won and
  `mosquitto.conf` for the lab broker). The Wokwi run is manual, never CI.
- To route a node to ThingSpeak instead of the local broker, change at
  minimum (all UNVERIFIED against live ThingSpeak — marked, not guessed):
  1. `MQTT_HOST` → the ThingSpeak MQTT host, `MQTT_PORT` → its port.
  2. `client.connect(...)` → the overload carrying username/password so
     the Write API Key is sent.
  3. `TELEMETRY_TOPIC` → the ThingSpeak channel publish topic, and the
     payload builder → the `field1=..&field2=..` form (PubSubClient
     default 256 B buffer already raised to 512 via `setBufferSize` —
     keep it; an 8-field payload still fits).
  4. Keep `delay(60000)` — it already satisfies the 15 s free-tier limit.
- Recommended instead: leave the firmware untouched and forward from
  Python (`iot/bridge.py:TelemetryBridge` already subscribes to
  `building/+/telemetry` `[done in repo]`) — one bridge edit beats four
  sketch edits and keeps the Wokwi demo on the local broker.

## 5. What the screenshot must show (report mapping)

Capture the ThingSpeak channel view showing at least two charts on the same
time window (one full simulated day): **Field 6 building power** and
**Field 4 occupancy** `[manual: needs human + cloud account]`. The shot must
visibly contain the channel name, the field labels from §1, and the sim date
(2026-01-15 window from `RUN_START`). Save as PNG and reference it in the
report alongside the matplotlib figures — it is a syllabus IoT-cloud
deliverable, not a replacement for any G-figure.

| Screenshot element | Maps to report figure | Why the pair matters |
|---|---|---|
| Field 6 power chart | G1 24 h load shape (`fig_g1_24h_profile.png`) | Same signal (building kW vs time); G1 is the controlled C3-vs-C4 comparison, the screenshot proves the cloud path carries it. |
| Field 4 occupancy chart | G1 occupancy shade / G5 forecaster input | Occupancy drives the savings story; matches the shade on G1 and the forecast target in G5. |
| Channel header (name + date) | `run_meta.json` (seed, scenario, git hash) | Ties the cloud shot to one exact run — cite seed/scenario in the caption. |
| Optional Field 1/3 (T_in, RH) | G3 comfort context (22–26 °C / 30–60 %RH band) | Shows comfort stayed in band while energy dropped. |

Caption template: `ThingSpeak channel <name> — <scenario> seed<NN>,
building-aggregated power (F6) + occupancy (F4); cf. G1.`

## 6. Blynk fallback (5 lines)

1. Create a free Blynk account → New Template → 8 Datastreams mirroring the §1 field table (V0–V7) `[manual: needs human + cloud account]`.
2. Export the same `results/thingspeak_upload.csv` columns to V0–V7 via one Blynk HTTP GET per row (`blynk.cloud/external/api/update?token=<TOKEN>&v5=<power>…`) `[manual: needs human + cloud account]`.
3. Keep ≥15 s between writes (1-min sim steps fit fine) `[done in repo: DT_S=60]`.
4. Screenshot the Blynk web dashboard showing power + occupancy widgets with template name and date visible `[manual: needs human + cloud account]`.
5. Caption it exactly like §5, swapping "ThingSpeak" for "Blynk (fallback)" — same G1 mapping applies `[manual: needs human + cloud account]`.
