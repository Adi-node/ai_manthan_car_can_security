from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from common.tokenizer import FRAME_DATA_LEN, VOCAB_SIZE, WINDOW_SIZE, WINDOW_TOKENS

SCHEMA_VERSION = "1.0"


class Frame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ts: float
    can_id: str
    dlc: int = Field(ge=0, le=8)
    data: list[int] = Field(min_length=FRAME_DATA_LEN, max_length=FRAME_DATA_LEN)
    flag: Optional[str] = None

    @field_validator("data")
    @classmethod
    def _bytes(cls, v: list[int]) -> list[int]:
        if any(b < 0 or b > 256 for b in v):
            raise ValueError("data tokens must be 0..256 (256 = PAD)")
        return v


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: Literal[16] = WINDOW_SIZE
    tokens: list[int] = Field(min_length=WINDOW_TOKENS, max_length=WINDOW_TOKENS)
    frames: list[Frame] = Field(min_length=WINDOW_SIZE, max_length=WINDOW_SIZE)
    label: Optional[Literal[0, 1]] = None

    @field_validator("tokens")
    @classmethod
    def _range(cls, v: list[int]) -> list[int]:
        if any(t < 0 or t >= VOCAB_SIZE for t in v):
            raise ValueError(f"tokens must be in [0, {VOCAB_SIZE - 1}]")
        return v


class V2X(BaseModel):
    model_config = ConfigDict(extra="forbid")
    msg_type: str = "RSU_ADVISORY"
    rsu_id: Optional[str] = None
    speed_limit_kph: float = Field(gt=0)
    vehicle_speed_kph: float = Field(ge=0)
    hazard: Optional[str] = None
    timestamp_ns: Optional[int] = None


class CanWindowMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["can_window"]
    schema_version: str = SCHEMA_VERSION
    seq: int
    vehicle_id: str = "CAV-01"
    sent_at_ns: int
    window: Window
    v2x: Optional[V2X] = None


class EndOfStream(BaseModel):
    type: Literal["end_of_stream"]
    seq: int = 0
