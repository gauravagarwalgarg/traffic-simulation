# Roadmap: Data Science & ML Features

## ✅ Implemented Today

| Feature | Module | Status |
|---------|--------|--------|
| Arrival distribution fitting (Poisson/Normal/Clustered) | `engine/analytics.py` | ✅ Live |
| Queue prediction (30s ahead, linear regression) | `engine/analytics.py` | ✅ Live |
| Green time recommendation (EMA-weighted demand) | `engine/analytics.py` | ✅ Live |
| Fundamental diagram computation (density/flow/speed) | `engine/analytics.py` | ✅ Live |
| Real-time distribution switching (Peak/Highway/Night/Festival) | `engine/webapp.py` | ✅ Live |
| ML Insight panel on simulation tab | `engine/webapp.py` | ✅ Live |

## 🔜 Next Sprint (Can Implement Now)

### 1. Arrival Rate Anomaly Detection
Detect unusual traffic surges (accident, event, roadblock) by comparing rolling mean to current rate. Flag when rate > 2σ above baseline.

### 2. Phase-Level Performance Scoring
Score each green phase by throughput efficiency: `vehicles_departed / green_time`. Track which phases underperform and auto-suggest longer greens.

### 3. Vehicle Type Classification Impact
Quantify how fleet composition affects intersection throughput. Compare: "What if we replaced 20% of two-wheelers with sedans?" using counterfactual simulation.

### 4. Wait Time Estimation per Vehicle
Track each vehicle's spawn_time → departure_time. Compute per-type average wait, percentiles (P50, P95, P99). Plot wait time distribution.

### 5. Congestion Heatmap
Discretize road into cells, count vehicles per cell over time. Generate spatial heatmap showing congestion hotspots.

## 📊 Medium-Term (Requires More Infra)

| Feature | Complexity | Value |
|---------|-----------|-------|
| Reinforcement Learning signal controller | High | Replace adaptive → RL-trained policy |
| Time-series forecasting (ARIMA/Prophet) | Medium | Predict 5-min ahead queue lengths |
| Multi-intersection network | High | Model corridor with coordinated signals |
| Historical pattern database | Medium | Store daily patterns, detect anomalies vs baseline |
| A/B testing framework | Medium | Compare two signal strategies on same traffic |

## 🔬 Research Extensions

- **Deep RL (DQN/PPO)** for signal optimization train on simulation, deploy to real controllers
- **GNN-based traffic prediction** model intersection as graph node, predict propagation
- **Digital twin** calibrate simulation from camera feed, predict real-time
- **Multi-agent simulation** each vehicle has independent route planning

## Architecture for ML Pipeline

```
Simulation (30fps) → Telemetry Buffer → SQLite/DuckDB
                                             ↓
                                    Batch Analytics (1Hz)
                                             ↓
                              ┌───────────────┼───────────────┐
                              ↓               ↓               ↓
                        Distribution     Regression      Optimization
                          Fitting        Prediction      Recommendation
                              ↓               ↓               ↓
                              └───────────── WebSocket → Frontend Charts
```
