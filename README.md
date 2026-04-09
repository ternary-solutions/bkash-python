# bkash-pgw-tokenized

[![PyPI version](https://img.shields.io/pypi/v/bkash-pgw-tokenized.svg)](https://pypi.org/project/bkash-pgw-tokenized/)
[![Python versions](https://img.shields.io/pypi/pyversions/bkash-pgw-tokenized.svg)](https://pypi.org/project/bkash-pgw-tokenized/)
[![CI](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/bkash-pgw-tokenized.svg)](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/blob/main/LICENSE)

Async Python client for **bKash Tokenized Checkout**: grant and refresh tokens,
create and execute payments, payment status, search transaction, refund, plus
helpers for **SNS-signed IPN** payloads.

- **Install name (pip):** `bkash-pgw-tokenized`
- **Import package:** `bkash_pgw_tokenized`
- **Requires:** Python 3.10+
- **Default upstream API target:** bKash Tokenized API `v1.2.0-beta`

Maintained by **Ternary Solutions** as an open source SDK for Bangladesh bKash
integrations. This is not an official bKash SDK; always verify upstream
platform behavior against the official
[bKash developer documentation](https://developer.bka.sh/).

## Table of Contents

- [Supported Versions](#supported-versions)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Status Codes and Outcomes](#status-codes-and-outcomes-success-failure-cancel)
- [IPN (SNS)](#ipn-sns)
- [Support](#support)
- [Versioning and Deprecation](#versioning-and-deprecation)
- [Development](#development)
- [License](#license)

## Supported Versions

| SDK line | Status | Python | Notes |
| -------- | ------ | ------ | ----- |
| `1.x`    | Active | 3.10 - 3.13 | Uses the tokenized checkout endpoints and default base URLs for `v1.2.0-beta` |

The default API roots include `/v1.2.0-beta`. Set `base_url` in the config to
target a different upstream version if bKash publishes one for your merchant
environment.

## Installation

```bash
pip install bkash-pgw-tokenized
```

## Quick Start

```python
from bkash_pgw_tokenized import Bkash, MemoryTokenStore, ensure_id_token

config = {
    "app_key": "...",
    "app_secret": "...",
    "username": "...",
    "password": "...",
    "sandbox": True,  # False for live
}

client = Bkash(config)
store = MemoryTokenStore()

id_token = await ensure_id_token(store, client)

create = await client.create_payment(
    id_token,
    mode="0011",
    payer_reference="INV-001",
    callback_url="https://your.site/payments/bkash/callback",
    amount="100.00",
    currency="BDT",
    intent="sale",
    merchant_invoice_number="INV-001",
)
# create["bkashURL"], create["paymentID"], ...

exec_res = await client.execute_payment(id_token, create["paymentID"])
status = await client.payment_status(id_token, create["paymentID"])
found = await client.search_transaction(id_token, trx_id="...")
refund = await client.refund(
    id_token,
    payment_id="...",
    trx_id="...",
    amount="100.00",
    sku="sku-1",
    reason="Customer request",
)
```

Optional config keys: `"sandbox"` (defaults to `True`) and `"base_url"`
(overrides the default host for that mode).

On HTTP error responses, the client raises `BkashHttpError` with `status_code`
and `response_body`.

Default API roots are `BKASH_TOKENIZED_SANDBOX_BASE_URL` and
`BKASH_TOKENIZED_LIVE_BASE_URL` (exported from `bkash_pgw_tokenized`). For
static typing of `config`, use `BkashConfig` (or `BkashConfigRequired` for only
the four secret fields).

**Authorization header:** the raw `id_token` is sent as `Authorization` (no
`Bearer` prefix), matching bKash's tokenized API.

`AsyncBkashClient` is an alias for `Bkash` (backward-compatible name).

## Status Codes and Outcomes (success, failure, cancel)

bKash surfaces outcomes in three places: the **browser callback** to your
`callbackURL`, **JSON from Execute / Payment status** APIs, and **IPN** (SNS)
payloads. They are **not** the same thing:

- **`statusCode` / `0000` on Create** only means "create payment session
  succeeded" and you received `bkashURL` / `paymentID`. It does **not** mean
  the customer paid.
- **Whether the user finished, failed, or cancelled** in the bKash UI is
  communicated on the **callback** via the **`status`** query parameter (and
  you need **`paymentID`** from that same redirect to call Execute).

### 1. Merchant callback URL (browser redirect)

After the customer acts in the bKash flow, bKash redirects their browser to the
**`callbackURL`** you sent in **Create payment**. That request is a normal HTTP
**GET** with **query-string parameters** appended (names are commonly camelCase
such as `paymentID`; treat lookups case-insensitively if your framework allows
duplicate casing).

**Parameters you should handle (tokenized checkout):**

| Query parameter | Typical presence | Meaning |
| --------------- | ---------------- | ------- |
| **`paymentID`** | Expected | The bKash payment id (same as in the Create response). Required to call **`execute_payment`** / **`payment_status`**. |
| **`status`**    | Expected | **This is where success vs failure vs cancel is indicated for the redirect.** String value from bKash (see classification table below). |
| **`signature`** | May be present | Reserved for **callback integrity verification** against bKash's rules. Your app should accept the parameter and verify it when your integration guide requires it. |

bKash may add other query keys over time. During integration, **log the full
query string** (or `request.GET` / `request.query_params`) in sandbox so you do
not miss extra fields your account or API version sends.

**How to decide failed vs cancelled vs successful (using only the callback):**

Normalize: `s = status.strip().lower()` (after ensuring `status` is a non-empty
string).

| If `s` is in... | Treat as | Then |
| ---------------- | -------- | ---- |
| `failure`, `fail`, `failed` | **Failed** | Do **not** call Execute. Mark order unpaid / show error. |
| `cancel`, `cancelled`, `canceled` | **Cancelled** | Do **not** call Execute. Mark as user-cancelled (distinct from a hard failure if you want different UX). |
| exactly `success` (after normalize) | **Callback success** | **Still not "paid" yet.** Call `await client.execute_payment(id_token, paymentID)` and apply the JSON rules in **section 2** (or `payment_status` if Execute is unclear). |
| anything else | **Unknown / unsafe** | Do **not** assume success. Treat like failure until you confirm with bKash docs or support for your environment. |

If **`paymentID`** or **`status`** is missing, you cannot complete the flow
safely; reject the request and do not Execute.

### 2. Execute and Payment status API JSON

After the callback indicates **`status=success`**, the source of truth for money
movement is the **Execute** response (and optionally **Payment status** if
Execute times out or returns an unusable body).

For **Execute** and **Payment status**, treat payment as **completed** only when
**all** of the following hold (same rules many merchants use in production):

| Field | Success value |
| ----- | ------------- |
| `statusCode` | `"0000"` |
| `statusMessage` | `"Successful"` |
| `transactionStatus` | `"Completed"` |

If `statusCode` is present and not `"0000"`, or `transactionStatus` is present
and not `"Completed"`, treat as **failure**. Use `errorCode` / `statusCode`
with `describe_code` from `bkash_pgw_tokenized` for human-readable messages:

```python
from bkash_pgw_tokenized import describe_code, is_success_status_code

if is_success_status_code(response.get("statusCode")):
    ...
else:
    reason = describe_code(response.get("statusCode") or response.get("errorCode"))
```

Non-success responses often include `statusMessage`, `errorMessage`, or
`message`; fall back to those for display.

### 3. Create payment response

**Create** is successful at the API level when `statusCode == "0000"`. You
still need `bkashURL` and `paymentID` in the payload to send the user to bKash.
Any other `statusCode` means create failed; use `describe_code` and the message
fields above.

### 4. IPN (SNS inner `Message` JSON)

For server-side notifications, use `ipn_inner_is_success(inner)` (see
[IPN (SNS)](#ipn-sns)). In short:

- If `errorCode` / `error_code` is set and non-empty -> **not** success.
- If `statusCode` / `status_code` is present -> it must be `"0000"`; if
  `transactionStatus` / `transaction_status` is also present, it must be
  `"Completed"`.
- If `statusCode` is **absent** (some samples) -> `transactionStatus` must be
  `"Completed"`.

### Reference

- Full numeric codes:
  [bKash error codes](https://developer.bka.sh/docs/error-codes)
- Success API code for many operations: **`0000`**

## IPN (SNS)

Payload parsing and validation (imported from `bkash_pgw_tokenized`):

```python
from bkash_pgw_tokenized import (
    amounts_match,
    extract_inner_from_sns_envelope,
    ipn_inner_is_success,
    verify_topic_arn,
)

if not verify_topic_arn(envelope, expected_topic_arn):
    ...
inner = extract_inner_from_sns_envelope(envelope)
ok, reason = ipn_inner_is_success(inner)
```

SNS **signature verification** (depends on `cryptography`, installed by
default):

```python
from bkash_pgw_tokenized.sns_verify import SnsVerificationError, verify_sns_signature

try:
    verify_sns_signature(envelope)
except SnsVerificationError:
    ...
```

## Support

- Questions, integration help, and design discussions:
  [GitHub Discussions](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/discussions)
- Bugs and feature requests:
  [GitHub Issues](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/issues)
- Private vulnerability reporting:
  [`devsecops@ternary.solutions`](mailto:devsecops@ternary.solutions)
- Contributor guidance:
  [CONTRIBUTING.md](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/blob/main/CONTRIBUTING.md)
- Security policy:
  [SECURITY.md](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/blob/main/SECURITY.md)

## Versioning and Deprecation

This project follows semantic versioning for the public Python package API.

- Patch releases fix bugs and docs without breaking callers.
- Minor releases add backward-compatible functionality.
- Major releases may remove or change public behavior.

When a deprecation is necessary, the intent will be documented in the changelog
before removal wherever practical.

## Development

From a local clone of the source tree (repository root, where `pyproject.toml`
lives):

```bash
python3 -m venv .venv
source .venv/bin/activate
make install-dev
pre-commit install
make check
```

If `python3 -m venv` is unavailable on Debian or Ubuntu, install the
`python3-venv` package or use `virtualenv .venv` as a fallback.

You can also run the main maintainer tasks individually:

```bash
make lint
make typecheck
make test
make build
```

## License

MIT. See
[LICENSE](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/blob/main/LICENSE).
