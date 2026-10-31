import math
import time
from typing import Any

import numpy as np
import onnxruntime as ort

from common.tokenizer import VOCAB_SIZE, WINDOW_TOKENS


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


class OnnxDetector:
    """Wraps the ONNX session. The model outputs a raw logit for one 144-token window."""

    def __init__(self, model_path: str, threads: int = 1, warmup_runs: int = 20):
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.warmup_ms = self._warmup(warmup_runs)

    def _warmup(self, runs: int) -> dict[str, float]:
        rng = np.random.default_rng(0)
        x = rng.integers(0, VOCAB_SIZE, size=(1, WINDOW_TOKENS), dtype=np.int64)
        times = []
        for _ in range(max(runs, 1)):
            t0 = time.perf_counter_ns()
            self.session.run([self.output_name], {self.input_name: x})
            times.append((time.perf_counter_ns() - t0) / 1e6)
        return {"first_ms": round(times[0], 4), "steady_mean_ms": round(float(np.mean(times[1:] or times)), 4)}

    def predict(self, tokens: np.ndarray) -> tuple[float, float, float]:
        """tokens: int64 [1, 144]. Returns (logit, probability, inference_ms); timing covers session.run only."""
        t0 = time.perf_counter_ns()
        out = self.session.run([self.output_name], {self.input_name: tokens})[0]
        inference_ms = (time.perf_counter_ns() - t0) / 1e6
        logit = float(np.asarray(out).reshape(-1)[0])
        return logit, _sigmoid(logit), inference_ms

    def info(self) -> dict[str, Any]:
        i, o = self.session.get_inputs()[0], self.session.get_outputs()[0]
        return {
            "input": {"name": i.name, "shape": i.shape, "type": i.type},
            "output": {"name": o.name, "shape": o.shape, "type": o.type},
            "providers": self.session.get_providers(),
            "warmup": self.warmup_ms,
        }
