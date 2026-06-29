# MOBIL Lateral Model

## Concept

MOBIL (Minimizing Overall Braking Induced by Lane changes) decides whether a vehicle should move laterally.

**Key adaptation for India:** Standard MOBIL uses discrete lanes. Our implementation uses **continuous lateral coordinates** because Indian vehicles don't follow lane markings.

## Decision Criteria

A vehicle moves laterally if:

1. **Safety:** The gap at the target position accommodates the vehicle's width + safety margin
2. **Incentive:** Moving provides an acceleration advantage exceeding a threshold

$$\tilde{a}_{new} - a_{current} > \Delta a_{threshold} + p \cdot (\tilde{a}_{follower,after} - \tilde{a}_{follower,before})$$

Where **p** = politeness factor.

## Indian Calibration

| Parameter | Indian | European | Reason |
|-----------|--------|----------|--------|
| Politeness (p) | 0.1–0.3 | 0.4–0.6 | Indian drivers prioritize self over collective |
| Safety margin | 0.3m | 0.5–1.0m | Tighter lateral gaps accepted |
| Threshold | 0.1 m/s² | 0.2–0.5 m/s² | Lower bar to initiate lane change |

## Lane-Splitting

Two-wheelers (width 0.7m) can fit in gaps that sedans (1.8m) cannot. The `impatience` factor in `VehicleProfile` controls how aggressively a vehicle seeks lateral gaps:

- Two-wheeler: impatience = 0.9 (almost always looking to filter)
- Sedan: impatience = 0.4 (only moves if clearly beneficial)
- Heavy truck: impatience = 0.2 (mostly stays put)

## Source

File: [`engine/mobil.py`](https://github.com/GauravAgarwalGarg/traffic-simulation/blob/main/engine/mobil.py)
