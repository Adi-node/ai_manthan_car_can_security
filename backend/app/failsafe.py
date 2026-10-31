from dataclasses import dataclass
from typing import Optional

from .schemas import V2X

CAN_REASON = "CAN_INTRUSION"
V2X_REASON = "CONTEXTUAL_ANOMALY: V2X_SPEED_MISMATCH"


@dataclass
class Decision:
    triggered: bool
    reason: Optional[str]
    consecutive_attack_windows: int
    speed_violation: bool


class FailsafeEngine:
    """Fuses the CAN model verdict with V2X context, tracked per vehicle.

    1. CAN path: model flags an attack for `k` consecutive windows -> CAN_INTRUSION.
    2. V2X path: model says benign but speed > ratio * limit -> CONTEXTUAL_ANOMALY.
    """

    def __init__(self, k: int = 3, speed_ratio: float = 1.2):
        self.k = k
        self.speed_ratio = speed_ratio
        self._streak: dict[str, int] = {}

    def evaluate(self, vehicle_id: str, is_attack: bool, v2x: Optional[V2X]) -> Decision:
        streak = self._streak.get(vehicle_id, 0) + 1 if is_attack else 0
        self._streak[vehicle_id] = streak
        violation = bool(v2x and v2x.vehicle_speed_kph > self.speed_ratio * v2x.speed_limit_kph)

        if streak >= self.k:
            return Decision(True, CAN_REASON, streak, violation)
        if not is_attack and violation:
            return Decision(True, V2X_REASON, streak, violation)
        return Decision(False, None, streak, violation)
