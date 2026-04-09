"""Verify Amazon SNS HTTP(S) notification signatures (bKash IPN envelope)."""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

_SNS_HOST_PATTERN = re.compile(r"^sns\.[a-zA-Z0-9\-]{3,}\.amazonaws\.com(\.cn)?$")

_SIGNABLE_KEYS_ORDER = (
    "Message",
    "MessageId",
    "Subject",
    "SubscribeURL",
    "Timestamp",
    "Token",
    "TopicArn",
    "Type",
)


class SnsVerificationError(Exception):
    pass


def _normalize_lambda_style_keys(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    replacements = {
        "SigningCertUrl": "SigningCertURL",
        "SubscribeUrl": "SubscribeURL",
        "UnsubscribeUrl": "UnsubscribeURL",
    }
    for old, new in replacements.items():
        if old in out and new not in out:
            out[new] = out.pop(old)
    return out


def _validate_signing_cert_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SnsVerificationError("SigningCertURL must be HTTPS with a host")
    if not url.endswith(".pem"):
        raise SnsVerificationError("SigningCertURL must end with .pem")
    if not _SNS_HOST_PATTERN.match(parsed.hostname):
        raise SnsVerificationError("SigningCertURL host is not a valid SNS endpoint")


def _cert_from_aws_sns(pem_bytes: bytes) -> x509.Certificate:
    try:
        certs = x509.load_pem_x509_certificates(pem_bytes)
    except ValueError as e:
        raise SnsVerificationError("No certificate in PEM response") from e
    if not certs:
        raise SnsVerificationError("No certificate in PEM response")
    cert = certs[0]
    issuer = cert.issuer.rfc4514_string()
    if "Amazon" not in issuer:
        raise SnsVerificationError("Certificate issuer is not Amazon")
    return cert


def build_string_to_sign(message: dict[str, Any]) -> str:
    sig_ver = str(message.get("SignatureVersion", ""))
    if sig_ver not in ("1", "2"):
        raise SnsVerificationError(f"Unsupported SignatureVersion: {sig_ver!r}")
    parts: list[str] = []
    for key in _SIGNABLE_KEYS_ORDER:
        if key in message and message[key] is not None:
            parts.append(f"{key}\n{message[key]}\n")
    return "".join(parts)


def fetch_signing_certificate(signing_cert_url: str, timeout: float = 10.0) -> x509.Certificate:
    _validate_signing_cert_url(signing_cert_url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(signing_cert_url)
        r.raise_for_status()
        return _cert_from_aws_sns(r.content)


def verify_sns_signature(message: dict[str, Any]) -> None:
    """
    Raises SnsVerificationError if the SNS message signature is invalid.
    ``message`` must be the top-level JSON object (after ``_normalize_lambda_style_keys``).
    """
    message = _normalize_lambda_style_keys(message)
    try:
        signing_cert_url = str(message["SigningCertURL"])
        signature_b64 = str(message["Signature"])
        sig_ver = str(message["SignatureVersion"])
    except KeyError as e:
        raise SnsVerificationError(f"Missing required SNS field: {e}") from e

    string_to_sign = build_string_to_sign(message)
    try:
        sig_bytes = base64.b64decode(signature_b64, validate=True)
    except Exception as e:
        raise SnsVerificationError("Invalid base64 Signature") from e

    cert = fetch_signing_certificate(signing_cert_url)
    pubkey = cert.public_key()
    if not isinstance(pubkey, RSAPublicKey):
        raise SnsVerificationError("SNS signing certificate public key is not RSA")

    hash_alg = hashes.SHA1() if sig_ver == "1" else hashes.SHA256()

    try:
        pubkey.verify(
            sig_bytes,
            string_to_sign.encode("utf-8"),
            padding.PKCS1v15(),
            hash_alg,
        )
    except Exception as e:
        raise SnsVerificationError("SNS signature verification failed") from e
