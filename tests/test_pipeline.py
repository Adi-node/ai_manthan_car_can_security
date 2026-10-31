import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.hub import DashboardHub
from backend.app.stats import Stats
from common.tokenizer import tokenize_frame

needs_model = pytest.mark.skipif(not os.path.exists(settings.model_path), reason="model not mounted")


def make_msg(seq=0, speed=57.0, label=0, tokens=None):
    frame_tokens = tokenize_frame("0316", ["05", "21", "68", "09", "21", "21", "00", "6f"])
    frame = {"ts": 1.0 + seq, "can_id": "0316", "dlc": 8, "data": frame_tokens[1:], "flag": "R"}
    return {"type": "can_window", "seq": seq, "vehicle_id": "CAV-01", "sent_at_ns": time.time_ns(),
            "window": {"size": 16, "tokens": tokens or frame_tokens * 16, "frames": [frame] * 16, "label": label},
            "v2x": {"speed_limit_kph": 60, "vehicle_speed_kph": speed}}


@needs_model
def test_ingest_to_dashboard_and_validation():
    from backend.app.main import app
    with TestClient(app) as client:
        with client.websocket_connect("/ws/dashboard") as dash, client.websocket_connect("/ws/ingest") as ing:
            ing.send_json(make_msg(seq=1, speed=80))  # benign-looking CAN, 33% overspeed
            assert ing.receive_json() == {"type": "ack", "seq": 1}
            frame = dash.receive_json()
            assert frame["type"] == "dashboard_frame"
            assert frame["latest"]["latency"]["inference_ms"] > 0
            assert frame["latest"]["v2x"]["speed_violation"] is True

            bad = make_msg(seq=2)
            bad["window"]["tokens"] = [0] * 10
            ing.send_json(bad)
            assert ing.receive_json()["type"] == "error"

            oob = make_msg(seq=3, tokens=[2500] * 144)
            ing.send_json(oob)
            assert ing.receive_json()["type"] == "error"
        info = client.get("/model/info").json()
        assert info["output"]["shape"] == [1]


def test_hub_rate_limit_and_attack_seqs_preserved():
    async def run():
        stats = Stats()
        hub = DashboardHub(stats, rate_hz=30, hold_s=2.0)
        q = hub.add(object())
        task = asyncio.create_task(hub.run())
        received = []

        async def consume():
            while True:
                received.append(__import__("json").loads(await q.get()))

        cons = asyncio.create_task(consume())
        from backend.app.failsafe import Decision
        t_end = time.monotonic() + 1.0
        i = 0
        while time.monotonic() < t_end:  # ~1000 results/s
            atk = i % 100 == 0
            hub.publish({"seq": i, "prediction": {"attack_probability": 0.9 if atk else 0.1, "is_attack": atk},
                         "latency": {"inference_ms": 0.4}}, Decision(False, None, 0, False))
            i += 1
            if i % 20 == 0:
                await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)
        task.cancel(); cons.cancel()
        return received, i

    received, total = asyncio.run(run())
    assert len(received) <= 32
    seen = {s for f in received for s in f["interval"]["attack_seqs"]}
    assert seen == {s for s in range(total) if s % 100 == 0}
