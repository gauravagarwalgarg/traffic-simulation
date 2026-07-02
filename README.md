# Traffic Simulation 🚦

[![CI](https://github.com/gauravagarwalgarg/traffic-simulation/actions/workflows/ci.yml/badge.svg)](https://github.com/gauravagarwalgarg/traffic-simulation/actions/workflows/ci.yml) [![Docs](https://img.shields.io/badge/docs-live-blue?logo=github)](https://gauravagarwalgarg.github.io/traffic-simulation/) ![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white) [![License](https://img.shields.io/github/license/gauravagarwalgarg/traffic-simulation)](https://github.com/gauravagarwalgarg/traffic-simulation/blob/development/LICENSE)

> 📖 **Documentation**: [https://gauravagarwalgarg.github.io/traffic-simulation/](https://gauravagarwalgarg.github.io/traffic-simulation/)
>
> 📦 **Repository**: [GitHub](https://github.com/gauravagarwalgarg/traffic-simulation)


> Microscopic traffic flow simulation for Indian road dynamics using IDM + MOBIL models.

## Architecture (4+1 View)

```
┌─────────────────────────────────────────────────────────────┐
│                    Logical View                               │
│  models.py → idm.py → mobil.py → simulation.py              │
│  (types)     (accel)   (lateral)   (orchestrator)            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Process View                               │
│  Main Thread: simulation.step() loop                         │
│  Background Thread: TelemetryWriter flush to SQLite          │
│  Thread-safe buffer: deque + Lock                            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Physical View                              │
│  Single process, multi-threaded, NumPy vectorized            │
│  500+ vehicles at >10x real-time on modern CPU               │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Development View                           │
│  engine/                                                     │
│  ├── models.py      # VehicleType, profiles, state           │
│  ├── idm.py         # Intelligent Driver Model (vectorized)  │
│  ├── mobil.py       # Lateral movement model                 │
│  ├── simulation.py  # Main loop, telemetry emission          │
│  ├── telemetry.py   # Background SQLite writer               │
│  └── runner.py      # Entry point                            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Scenario View (+1)                         │
│  Indian Traffic:                                             │
│  - 45% two-wheelers (lane-splitting, tight gaps)             │
│  - Non-lane discipline (continuous lateral positioning)      │
│  - Reduced headway (0.8-1.2s vs 1.5-2.0s European)          │
│  - Aggressive gap acceptance                                 │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
pip install -r requirements.txt
```

### Option 1: Streamlit Dashboard (recommended)

Interactive data science dashboard with real-time charts, analytics, and CSV export:

```bash
streamlit run app.py
```

The app includes multiple pages:
- **📊 Simulation**Run and analyze intersection simulation
- **🚗 Traffic UI**Visual traffic model with animated intersection view
- **🧠 ML Ingress**Data ingress engine with 6 local ML models

See [docs/streamlit.md](docs/streamlit.md) for full documentation.

### Option 2: WebSocket + Canvas Visualization

Real-time browser visualization via WebSocket and HTML Canvas:

```bash
python -m engine --web
```

### Option 3: Headless Simulation

Run the engine without any UI (writes telemetry to SQLite):

```bash
python -m engine
```

## Indian Traffic Calibration

| Parameter | European | Indian | Why |
|-----------|----------|--------|-----|
| Min gap (s0) | 2.0m | 0.5-1.5m | Tighter following distance |
| Headway (T) | 1.5-2.0s | 0.8-1.2s | Less time gap accepted |
| Politeness (p) | 0.5 | 0.1-0.3 | Aggressive lane changes |
| Delta (accel exponent) | 4 | 3 | Sharper acceleration |

## Telemetry Queries

After running, query `telemetry.db`:
```sql
-- Average speed by vehicle type
SELECT vehicle_type, AVG(speed) * 3.6 AS avg_kmph
FROM telemetry GROUP BY vehicle_type;

-- Traffic density over time
SELECT CAST(timestamp AS INT) AS second, COUNT(DISTINCT vehicle_id) AS vehicles
FROM telemetry GROUP BY second;
```

## Data Ingress Engine + ML Models

The `engine/ingress.py` and `engine/ml_models.py` modules provide a real-time ML pipeline:

```
Simulation (30fps) → Ingress Buffer → Preprocessor → ML Models → Results Store → UI
```

| Model | Method | Purpose |
|-------|--------|---------|
| Anomaly Detection | Z-score + IQR | Detect traffic surges, incidents |
| LOS Classification | PCU density (INDO-HCM) | Level of Service A–F grading |
| Speed Prediction | Online Linear Regression | Forecast speed 10s ahead |
| Congestion Clustering | Density-based spatial | Identify hotspot cells |
| Signal Optimizer | Online gradient descent | Optimize green time per arm |
| Pattern Detection | Autocorrelation/FFT | Find cyclic traffic patterns |

All models run **locally**no cloud APIs, no GPU required.

## Legacy Code

The `Microscopic/` and `Project 2017/` folders contain the original 2017 implementation. The new `engine/` package is a complete rewrite with:
- Type-safe Python 3.10+
- NumPy vectorized physics
- IDM + MOBIL models (not custom acceleration)
- Thread-safe telemetry pipeline
- ML-powered data ingress engine
