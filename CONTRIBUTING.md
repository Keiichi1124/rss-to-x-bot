# Contributing

Thanks for considering a contribution to RSS-to-X Bot.

## Development Setup

```bash
poetry install
cp .env.example .env
poetry run pytest -vv
```

Use placeholder credentials for local tests. Do not commit real API keys, tokens, local databases, logs, or `.env` files.

## Pull Request Guidelines

- Keep changes focused and explain the user-facing behavior they change.
- Add or update tests when changing queueing, RSS parsing, formatting, OAuth, or posting behavior.
- Prefer `--dry-run` examples for new posting workflows.
- Avoid logging secrets, request headers, token fragments, or full credential-bearing URLs.
- Update `README.md` when setup, environment variables, commands, or safety assumptions change.

## Local Quality Checks

```bash
poetry check
poetry run pytest -vv
```

## Maintainer Workflow

- Review dependency updates for security and compatibility.
- Keep CI passing on `main`.
- Cut releases for meaningful behavior changes.
- Use issues for bug reports, feature requests, and roadmap discussion.
