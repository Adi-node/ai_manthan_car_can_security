import asyncio
import contextlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .config import settings
from .failsafe import FailsafeEngine
from .hub import DashboardHub
from .inference import OnnxDetector
from .schemas import SCHEMA_VERSION, CanWindowMessage, EndOfStream
from .stats import Stats

log = logging.getLogger("cav-ids")
STATIC = Path(__file__).parent / "static"


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = OnnxDetector(settings.model_path, settings.ort_threads, settings.warmup_runs)
    app.state.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="onnx")
    app.state.stats = Stats(settings.latency_window)
    app.state.hub = DashboardHub(app.state.stats, settings.broadcast_hz, settings.failsafe_hold_s)
    app.state.failsafe = FailsafeEngine(settings.failsafe_k, settings.speed_mismatch_ratio)
    task = asyncio.create_task(app.state.hub.run())
    log.info("model loaded: %s", app.state.detector.info())
    yield
    task.cancel()
    app.state.executor.shutdown(wait=False)


app = FastAPI(title="CAV CAN-bus IDS", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/model/info")
async def model_info():
    return {**app.state.detector.info(), "threshold": settings.threshold,
            "failsafe_k": settings.failsafe_k, "speed_mismatch_ratio": settings.speed_mismatch_ratio}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


async def _process(msg: CanWindowMessage) -> None:
    t_recv = time.perf_counter_ns()
    tokens = np.asarray(msg.window.tokens, dtype=np.int64)[None, :]
    loop = asyncio.get_running_loop()
    logit, prob, inference_ms = await loop.run_in_executor(app.state.executor, app.state.detector.predict, tokens)
    is_attack = prob >= settings.threshold

    decision = app.state.failsafe.evaluate(msg.vehicle_id, is_attack, msg.v2x)
    frames = msg.window.frames
    v2x = msg.v2x
    latest = {
        "seq": msg.seq,
        "vehicle_id": msg.vehicle_id,
        "prediction": {"attack_logit": round(logit, 5), "attack_probability": round(prob, 5),
                       "is_attack": is_attack, "threshold": settings.threshold},
        "ground_truth": msg.window.label,
        "latency": {
            "inference_ms": round(inference_ms, 4),
            "server_pipeline_ms": round((time.perf_counter_ns() - t_recv) / 1e6, 4),
            "e2e_ms": round((time.time_ns() - msg.sent_at_ns) / 1e6, 4),
        },
        "v2x": None if v2x is None else {
            "speed_limit_kph": v2x.speed_limit_kph, "vehicle_speed_kph": v2x.vehicle_speed_kph,
            "speed_violation": decision.speed_violation, "hazard": v2x.hazard},
        "window_summary": {"can_ids": [f.can_id for f in frames],
                           "first_ts": frames[0].ts, "last_ts": frames[-1].ts},
    }
    app.state.stats.record(inference_ms, is_attack, msg.window.label)
    app.state.hub.publish(latest, decision)


@app.websocket("/ws/ingest")
async def ws_ingest(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                if '"end_of_stream"' in raw[:80]:
                    eos = EndOfStream.model_validate_json(raw)
                    await ws.send_json({"type": "ack", "seq": eos.seq})
                    continue
                msg = CanWindowMessage.model_validate_json(raw)
            except ValidationError as e:
                await ws.send_json({"type": "error", "seq": None, "code": "INVALID_MESSAGE",
                                    "detail": str(e.errors(include_url=False, include_input=False)[:3])})
                continue
            await _process(msg)
            await ws.send_json({"type": "ack", "seq": msg.seq})
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    hub: DashboardHub = app.state.hub
    queue = hub.add(ws)

    async def sender():
        while True:
            await ws.send_text(await queue.get())

    send_task = asyncio.create_task(sender())
    try:
        while True:
            await ws.receive_text()  # ignore client input; detects disconnects
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        hub.remove(ws)
