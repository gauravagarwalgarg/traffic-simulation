# Data Science Roadmap

## Live Features

| Feature | Algorithm | What It Computes |
|---------|-----------|-----------------|
| Arrival Distribution | Coefficient of Variation | Poisson (random) vs Normal (platoon) vs Clustered (burst) |
| Queue Prediction | Linear Regression (60s window) | Predicted queue 30s ahead + trend direction |
| Green Recommendation | EMA-weighted demand | Optimal NS/EW green split with confidence |
| Fundamental Diagram | Density-Flow-Speed | Classic traffic engineering relationship |
| Wait Time Tracking | Per-vehicle spawn→depart | Avg, P50, P95, P99 by vehicle type |
| Phase Performance | Departed/duration per phase | Efficiency scoring for signal optimization |

## Planned

- **Anomaly Detection** flag surges > 2σ above baseline
- **Reinforcement Learning** train DQN/PPO for signal control
- **Time-Series Forecasting** ARIMA/Prophet for 5-min predictions
- **Congestion Heatmap** spatial hotspot visualization
- **A/B Testing** compare signal strategies on same traffic stream

See [ROADMAP.md](https://github.com/GauravAgarwalGarg/traffic-simulation/blob/main/ROADMAP.md) for the full plan.
