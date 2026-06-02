# Security Policy

## Supported Versions

This project is early-stage. Security fixes are applied to the `main` branch.

## Reporting A Vulnerability

Do not post secrets, tokens, request headers, or exploit details in a public issue.

If you find a vulnerability, open a GitHub issue with a minimal description that does not include sensitive details, and ask the maintainer to continue privately. If you already have a private contact path for the maintainer, use that instead.

## Secrets Handling

- Real `.env` files are ignored by git.
- X API credentials, refresh tokens, Bitly tokens, local databases, and logs must not be committed.
- The bot avoids logging token values, including partial token fragments.
- Refreshed OAuth tokens are held in process memory/environment variables only; production users should add a secure persistence layer before relying on long-running deployments.

## Operational Notes

- Run with `--dry-run` before enabling live posting.
- Review X API automation policies, rate limits, and app permissions.
- Add a human approval step if feeds can contain sensitive or untrusted content.
