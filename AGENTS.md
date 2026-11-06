# Repository instructions

## Virtual environments

- `.venv` is the user-managed Windows execution and build environment. Never create, delete, recreate, replace, synchronize, or modify it, and never install packages into it.
- Do not run implicit `uv run` or `uv sync` commands that may select `.venv`.
- Use the Codex-managed Linux environment `.codex-venv` for development checks and tests.
- Codex may create, recreate, and install dependencies in `.codex-venv` as needed.
- Explicitly target `.codex-venv` for environment-management commands and invoke `.codex-venv/bin/python` directly for verification.
- Keep `.codex-venv` excluded from Git tracking.
