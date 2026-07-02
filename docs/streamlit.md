# Streamlit Dashboard

Interactive data science dashboard for the Indian traffic microsimulation.

## Prerequisites

- Python 3.10+
- The `engine/` package (included in this repo)

## Installation

```bash
cd traffic-simulation
pip install -r requirements.txt
```

## Running Locally

```bash
streamlit run app.py
```

This opens the dashboard at `http://localhost:8501`.

## Features

### Simulation Tab
- Configure spawn rate, vehicle distribution, and IDM parameters in the sidebar
- Click **Run Simulation** to execute N seconds of the intersection model
- View real-time results: vehicle counts, speed trends, cumulative departures
- Fundamental diagram (flow vs density, speed vs density)
- Adaptive signal timing recommendations

### Analytics Tab
- Arrival distribution fitting (Poisson, Exponential, Normal)
- Queue length prediction with 30-second horizon
- Speed distribution histogram
- Queue length heatmap across all directions

### Data Explorer Tab
- Full telemetry DataFrame with sorting/filtering
- Summary statistics
- CSV export for offline analysis
- Custom multi-metric plotting

### About Tab
- Model documentation (IDM, MOBIL, Webster's)
- Vehicle type specifications
- Architecture overview

## Configuration

All parameters are adjustable via the sidebar:

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Spawn rate | 0.5–5.0 veh/s | 2.0 | Vehicle arrival rate |
| Duration | 30–300 s | 120 | Simulation length |
| Two-wheelers % | 0–100 | 45 | Vehicle mix |
| Auto-rickshaws % | 0–100 | 20 | Vehicle mix |
| Sedans % | 0–100 | 25 | Vehicle mix |
| Trucks % | 0–100 | 10 | Vehicle mix |
| Min gap factor | 0.5–2.0 | 1.0 | IDM aggressiveness |
| Headway factor | 0.5–2.0 | 1.0 | Time headway multiplier |
| Arm length | 100–600 m | 300 | Intersection approach length |
| Min green | 5–30 s | 15 | Minimum green phase |
| Max green | 30–90 s | 60 | Maximum green phase |

## Deployment

For sharing with others, you can deploy to [Streamlit Community Cloud](https://streamlit.io/cloud):

1. Push to GitHub
2. Connect your repo at share.streamlit.io
3. Set `app.py` as the main file

## Troubleshooting

**Import errors**: Make sure you run `streamlit run app.py` from the project root
(the directory containing both `app.py` and the `engine/` folder).

**Slow simulation**: Reduce the duration or spawn rate. The engine is vectorized
with NumPy but very high vehicle counts (>500 per arm) can slow things down.
