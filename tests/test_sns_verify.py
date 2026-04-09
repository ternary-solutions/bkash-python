from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import NameOID

from bkash_pgw_tokenized.sns_verify import (
    SnsVerificationError,
    build_string_to_sign,
    fetch_signing_certificate,
    verify_sns_signature,
)


def _issue_certificate(
    *, organization_name: str
) -> tuple[rsa.RSAPrivateKey, x509.Certificate, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
            x509.NameAttribute(NameOID.COMMON_NAME, "SNS Test Certificate"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    return key, cert, pem


def _signed_message(
    key: rsa.RSAPrivateKey,
    *,
    signature_version: str = "2",
) -> dict[str, str]:
    message = {
        "Type": "Notification",
        "Message": '{"statusCode":"0000","transactionStatus":"Completed"}',
        "MessageId": "mid-1",
        "Subject": "Payment update",
        "Timestamp": "2026-04-09T00:00:00.000Z",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:bkash-ipn",
        "SignatureVersion": signature_version,
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
    }
    hash_alg = hashes.SHA1() if signature_version == "1" else hashes.SHA256()
    signature = key.sign(
        build_string_to_sign(message).encode("utf-8"),
        padding.PKCS1v15(),
        hash_alg,
    )
    message["Signature"] = base64.b64encode(signature).decode("ascii")
    return message


def _ec_certificate() -> x509.Certificate:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Amazon"),
            x509.NameAttribute(NameOID.COMMON_NAME, "SNS Test Certificate"),
        ]
    )
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )


def test_build_string_to_sign_orders_fields() -> None:
    text = build_string_to_sign(
        {
            "Type": "Notification",
            "Message": "hello",
            "MessageId": "123",
            "Timestamp": "2026-04-09T00:00:00.000Z",
            "TopicArn": "arn:aws:sns:us-east-1:123:test",
            "SignatureVersion": "2",
        }
    )

    assert text.startswith("Message\nhello\nMessageId\n123\n")
    assert text.endswith("TopicArn\narn:aws:sns:us-east-1:123:test\nType\nNotification\n")


def test_build_string_to_sign_rejects_unsupported_signature_versions() -> None:
    with pytest.raises(SnsVerificationError, match="Unsupported SignatureVersion"):
        build_string_to_sign({"SignatureVersion": "3"})


def test_fetch_signing_certificate_rejects_invalid_urls() -> None:
    with pytest.raises(SnsVerificationError, match="HTTPS"):
        fetch_signing_certificate("http://example.com/cert.pem")


def test_fetch_signing_certificate_requires_pem_suffix() -> None:
    with pytest.raises(SnsVerificationError, match=r"\.pem"):
        fetch_signing_certificate("https://sns.us-east-1.amazonaws.com/cert.txt")


def test_fetch_signing_certificate_rejects_invalid_hosts() -> None:
    with pytest.raises(SnsVerificationError, match="valid SNS endpoint"):
        fetch_signing_certificate("https://example.com/cert.pem")


def test_fetch_signing_certificate_loads_an_amazon_issued_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, cert, pem = _issue_certificate(organization_name="Amazon")

    class FakeClient:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            assert timeout == 10.0
            assert follow_redirects is True

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(200, content=pem, request=request)

    monkeypatch.setattr("bkash_pgw_tokenized.sns_verify.httpx.Client", FakeClient)

    loaded = fetch_signing_certificate("https://sns.us-east-1.amazonaws.com/cert.pem")
    assert loaded.serial_number == cert.serial_number


def test_fetch_signing_certificate_rejects_empty_pem_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            assert timeout == 10.0
            assert follow_redirects is True

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(200, content=b"", request=request)

    monkeypatch.setattr("bkash_pgw_tokenized.sns_verify.httpx.Client", FakeClient)

    with pytest.raises(SnsVerificationError, match="No certificate"):
        fetch_signing_certificate("https://sns.us-east-1.amazonaws.com/cert.pem")


def test_fetch_signing_certificate_rejects_non_amazon_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, pem = _issue_certificate(organization_name="Example Corp")

    class FakeClient:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            assert timeout == 10.0
            assert follow_redirects is True

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(200, content=pem, request=request)

    monkeypatch.setattr("bkash_pgw_tokenized.sns_verify.httpx.Client", FakeClient)

    with pytest.raises(SnsVerificationError, match="issuer is not Amazon"):
        fetch_signing_certificate("https://sns.us-east-1.amazonaws.com/cert.pem")


def test_verify_sns_signature_accepts_lambda_style_key_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key, cert, _ = _issue_certificate(organization_name="Amazon")
    message = _signed_message(key)
    message["SigningCertUrl"] = message.pop("SigningCertURL")

    monkeypatch.setattr(
        "bkash_pgw_tokenized.sns_verify.fetch_signing_certificate",
        lambda signing_cert_url: cert,
    )

    verify_sns_signature(message)


def test_verify_sns_signature_rejects_invalid_base64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key, cert, _ = _issue_certificate(organization_name="Amazon")
    message = _signed_message(key)
    message["Signature"] = "***not-base64***"

    monkeypatch.setattr(
        "bkash_pgw_tokenized.sns_verify.fetch_signing_certificate",
        lambda signing_cert_url: cert,
    )

    with pytest.raises(SnsVerificationError, match="Invalid base64 Signature"):
        verify_sns_signature(message)


def test_verify_sns_signature_rejects_non_rsa_public_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key, _, _ = _issue_certificate(organization_name="Amazon")
    message = _signed_message(key)
    message["Signature"] = base64.b64encode(b"signature").decode("ascii")

    monkeypatch.setattr(
        "bkash_pgw_tokenized.sns_verify.fetch_signing_certificate",
        lambda signing_cert_url: _ec_certificate(),
    )

    with pytest.raises(SnsVerificationError, match="public key is not RSA"):
        verify_sns_signature(message)


def test_verify_sns_signature_rejects_invalid_signatures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key, cert, _ = _issue_certificate(organization_name="Amazon")
    message = _signed_message(key)
    message["Message"] = '{"statusCode":"2001"}'

    monkeypatch.setattr(
        "bkash_pgw_tokenized.sns_verify.fetch_signing_certificate",
        lambda signing_cert_url: cert,
    )

    with pytest.raises(SnsVerificationError, match="verification failed"):
        verify_sns_signature(message)


def test_verify_sns_signature_requires_required_fields() -> None:
    with pytest.raises(SnsVerificationError, match="Missing required SNS field"):
        verify_sns_signature({"SignatureVersion": "2"})
