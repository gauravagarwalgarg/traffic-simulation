# Architecture (4+1 View)

## Logical View

```
models.py → idm.py → mobil.py → simulation.py → telemetry.py
(types)     (accel)   (lateral)   (orchestrator)   (persistence)
```

Data flows left-to-right: models define types, physics models compute accelerations and lateral moves, simulation orchestrates the tick loop, telemetry persists results.

## Process View

```
┌────────────────────────────────────┐
│          Main Thread               │
│  for step in range(steps):         │
│    sim.spawn_vehicle()             │
│    sim.step()  ← IDM + MOBIL      │
│      └─ _emit_telemetry()         │
│           └─ deque.append()        │
└────────────────────────────────────┘
           │ drain_telemetry()
           ▼
┌────────────────────────────────────┐
│       Background Thread            │
│  TelemetryWriter._run_loop()       │
│    sleep(0.5s)                     │
│    drain → SQLite batch insert     │
└────────────────────────────────────┘
```

Thread-safe handoff via `deque` + `threading.Lock`.

## Physical View

- Single process, 2 threads (main + writer)
- NumPy vectorized IDM: O(n) per tick for n vehicles
- MOBIL: O(n²) worst case (each vehicle checks neighbors), bounded by 30m radius
- Handles 500+ vehicles at >30x real-time on a modern CPU

## Development View

```
traffic-simulation/
├── engine/
│   ├── __init__.py       # Package exports
│   ├── __main__.py       # python -m engine
│   ├── models.py         # VehicleType, VehicleProfile, VehicleState
│   ├── idm.py            # Intelligent Driver Model
│   ├── mobil.py          # MOBIL lateral model
│   ├── simulation.py     # Core simulation loop
│   ├── telemetry.py      # SQLite writer
│   └── runner.py         # Entry point
├── docs/                 # MkDocs documentation
├── references/           # Research papers (PDF)
├── mkdocs.yml
├── requirements.txt
└── README.md
```

## Scenario View (+1)

Indian urban traffic at peak hour:
- 45% two-wheelers (bikes/scooters) lane-splitting, 0.5m gaps
- 20% auto-rickshaws erratic, moderate speed
- 25% sedans following traffic norms loosely
- 10% heavy trucks/buses slow, wide, blocking
