# Releasing

This repository publishes to PyPI from GitHub Actions when a version tag is
pushed.

## Prerequisites

- The version in `pyproject.toml` is final.
- `CHANGELOG.md` is updated.
- `make check` passes locally.
- The GitHub repository has a protected `pypi` environment with the
  `PYPI_API_TOKEN` secret configured.

## Release Steps

1. Update `pyproject.toml` and `CHANGELOG.md`.
2. Open and merge a pull request with the release changes.
3. Create an annotated version tag that matches the package version exactly.

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

4. Watch the `Release` workflow in GitHub Actions.
5. Confirm the release appears on PyPI and the GitHub release includes the
   generated notes and attached artifacts.

## Dry Runs

Use the `Release` workflow's `workflow_dispatch` trigger to run the build and
package checks without publishing to PyPI.

## Versioning Rules

- Tags must be prefixed with `v`, for example `v1.2.3`.
- The tag must match `project.version` in `pyproject.toml`.
- Breaking changes require a new major version.
