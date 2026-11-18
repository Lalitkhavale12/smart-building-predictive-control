# Viva prep - 20 questions and how to answer them

Every number here comes from `results/report_tables/` or `REPORT.md`. If you are
asked something not in this file, say what you measured and what you did not.

**Answer shape:** claim -> number -> caveat. Roughly 25 seconds, then stop.
Stopping early is what makes an answer look confident.

---

## A. Motivation and scope

### Q1. In one minute, what did you build and what did you find?

A four-room simulated building where every room has a virtual ESP32 publishing
telemetry over MQTT, a 30-60 minute occupancy forecaster, and four controllers
compared on energy, cost, CO2 and comfort across four scenarios and five paired
seeds. The finding is that predictive control does not save energy against a
competent setback baseline - it buys comfort. Weekday: +3.0 comfort points for
-0.28% energy. Heatwave: +6.1 points for -2.49% energy (+0.68 kWh). Weekend is
a tie. Exam day: +4.7 points for -0.77% energy.

### Q2. If it doesn't save energy, why is this a contribution?

Because the interesting claim was testable and we tested it honestly. The
popular story is "smart control saves 20%". On a physically calibrated plant
with a setback baseline, the smart controller spends a little more to hold the
band during occupancy - which is what the building operator actually wants.
We also show which controller *does* win on raw kWh (C2, the occupancy rule:
24.76 kWh vs C4's 25.23 on weekday), so the trade-off is explicit rather than
hidden behind one headline number.

### Q3. Why a simulator instead of a real building?

We had no building access, no instrumented HVAC, and one semester. The
simulator gives us something a real pilot cannot: deterministic paired seeds, so
a 0.07 kWh difference is attributable to the controller and not to weather.
The whole matrix - 100 runs - rebuilds in 11 seconds, so anyone can reproduce
every figure. The hardware path is real, not hypothetical: `iot/esp32_node.ino`
is a Wokwi firmware that speaks the same topics, so the simulator is the only
piece that would be swapped.

---

## B. Physics and simulator

### Q4. Explain your thermal model.

One resistance-capacitance node per room: C dT/dt = (T_out - T)/R + Q_hvac +
Q_occupants + Q_solar. R = 30 C/kW, C = 0.12 kWh/K, so tau = R*C = 3.6 hours.
HVAC at full is -3.5 kW thermal, reduced is -1.2 kW, off is 0; electrical power
is thermal over COP 3.0. Each room gets +/-15% spread on R and C so they do not
behave identically. Weather is a Pune warm-day sinusoid, mean 31 C, +/-4 C,
peaking at 15:00.

### Q5. How do you know the model is right?

Three ways, and the honest part is the bug. First, tau = 3.6 h sits inside the
published range for a classroom-sized zone, so drift and recovery times look
right: an overnight setback drifts a few degrees, and recovery takes tens of
minutes, not seconds. Second, we found our own bug: before recalibration rooms
froze toward -44 C, which is physically impossible - the HVAC term had a
sign/magnitude error. We fixed it with a thermostat deadband, a humidity
random-walk that puts ~85% of minutes in band, and a real exam-day timetable,
then wiped every pre-fix CSV as invalid. Third, sensitivity: +/-15% on R and C
moves energy modestly and does not reorder the controllers.

### Q6. Why 1-minute steps but control every 5 minutes?

The sim integrates at 1 minute because that is the telemetry cadence; the
controller runs every 5 minutes (`CONTROL_HOOK_STEPS = 5`), which is realistic
for a BMS loop and keeps the controller cheap. There is a real trap here that
we guarded with a test: policies must count *sim minutes*, not `step()` calls -
counting calls stretched C2's 15-minute vacancy delay to 75 minutes.

### Q7. What is comfort, exactly?

A minute is comfortable only if the room is occupied AND temperature is inside
22-26 C AND relative humidity is inside 30-60%. Unoccupied minutes are excluded
from the denominator. That strictness is why we report 68-75% rather than 95% -
the band is a real band, not a "not freezing" check.

Worth knowing the decomposition, because it is the sharpest thing in the whole
analysis: on weekday C3, temperature is in band for 95.7% of occupied minutes
but humidity only 71.7%, so comfort lands at 68.3%. And humidity is *identical*
for C3 and C4 (71.7% both) because nothing in the plant dehumidifies - RH is an
exogenous random walk. So the ~72% humidity ceiling caps comfort, and the only
thing a controller can move is the temperature term. That is exactly what C4
does: 95.7% -> 99.4% temperature compliance, 68.3% -> 71.3% comfort.

---

## C. IoT layer

### Q8. Why MQTT rather than HTTP or CoAP?

Pub/sub fits the shape of the problem: four independent nodes and one controller
that nobody wants to poll. HTTP would mean the controller polling every room
every 5 minutes - request/response, no push, bigger headers. CoAP is the right
answer for battery nodes on lossy links, but we have mains-powered nodes and we
wanted broker tooling (Mosquitto, MQTT Explorer) for the demo. MQTT also gives
us last-will-and-testament for free, which is how a dead node announces itself.

### Q9. Walk me through one control cycle.

Each virtual ESP32 publishes to `building/<room>/telemetry` - temperature,
humidity, occupancy, power, HVAC state. The bridge (`iot/bridge.py`) subscribes,
feeds the policy, and publishes to `building/<room>/command`. The node applies
the command and the sim advances 5 minutes. Repeat. Topics are defined once in
`iot/topics.py` so the simulator, the bridge and the firmware cannot drift apart.

### Q10. What QoS do you use, and why? Retained? Last will?

Telemetry is QoS 0: a lost reading is superseded 60 seconds later, so
redelivery buys nothing. Commands are QoS 1: a dropped "OFF" is a comfort and
energy bug. Telemetry is never retained - a stale retained value is worse than
no value, because a controller that reconnects would act on hour-old data. The
last command is retained so a rebooted node resumes its state. Each node sets a
last will on `building/<room>/status` so the bridge sees `offline` instead of
silently missing data.

### Q11. What actually breaks, and what did you have to fix?

Two things. A dead node: the LWT fires, the bridge logs it, the other three
rooms keep running - we did not measure the comfort cost of the missing room,
and we say so. A broker restart or a slow SUBSCRIBE: this one bit us for real.
The first publish could land before the subscription was established, so the
message vanished. `_publish_until_recv` now republishes until the receiver
confirms or a 10-second deadline passes, and fails loudly if not.

---

## D. Forecasting and machine learning

### Q12. How do you know the forecaster isn't leaking?

The split is chronological by timestamp *before* windows are built, so no
window straddles the boundary, and evaluation is walk-forward: predict, then
advance. Features contain only past values plus the known clock. Every seed is
split independently. If we had windowed first and split second, adjacent windows
would leak the test period into training - that is the classic time-series
mistake and it is the one we designed against.

### Q13. Which model won, and which one do you actually ship?

The bake-off compared persistence, random forest, HistGradientBoosting and an
LSTM. The LSTM wins by roughly 84% and 82% MAE at the two horizons - and we do
not ship it. The controller runs the frozen HistGB, because it trains on CPU in
seconds and the artifacts are reproducible on any machine. Shipping the LSTM is
listed as future work, not claimed as a result. Occupancy R2 is 0.9818 at 30
minutes and 0.9834 at 60.

### Q14. What does the forecast actually buy?

Measured by ablation: C4 with the forecast versus C4 with the forecast disabled
(same code, same seed). Weekday: +2.97 comfort points for +0.071 kWh. Heatwave:
+6.09 points for +0.68 kWh. Exam day: +4.67 points for +0.21 kWh. Weekend: zero
on both - the building is empty, so a forecast has nothing to act on. That is
the cleanest single table in the project: it prices the forecast in kWh per
comfort point.

---

## E. Evaluation and results

### Q15. Why five seeds, and what does "paired" mean?

Every controller sees the identical weather and occupancy for a given seed, so
differences isolate the controller instead of sampling noise. Seed spread is
small - weekday energy sd is about 0.5 kWh - so five is enough to see a 0.07 kWh
effect with a paired comparison. Paired is the key word: we compare seed to
seed, not mean to mean.

### Q16. Is +3 comfort points real, or noise?

Real, and the test is the paired difference, not the raw spread. The weekday
forecast ablation gives +2.97 points with sd 0.48 across seeds - a consistent
sign every seed. Heatwave is +6.09 with sd 1.83, still consistent. The mechanism
is visible in G1: the room is pulled down before people arrive instead of after,
and it shows up as temperature compliance going 95.7% -> 99.4% on weekday,
90.5% -> 97.8% on heatwave, 92.8% -> 98.7% on exam day. Humidity does not move
at all, which is how we know the gain is the controller and not the seed.

### Q17. Where do your CO2 numbers come from?

CEA v21.0 grid emission factor, 0.710 tCO2/MWh for FY2024-25, applied hourly
through a documented daily shape - 0.80 solar dip, 0.95 morning, 1.18 evening
peak, 1.02 night. Using one flat constant would overstate weekday CO2 by about
15.8% (C1: 18.29 kg flat versus 15.40 kg hourly) while leaving energy
identical. A test forbids a flat-only implementation, so the distinction cannot
quietly disappear.

### Q18. And the tariff?

MSEDCL commercial, roughly Rs 9/kWh base, minus 1.50 for 22:00-06:00, plus 0.80
for 09:00-12:00, plus 1.10 for 18:00-22:00. Weekday cost is Rs 234.57 for C3 and
235.23 for C4. We scale the tariff and the emission factor by +/-20% in the
sensitivity table: cost and CO2 move linearly, energy and comfort do not move,
and the controller ranking is unchanged. So the conclusions are not an artifact
of the price assumptions.

---

## F. Weaknesses and next steps

### Q19. What is the weakest part of this work?

Validation. Occupancy skill is proven on jittered synthetic timetables, and the
UCI adapter validates demand only - there is no occupancy ground truth there.
The grid shape and the tariff slabs are documented assumptions, not measured
data. The sensor-failure path exists but its cost under packet loss is not
measured. There is no MPC and no real hardware. Every one of those is written in
the limitations section rather than hidden.

### Q20. What would you do next?

Four things, in order: ship the LSTM and re-measure the ablation; train an
exam-day-specific forecaster instead of reusing the weekday one; run the same
firmware on real ESP32s with real sensors, swapping only the plant; and move
from rule-plus-overlay to MPC over the 30-60 minute horizon, which is the only
way the carbon signal could ever pay off - and it did not pay off as a rule.

---

## Quick-fire gotchas

**"Your weekend comfort is 8.9% for one seed - that's broken."**
Weekend has almost no occupied minutes, so a handful of cold arrival minutes
dominates the percentage. The sd of 37.7 points says the metric is fragile on
weekend, which is exactly why we call weekend a tie rather than a result.

**"C3 uses more energy than C1 on the weekend. Your smart controller is worse?"**
1.97 vs 2.09 kWh - a 0.12 kWh gap on a 2 kWh base. C1's weekend timetable is
empty so it never runs; C3 reacts to the few pop-in arrivals at full ON. It is
5.6% of a very small number and we do not build any claim on it.

**"Your demo printed 34.5% comfort but the report says 68.3%."**
The demo covers 30 minutes, starting at the arrival transient - the worst
30 minutes of the day by construction. 68.3% is the whole day's occupied
minutes. Same plant, different window.

**"Why is C4 cheaper in heatwave but not on a weekday?"**
Bigger cooling load means more ON minutes for pre-cooling to displace, so the
overlay's spend lands where it is worth more comfort.

**"What was the -12.9% / -25.3% figure I saw?"**
Pre-recalibration, on a plant where rooms froze to -44 C. Those CSVs were wiped
as physically invalid. Never quote those numbers as a result - the recalibration
documents exist to explain why they are gone.

**"I ran `python -m sim.run` and the rooms hit 94 C."**
Correct, and it is not a bug. That module is the phase-1 plant probe: the policy
is AlwaysOffPolicy, so an occupied classroom holding ~2.7 kW of gains against
R = 30 C/kW equilibrates above 100 C. It exists to prove the physics loop in
isolation, and the CLI now prints that warning. Controlled single runs are
`python -m eval.matrix --controllers c3 --scenarios weekday --seeds 1`, which
keeps the rooms at 23-30 C.

**"0.28% is not a saving."**
Correct, and we do not claim it. It is inside seed noise. The claim is comfort
per kWh, and the report says so in the first paragraph of results.

**"Your comfort is only 68% - so the controller barely matters?"**
The ceiling is humidity, not the controller. Occupied minutes: temperature in
band 95.7%, humidity in band 71.7%, both 68.3%. RH is identical for every
controller (71.7% for both C3 and C4) because the plant has no dehumidification,
so humidity is exogenous noise. The controller moves the temperature term
(95.7% -> 99.4%), which is where the +3 points come from. On a real building
with dehumidification the same control logic would score higher - we say that
as a limitation, not as a result.

---

## Eight numbers to have cold

| Thing | Value |
|---|---|
| Weekday energy, C3 -> C4 | 25.16 -> 25.23 kWh (-0.28%) |
| Weekday comfort, C3 -> C4 | 68.3% -> 71.3% (+3.0 pp) |
| Heatwave comfort, C3 -> C4 | 64.2% -> 70.3% (+6.1 pp), +0.68 kWh |
| Forecast ablation, weekday | +2.97 pp comfort for +0.071 kWh |
| Occupancy R2 | 0.9818 (30 min), 0.9834 (60 min) |
| Plant time constant | tau = R*C = 3.6 h |
| Comfort band | 22-26 C and 30-60% RH, occupied minutes only |
| Why comfort stops at ~72% | RH in band 71.7% (same for every controller), T 95.7% -> 99.4% |
| Peak share after carbon overlay | 0.071 -> 0.080 (no shifting) |
