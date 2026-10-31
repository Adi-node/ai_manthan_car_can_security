import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "micro_transformer_can_ids.onnx"


@dataclass(frozen=True)
class Settings:
    model_path: str = os.getenv("MODEL_PATH", str(_DEFAULT_MODEL))
    threshold: float = float(os.getenv("THRESHOLD", "0.5"))
    failsafe_k: int = int(os.getenv("FAILSAFE_K", "3"))
    speed_mismatch_ratio: float = float(os.getenv("SPEED_MISMATCH_RATIO", "1.2"))
    failsafe_hold_s: float = float(os.getenv("FAILSAFE_HOLD_S", "2.0"))
    broadcast_hz: float = float(os.getenv("BROADCAST_HZ", "30"))
    warmup_runs: int = int(os.getenv("WARMUP_RUNS", "20"))
    latency_window: int = int(os.getenv("LATENCY_WINDOW", "5000"))
    ort_threads: int = int(os.getenv("ORT_THREADS", "1"))


settings = Settings()
