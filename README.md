# Carbon- and Comfort-Aware Predictive Control for Smart Buildings

MM0402A IoT and Sustainability course project (Group 5). Simulated multi-room
building: virtual sensors track occupancy/temperature/humidity/energy, an ML
model forecasts demand, and a predictive controller drives HVAC + lighting to
beat fixed-schedule control on energy, cost and CO2 without breaking comfort.

## Quickstart

> **Python version: 3.12.x required.** Later versions (this machine has 3.14.6)
> lack TensorFlow CPU wheels needed in Phase 4. Importing `sim` on a
> non-3.12 interpreter prints a warning but keeps working — physics,
> simulation and tests have no TF dependency.

```bash
# 1. Install Python 3.12.x side-by-side (python.org/downloads), then:
py -3.12 -m venv .venv
.venv\Scripts\activate

# 2. Install pinned deps
pip install -r requirements.txt

# 3. Sanity check + tests
python -c "import sim.thermal, sim.config; print(sim.config.BASE_TAU_HOURS)"
pytest tests/ -q
```
