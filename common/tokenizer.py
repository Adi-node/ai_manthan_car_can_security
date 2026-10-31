"""Tokenizer shared by the simulator and the tests.

Must match the training script exactly:
  * CAN ID token    = (int(id_hex, 16) % 2048) + ID_OFFSET   (257; never collides with 0..255 or PAD)
  * data byte token = int(byte_hex, 16)                       (missing/corrupt bytes -> PAD_TOKEN 256)
  * every frame is 9 tokens, a window is WINDOW_SIZE frames -> 144 tokens
  * a window's training label is its LAST frame's flag
"""
from typing import Optional, Sequence

ID_OFFSET = 257
PAD_TOKEN = 256
ID_MOD = 2048
FRAME_DATA_LEN = 8
TOKENS_PER_FRAME = 1 + FRAME_DATA_LEN
WINDOW_SIZE = 16
WINDOW_TOKENS = WINDOW_SIZE * TOKENS_PER_FRAME
VOCAB_SIZE = 2500


def _byte(value: Optional[str]) -> int:
    s = "" if value is None else str(value).strip()
    try:
        return int(s, 16)
    except ValueError:  # empty, NaN or corrupt -> PAD, as in training
        return PAD_TOKEN


def tokenize_frame(can_id_hex: str, data_hex: Sequence[Optional[str]]) -> list[int]:
    try:
        id_token = int(str(can_id_hex).strip(), 16) % ID_MOD + ID_OFFSET
    except ValueError:
        id_token = ID_OFFSET
    data = [_byte(b) for b in list(data_hex)[:FRAME_DATA_LEN]]
    data += [PAD_TOKEN] * (FRAME_DATA_LEN - len(data))
    return [id_token, *data]


def tokenize_window(frames: Sequence[Sequence[int]]) -> list[int]:
    """Flatten already-tokenized frames (9 ints each) into one window."""
    if len(frames) != WINDOW_SIZE:
        raise ValueError(f"window needs {WINDOW_SIZE} frames, got {len(frames)}")
    return [t for f in frames for t in f]
