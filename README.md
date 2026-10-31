# CAV CAN-bus Intrusion Detection Backend

FastAPI + onnxruntime server for the Micro-Transformer IDS, a replay simulator, and a debug dashboard.

## Run
```bash
# 1. put the test CSV at data/test.csv (header: Timestamp,CAN ID,DLC,DATA0..DATA7,Flag)
docker compose up --build backend          # http://localhost:8000  (dashboard + /model/info)
docker compose --profile sim up simulator  # replays the CSV; SIM_RATE=0 for max speed, SIM_LOOP=1 to repeat
docker compose run --rm backend pytest tests/
```
Headerless CSV: run the simulator with `--no-header`.

## Model contract (decoded from the ONNX file)
Input `input_sequence` int64 `[batch, 144]` (16 frames x 9 tokens) -> output `attack_logit` float32 `[1]` (raw logit,
sigmoid applied server-side). Batch is 1 per window.

Tokenizer (matches the training script): ID token = `(int(id,16) % 2048) + 257`; data bytes `0..255`; missing/corrupt bytes = PAD `256`.
The training label of a window is its **last frame's** flag, and the simulator labels windows the same way.

## WebSocket schema (v1.0)
- `WS /ws/ingest` (simulator -> backend): `can_window` {seq, vehicle_id, sent_at_ns, window{size, tokens[144], frames[16], label}, v2x?},
  `end_of_stream`. Replies `ack` {seq} or `error` {code, detail}. Models live in `backend/app/schemas.py`.
- `WS /ws/dashboard` (backend -> frontend, max 30 msg/s): `dashboard_frame` {interval, failsafe, latest{prediction, latency, v2x,
  window_summary, ground_truth}, stats (about 1/s, else null)}. `latency.inference_ms` is the `session.run` time only.

## Fail-safe fusion
1. `FAILSAFE_K` (3) consecutive attack windows -> `CAN_INTRUSION`.
2. Model benign but `vehicle_speed_kph > 1.2 x speed_limit_kph` -> `CONTEXTUAL_ANOMALY: V2X_SPEED_MISMATCH`.

Env knobs: `THRESHOLD`, `FAILSAFE_K`, `SPEED_MISMATCH_RATIO`, `FAILSAFE_HOLD_S`, `BROADCAST_HZ`, `MODEL_PATH`.
