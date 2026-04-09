from bkash_pgw_tokenized.codes import describe_code, is_success_status_code, normalize_code


def test_normalize_code_trims_and_handles_empty_values() -> None:
    assert normalize_code(" 0000 ") == "0000"
    assert normalize_code("   ") is None
    assert normalize_code(None) is None


def test_describe_code_uses_known_and_unknown_messages() -> None:
    assert describe_code("0000") == "Successful"
    assert describe_code("9999") == "Unknown code: 9999"
    assert describe_code(None) == "Unknown error"


def test_is_success_status_code_only_accepts_0000() -> None:
    assert is_success_status_code("0000") is True
    assert is_success_status_code(" 0000 ") is True
    assert is_success_status_code("2001") is False
