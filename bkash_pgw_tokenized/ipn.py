"""Parse and validate bKash IPN payloads (inner JSON from SNS ``Message``)."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from bkash_pgw_tokenized.codes import describe_code, is_success_status_code


def extract_inner_from_sns_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Decode the SNS ``Message`` string into a JSON object."""
    raw_msg = envelope.get("Message")
    if not isinstance(raw_msg, str):
        raise ValueError("SNS envelope missing string Message")
    inner = json.loads(raw_msg)
    if not isinstance(inner, dict):
        raise ValueError("Inner Message must be a JSON object")
    return inner


def verify_topic_arn(envelope: dict[str, Any], expected_topic_arn: str | None) -> bool:
    """If ``expected_topic_arn`` is set, it must match ``envelope['TopicArn']``."""
    if not expected_topic_arn or not str(expected_topic_arn).strip():
        return True
    return envelope.get("TopicArn") == str(expected_topic_arn).strip()


def amounts_match(expected: str, received: str) -> bool:
    try:
        a = Decimal(expected.strip())
        b = Decimal(str(received).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return False
    return a.quantize(Decimal("0.01")) == b.quantize(Decimal("0.01"))


def ipn_inner_is_success(inner: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Returns (ok, failure_reason).

    If statusCode is present, it must be 0000; if transactionStatus is present,
    it must be Completed.
    If statusCode is absent, transactionStatus must be Completed (documented IPN sample).
    """
    err = inner.get("errorCode") if "errorCode" in inner else inner.get("error_code")
    if err is not None and str(err).strip() != "":
        return False, describe_code(err)

    has_status_code = "statusCode" in inner or "status_code" in inner
    sc = inner.get("statusCode") if "statusCode" in inner else inner.get("status_code")

    ts = (
        inner.get("transactionStatus")
        if "transactionStatus" in inner
        else inner.get("transaction_status")
    )

    if has_status_code:
        if not is_success_status_code(sc):
            return False, describe_code(sc)
        if ts is not None and str(ts).strip() != "Completed":
            return False, str(ts).strip() or "Transaction not completed"
    else:
        if str(ts).strip() != "Completed":
            return False, describe_code(ts) if ts is not None else "Transaction not completed"

    return True, None
