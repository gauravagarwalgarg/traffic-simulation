# Telemetry Pipeline

## Architecture

```
Simulation.step()
  └─ _emit_telemetry()
       └─ deque.append(TelemetryRecord)   [thread-safe, Lock-guarded]
              │
              │ drain_telemetry() every 0.5s
              ▼
       TelemetryWriter (background thread)
         └─ SQLite batch INSERT
              └─ telemetry.db
```

## Schema

```sql
CREATE TABLE telemetry (
    timestamp REAL,        -- simulation time (seconds)
    vehicle_id INTEGER,    -- unique per spawned vehicle
    vehicle_type TEXT,      -- two_wheeler | auto_rickshaw | sedan | heavy_truck
    x REAL,                -- longitudinal position (meters)
    y REAL,                -- lateral position (meters, continuous)
    speed REAL,            -- m/s
    acceleration REAL      -- m/s²
);
```

## Thesis Query Examples

```sql
-- Average speed by vehicle type (km/h)
SELECT vehicle_type, ROUND(AVG(speed) * 3.6, 1) AS avg_kmph
FROM telemetry GROUP BY vehicle_type;

-- Traffic density over time
SELECT CAST(timestamp AS INT) AS second,
       COUNT(DISTINCT vehicle_id) AS vehicles
FROM telemetry GROUP BY second;

-- Space-time diagram (for fundamental diagram)
SELECT timestamp, x, speed FROM telemetry
WHERE vehicle_id = 42 ORDER BY timestamp;

-- Headway distribution
SELECT vehicle_type, AVG(speed) * 3.6, COUNT(*)
FROM telemetry
WHERE timestamp BETWEEN 10 AND 20
GROUP BY vehicle_type;
```

## Performance

- Buffer: `collections.deque(maxlen=100_000)` bounded, O(1) append
- Batch interval: 0.5s balances latency vs write overhead
- Thread safety: `threading.Lock` around buffer access
- SQLite write: single `executemany` per batch (efficient)

## Source

File: [`engine/telemetry.py`](https://github.com/GauravAgarwalGarg/traffic-simulation/blob/main/engine/telemetry.py)
