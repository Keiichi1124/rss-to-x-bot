# RSS-to-X Bot

RSS-to-X automation bot with queueing, duplicate prevention, OAuth posting, dry-run support, Docker packaging, CI, and JSON logging.

This project is for small publishers, newsletter operators, developer blogs, and personal media workflows that need a reusable starting point for turning RSS feed items into queued X posts. It is maintained by [Keiichi1124](https://github.com/Keiichi1124).

> Status: early-stage OSS. The core queue, RSS ingestion, posting path, tests, and deployment skeleton are present. Production users should review the X API requirements, rate limits, and their own content approval process before enabling live posting.

## Features

- Fetch articles from an RSS feed.
- Store queued articles in SQLite and skip duplicate GUIDs.
- Add a URL manually from the CLI.
- Format X posts with title, URL, and a configurable hashtag.
- Optionally shorten URLs with Bitly.
- Post to X API v2 with OAuth 2.0 user-context credentials.
- Run once, run continuously with APScheduler, or run a standalone health server.
- Use `--dry-run` to format and inspect posts without sending them or mutating queue state.
- Emit JSON logs suitable for CloudWatch or other log collectors.
- Run tests in GitHub Actions.
- Build and run with Docker.

## Architecture

```text
RSS feed / manual URL
  -> bot/rss_ingest.py or bot/manual_queue.py
  -> SQLite queue in data/bot.db
  -> bot/tweet_formatter.py
  -> bot/x_client.py
  -> X API v2
```

Key modules:

- `bot/db.py`: SQLite queue initialization and article state updates.
- `bot/rss_ingest.py`: RSS parsing, date normalization, duplicate-safe inserts.
- `bot/manual_queue.py`: Manual URL fetch and title/content extraction.
- `bot/tweet_formatter.py`: Tweet-length handling, hashtag insertion, optional Bitly shortening.
- `bot/x_client.py`: OAuth-backed X API v2 posting.
- `bot/scheduler.py`: CLI entrypoint and scheduled loop.
- `bot/health_check.py`: Flask `/health` endpoint.

## Requirements

- Python 3.11 or newer
- Poetry
- X Developer account and API credentials for posting
- Optional: Bitly access token for URL shortening

## Setup

```bash
git clone https://github.com/Keiichi1124/rss-to-x-bot.git
cd rss-to-x-bot
poetry install
cp .env.example .env
```

Edit `.env` with your runtime credentials:

```text
X_API_KEY="..."
X_API_SECRET="..."
X_ACCESS_TOKEN="..."
X_REFRESH_TOKEN="..."
RSS_FEED_URL="https://example.com/feed.xml"
DEFAULT_HASHTAG="#NewsDigest"
```

Keep real credentials out of git. `.env` is ignored by default.

## Usage

Fetch the configured RSS feed and post queued articles:

```bash
poetry run python bot/scheduler.py run
```

Preview work without posting or marking articles as posted:

```bash
poetry run python bot/scheduler.py run --dry-run
```

Add one URL manually:

```bash
poetry run python bot/scheduler.py add "https://example.com/article"
```

Run continuously with a health endpoint:

```bash
poetry run python bot/scheduler.py loop
```

Run only the health endpoint:

```bash
poetry run python bot/scheduler.py health-server
```

## Docker

Build:

```bash
docker build -t rss-to-x-bot .
```

Run with runtime environment variables:

```bash
docker run --env-file .env -p 8080:8080 rss-to-x-bot
```

## Testing

```bash
poetry run pytest -vv
```

The test suite mocks external HTTP and X API calls. It should not require live network access.

## Safety And Compliance

- Review X API rate limits and automation policies before live posting.
- Use `--dry-run` before enabling scheduled posting.
- Do not commit `.env`, access tokens, refresh tokens, local databases, or logs.
- Treat refreshed tokens as secrets. The bot updates in-process environment variables but does not persist refreshed tokens to a secure store yet.
- Add human approval before posting if the feed can contain sensitive, paid, or user-generated content.

## Known Limitations

- The bot currently reads one RSS feed from `RSS_FEED_URL`.
- Refreshed OAuth tokens are not persisted across restarts.
- The scheduler is intentionally simple; production users may prefer cron, GitHub Actions, Cloud Run Jobs, or another external scheduler.
- Content extraction for manually added URLs is basic HTML parsing.

## Roadmap

- Multiple RSS feed support.
- Optional AI-generated summaries and post variants.
- Approval queue before live posting.
- Persistent secure token storage.
- Release workflow and dependency update automation.
- More structured logging and metrics.

## Contributing

Pull requests and issues are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before opening changes that affect credentials, posting behavior, or network handling.

## License

MIT. See [LICENSE](LICENSE).
