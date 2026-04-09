import pytest

from bkash_pgw_tokenized import (
    amounts_match,
    extract_inner_from_sns_envelope,
    ipn_inner_is_success,
    verify_topic_arn,
)


def test_ipn_inner_success_with_status_code() -> None:
    ok, reason = ipn_inner_is_success(
        {"statusCode": "0000", "transactionStatus": "Completed"},
    )
    assert ok is True
    assert reason is None


def test_ipn_inner_fails_bad_status_code() -> None:
    ok, reason = ipn_inner_is_success({"statusCode": "2002", "transactionStatus": "Completed"})
    assert ok is False
    assert reason is not None


def test_ipn_inner_without_status_code_requires_completed() -> None:
    ok, _ = ipn_inner_is_success({"transactionStatus": "Completed"})
    assert ok is True


def test_amounts_match() -> None:
    assert amounts_match("10.00", "10.0") is True
    assert amounts_match("10.00", "10.01") is False


def test_verify_topic_arn() -> None:
    assert verify_topic_arn({"TopicArn": "arn:aws:sns:1"}, None) is True
    assert verify_topic_arn({"TopicArn": "arn:aws:sns:1"}, "  ") is True
    assert verify_topic_arn({"TopicArn": "arn:aws:sns:1"}, "arn:aws:sns:1") is True
    assert verify_topic_arn({"TopicArn": "arn:aws:sns:2"}, "arn:aws:sns:1") is False


def test_extract_inner_from_sns_envelope() -> None:
    inner = extract_inner_from_sns_envelope(
        {"Message": '{"merchantInvoiceNumber":"INV1","transactionStatus":"Completed"}'},
    )
    assert inner["merchantInvoiceNumber"] == "INV1"


def test_extract_inner_errors() -> None:
    with pytest.raises(ValueError, match="missing string Message"):
        extract_inner_from_sns_envelope({"Message": 1})  # type: ignore[arg-type]


def test_extract_inner_requires_json_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        extract_inner_from_sns_envelope({"Message": '["not-an-object"]'})


def test_amounts_match_returns_false_for_invalid_values() -> None:
    assert amounts_match("bad", "10.00") is False


def test_ipn_inner_fails_when_error_code_is_present() -> None:
    ok, reason = ipn_inner_is_success({"errorCode": "2002"})
    assert ok is False
    assert reason == "Invalid Payment ID"


def test_ipn_inner_with_status_code_requires_completed_transaction() -> None:
    ok, reason = ipn_inner_is_success(
        {"statusCode": "0000", "transactionStatus": "Pending"},
    )
    assert ok is False
    assert reason == "Pending"


def test_ipn_inner_without_status_code_fails_when_not_completed() -> None:
    ok, reason = ipn_inner_is_success({"transactionStatus": "Pending"})
    assert ok is False
    assert reason == "Unknown code: Pending"
