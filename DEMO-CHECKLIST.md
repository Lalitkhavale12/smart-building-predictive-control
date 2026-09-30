# Demo Rehearsal Checklist (~15 min total)

Rehearse in order. Fallback line for every section — if anything fails live,
say the line, show the simulated path, move on. Never claim a live-broker
result you did not just run.

## 0. Setup (before the room, ~3 min)

1. `pip install -r requirements.txt` — Python 3.12 for TF-strict training
   machines, else the pinned interpreter in `REPRODUCE.md`.
2. Install Mosquitto 2.0.22 (Windows x64):
   `https://mosquitto.org/files/binary/win64/mosquitto-2.0.22-install-windows-x64.exe`
3. Start the broker with the repo config (keep this window visible):
   `mosquitto -c mosquitto.conf -v`
   Expect `Opening ipv4 listen socket on port 1883`. Config is local-only,
   anonymous (`mosquitto.conf`); the TLS block stays commented (Unit-3 note).
4. Pre-generate the report once: `python -m eval.report` → 7 figures in
   `results/figures/`, 11 tables in `results/report_tables/` (~1 min).

> Fallback: "Broker unavailable on this machine — showing the simulated
> roundtrip; the unit suite covers the live path."

## 1. Live MQTT roundtrip (~2 min)

`python scripts/live_broker_demo.py --steps 30 --scenario weekday --start-minute 530`

- `--start-minute 530` fast-forwards sim-time under OFF hold to just before
  the ~09:00 arrival, so the 30 demo steps show occupied rooms, ON commands,
  and the thermostat cutout cycling power (no physics change, stated on screen).
- Watch for the `MODE:` line first — `live-broker` with Mosquitto up,
  `simulated (FakeBroker …)` without. Name it out loud either way.
- Per-step lines: occupancy → C3 setback commands → sim steps, telemetry
  flowing `building/+/telemetry`, commands QoS 1 never-retained
  (`iot/topics.py` is the single source of truth).
- Final `RESULT` line: energy kWh + comfort % for the 12 steps.
- (Optional, MQTT Explorer open on `building/#`: telemetry ticking,
  `building/<room>/status` retained online.)

> Fallback: "Broker unavailable — showing simulated roundtrip, unit suite
> covers the live path." Then run
> `pytest tests/test_integration_mqtt.py -q` to show the live gate skipping
> cleanly (2 skipped = by design, not failure).

## 2. Dashboard (~2 min)

`streamlit run dashboard/app.py` → `http://localhost:8501`

- Energy / comfort / savings sections over the saved Phase-5 artifacts;
  empty `results/` shows a guided warning (run step 0.4 first).
- Keep the default localhost bind — never `--server.address 0.0.0.0` on a
  shared network.

> Fallback: screenshots in `results/figures/fig_g7_dashboard.png` + the PNGs
> below — the whole story survives without a live dashboard.

## 3. Report figures, in order (~5 min)

Honest thesis throughout: **prediction buys comfort-per-kWh, not absolute
savings; peak-shifting is ~zero.** Say it up front, then each figure is
evidence, not hype.

| # | Figure | One-line talking point |
|---|--------|------------------------|
| G1 | `fig_g1_24h_profile.png` | 24 h energy trace: controllers separate at occupied hours, converge overnight. |
| G2 | `fig_g2_savings.png` | Savings vs C3 across scenarios/seeds — C4-with sits slightly *negative*: it spends a little more energy than setback. |
| G3 | `fig_g3_pareto.png` | Energy-vs-comfort Pareto: C4-with is the comfort-per-kWh point — more comfort per unit energy, not less energy. |
| G4 | `fig_g4_co2.png` | CO₂ and cost follow energy 1:1 — there is no separate carbon miracle, only the energy story repriced. |
| G5 | `fig_g5_pred_actual.png` | Predicted-vs-actual occupancy: the forecast is good enough to pre-cool/early-off on, which is where the comfort gain comes from. |
| G6 | `fig_g6_ablation.png` | Ablations (forecast off / carbon off): killing the forecast collapses C4 to C3 exactly — the fallback path *is* the ablation arm. |
| G7 | `fig_g7_dashboard.png` | Live dashboard screenshot — the same view as section 2, frozen for the report. |

Shifting addendum (`shifting_peak_share.csv`): C4−C3 peak-share deltas hover
around ±0.001 — no load shifting achieved; pre-cooling is comfort-timed, not
tariff-timed. Say it, don't hide it.

## 4. Kill-a-node fault demo (~2 min)

`pytest tests/test_faults.py tests/test_bridge.py -q` (~10 s, brokerless)

- Narrate: 4-room fleet, kill room 2 → 3 survivors × 3 cycles green, retained
  `status` reads offline (LWT fired), `sim.minute` keeps stepping.
- Seeded 10 % drop × 200 msgs: zero exceptions, gaps counted not crashed.
- Bridge resubscribes telemetry+status wildcards on every reconnect.
- Live variant (broker up): `Ctrl+C` one `mosquitto_pub`… simpler — kill a
  node by disconnecting it and watch the retained offline status in MQTT
  Explorer while the other three keep flowing.

> Fallback: "Fault proofs run on FakeBroker by design — deterministic and
> faster than pulling cables; the two live-path tests gate on a real broker."

## 5. Close (~1 min)

- Restate the thesis in one sentence: occupancy forecasts traded a small
  energy premium for higher comfort — comfort-per-kWh improved, absolute
  savings and peak-shifting did not.
- Point at `REPRODUCE.md`: fresh clone → full report in one command.
- Kill the broker window / `Ctrl+C` Streamlit.

## Timing budget

| Section | Min |
|---------|-----|
| 0 setup | 3 |
| 1 live roundtrip | 2 |
| 2 dashboard | 2 |
| 3 figures | 5 |
| 4 faults | 2 |
| 5 close | 1 |
| **Total** | **~15** |
