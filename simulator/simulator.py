"""Replays a CAN CSV into the backend as 16-frame sliding windows with mock V2X data.

Usage: python -m simulator.simulator --csv data/test.csv --url ws://localhost:8000/ws/ingest --rate 200
"""
import argparse
import asyncio
import json
import os
import random
import time
from typing import Iterator, Optional

import pandas as pd
import websockets

from common.tokenizer import FRAME_DATA_LEN, WINDOW_SIZE, tokenize_frame

SCHEMA_VERSION = "1.0"
DATA_COLS = [f"DATA{i}" for i in range(FRAME_DATA_LEN)]
HEADERLESS_COLS = ["Timestamp", "CAN ID", "DLC", *DATA_COLS, "Flag"]


def has_header(csv_path: str) -> bool:
    """A headerless file starts with a numeric timestamp."""
    with open(csv_path) as f:
        first = f.readline().split(",")[0].strip()
    try:
        float(first)
        return False
    except ValueError:
        return True


def load_frames(csv_path: str, header: bool, limit: Optional[int]) -> list[dict]:
    df = pd.read_csv(csv_path, dtype=str, header=0 if header else None,
                     names=None if header else HEADERLESS_COLS, nrows=limit,
                     skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    # Ragged rows (DLC < 8) have fewer fields, so pandas leaves Flag empty and the flag
    # lands in the last populated DATA column; move it back.
    short = df["Flag"].isna()
    if short.any():
        sub = df.loc[short, DATA_COLS]
        last = sub.ffill(axis=1).iloc[:, -1]
        df.loc[short, "Flag"] = last
        df.loc[short, DATA_COLS] = sub.mask(sub.eq(last, axis=0))
    flags = df["Flag"]
    data = df[DATA_COLS] if all(c in df.columns for c in DATA_COLS) \
        else df.iloc[:, 3:3 + FRAME_DATA_LEN]
    can_ids = df["CAN ID"] if "CAN ID" in df.columns else df.iloc[:, 1]
    dlcs = df["DLC"] if "DLC" in df.columns else df.iloc[:, 2]
    ts = df["Timestamp"] if "Timestamp" in df.columns else df.iloc[:, 0]

    frames = []
    for t, cid, dlc, row, flag in zip(ts, can_ids, dlcs, data.itertuples(index=False), flags):
        row = list(row)
        tokens_row = tokenize_frame(cid, row)
        frames.append({
            "tokens": tokens_row,
            "json": {"ts": float(t), "can_id": str(cid).strip().lower(), "dlc": int(dlc),
                     "data": [t for t in tokens_row[1:]], "flag": str(flag).strip()},
            "attack": str(flag).strip().upper() in ("T", "1"),
        })
    return frames


class V2XMock:
    """RSU speed-limit advisories + a vehicle speed random walk, with occasional overspeed episodes."""

    LIMITS = [30, 40, 50, 60, 80, 100]

    def __init__(self, overspeed_prob: float, segment_windows: int = 2000, seed: int = 7):
        self.rng = random.Random(seed)
        self.overspeed_prob = overspeed_prob
        self.segment_windows = segment_windows
        self.limit = 60
        self.speed = 55.0
        self.n = 0
        self.overspeed_left = 0
        self.rsu = "RSU-01"

    def next(self) -> dict:
        self.n += 1
        if self.n % self.segment_windows == 1:
            self.limit = self.rng.choice(self.LIMITS)
            self.rsu = f"RSU-{self.rng.randint(1, 12):02d}"
        if self.overspeed_left == 0 and self.rng.random() < self.overspeed_prob:
            self.overspeed_left = self.rng.randint(300, 1500)
        if self.overspeed_left > 0:
            self.overspeed_left -= 1
            target = self.limit * 1.3
        else:
            target = self.limit * 0.95
        self.speed += (target - self.speed) * 0.01 + self.rng.gauss(0, 0.15)
        self.speed = max(0.0, self.speed)
        hazard = "ROADWORK_AHEAD" if self.rng.random() < 0.0005 else None
        return {"msg_type": "RSU_ADVISORY", "rsu_id": self.rsu, "speed_limit_kph": float(self.limit),
                "vehicle_speed_kph": round(self.speed, 2), "hazard": hazard,
                "timestamp_ns": time.time_ns()}


def windows(frames: list[dict], stride: int) -> Iterator[tuple[list[int], list[dict], int]]:
    for end in range(WINDOW_SIZE, len(frames) + 1, stride):
        chunk = frames[end - WINDOW_SIZE:end]
        tokens = [t for f in chunk for t in f["tokens"]]
        yield tokens, [f["json"] for f in chunk], int(chunk[-1]["attack"])  # training label = last frame


async def stream(args, frames: list[dict]) -> None:
    v2x = V2XMock(args.overspeed_prob)
    interval = 1.0 / args.rate if args.rate > 0 else 0.0
    stats = {"sent": 0, "ack": 0, "err": 0}

    async def drain(ws):
        async for raw in ws:
            m = json.loads(raw)
            if m.get("type") == "ack":
                stats["ack"] += 1
            elif m.get("type") == "error":
                stats["err"] += 1
                print("backend error:", m)

    async with websockets.connect(args.url, max_size=None, ping_interval=20) as ws:
        reader = asyncio.create_task(drain(ws))
        next_t = time.perf_counter()
        seq = 0
        for tokens, wframes, label in windows(frames, args.stride):
            msg = {"type": "can_window", "schema_version": SCHEMA_VERSION, "seq": seq,
                   "vehicle_id": args.vehicle_id, "sent_at_ns": time.time_ns(),
                   "window": {"size": WINDOW_SIZE, "tokens": tokens, "frames": wframes, "label": label},
                   "v2x": v2x.next()}
            await ws.send(json.dumps(msg))
            seq += 1
            stats["sent"] += 1
            if interval:
                next_t += interval
                await asyncio.sleep(max(0.0, next_t - time.perf_counter()))
            elif seq % 64 == 0:
                while stats["sent"] - stats["ack"] > 256:  # backpressure at max rate
                    await asyncio.sleep(0.001)
            if seq % 2000 == 0:
                print(f"sent={stats['sent']} ack={stats['ack']} err={stats['err']}")
        await ws.send(json.dumps({"type": "end_of_stream", "seq": seq}))
        while stats["ack"] < stats["sent"] and stats["err"] == 0:
            await asyncio.sleep(0.05)
        reader.cancel()
    print(f"done: sent={stats['sent']} ack={stats['ack']} err={stats['err']}")


async def main() -> None:
    env = os.environ.get
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=env("SIM_CSV", "data/test.csv"))
    p.add_argument("--url", default=env("SIM_URL", "ws://localhost:8000/ws/ingest"))
    p.add_argument("--rate", type=float, default=float(env("SIM_RATE", "100")), help="windows/s, 0 = max")
    p.add_argument("--stride", type=int, default=int(env("SIM_STRIDE", "1")))
    p.add_argument("--limit", type=int, default=int(env("SIM_LIMIT", "0")) or None, help="max CSV rows")
    p.add_argument("--vehicle-id", default=env("SIM_VEHICLE_ID", "CAV-01"))
    p.add_argument("--overspeed-prob", type=float, default=float(env("SIM_OVERSPEED_PROB", "0.002")))
    p.add_argument("--no-header", action="store_true", default=env("SIM_NO_HEADER") == "1", help="CSV has no header row")
    p.add_argument("--loop", action="store_true", default=env("SIM_LOOP") == "1", help="replay forever")
    args = p.parse_args()

    header = has_header(args.csv) and not args.no_header
    print(f"CSV header detected: {header}")
    frames = load_frames(args.csv, header=header, limit=args.limit)
    print(f"loaded {len(frames)} frames from {args.csv}")
    while True:
        try:
            await stream(args, frames)
            if not args.loop:
                return
        except (OSError, websockets.ConnectionClosed) as e:
            print(f"connection problem ({e!r}); retrying in 2s")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
