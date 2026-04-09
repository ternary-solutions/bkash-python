# Contributing

Thanks for helping improve `bkash-pgw-tokenized`. We want this library to stay
predictable for merchants, easy to maintain, and safe to use in production.

## Before You Start

- Search existing [issues](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/issues)
  and [discussions](https://github.com/ternary-solutions/bkash-pgw-tokenized-python-package/discussions)
  before opening something new.
- Use GitHub Discussions for setup questions, integration help, and design ideas.
- Use GitHub Issues for bugs, regressions, and concrete feature requests.
- Use `devsecops@ternary.solutions` for private security disclosures only.

## Local Setup

1. Create and activate a virtual environment.
2. Install the development dependencies.
3. Install the pre-commit hooks.

```bash
python3 -m venv .venv
source .venv/bin/activate
make install-dev
pre-commit install
```

If `python3 -m venv` is unavailable on Debian or Ubuntu, install the
`python3-venv` package or use `virtualenv .venv` as a fallback.

## Development Workflow

1. Start from the latest `main`.
2. Make a focused change with tests.
3. Run `make check` before opening a pull request.
4. Update `README.md` when behavior, setup, or examples change.
5. Add a `CHANGELOG.md` entry for user-visible changes.

## Standards We Expect

- Keep the public Python API backward compatible unless the change is planned
  for a major release.
- Add or update tests for every behavior change.
- Prefer sandbox-safe, redacted examples in docs, issues, and pull requests.
- Do not post merchant credentials, tokens, phone numbers, or payment payloads
  with sensitive data in public threads.
- Keep pull requests small enough to review with confidence.

## Pull Requests

Please include:

- A short explanation of the problem and the approach.
- Links to any relevant issue or discussion.
- Notes about any docs or changelog updates.
- The commands you ran locally, usually `make check`.

Pull requests are reviewed by the CODEOWNERS team. We may ask for changes to
tests, docs, or API shape before merging.

## Release Notes

If your change affects users, add a short entry under `Unreleased` in
`CHANGELOG.md`. We use semantic versioning:

- Patch: bug fixes and documentation-only fixes.
- Minor: backward-compatible features.
- Major: breaking changes.

## Need Help?

- Usage questions: GitHub Discussions
- Bugs and feature requests: GitHub Issues
- Security reports: `devsecops@ternary.solutions`
