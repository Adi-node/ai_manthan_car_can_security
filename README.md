# CAV CAN-bus Intrusion Detection Backend

FastAPI + onnxruntime server for the Micro-Transformer IDS, a CSV replay simulator, and a debug dashboard.
It scores sliding 16-frame windows of CAN traffic, fuses the verdict with simulated V2X data, and broadcasts
results (with per-prediction inference latency) to a dashboard.

## Quick start

Requirements: Docker. The model files must be in `models/` (`micro_transformer_can_ids.onnx` + `.onnx.data`).

**1. Add the test CSV** at `data/test.csv`. A header is optional; it is detected automatically.
Columns: `Timestamp, CAN ID, DLC, DATA0..DATA7, Flag` (`R` = normal, `T` = attack). Short rows (DLC < 8) are handled.

**2. Start the backend** (terminal 1):
```bash
docker compose up --build backend
```
Dashboard: http://localhost:8000 · Model info: http://localhost:8000/model/info · Health: http://localhost:8000/health

**3. Run the simulator** (terminal 2):
```bash
SIM_LIMIT=30000 SIM_RATE=400 docker compose --profile sim up --build simulator
```
Then watch the dashboard. The first attack rows in the CSV appear around row 1,477.

**4. Stop everything:**
```bash
docker compose --profile sim down
```

### Simulator options
Set as environment variables in front of the command above:

| Variable | Default | Meaning |
|---|---|---|
| `SIM_CSV` | `/data/test.csv` | CSV path inside the container (`./data` is mounted at `/data`) |
| `SIM_LIMIT` | `0` (all rows) | Max CSV rows to load. The full file is 3.67M rows and needs a lot of RAM, so set this |
| `SIM_RATE` | `100` | Windows per second; `0` = as fast as possible |
| `SIM_LOOP` | `0` | `1` replays the CSV forever |
| `SIM_NO_HEADER` | `0` | `1` forces headerless parsing (normally auto-detected) |

Keep `SIM_RATE` at or below about 500. The backend handles roughly 550 windows/s on CPU, and above that
acknowledgements fall far behind. Extra flags are available when running the module directly
(`python -m simulator.simulator --help`): `--stride`, `--vehicle-id`, `--overspeed-prob`.

Examples:
```bash
# replay the whole attack burst slowly, looping
SIM_LIMIT=60000 SIM_RATE=100 SIM_LOOP=1 docker compose --profile sim up simulator
# stress test at maximum speed
SIM_LIMIT=20000 SIM_RATE=0 docker compose --profile sim up simulator
```

### Tests
```bash
docker compose run --rm --no-deps backend pytest tests/
```

## Reading the dashboard
- **Fail-safe banner:** green = nominal, red = fail-safe fired (stays red for 2 s). Reasons are listed below.
- **Attack probability chart:** the model's probability per window; the dashed line is the 0.5 threshold.
- **Inference latency:** p50/p95/p99/max of `session.run` time per prediction, in ms.
- **V2X panel:** speed limit, vehicle speed and hazard. These values are **simulated**, not from the CSV.
- **Confusion matrix** (against the CSV's `R`/`T` flags, window labelled by its last frame):
  - TP: attack caught · FP: false alarm · TN: normal correctly ignored · FN: attack missed.

## Model contract (decoded from the ONNX file)
Input `input_sequence` int64 `[batch, 144]` (16 frames x 9 tokens) -> output `attack_logit` float32 `[1]` (raw logit;
the server applies a sigmoid). The export fixes the output to one window, so inference runs one window at a time.

Tokenizer (matches the training script, in `common/tokenizer.py`):
- CAN ID token = `(int(id, 16) % 2048) + 257`
- data byte token = `int(byte, 16)` (0..255); missing or corrupt bytes = PAD `256`
- a window's label is its **last frame's** flag, and the simulator labels windows the same way

Accuracy note: the test CSV is the same file the model was trained on (DoS only), so the numbers below are
optimistic. A replay of the first 30k rows gave recall 91.4%, precision 98.3%, p99 latency 1.8 ms.

## WebSocket schema (v1.0)
- `WS /ws/ingest` (simulator -> backend): `can_window` {seq, vehicle_id, sent_at_ns, window{size, tokens[144], frames[16], label}, v2x?},
  `end_of_stream`. Replies `ack` {seq} or `error` {code, detail}. Models live in `backend/app/schemas.py`.
- `WS /ws/dashboard` (backend -> frontend, max 30 msg/s): `dashboard_frame` {interval, failsafe, latest{prediction, latency, v2x,
  window_summary, ground_truth}, stats (about 1/s, else null)}. `latency.inference_ms` is the `session.run` time only.
  Raw stream: `python -m websockets ws://localhost:8000/ws/dashboard`.

## Fail-safe fusion
1. `FAILSAFE_K` (3) consecutive attack windows -> `CAN_INTRUSION`.
2. Model says benign but `vehicle_speed_kph > 1.2 x speed_limit_kph` -> `CONTEXTUAL_ANOMALY: V2X_SPEED_MISMATCH`.

## Backend settings
Read from the backend's environment (add them under `backend.environment` in `docker-compose.yml` to change them): `THRESHOLD` (0.5), `FAILSAFE_K` (3), `SPEED_MISMATCH_RATIO` (1.2),
`FAILSAFE_HOLD_S` (2.0), `BROADCAST_HZ` (30), `MODEL_PATH`.

## Layout
```
backend/app/   FastAPI app: main, inference (ONNX), failsafe, hub (30 Hz broadcaster), stats, schemas, static/index.html
common/        tokenizer shared by simulator and tests
simulator/     CSV replay + mock V2X
tests/         tokenizer, fail-safe, pipeline and rate-limit tests
```
