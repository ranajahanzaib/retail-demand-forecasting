# Contributing

Contributions that improve forecasting correctness, data quality, usability, or documentation are welcome.

## Development setup

Install the dependencies described in the [README](README.md), including Node.js 20.19+ or 22.13+ and `libomp` on macOS, then work from the repository root. The API and dashboard can be run independently.

## Checks

Run the relevant checks before opening a pull request:

```bash
cd apps/api
uv run ruff check src tests
uv run pytest

cd ../web
pnpm lint
pnpm test
pnpm build
```

The Playwright smoke test requires generated demo artifacts and an installed Chromium browser. Build the fixture with `uv run demandsense build-demo` from `apps/api`, then run `pnpm test:e2e` from `apps/web`.

## Pull requests

Describe the problem, summarize the change, and list the checks that were run. Include test coverage for behavior changes and update documentation when commands, data semantics, API responses, or user-facing behavior change. Document breaking changes and migration steps.

For reproducible bugs, include the command, data mode, environment, and relevant error output. Remove credentials, personal data, and private transaction details from logs and examples.
