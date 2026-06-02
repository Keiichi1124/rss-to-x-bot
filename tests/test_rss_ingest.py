# tests/test_rss_ingest.py
import pytest
import os
import sqlite3
from unittest.mock import patch, MagicMock
import time
from datetime import datetime, timezone

# Make sure bot modules can be imported
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot import db
from bot import rss_ingest

# Define test DB path
TEST_DB_DIR = "test_data"
TEST_DB_NAME = "test_bot.db"
TEST_DB_PATH = os.path.join(TEST_DB_DIR, TEST_DB_NAME)

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Sets up a temporary, isolated database for tests."""
    # Ensure the test data directory exists
    os.makedirs(TEST_DB_DIR, exist_ok=True)

    # Monkeypatch the DB_PATH in the db module used by rss_ingest
    monkeypatch.setattr("bot.db.DB_PATH", TEST_DB_PATH)
    monkeypatch.setattr("bot.db.DB_DIR", TEST_DB_DIR)

    # Initialize the test database (clears existing table if present)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db._init_db() # Re-initialize with the patched path

    yield # Run the test

    # Teardown: Remove the test database file after the test
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    if os.path.exists(TEST_DB_DIR):
        try:
            # Attempt to remove the directory if empty
            os.rmdir(TEST_DB_DIR)
        except OSError:
            pass # Ignore if not empty (e.g., if other files were created)


@pytest.fixture
def mock_feedparser():
    """Mocks the feedparser.parse function with properly configured entries."""

    def entry_get_side_effect(self, key, default=None):
        # Simulate dict.get() behavior on the mock object
        return getattr(self, key, default)

    mock_feed = MagicMock()
    mock_feed.bozo = 0

    # Entry 1: Has id, published_parsed, summary
    entry1 = MagicMock(
        id="guid1",
        link="http://example.com/1",
        title="Article 1",
        published_parsed=time.struct_time((2024, 5, 1, 10, 0, 0, 2, 122, 0)),
        summary="Summary 1"
    )
    # Remove potentially conflicting date fields if they exist on the mock
    if hasattr(entry1, "published"): del entry1.published
    if hasattr(entry1, "updated_parsed"): del entry1.updated_parsed
    if hasattr(entry1, "updated"): del entry1.updated
    if hasattr(entry1, "description"): del entry1.description
    entry1.get.side_effect = entry_get_side_effect.__get__(entry1, MagicMock)

    # Entry 2: Has id, published (string), description
    entry2 = MagicMock(
        id="guid2",
        link="http://example.com/2",
        title="Article 2",
        published="2024-05-01T11:00:00Z",
        description="Description 2"
    )
    if hasattr(entry2, "published_parsed"): del entry2.published_parsed
    if hasattr(entry2, "updated_parsed"): del entry2.updated_parsed
    if hasattr(entry2, "updated"): del entry2.updated
    if hasattr(entry2, "summary"): del entry2.summary
    entry2.get.side_effect = entry_get_side_effect.__get__(entry2, MagicMock)

    # Entry 3: No id (should use link), has updated_parsed, summary
    entry3 = MagicMock(
        # No id attribute defined here
        link="http://example.com/3",
        title="Article 3",
        updated_parsed=time.struct_time((2024, 5, 1, 12, 0, 0, 2, 122, 0)),
        summary="Summary 3"
    )
    if hasattr(entry3, "id"): del entry3.id # Ensure id is missing
    if hasattr(entry3, "published_parsed"): del entry3.published_parsed
    if hasattr(entry3, "published"): del entry3.published
    if hasattr(entry3, "updated"): del entry3.updated
    if hasattr(entry3, "description"): del entry3.description
    entry3.get.side_effect = entry_get_side_effect.__get__(entry3, MagicMock)

    # Entry 4: Duplicate id (guid1), different link/title/date/summary
    entry4 = MagicMock(
        id="guid1",
        link="http://example.com/1-updated",
        title="Article 1 Updated",
        published_parsed=time.struct_time((2024, 5, 1, 13, 0, 0, 2, 122, 0)),
        summary="Summary 1 Updated"
    )
    if hasattr(entry4, "published"): del entry4.published
    if hasattr(entry4, "updated_parsed"): del entry4.updated_parsed
    if hasattr(entry4, "updated"): del entry4.updated
    if hasattr(entry4, "description"): del entry4.description
    entry4.get.side_effect = entry_get_side_effect.__get__(entry4, MagicMock)

    mock_feed.entries = [entry1, entry2, entry3, entry4]

    with patch("bot.rss_ingest.feedparser.parse", return_value=mock_feed) as mock_parse:
        yield mock_parse, mock_feed

def test_fetch_and_store_feed_success(mock_feedparser, setup_test_db):
    """Tests fetching a feed and storing new articles, skipping duplicates."""
    mock_parse, mock_feed = mock_feedparser
    test_feed_url = "http://test.feed.com/rss"

    # --- First fetch ---
    db._init_db() # Ensure test DB is initialized right before use
    rss_ingest.fetch_and_store_feed(test_feed_url)

    # Assert feedparser.parse was called
    mock_parse.assert_called_once_with(test_feed_url)

    # Check database content
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT guid, title, link, published_date, feed_source FROM articles ORDER BY published_date")
    articles = cursor.fetchall()
    conn.close()

    assert len(articles) == 3 # guid1, guid2, http://example.com/3
    assert articles[0] == ("guid1", "Article 1", "http://example.com/1", "2024-05-01T10:00:00Z", test_feed_url)
    assert articles[1] == ("guid2", "Article 2", "http://example.com/2", "2024-05-01T11:00:00Z", test_feed_url)
    assert articles[2] == ("http://example.com/3", "Article 3", "http://example.com/3", "2024-05-01T12:00:00Z", test_feed_url)

    # --- Second fetch (should skip all) ---
    # Reset mock call count if needed, or just check calls after second run
    mock_parse.reset_mock()
    rss_ingest.fetch_and_store_feed(test_feed_url)

    # Assert feedparser.parse was called again
    mock_parse.assert_called_once_with(test_feed_url)

    # Check database content again - should be unchanged
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 3 # No new articles added

@patch("bot.rss_ingest.logger")
def test_fetch_feed_ill_formed(mock_logger, setup_test_db):
    """Tests handling of ill-formed feeds (bozo flag)."""
    mock_feed = MagicMock()
    mock_feed.bozo = 1
    mock_feed.get.side_effect = lambda key, default: "Something went wrong" if key == "bozo_exception" else default
    mock_feed.entries = [] # No entries to process

    with patch("bot.rss_ingest.feedparser.parse", return_value=mock_feed) as mock_parse:
        rss_ingest.fetch_and_store_feed("http://bad.feed.com/rss")
        mock_parse.assert_called_once_with("http://bad.feed.com/rss")
        mock_logger.warning.assert_any_call("Feed http://bad.feed.com/rss may be ill-formed: Something went wrong")
        mock_logger.info.assert_any_call("No entries found in feed: http://bad.feed.com/rss")

@patch("bot.rss_ingest.logger")
def test_fetch_feed_exception(mock_logger, setup_test_db):
    """Tests handling of exceptions during feed fetching."""
    with patch("bot.rss_ingest.feedparser.parse", side_effect=Exception("Network Error")) as mock_parse:
        rss_ingest.fetch_and_store_feed("http://error.feed.com/rss")
        mock_parse.assert_called_once_with("http://error.feed.com/rss")
        mock_logger.error.assert_called_once_with("Error fetching or processing feed http://error.feed.com/rss: Network Error")

def test_parse_published_date_variations():
    """Tests the date parsing logic with different input formats."""
    # 1. Using published_parsed (struct_time)
    entry1 = {"published_parsed": time.struct_time((2023, 12, 25, 15, 30, 0, 0, 359, 0))}
    assert rss_ingest.parse_published_date(entry1) == "2023-12-25T15:30:00Z"

    # 2. Using published (string)
    entry2 = {"published": "Tue, 26 Dec 2023 10:00:00 +0000"}
    assert rss_ingest.parse_published_date(entry2) == "2023-12-26T10:00:00Z"

    # 3. Using updated_parsed as fallback
    entry3 = {"updated_parsed": time.struct_time((2024, 1, 1, 0, 0, 0, 0, 1, 0))}
    assert rss_ingest.parse_published_date(entry3) == "2024-01-01T00:00:00Z"

    # 4. Using updated string as fallback
    entry4 = {"updated": "2024-02-14T12:34:56Z"}
    assert rss_ingest.parse_published_date(entry4) == "2024-02-14T12:34:56Z"

    # 5. No date information
    entry5 = {}
    assert rss_ingest.parse_published_date(entry5) is None

    # 6. Unparseable date string
    entry6 = {"published": "Not a real date"}
    assert rss_ingest.parse_published_date(entry6) is None
