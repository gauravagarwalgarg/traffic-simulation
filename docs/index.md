# Indian Traffic Simulation 🚦

Microscopic traffic flow simulation using the Intelligent Driver Model (IDM) and MOBIL lane-change model, calibrated for Indian road dynamics.

## Quick Start

```bash
pip install numpy
python -m engine
```

## Why This Exists

Indian traffic is fundamentally different from European/American traffic:

- **Non-lane discipline** vehicles use continuous lateral positioning
- **Heterogeneous fleet** two-wheelers, auto-rickshaws, sedans, trucks share the same road
- **Aggressive gap acceptance** headway of 0.8s vs 1.5s in Europe
- **Lane-splitting** two-wheelers filter between larger vehicles

Standard traffic models (calibrated for lane-based European traffic) fail to capture these dynamics.

## Source Modules

| Module | File | Purpose |
|--------|------|---------|
| Data Models | `engine/models.py` | Vehicle types, profiles, state |
| IDM | `engine/idm.py` | Longitudinal acceleration (vectorized NumPy) |
| MOBIL | `engine/mobil.py` | Lateral movement decisions |
| Intersection | `engine/intersection.py` | 4-way intersection + adaptive signals |
| Simulation | `engine/simulation.py` | Single-road simulation loop |
| Analytics | `engine/analytics.py` | ML: distribution fitting, prediction, wait times |
| Telemetry | `engine/telemetry.py` | Background SQLite writer |
| Web UI | `engine/webapp.py` | Browser-based 5-tab visualization |
| Terminal UI | `engine/visualizer.py` | ASCII terminal rendering |
| Runner | `engine/runner.py` | Headless entry point |

## Output

The simulation produces a SQLite database (`telemetry.db`) with per-vehicle, per-timestep records for offline analysis.

```sql
SELECT vehicle_type, AVG(speed) * 3.6 AS avg_kmph, COUNT(*)
FROM telemetry GROUP BY vehicle_type;
```
