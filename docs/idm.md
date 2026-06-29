# Intelligent Driver Model (IDM)

## Formula

$$a = a_{max} \left[ 1 - \left(\frac{v}{v_0}\right)^\delta - \left(\frac{s^*(v, \Delta v)}{s}\right)^2 \right]$$

Where the desired gap:

$$s^*(v, \Delta v) = s_0 + \max\left(0,\; vT + \frac{v \cdot \Delta v}{2\sqrt{a_{max} \cdot b}}\right)$$

## Parameters

| Symbol | Meaning | Indian Value | European Value |
|--------|---------|-------------|----------------|
| $a_{max}$ | Max acceleration | 1.0–3.0 m/s² | 1.0–2.0 m/s² |
| $b$ | Comfortable deceleration | 2.0–4.0 m/s² | 1.5–3.0 m/s² |
| $s_0$ | Minimum gap | 0.5–3.0 m | 2.0–4.0 m |
| $T$ | Desired headway | 0.8–2.0 s | 1.5–2.5 s |
| $v_0$ | Desired speed | varies | varies |
| $\delta$ | Accel exponent | **3** | 4 |

## Indian Adaptation

- **delta = 3** (not 4): more aggressive acceleration profile Indian drivers floor it faster
- **s0 reduced 30-50%**: tighter bumper-to-bumper gaps accepted
- **T reduced**: shorter time headway (0.8s for two-wheelers vs 1.5s European)

## Implementation

`engine/idm.py` uses NumPy vectorization to compute acceleration for all vehicles simultaneously:

```python
acceleration = max_accel * (free_road_term - interaction_gap_term)
```

Where `free_road_term` captures the desire to reach desired speed, and `interaction_gap_term` captures the braking response to a close leader.

## Source

File: [`engine/idm.py`](https://github.com/GauravAgarwalGarg/traffic-simulation/blob/main/engine/idm.py)
