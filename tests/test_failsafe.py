from backend.app.failsafe import CAN_REASON, V2X_REASON, FailsafeEngine
from backend.app.schemas import V2X


def v2x(speed, limit=60):
    return V2X(speed_limit_kph=limit, vehicle_speed_kph=speed)


def test_contextual_anomaly_when_model_benign():
    d = FailsafeEngine().evaluate("a", False, v2x(75))  # 25% over
    assert d.triggered and d.reason == V2X_REASON


def test_no_trigger_15_percent_over():
    assert not FailsafeEngine().evaluate("a", False, v2x(69)).triggered


def test_can_intrusion_after_k_windows():
    e = FailsafeEngine(k=3)
    assert not e.evaluate("a", True, None).triggered
    assert not e.evaluate("a", True, None).triggered
    d = e.evaluate("a", True, None)
    assert d.triggered and d.reason == CAN_REASON


def test_streak_resets_and_is_per_vehicle():
    e = FailsafeEngine(k=2)
    e.evaluate("a", True, None)
    e.evaluate("b", False, None)
    assert not e.evaluate("b", True, None).triggered
    assert e.evaluate("a", True, None).triggered
