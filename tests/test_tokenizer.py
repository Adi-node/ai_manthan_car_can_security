from common.tokenizer import PAD_TOKEN, WINDOW_TOKENS, tokenize_frame, tokenize_window


def test_id_offset():
    assert tokenize_frame("01A4", ["00"] * 8)[0] == 0x1A4 + 257
    assert tokenize_frame("0000", ["00"] * 8)[0] == 257  # DoS ID is not the PAD slot


def test_missing_and_corrupt_bytes_are_pad():
    toks = tokenize_frame("0316", ["05", "21", None, float("nan"), "zz"])
    assert toks == [0x316 + 257, 5, 33, PAD_TOKEN, PAD_TOKEN, PAD_TOKEN, PAD_TOKEN, PAD_TOKEN, PAD_TOKEN]


def test_window_length():
    assert len(tokenize_window([tokenize_frame("0316", ["ff"] * 8)] * 16)) == WINDOW_TOKENS
