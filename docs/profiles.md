# Vehicle Profiles

Physical characteristics calibrated from IRC (Indian Roads Congress) data and field studies.

## Fleet Composition

| Type | Proportion | Examples |
|------|-----------|----------|
| Two-Wheeler | 45% | Honda Activa, Bajaj Pulsar, TVS Jupiter |
| Auto-Rickshaw | 20% | Bajaj RE, Piaggio Ape |
| Sedan | 25% | Maruti Swift, Hyundai i20, Toyota Innova |
| Heavy Truck | 10% | Tata trucks, Ashok Leyland buses |

Source: IRC SP:41 typical Indian urban traffic composition.

## Physical Parameters

| Parameter | Two-Wheeler | Auto-Rickshaw | Sedan | Heavy Truck |
|-----------|------------|---------------|-------|-------------|
| Length | 2.0 m | 2.7 m | 4.5 m | 10.0 m |
| Width | 0.7 m | 1.4 m | 1.8 m | 2.5 m |
| Max Speed | 60 km/h (16.7 m/s) | 40 km/h (11.1 m/s) | 80 km/h (22.2 m/s) | 60 km/h (16.7 m/s) |
| Max Accel | 3.0 m/s² | 2.0 m/s² | 2.5 m/s² | 1.0 m/s² |
| Comfortable Decel | 4.0 m/s² | 3.0 m/s² | 3.5 m/s² | 2.0 m/s² |
| Min Gap (s₀) | 0.5 m | 0.8 m | 1.5 m | 3.0 m |
| Desired Headway (T) | 0.8 s | 1.0 s | 1.2 s | 2.0 s |
| Impatience | 0.9 | 0.7 | 0.4 | 0.2 |

## Impatience Factor

Controls lateral gap-seeking behavior:
- **0.9** = constantly looking for gaps to filter through (two-wheelers)
- **0.2** = almost never changes lateral position (trucks)

## Source

File: [`engine/models.py`](https://github.com/GauravAgarwalGarg/traffic-simulation/blob/main/engine/models.py)
